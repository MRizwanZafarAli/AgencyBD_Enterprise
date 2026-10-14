"""
Local client hunt: find businesses in a city (Google Places or free OpenStreetMap), classify their web presence from
real checks, and rank them by how winnable they are for a web / performance / AI service.

Nothing here is invented. Each result carries `reasons` (what raised its score) and `checks` (what was verified), and a
missing website is only called "proven" when the provider is Google (OSM coverage is community-made).
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from config.honesty import NotConfiguredError
from intel import places
from intel.presence import _is_social
from net.validate import clean_domain


def provider_status() -> Dict[str, Any]:
    return {"google": places.places_configured(), "osm": True}


def _site_signals(site_url: str, name: str) -> Dict[str, Any]:
    """Cheap homepage checks. Reports only what was observed; a blocked or inconclusive check is never called 'down'."""
    import requests
    from intel.site_profile import extract_profile
    from net.fetcher import HostUnreachableError, SafeFetcher

    domain = clean_domain(site_url).split(":")[0]
    res, error = None, None
    for scheme in ("https", "http"):
        try:
            res = SafeFetcher.safe_fetch(f"{scheme}://{domain}", timeout=8)
            break
        except HostUnreachableError as exc:
            error = ("dns", str(exc))
            break                                   # no DNS answer: http would fail the same way
        except requests.exceptions.SSLError:
            error = ("tls", "")
            break
        except Exception as exc:                    # timeouts, resets, SSRF blocks: inconclusive
            error = ("other", str(exc)[:60])
    if res is None:
        kind = error[0] if error else "other"
        if kind == "dns" and "DNS resolution" in error[1]:
            return {"classification": "domain_unreachable", "domain": domain, "issues": ["domain does not resolve (DNS lookup fails)"]}
        if kind == "tls":
            return {"classification": "tls_broken", "domain": domain, "issues": ["browsers show a security/certificate error for this site"]}
        return {"classification": "has_site", "domain": domain, "issues": [], "check_note": "could not be checked right now (inconclusive)"}
    if res.status_code in (401, 403, 429, 503):
        return {"classification": "has_site", "domain": domain, "issues": [],
                "check_note": f"site blocked our automated check (HTTP {res.status_code}); not assessed"}
    if res.status_code >= 400:
        return {"classification": "has_site", "domain": domain, "issues": [f"homepage returns HTTP {res.status_code}"]}
    profile = extract_profile(res.text, res.final_url)
    if profile["is_parked"]:
        return {"classification": "domain_parked", "domain": domain, "issues": ["domain looks parked or nearly empty"]}
    html = (res.text or "").lower()
    issues: List[str] = []
    if not str(res.final_url).startswith("https://"):
        issues.append("site is not served over HTTPS")
    if 'name="viewport"' not in html and "name='viewport'" not in html:
        issues.append("no mobile viewport tag (likely not mobile-friendly)")
    if profile["word_count"] < 120:
        issues.append(f"very little content ({profile['word_count']} words)")
    if not profile["meta_description"]:
        issues.append("no meta description (SEO)")
    return {"classification": "has_site", "domain": domain, "issues": issues}


def score_candidate(c: Dict[str, Any]) -> Dict[str, Any]:
    cls, reasons, score = c["classification"], [], 0
    weights = {"no_website_listed": (50, "No website on its Google profile"), "no_website_in_osm": (35, "No website in OpenStreetMap (weaker evidence: verify)"),
               "social_only": (40, "Only a social/page-builder link as its website"), "domain_unreachable": (45, "Its website domain does not resolve (dead link on its listing)"),
               "domain_parked": (45, "Its domain is parked or empty"),
               "tls_broken": (40, "Its website shows a security certificate error")}
    if cls in weights:
        score += weights[cls][0]
        reasons.append(weights[cls][1])
    else:
        n = len(c.get("issues", []))
        score += min(10 + 8 * n, 40)
        reasons += [i.capitalize() for i in c.get("issues", [])] or [c["check_note"].capitalize() if c.get("check_note") else "Has a working site (lower urgency)"]
    reviews = c.get("reviews") or 0
    if reviews >= 50:
        score += 20; reasons.append(f"Well established ({reviews} Google reviews)")
    elif reviews >= 15:
        score += 12; reasons.append(f"Active business ({reviews} reviews)")
    elif reviews >= 5:
        score += 6; reasons.append(f"{reviews} reviews")
    if (c.get("rating") or 0) >= 4.0:
        score += 5; reasons.append(f"Good reputation ({c['rating']}★)")
    if c.get("phone"):
        score += 5; reasons.append("Phone number available")
    c["score"], c["reasons"] = min(score, 100), reasons
    return c


def hunt(category: str, city: str, limit: int = 20, provider: Optional[str] = None) -> Dict[str, Any]:
    category, city = (category or "").strip(), (city or "").strip()
    if len(category) < 2 or len(city) < 2:
        raise ValueError("category and city are required.")
    limit = max(1, min(int(limit), 40))
    provider = provider or ("google" if places.places_configured() else "osm")
    if provider == "google" and not places.places_configured():
        raise NotConfiguredError("google_places", "Set GOOGLE_PLACES_API_KEY to search Google, or use provider=osm (free).")
    raw = places.search_google(category, city, limit) if provider == "google" else places.search_osm(category, city, limit)
    raw = [r for r in raw if r.get("name") and r.get("business_status") in (None, "OPERATIONAL")]

    def classify(r: Dict[str, Any]) -> Dict[str, Any]:
        site = r.get("website")
        if site and _is_social(site):
            r["classification"], r["domain"], r["issues"] = "social_only", None, []
        elif site:
            r.update(_site_signals(site, r["name"]))
        elif r["provider"] == "osm" and (r.get("facebook") or r.get("instagram")):
            r["classification"], r["domain"], r["issues"] = "social_only", None, []
        else:
            r["classification"] = "no_website_listed" if r["provider"] == "google" else "no_website_in_osm"
            r["domain"], r["issues"] = None, []
        r["verified_absence"] = r["classification"] == "no_website_listed"
        return score_candidate(r)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(classify, raw))
    results.sort(key=lambda r: r["score"], reverse=True)
    notes = (["OpenStreetMap is community-mapped: 'no website' here means none is recorded, not proven. Check the business before pitching."]
             if provider == "osm" else [])
    if provider == "osm" and not results:
        notes.append("OpenStreetMap has little or no data for this category in this city (trades and small services are often unmapped). "
                     "Try restaurant, dentist, cafe, hotel or salon, or set GOOGLE_PLACES_API_KEY for full coverage.")
    return {"provider": provider, "category": category, "city": city, "count": len(results), "results": results, "notes": notes}
