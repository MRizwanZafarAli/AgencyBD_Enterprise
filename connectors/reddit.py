"""Reddit r/forhire connector (public Atom feed, no key). Keeps only [HIRING] posts, i.e. people looking to pay someone.
Each item links back to the Reddit post; replying is done by a person on Reddit."""

import xml.etree.ElementTree as ET
from typing import List, Optional

from connectors.base import BaseConnector, OpportunityItem
from connectors.text import clean_html, money
from net.fetcher import SafeFetcher

FEED = "https://www.reddit.com/r/forhire/new.rss?limit=100"
NS = {"a": "http://www.w3.org/2005/Atom"}
UA = {"User-Agent": "AgencyBD-Enterprise/1.0 (opportunity radar; read-only)"}


def parse_feed(xml_text: str) -> List[OpportunityItem]:
    items: List[OpportunityItem] = []
    for e in ET.fromstring(xml_text).findall("a:entry", NS):
        title = (e.findtext("a:title", "", NS) or "").strip()
        if not title.lower().startswith(("[hiring]", "[ hiring ]", "[task]")):
            continue
        link = (e.find("a:link", NS).get("href") if e.find("a:link", NS) is not None else "")
        body = clean_html(e.findtext("a:content", "", NS) or "")
        amounts = money(title + " " + body[:800])
        author = (e.findtext("a:author/a:name", "", NS) or "").lstrip("/u/")
        items.append(OpportunityItem(
            type="inbound", source="reddit", external_id=(e.findtext("a:id", "", NS) or link).rsplit("/", 1)[-1], title=title.split("]", 1)[-1].strip() or title,
            description=body, company_name=None, url=link, posted_at=e.findtext("a:updated", None, NS),
            budget_min=min(amounts) if amounts else None, budget_max=max(amounts) if amounts else None,
            metadata={"author": author, "attribution": "Source: Reddit r/forhire", "contact_method": "reply on Reddit"}))
    return items


class RedditConnector(BaseConnector):
    source_name = "reddit"
    terms_url = "https://www.redditinc.com/policies/data-api-terms"
    automation_level = "L0"
    rate_limit_per_minute = 5
    max_fetch = 100

    def fetch(self, query: Optional[str] = None, limit: int = 100, org_id: Optional[str] = None) -> List[OpportunityItem]:
        status, text, _ = SafeFetcher.safe_get(FEED, timeout=15, headers=UA)
        if status != 200:
            raise RuntimeError(f"Reddit returned HTTP {status} (it rate-limits anonymous readers; retry later)")
        return parse_feed(text)[:limit]
