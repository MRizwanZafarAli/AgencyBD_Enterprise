"""
Hacker News "Who is hiring?" connector (public Algolia HN API, no key).

Reads the NEWEST monthly thread and turns each top-level comment into one hiring signal. (The old connector picked the
wrong thread and stored a single placeholder row with invented skills.) The "Freelancer? Seeking freelancer?" thread is
no longer published, so it is not used.
"""

import json
from typing import List, Optional

from connectors.base import BaseConnector, OpportunityItem
from connectors.text import clean_html, money
from net.fetcher import SafeFetcher

THREADS_URL = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=12"
ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"


def latest_hiring_thread(threads: dict) -> Optional[dict]:
    hits = [h for h in threads.get("hits", []) if h.get("title", "").lower().startswith("ask hn: who is hiring")]
    return max(hits, key=lambda h: h.get("created_at", ""), default=None)


def parse_thread(thread: dict, limit: int) -> List[OpportunityItem]:
    items: List[OpportunityItem] = []
    for c in thread.get("children", []):
        if not c.get("text") or c.get("author") is None:   # deleted / dead comments
            continue
        text = clean_html(c["text"])
        header = text.split("\n", 1)[0]
        parts = [p.strip() for p in header.replace("—", "|").split("|") if p.strip()]
        company = parts[0][:80] if parts else "Unknown"
        amounts = money(header + " " + text[:600])
        items.append(OpportunityItem(
            type="hiring_signal", source="hn", external_id=f"hn_{c['id']}", title=header[:200] or f"Posting by {c['author']}",
            description=text, company_name=company, url=f"https://news.ycombinator.com/item?id={c['id']}",
            posted_at=c.get("created_at"), budget_min=min(amounts) if amounts else None, budget_max=max(amounts) if amounts else None,
            currency="USD", metadata={"thread": thread.get("title"), "author": c["author"]}))
        if len(items) >= limit:
            break
    return items


class HackerNewsConnector(BaseConnector):
    source_name = "hn"
    terms_url = "https://github.com/HackerNews/API"
    automation_level = "L0"
    rate_limit_per_minute = 30
    max_fetch = 400

    def fetch(self, query: Optional[str] = None, limit: int = 400, org_id: Optional[str] = None) -> List[OpportunityItem]:
        status, text, _ = SafeFetcher.safe_get(THREADS_URL, timeout=15)
        if status != 200:
            raise RuntimeError(f"HN thread search returned HTTP {status}")
        latest = latest_hiring_thread(json.loads(text))
        if not latest:
            return []
        status, text, _ = SafeFetcher.safe_get(ITEM_URL.format(id=latest["objectID"]), timeout=40, max_bytes=20_000_000)
        if status != 200:
            raise RuntimeError(f"HN thread fetch returned HTTP {status}")
        return parse_thread(json.loads(text), limit)
