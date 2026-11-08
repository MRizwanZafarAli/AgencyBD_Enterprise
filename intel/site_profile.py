"""Extracts verifiable facts from a homepage: what the page says about itself, structured data, and social profiles."""

import json
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

SOCIAL_HOSTS = ("facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com", "tiktok.com", "github.com")
PARKED = re.compile(r"domain (is )?for sale|buy this domain|this domain may be for sale|parked (free )?(domain|page)|domain parking|"
                    r"hugedomains|sedo\.com|afternic|is available for purchase", re.IGNORECASE)


def _flatten_jsonld(node: Any) -> List[Dict[str, Any]]:
    if isinstance(node, list):
        return [x for item in node for x in _flatten_jsonld(item)]
    if isinstance(node, dict):
        out = [node]
        if "@graph" in node:
            out += _flatten_jsonld(node["@graph"])
        return out
    return []


def _types(item: Dict[str, Any]) -> List[str]:
    t = item.get("@type", [])
    return [t] if isinstance(t, str) else [str(x) for x in t]


def looks_js_rendered(soup: BeautifulSoup, words: int) -> bool:
    """True when the page is an app shell: almost no server-rendered text but script bundles or a mount point. Such a page's real content only exists
    in a browser, so a short word count says nothing about the site (Next.js, React, Wix and Squarespace all look like this to a plain fetch)."""
    if words >= 60:
        return False
    scripts = len(soup.find_all("script", src=True))
    mount = soup.find(id=lambda i: i in ("root", "__next", "app", "__nuxt", "___gatsby", "svelte"))
    return scripts >= 2 or bool(mount) or bool(soup.find("noscript"))


def extract_profile(html: str, url: str = "") -> Dict[str, Any]:
    soup = BeautifulSoup(html or "", "html.parser")

    def meta(**attrs) -> str:
        tag = soup.find("meta", attrs=attrs)
        return (tag.get("content") or "").strip() if tag else ""

    jsonld: List[Dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            jsonld += _flatten_jsonld(json.loads(script.string or script.get_text() or ""))
        except (ValueError, TypeError):
            continue
    org = next((i for i in jsonld if set(_types(i)) & {"Organization", "LocalBusiness", "Corporation", "ProfessionalService", "Store",
                                                       "Restaurant", "MedicalBusiness", "LegalService"} or any("Business" in t for t in _types(i))), {})
    same_as = org.get("sameAs", []) if isinstance(org.get("sameAs", []), list) else [org.get("sameAs")]

    socials = sorted({a["href"].split("?")[0] for a in soup.find_all("a", href=True)
                      if any(h in (urlparse(a["href"]).hostname or "") for h in SOCIAL_HOSTS)} |
                     {s for s in same_as if isinstance(s, str)})
    text = soup.get_text(" ", strip=True)
    footer = soup.find("footer")
    copyright_match = re.search(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*)?([^|.\n]{2,60})", (footer.get_text(" ", strip=True) if footer else text[-400:]), re.IGNORECASE)
    address = org.get("address")
    if isinstance(address, dict):
        address = ", ".join(str(address.get(k)) for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry") if address.get(k))

    return {
        "url": url,
        "title": (soup.title.string or "").strip() if soup.title and soup.title.string else "",
        "meta_description": meta(name="description"),
        "og_site_name": meta(property="og:site_name"),
        "og_description": meta(property="og:description"),
        "h1": [h.get_text(" ", strip=True) for h in soup.find_all("h1")][:3],
        "copyright_holder": copyright_match.group(1).strip() if copyright_match else "",
        "org_jsonld": {k: org.get(k) for k in ("name", "description", "telephone", "email", "url") if org.get(k)} | ({"address": address} if address else {}),
        "schema_types": sorted({t for i in jsonld for t in _types(i)}),
        "social_profiles": socials[:12],
        # Parked needs positive evidence. A near-empty page is only "parked" if it is not an app shell (no script bundles or mount point).
        "is_parked": bool(PARKED.search(text[:6000])) or (len(text.split()) < 15 and not looks_js_rendered(soup, len(text.split()))),
        "word_count": len(text.split()),
        "js_rendered": looks_js_rendered(soup, len(text.split())),
    }
