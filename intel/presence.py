"""
Presence Rescue: does this business have a website, and is it any good?

It reports only what its checks established, together with the checks it ran and their limits. A business is never
declared "without a website" on thin evidence: absence is `no_website_listed` (Google has none on file) or
`not_found` (our name-based search found nothing, and that is NOT proof).

Classifications: has_site | social_only | domain_unreachable | domain_parked | no_website_listed | not_found
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from intel.places import find_business, places_configured
from intel.resolver import CompanyResolver, probe, name_tokens
from intel.services import ServiceCatalog
from net.validate import clean_domain

SOCIAL_HOSTS = ("facebook.com", "instagram.com", "linktr.ee", "linktree.com", "twitter.com", "x.com", "linkedin.com", "tiktok.com", "wa.me", "wixsite.com", "business.site")


def _is_social(url: str) -> bool:
    host = (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in SOCIAL_HOSTS)


class PresenceRescueEngine:
    @classmethod
    def evaluate_presence(cls, business_name: str, city: str, provided_domain: Optional[str] = None, org_id: str = "org_default") -> Dict[str, Any]:
        name, city = (business_name or "").strip(), (city or "").strip()
        if len(name) < 2:
            raise ValueError("business_name is required.")
        checks: List[Dict[str, Any]] = []
        tokens = name_tokens(name)

        def note(check: str, outcome: str):
            checks.append({"check": check, "outcome": outcome, "at": datetime.now(timezone.utc).isoformat()})

        classification, domain, verified, confidence, place_id = "not_found", None, False, 0.3, None

        if provided_domain:
            domain = clean_domain(provided_domain).split(":")[0]
            result = probe(domain, tokens)
            if result is None:
                classification, verified, confidence = "domain_unreachable", True, 0.7
                note("fetch provided domain", f"{domain} could not be reached")
            elif result["parked"]:
                classification, verified, confidence = "domain_parked", True, 0.8
                note("fetch provided domain", f"{domain} is parked or for sale")
            else:
                classification, verified, confidence = "has_site", True, 0.95
                note("fetch provided domain", f"{domain} answers but refuses automated access ({result['block_reason']}); the page was not read" if result.get("blocked")
                     else f"{domain} is live ('{result['profile']['title'][:60]}')")
        else:
            place = None
            if places_configured():
                try:
                    place = find_business(name, city)
                    note("Google Places lookup", "no match" if not place else f"match: {place['name']} ({place['address']})")
                except Exception as exc:
                    note("Google Places lookup", f"failed: {str(exc)[:80]}")
            else:
                note("Google Places lookup", "skipped (GOOGLE_PLACES_API_KEY not set)")

            if place:
                place_id = place["place_id"]
                if place["website"] and _is_social(place["website"]):
                    classification, verified, confidence = "social_only", True, 0.85
                    domain = None
                    note("website on Google profile", f"only a social/page-builder link: {place['website']}")
                elif place["website"]:
                    domain = clean_domain(place["website"]).split(":")[0]
                    live = probe(domain, tokens)
                    classification = "has_site" if live and not live["parked"] else "domain_unreachable"
                    verified, confidence = True, 0.9
                    note("website on Google profile", f"{place['website']} ({'live' if classification == 'has_site' else 'not reachable'})")
                else:
                    classification, verified, confidence = "no_website_listed", True, 0.75
                    note("website on Google profile", "the profile lists no website")
            else:
                found = CompanyResolver.resolve_domain_from_name(name, None, org_id=org_id)
                note(f"search {len(found['candidates'])} likely domains for the name", f"result: {found['status']}")
                if found["status"] == "resolved":
                    classification, domain, verified, confidence = "has_site", found["domain"], True, found["confidence"]
                elif found["status"] == "ambiguous":
                    classification, verified, confidence = "not_found", False, 0.2
                else:
                    classification, verified, confidence = "not_found", False, 0.3

        offer = cls._offer(classification, name, city, org_id)
        return {
            "business_name": name, "city": city, "domain": domain, "place_id": place_id,
            "classification": classification, "verified": verified, "confidence": round(confidence, 2),
            "checks_performed": checks,
            "limitations": ["Name-based search can miss real websites (different brand name, new domain, non-English name).",
                            "Confirm by phone or Google Maps before telling a business it has no website."] if not verified else [],
            "offer": offer,
        }

    @staticmethod
    def _offer(classification: str, name: str, city: str, org_id: str) -> Dict[str, Any]:
        key = "presence_rescue" if classification in ("no_website_listed", "not_found", "social_only", "domain_unreachable", "domain_parked") else "performance_engineering"
        service = ServiceCatalog.get(org_id, key)
        hooks = {
            "no_website_listed": f"Hi, I looked up {name} in {city} and your Google profile doesn't list a website. Is that on purpose?",
            "social_only": f"Hi, I looked up {name} in {city} and the only web link I found was a social page. Do you want a proper site customers can book from?",
            "domain_unreachable": f"Hi, I tried to open the website listed for {name} and it didn't load for me. Are you aware of that?",
            "domain_parked": f"Hi, the domain listed for {name} looks parked rather than a live site. Is a new site on your list?",
            "not_found": f"Hi, I searched for a website for {name} in {city} and couldn't find one. Do you have one I missed?",
            "has_site": f"Hi, I ran a quick technical check on the {name} website and found a few things worth a look.",
        }
        return {
            "service_key": key, "service": ServiceCatalog.label(key),
            "price_band": service["price_band"] if service and service.get("price_band") else None,
            "price_note": None if (service and service.get("price_band")) else "No price band set. Add one under Services.",
            "components": ([s.strip() for s in service["offer"].split(";") if s.strip()] if service else []),
            "cold_call_hook": hooks[classification],
        }
