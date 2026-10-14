"""RemoteOK connector (public JSON feed, no key). Terms: free to use with attribution and a link back to each job."""

import json
from typing import List, Optional

from connectors.base import BaseConnector, OpportunityItem
from connectors.text import clean_html
from net.fetcher import SafeFetcher


def parse_rows(rows: list) -> List[OpportunityItem]:
    items = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("position"):   # row 0 is a legal notice
            continue
        lo, hi = row.get("salary_min") or None, row.get("salary_max") or None
        items.append(OpportunityItem(
            type="hiring_signal", source="remoteok", external_id=str(row.get("id")), title=f"{row['position']} at {row.get('company', 'Unknown')}",
            description=clean_html(row.get("description") or ""), company_name=row.get("company"),
            url=row.get("url") or row.get("apply_url"), posted_at=row.get("date"), skills_required=list(row.get("tags") or [])[:10],
            budget_min=float(lo) if lo else None, budget_max=float(hi) if hi else None, currency="USD",
            metadata={"location": row.get("location"), "attribution": "Source: RemoteOK (remoteok.com)"}))
    return items


class RemoteOKConnector(BaseConnector):
    source_name = "remoteok"
    terms_url = "https://remoteok.com/legal"
    automation_level = "L0"
    rate_limit_per_minute = 10
    max_fetch = 100

    def fetch(self, query: Optional[str] = None, limit: int = 100, org_id: Optional[str] = None) -> List[OpportunityItem]:
        status, text, _ = SafeFetcher.safe_get("https://remoteok.com/api", timeout=15)
        if status != 200:
            raise RuntimeError(f"RemoteOK returned HTTP {status}")
        return parse_rows(json.loads(text))[:limit]
