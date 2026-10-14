"""Google Places API (New) client for finding a business and the website Google has on file for it.

Only fields needed for classification are requested (billing follows the most expensive field). Only the place id
is stored, as Google's terms restrict caching of Places content. Fixed vendor host."""

import os
from typing import Any, Dict, Optional

import requests

URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = "places.id,places.displayName,places.websiteUri,places.formattedAddress,places.businessStatus"


def places_configured() -> bool:
    key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    return bool(key and not key.startswith("your_"))


def find_business(name: str, city: str) -> Optional[Dict[str, Any]]:
    """Returns the best Places match, or None if no result. Raises on transport/auth errors."""
    resp = requests.post(
        URL, json={"textQuery": f"{name} {city}".strip(), "maxResultCount": 1},
        headers={"X-Goog-Api-Key": os.environ["GOOGLE_PLACES_API_KEY"], "X-Goog-FieldMask": FIELDS, "Content-Type": "application/json"},
        timeout=15)
    resp.raise_for_status()
    places = resp.json().get("places") or []
    if not places:
        return None
    p = places[0]
    return {"place_id": p.get("id"), "name": (p.get("displayName") or {}).get("text"), "website": p.get("websiteUri"),
            "address": p.get("formattedAddress"), "business_status": p.get("businessStatus")}


# --------------------------------------------------------------------------------------------------------------------
# Multi-result discovery (client hunting). Two providers:
#   google  Places API text search, richer (ratings, review counts, phone). Needs GOOGLE_PLACES_API_KEY.
#   osm     OpenStreetMap (Nominatim + Overpass), free and keyless, but community-mapped: a missing website tag is weaker
#           evidence than a missing website on Google, and coverage varies by city.
# Both fixed vendor hosts.

SEARCH_FIELDS = ("places.id,places.displayName,places.websiteUri,places.formattedAddress,places.businessStatus,places.rating,"
                 "places.userRatingCount,places.nationalPhoneNumber,places.googleMapsUri,places.primaryTypeDisplayName,places.location,nextPageToken")
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSM_UA = "AgencyBD-Enterprise/1.0 (client discovery; read-only)"


def geocode_city(city: str) -> Optional[Dict[str, Any]]:
    """Geocodes a city using OpenStreetMap Nominatim with zero API key requirement."""
    try:
        resp = requests.get(NOMINATIM, headers={"User-Agent": OSM_UA}, timeout=10, params={"q": city, "format": "jsonv2", "limit": 1})
        if resp.status_code == 200 and resp.json():
            item = resp.json()[0]
            bbox = item.get("boundingbox")
            return {
                "lat": float(item["lat"]) if item.get("lat") else None,
                "lon": float(item["lon"]) if item.get("lon") else None,
                "bbox": [float(x) for x in bbox] if bbox and len(bbox) == 4 else None,
                "display_name": item.get("display_name"),
            }
    except Exception:
        pass
    return None


def search_google(query: str, city: str, limit: int = 20) -> list:
    """Text search returning up to `limit` places (paged). Raises on transport/auth errors."""
    out: list = []
    token = None
    while len(out) < limit:
        body: Dict[str, Any] = {"textQuery": f"{query} in {city}".strip(), "pageSize": min(20, limit - len(out))}
        if token:
            body["pageToken"] = token
        resp = requests.post(URL, json=body, timeout=20, headers={
            "X-Goog-Api-Key": os.environ["GOOGLE_PLACES_API_KEY"], "X-Goog-FieldMask": SEARCH_FIELDS, "Content-Type": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        for p in data.get("places") or []:
            loc = p.get("location") or {}
            out.append({
                "provider": "google", "place_id": p.get("id"), "name": (p.get("displayName") or {}).get("text"),
                "website": p.get("websiteUri"), "address": p.get("formattedAddress"), "phone": p.get("nationalPhoneNumber"),
                "rating": p.get("rating"), "reviews": p.get("userRatingCount") or 0, "maps_url": p.get("googleMapsUri"),
                "category": (p.get("primaryTypeDisplayName") or {}).get("text"), "business_status": p.get("businessStatus"),
                "lat": loc.get("latitude"), "lon": loc.get("longitude")})
        token = data.get("nextPageToken")
        if not token:
            break
    return out[:limit]


def parse_nominatim(rows: list, category: str, fallback_lat: Optional[float] = None, fallback_lon: Optional[float] = None) -> list:
    out: list = []
    for r in rows:
        t = r.get("extratags") or {}
        a = r.get("address") or {}
        street = " ".join(x for x in (a.get("house_number"), a.get("road")) if x)
        lat = float(r["lat"]) if r.get("lat") else fallback_lat
        lon = float(r["lon"]) if r.get("lon") else fallback_lon
        out.append({
            "provider": "osm", "place_id": f"osm_{r.get('osm_type')}_{r.get('osm_id')}", "name": r.get("name") or None,
            "website": t.get("website") or t.get("contact:website") or t.get("url"),
            "address": ", ".join(x for x in (street, a.get("suburb") or a.get("city_district"), a.get("city") or a.get("town")) if x) or None,
            "phone": t.get("phone") or t.get("contact:phone"), "rating": None, "reviews": 0,
            "maps_url": f"https://www.openstreetmap.org/{r.get('osm_type')}/{r.get('osm_id')}", "category": category, "business_status": None,
            "facebook": t.get("contact:facebook") or t.get("facebook"), "instagram": t.get("contact:instagram") or t.get("instagram"),
            "lat": lat, "lon": lon})
    return out


def search_osm(category: str, city: str, limit: int = 20) -> list:
    """Free universal provider (OpenStreetMap Nominatim, zero API key required)."""
    geo = geocode_city(city)
    fallback_lat = geo["lat"] if geo else None
    fallback_lon = geo["lon"] if geo else None

    items: list = []
    seen = set()

    # Strategy 1: If bounding box is available, perform bounded high-precision search
    if geo and geo.get("bbox"):
        bbox = geo["bbox"]  # [south, north, west, east]
        s, n, w, e = bbox[0], bbox[1], bbox[2], bbox[3]
        try:
            resp = requests.get(NOMINATIM, headers={"User-Agent": OSM_UA}, timeout=15, params={
                "q": category, "viewbox": f"{w},{n},{e},{s}", "bounded": 1, "format": "jsonv2",
                "extratags": 1, "addressdetails": 1, "limit": max(limit * 2, 20)})
            if resp.status_code == 200:
                for row in resp.json():
                    pid = f"{row.get('osm_type')}_{row.get('osm_id')}"
                    if pid not in seen:
                        seen.add(pid)
                        items.append(row)
        except Exception:
            pass

    # Strategy 2: Text search with city anchor
    if len(items) < limit:
        try:
            resp = requests.get(NOMINATIM, headers={"User-Agent": OSM_UA}, timeout=20, params={
                "q": f"{category} in {city}", "format": "jsonv2", "extratags": 1, "addressdetails": 1,
                "limit": min(max(limit * 2, 10), 40)})
            if resp.status_code == 200:
                for row in resp.json():
                    pid = f"{row.get('osm_type')}_{row.get('osm_id')}"
                    if pid not in seen:
                        seen.add(pid)
                        items.append(row)
        except Exception:
            pass

    return parse_nominatim(items, category, fallback_lat=fallback_lat, fallback_lon=fallback_lon)[:limit]
