"""Optional web-search provider (Brave Search API) used to propose candidate domains for a company name.
Candidates are always verified by fetching the homepage; a search hit alone proves nothing. Fixed vendor host."""

import os
from typing import List
from urllib.parse import urlparse

import requests

URL = "https://api.search.brave.com/res/v1/web/search"
SKIP = ("linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "wikipedia.org", "crunchbase.com", "youtube.com",
        "glassdoor.com", "yelp.com", "bloomberg.com", "reddit.com", "indeed.com", "zoominfo.com", "dnb.com")


def search_configured() -> bool:
    key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    return bool(key and not key.startswith("your_"))


def candidate_domains(query: str, limit: int = 6) -> List[str]:
    resp = requests.get(URL, params={"q": f"{query} official website", "count": 10},
                        headers={"X-Subscription-Token": os.environ["BRAVE_SEARCH_API_KEY"], "Accept": "application/json"}, timeout=15)
    resp.raise_for_status()
    seen: List[str] = []
    for item in (resp.json().get("web") or {}).get("results", []):
        host = (urlparse(item.get("url", "")).hostname or "").lower().removeprefix("www.")
        if host and not any(host == s or host.endswith("." + s) for s in SKIP) and host not in seen:
            seen.append(host)
    return seen[:limit]
