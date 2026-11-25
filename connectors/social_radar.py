"""
Social Media Buying-Intent Radar Connector.
Monitors public Reddit communities, Hacker News Ask HN, and Product Hunt launches
for active buyer intent signals ("looking for agency", "need a developer",
"website slow", "alternative to") using SafeFetcher + defusedxml.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import defusedxml.ElementTree as ET

from connectors.base import BaseConnector, OpportunityItem
from connectors.text import clean_html
from net.fetcher import SafeFetcher

logger = logging.getLogger("AgencyBD.social_radar")

NS = {"a": "http://www.w3.org/2005/Atom"}
UA = {"User-Agent": "AgencyBD-Enterprise/1.0 (social intent radar; read-only)"}

INTENT_PHRASES = [
    "looking for",
    "need a developer",
    "need an agency",
    "recommend a",
    "anyone know a",
    "hire",
    "redesign",
    "website slow",
    "seo help",
    "alternative to",
    "build an mvp",
    "freelancer",
    "contractor",
]

REDDIT_INTENT_FEEDS = [
    ("r/smallbusiness", "https://www.reddit.com/r/smallbusiness/new.rss?limit=40"),
    ("r/entrepreneur", "https://www.reddit.com/r/entrepreneur/new.rss?limit=40"),
    ("r/saas", "https://www.reddit.com/r/SaaS/new.rss?limit=40"),
]


class SocialIntentRadarConnector(BaseConnector):
    source_name = "social_radar"
    terms_url = "https://www.redditinc.com/policies/data-api-terms"
    automation_level = "L0"
    rate_limit_per_minute = 10
    max_fetch = 60

    def _match_intent(self, text: str, query: Optional[str]) -> Optional[str]:
        low = text.lower()
        if query and query.strip().lower() not in low:
            return None
        for phrase in INTENT_PHRASES:
            if phrase in low:
                return phrase
        return None

    def fetch_reddit_intent(self, query: Optional[str] = None, limit: int = 20) -> List[OpportunityItem]:
        items: List[OpportunityItem] = []
        for sub, feed_url in REDDIT_INTENT_FEEDS:
            try:
                status, text, _ = SafeFetcher.safe_get(feed_url, timeout=10, headers=UA)
                if status != 200 or not text:
                    continue
                root = ET.fromstring(text)
                for e in root.findall("a:entry", NS):
                    title = (e.findtext("a:title", "", NS) or "").strip()
                    body = clean_html(e.findtext("a:content", "", NS) or "")
                    matched = self._match_intent(f"{title} {body[:600]}", query)
                    if not matched:
                        continue
                    link = e.find("a:link", NS).get("href") if e.find("a:link", NS) is not None else ""
                    author = (e.findtext("a:author/a:name", "", NS) or "").lstrip("/u/")
                    items.append(
                        OpportunityItem(
                            type="social",
                            source=f"reddit:{sub}",
                            external_id=(e.findtext("a:id", "", NS) or link).rsplit("/", 1)[-1],
                            title=title,
                            description=body[:1200],
                            company_name=None,
                            url=link,
                            posted_at=e.findtext("a:updated", None, NS),
                            metadata={
                                "platform": "Reddit",
                                "community": sub,
                                "author": author,
                                "intent_phrase": matched,
                            },
                        )
                    )
                    if len(items) >= limit:
                        return items
            except Exception as exc:
                logger.debug(f"Reddit intent feed {sub} skipped: {exc}")
        return items

    def fetch_hn_intent(self, query: Optional[str] = None, limit: int = 15) -> List[OpportunityItem]:
        items: List[OpportunityItem] = []
        try:
            url = "https://hn.algolia.com/api/v1/search_by_date?tags=ask_hn&hitsPerPage=30"
            status, text, _ = SafeFetcher.safe_get(url, timeout=10, headers=UA)
            if status != 200 or not text:
                return items
            data = json.loads(text)
            for hit in data.get("hits", []):
                title = (hit.get("title") or "").strip()
                body = clean_html(hit.get("story_text") or "")
                matched = self._match_intent(f"{title} {body[:500]}", query)
                if not matched and not query:
                    continue
                if query and query.strip().lower() not in f"{title} {body}".lower():
                    continue
                oid = hit.get("objectID", "")
                items.append(
                    OpportunityItem(
                        type="social",
                        source="hn_ask",
                        external_id=str(oid),
                        title=title,
                        description=body[:1200] or title,
                        company_name=None,
                        url=f"https://news.ycombinator.com/item?id={oid}",
                        posted_at=hit.get("created_at"),
                        metadata={
                            "platform": "Hacker News",
                            "author": hit.get("author", ""),
                            "intent_phrase": matched or (query or "ask_hn"),
                        },
                    )
                )
                if len(items) >= limit:
                    break
        except Exception as exc:
            logger.debug(f"HN intent skipped: {exc}")
        return items

    def fetch(self, query: Optional[str] = None, limit: int = 30, org_id: Optional[str] = None) -> List[OpportunityItem]:
        reddit_items = self.fetch_reddit_intent(query=query, limit=limit)
        hn_items = self.fetch_hn_intent(query=query, limit=max(5, limit // 2))
        return (reddit_items + hn_items)[:limit]


def scan_social_intent(query: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    connector = SocialIntentRadarConnector()
    items = connector.fetch(query=query, limit=limit)
    out: List[Dict[str, Any]] = []
    for it in items:
        out.append({
            "source": it.source,
            "type": it.type,
            "external_id": it.external_id,
            "title": it.title,
            "description": it.description,
            "url": it.url,
            "posted_at": it.posted_at,
            "platform": it.metadata.get("platform", it.source),
            "author": it.metadata.get("author", ""),
            "intent_phrase": it.metadata.get("intent_phrase", ""),
        })
    return out
