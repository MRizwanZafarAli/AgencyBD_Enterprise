"""
SAM.gov Opportunities connector (US federal). Needs a free API key (SAM_GOV_API_KEY).

The API requires postedFrom/postedTo (MM/DD/YYYY, at most one year apart) and only searches titles, so we filter by
software-related NAICS codes (541511 programming, 541512 systems design, 541519 other IT). The `description` field of a
notice is a URL to the full text, not the text itself; we keep the link.
NOTE: parsing follows SAM.gov's documented response shape. It has not been exercised against the live API in this project
because that needs a key.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from connectors.base import BaseConnector, ConnectorNotConfigured, OpportunityItem
from net.fetcher import SafeFetcher

URL = "https://api.sam.gov/opportunities/v2/search"
NAICS = ("541511", "541512", "541519")


def parse_notices(data: Dict[str, Any]) -> List[OpportunityItem]:
    items = []
    for o in data.get("opportunitiesData", []):
        poc = (o.get("pointOfContact") or [{}])[0]
        office = o.get("officeAddress") or {}
        items.append(OpportunityItem(
            type="tender", source="sam_gov", external_id=str(o.get("noticeId")), title=o.get("title") or "Federal opportunity",
            description=" | ".join(x for x in [f"Type: {o.get('type')}", f"Solicitation: {o.get('solicitationNumber')}", f"NAICS: {o.get('naicsCode')}",
                                               f"Place: {office.get('city', '')} {office.get('state', '')}".strip(), f"Contact: {poc.get('fullName', '')} {poc.get('email', '')}".strip()] if x),
            company_name=o.get("fullParentPathName") or o.get("department"), url=o.get("uiLink"), posted_at=o.get("postedDate"),
            deadline=o.get("responseDeadLine"), skills_required=[f"NAICS {o.get('naicsCode')}"] if o.get("naicsCode") else [],
            risk_flags=["requires_sam_registration"], metadata={"description_url": o.get("description")}))
    return items


class SamGovConnector(BaseConnector):
    source_name = "sam_gov"
    terms_url = "https://open.gsa.gov/api/opportunities-api/"
    automation_level = "L0"
    rate_limit_per_minute = 10
    requires_api_key = True
    max_fetch = 100

    def fetch(self, query: Optional[str] = None, limit: int = 100, org_id: Optional[str] = None) -> List[OpportunityItem]:
        key = os.getenv("SAM_GOV_API_KEY", "")
        if not key or key.startswith("your_"):
            raise ConnectorNotConfigured("Set SAM_GOV_API_KEY (free at sam.gov > Account Details > Public API Key).")
        now = datetime.now(timezone.utc)
        items: List[OpportunityItem] = []
        for code in NAICS:
            params = {"api_key": key, "postedFrom": (now - timedelta(days=30)).strftime("%m/%d/%Y"), "postedTo": now.strftime("%m/%d/%Y"),
                      "ncode": code, "limit": min(limit, 100), "active": "Yes"}
            status, text, _ = SafeFetcher.safe_get(f"{URL}?{urlencode(params)}", timeout=30)
            if status != 200:
                raise RuntimeError(f"SAM.gov returned HTTP {status}: {text[:120]}")
            items += parse_notices(json.loads(text))
        seen, unique = set(), []
        for i in items:
            if i.external_id not in seen:
                seen.add(i.external_id)
                unique.append(i)
        return unique[:limit]
