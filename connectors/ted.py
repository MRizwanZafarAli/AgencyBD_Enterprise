"""
TED (Tenders Electronic Daily, EU) connector. Official search API v3, free, no key.
IT services = CPV division 72. Notice titles are multilingual; English is preferred when published.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, OpportunityItem
from net.fetcher import SafeFetcher

URL = "https://api.ted.europa.eu/v3/notices/search"
FIELDS = ["notice-title", "publication-date", "buyer-name", "deadline-receipt-tender-date-lot", "classification-cpv",
          "description-lot", "estimated-value-lot"]


def _pick(lang_map: Any) -> (str, str):
    """(text, language) from a {lang: text-or-list} map, preferring English."""
    if isinstance(lang_map, dict) and lang_map:
        lang = "eng" if "eng" in lang_map else next(iter(lang_map))
        val = lang_map[lang]
        return (val[0] if isinstance(val, list) and val else str(val)), lang
    return "", ""


def parse_notices(data: Dict[str, Any]) -> List[OpportunityItem]:
    items = []
    for n in data.get("notices", []):
        pub = n.get("publication-number")
        title, lang = _pick(n.get("notice-title"))
        desc, _ = _pick(n.get("description-lot"))
        buyer, _ = _pick(n.get("buyer-name"))
        deadlines = n.get("deadline-receipt-tender-date-lot") or []
        values = [v for v in (n.get("estimated-value-lot") or []) if isinstance(v, (int, float))]
        flags = ["non_english_notice"] if lang and lang != "eng" else []
        items.append(OpportunityItem(
            type="tender", source="ted", external_id=str(pub), title=title or f"TED notice {pub}", description=desc,
            company_name=buyer or None, url=f"https://ted.europa.eu/en/notice/{pub}/html", posted_at=n.get("publication-date"),
            deadline=min(deadlines) if deadlines else None, budget_max=max(values) if values else None, currency="EUR",
            skills_required=[f"CPV {c}" for c in (n.get("classification-cpv") or [])[:3]], risk_flags=flags,
            metadata={"language": lang}))
    return items


class TedConnector(BaseConnector):
    source_name = "ted"
    terms_url = "https://ted.europa.eu/en/simap/api-and-data-reuse"
    automation_level = "L0"
    rate_limit_per_minute = 10
    max_fetch = 50

    def fetch(self, query: Optional[str] = None, limit: int = 50, org_id: Optional[str] = None) -> List[OpportunityItem]:
        since = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y%m%d")
        body = {"query": f"classification-cpv=72* AND publication-date>={since}", "fields": FIELDS, "limit": min(limit, 50), "page": 1, "scope": "ACTIVE"}
        res = SafeFetcher.safe_fetch(URL, method="POST", json_body=body, timeout=30, max_bytes=20_000_000)
        if res.status_code != 200:
            raise RuntimeError(f"TED returned HTTP {res.status_code}: {res.text[:120]}")
        return parse_notices(json.loads(res.text))
