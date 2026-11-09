"""We Work Remotely connector (official public RSS feeds, no key). Attribution: every item keeps its link back to WWR."""

import re
import defusedxml.ElementTree as ET     # hardened parser: refuses entity-expansion (XML bomb) attacks in outside feeds
from email.utils import parsedate_to_datetime
from typing import List, Optional

from connectors.base import BaseConnector, OpportunityItem
from connectors.text import clean_html
from net.fetcher import SafeFetcher

FEEDS = ["https://weworkremotely.com/categories/remote-programming-jobs.rss",
         "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
         "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss"]


def parse_feed(xml_text: str) -> List[OpportunityItem]:
    root = ET.fromstring(xml_text)
    items = []
    for it in root.find("channel").findall("item"):
        title = (it.findtext("title") or "").strip()
        company, _, role = title.partition(":")
        link = (it.findtext("link") or it.findtext("guid") or "").strip()
        try:
            posted = parsedate_to_datetime(it.findtext("pubDate")).isoformat()
        except (TypeError, ValueError):
            posted = None
        items.append(OpportunityItem(
            type="hiring_signal", source="wwr", external_id=link.rsplit("/", 1)[-1] or title, title=role.strip() or title,
            description=clean_html(it.findtext("description") or ""), company_name=company.strip() or None, url=link, posted_at=posted,
            metadata={"region": it.findtext("region"), "category": it.findtext("category")}))
    return items


class WeWorkRemotelyConnector(BaseConnector):
    source_name = "wwr"
    terms_url = "https://weworkremotely.com/remote-job-rss-feed"
    automation_level = "L0"
    rate_limit_per_minute = 6
    max_fetch = 150

    def fetch(self, query: Optional[str] = None, limit: int = 150, org_id: Optional[str] = None) -> List[OpportunityItem]:
        seen, items = set(), []
        for feed in FEEDS:
            status, text, _ = SafeFetcher.safe_get(feed, timeout=15, headers={"User-Agent": "Mozilla/5.0 (compatible; AgencyBD/2.0)"})
            if status != 200:
                raise RuntimeError(f"WWR feed returned HTTP {status}")
            for item in parse_feed(text):
                if item.external_id not in seen:
                    seen.add(item.external_id)
                    items.append(item)
        return items[:limit]
