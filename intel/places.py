"""Google Places API (New) client for finding a business and the website Google has on file for it.

Only fields needed for classification are requested (billing follows the most expensive field). Only the place id
is stored, as Google's terms restrict caching of Places content. Fixed vendor host."""

import os
from typing import Any, Dict, List, Optional

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


def fetch_wikidata_website(qid: str) -> Optional[str]:
    """Resolves official website (P856) from Wikidata for an entity QID (100% free, zero key required)."""
    if not qid or not str(qid).startswith("Q"):
        return None
    try:
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        resp = requests.get(url, headers={"User-Agent": OSM_UA}, timeout=6)
        if resp.status_code == 200:
            claims = resp.json().get("entities", {}).get(qid, {}).get("claims", {})
            p856 = claims.get("P856")
            if p856 and isinstance(p856, list):
                val = p856[0].get("mainsnak", {}).get("datavalue", {}).get("value")
                if val and isinstance(val, str) and val.startswith("http"):
                    return val
    except Exception:
        pass
    return None


def parse_nominatim(rows: list, category: str, fallback_lat: Optional[float] = None, fallback_lon: Optional[float] = None) -> list:
    out: list = []
    for r in rows:
        t = r.get("extratags") or {}
        a = r.get("address") or {}
        street = " ".join(x for x in (a.get("house_number"), a.get("road")) if x)
        lat = float(r["lat"]) if r.get("lat") else fallback_lat
        lon = float(r["lon"]) if r.get("lon") else fallback_lon
        raw_web = (
            t.get("website") or t.get("contact:website") or t.get("url")
            or t.get("brand:website") or t.get("operator:website")
        )
        out.append({
            "provider": "osm", "place_id": f"osm_{r.get('osm_type')}_{r.get('osm_id')}", "name": r.get("name") or None,
            "website": raw_web,
            "address": ", ".join(x for x in (street, a.get("suburb") or a.get("city_district"), a.get("city") or a.get("town")) if x) or None,
            "phone": t.get("phone") or t.get("contact:phone"), "rating": None, "reviews": 0,
            "maps_url": f"https://www.openstreetmap.org/{r.get('osm_type')}/{r.get('osm_id')}", "category": category, "business_status": None,
            "facebook": t.get("contact:facebook") or t.get("facebook"), "instagram": t.get("contact:instagram") or t.get("instagram"),
            "lat": lat, "lon": lon,
            "extratags": t})
    return out


SEMANTIC_CATEGORY_MAP: Dict[str, List[str]] = {
    "healthtech": ["medical clinic", "clinic", "health center", "doctor", "hospital", "healthcare"],
    "medtech": ["medical clinic", "clinic", "health center", "doctor", "hospital"],
    "telehealth": ["medical clinic", "clinic", "health center", "doctor"],
    "healthcare": ["medical clinic", "clinic", "health center", "doctor", "hospital"],
    "dental": ["dentist", "dental clinic", "orthodontist"],
    "dentistry": ["dentist", "dental clinic"],
    "fintech": ["financial", "bank", "accounting", "accountant", "investment", "tax"],
    "finance": ["financial", "bank", "accounting", "accountant", "investment"],
    "wealth": ["financial", "bank", "investment", "accounting"],
    "proptech": ["real estate", "estate agent", "property management"],
    "real estate": ["real estate", "estate agent", "property management"],
    "edtech": ["education", "school", "college", "tutoring", "academy"],
    "education": ["school", "college", "tutoring", "training"],
    "software agency": ["software", "it services", "computer", "web design", "marketing"],
    "ai agency": ["software", "it services", "computer", "consulting", "technology"],
    "dev agency": ["software", "it services", "web design", "computer"],
    "it agency": ["software", "it services", "computer"],
    "contractors": ["contractor", "roofing", "plumber", "electrician", "construction", "hvac"],
    "contractor": ["contractor", "roofing", "plumber", "electrician", "construction", "hvac"],
    "trades": ["plumber", "electrician", "roofing", "contractor", "hvac"],
    "roofing": ["roofing", "contractor", "construction"],
    "hvac": ["hvac", "contractor", "electrician"],
    "ecommerce": ["boutique", "shop", "clothing", "store", "retail"],
    "retail": ["boutique", "shop", "clothing", "store"],
    "d2c": ["boutique", "shop", "clothing", "store"],
    "legal": ["lawyer", "attorney", "law firm", "legal"],
    "law firm": ["lawyer", "attorney", "law firm", "legal"],
    "marketing": ["marketing", "advertising", "public relations"],
}


def expand_search_terms(query: str) -> List[str]:
    q = (query or "").lower().strip()
    terms = [q]
    if q in SEMANTIC_CATEGORY_MAP:
        for t in SEMANTIC_CATEGORY_MAP[q]:
            if t not in terms:
                terms.append(t)
    else:
        for key, syns in SEMANTIC_CATEGORY_MAP.items():
            if key in q or q in key:
                for t in syns:
                    if t not in terms:
                        terms.append(t)
    return terms


def search_osm(category: str, city: str, limit: int = 20) -> list:
    """Free universal provider (OpenStreetMap Nominatim, zero API key required)."""
    geo = geocode_city(city)
    fallback_lat = geo["lat"] if geo else None
    fallback_lon = geo["lon"] if geo else None

    items: list = []
    seen = set()
    terms = expand_search_terms(category)

    for term in terms:
        if len(items) >= limit:
            break

        # Strategy 1: If bounding box is available, perform bounded high-precision search
        if geo and geo.get("bbox"):
            bbox = geo["bbox"]  # [south, north, west, east]
            s, n, w, e = bbox[0], bbox[1], bbox[2], bbox[3]
            try:
                resp = requests.get(NOMINATIM, headers={"User-Agent": OSM_UA}, timeout=15, params={
                    "q": term, "viewbox": f"{w},{n},{e},{s}", "bounded": 1, "format": "jsonv2",
                    "extratags": 1, "addressdetails": 1, "limit": max(limit * 2, 20)})
                if resp.status_code == 200:
                    for row in resp.json():
                        pid = f"{row.get('osm_type')}_{row.get('osm_id')}"
                        if pid not in seen:
                            seen.add(pid)
                            items.append(row)
            except Exception:
                pass

        if len(items) >= limit:
            break

        # Strategy 2: Text search with city anchor
        try:
            resp = requests.get(NOMINATIM, headers={"User-Agent": OSM_UA}, timeout=20, params={
                "q": f"{term} in {city}", "format": "jsonv2", "extratags": 1, "addressdetails": 1,
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

