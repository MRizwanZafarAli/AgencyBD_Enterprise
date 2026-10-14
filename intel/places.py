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
                 "places.userRatingCount,places.nationalPhoneNumber,places.googleMapsUri,places.primaryTypeDisplayName,nextPageToken")
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSM_UA = "AgencyBD-Enterprise/1.0 (client discovery; read-only)"


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
            out.append({
                "provider": "google", "place_id": p.get("id"), "name": (p.get("displayName") or {}).get("text"),
                "website": p.get("websiteUri"), "address": p.get("formattedAddress"), "phone": p.get("nationalPhoneNumber"),
                "rating": p.get("rating"), "reviews": p.get("userRatingCount") or 0, "maps_url": p.get("googleMapsUri"),
                "category": (p.get("primaryTypeDisplayName") or {}).get("text"), "business_status": p.get("businessStatus")})
        token = data.get("nextPageToken")
        if not token:
            break
    return out[:limit]


def parse_nominatim(rows: list, category: str) -> list:
    out: list = []
    for r in rows:
        t = r.get("extratags") or {}
        a = r.get("address") or {}
        street = " ".join(x for x in (a.get("house_number"), a.get("road")) if x)
        out.append({
            "provider": "osm", "place_id": f"osm_{r.get('osm_type')}_{r.get('osm_id')}", "name": r.get("name") or None,
            "website": t.get("website") or t.get("contact:website") or t.get("url"),
            "address": ", ".join(x for x in (street, a.get("suburb") or a.get("city_district"), a.get("city") or a.get("town")) if x) or None,
            "phone": t.get("phone") or t.get("contact:phone"), "rating": None, "reviews": 0,
            "maps_url": f"https://www.openstreetmap.org/{r.get('osm_type')}/{r.get('osm_id')}", "category": category, "business_status": None,
            "facebook": t.get("contact:facebook") or t.get("facebook"), "instagram": t.get("contact:instagram") or t.get("instagram")})
    return out


def search_osm(category: str, city: str, limit: int = 20) -> list:
    """Free provider (OpenStreetMap Nominatim, any free-text category). At most 40 results per search."""
    resp = requests.get(NOMINATIM, headers={"User-Agent": OSM_UA}, timeout=25, params={
        "q": f"{category} in {city}", "format": "jsonv2", "extratags": 1, "addressdetails": 1, "limit": min(max(limit * 2, 10), 40)})
    resp.raise_for_status()
    return parse_nominatim(resp.json(), category)[:limit]
