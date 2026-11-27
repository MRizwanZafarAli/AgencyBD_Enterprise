"""UK Contracts Finder connector (official OCDS API, free, no key) — SME-friendly £10k–£138k UK public contracts."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, OpportunityItem
from connectors.uk_fts import parse_releases
from net.fetcher import SafeFetcher

URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"


class UkContractsFinderConnector(BaseConnector):
    source_name = "uk_cf"
    terms_url = "https://www.contractsfinder.service.gov.uk/Home/About"
    automation_level = "L0"
    rate_limit_per_minute = 10
    max_fetch = 40

    def fetch(self, query: Optional[str] = None, limit: int = 40, org_id: Optional[str] = None) -> List[OpportunityItem]:
        since = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00")
        url = f"{URL}?publishedFrom={since}&size=50"
        status, text, _ = SafeFetcher.safe_get(url, timeout=25, max_bytes=15_000_000)
        if status != 200:
            raise RuntimeError(f"Contracts Finder returned HTTP {status}")
        data = json.loads(text)
        items = parse_releases(data, only_it=True)
        for it in items:
            it.source = "uk_cf"
            if it.external_id:
                it.url = f"https://www.contractsfinder.service.gov.uk/Notice/{it.external_id}"
        return items[:limit]
