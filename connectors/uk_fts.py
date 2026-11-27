"""UK Find a Tender connector (official OCDS API, free, no key, Open Government Licence). IT services = CPV 72."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, OpportunityItem
from net.fetcher import SafeFetcher

URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"


def _cpv(release: Dict[str, Any]) -> List[str]:
    t = release.get("tender", {})
    codes = [(t.get("classification") or {}).get("id")]
    for item in t.get("items") or []:
        codes += [(item.get("classification") or {}).get("id")] + [
            c.get("id") for c in item.get("additionalClassifications") or []
        ]
    return [str(c) for c in codes if c]


def _extract_buyer_contact(release: Dict[str, Any]) -> Dict[str, str]:
    buyer_id = (release.get("buyer") or {}).get("id")
    for party in release.get("parties") or []:
        roles = party.get("roles") or []
        if party.get("id") == buyer_id or "buyer" in roles:
            cp = party.get("contactPoint") or {}
            addr = party.get("address") or {}
            return {
                "email": (cp.get("email") or "").strip(),
                "phone": (cp.get("telephone") or "").strip(),
                "contact_name": (cp.get("name") or "").strip(),
                "country": (addr.get("countryName") or "United Kingdom").strip(),
                "locality": (addr.get("locality") or "").strip(),
            }
    return {"email": "", "phone": "", "contact_name": "", "country": "United Kingdom", "locality": ""}


def _uk_notice_stage(release: Dict[str, Any]) -> str:
    tags = [str(x).lower() for x in (release.get("tag") or [])]
    t = release.get("tender") or {}
    title = (t.get("title") or "").lower()
    if any("planning" in x for x in tags) or "prior information" in title or "early market" in title:
        return "pin"
    if any("award" in x for x in tags) or release.get("awards"):
        return "award"
    if t.get("hasFrameworkAgreement") or "framework" in title or "dps" in title:
        return "framework"
    return "rfp"


def parse_releases(data: Dict[str, Any], only_it: bool = True) -> List[OpportunityItem]:
    items = []
    for r in data.get("releases", []):
        cpv = _cpv(r)
        if only_it and not any(c.startswith("72") for c in cpv):
            continue
        t = r.get("tender", {})
        value = t.get("value") or {}
        contact = _extract_buyer_contact(r)
        stage = _uk_notice_stage(r)
        awards = r.get("awards") or []
        incumbent = ""
        award_date = None
        if awards:
            sup = (awards[0].get("suppliers") or [{}])[0]
            incumbent = sup.get("name") or ""
            award_date = awards[0].get("date")
        items.append(
            OpportunityItem(
                type="tender",
                source="uk_fts",
                external_id=str(r.get("id") or r.get("ocid")),
                title=t.get("title") or "UK tender",
                description=(t.get("description") or "")[:4000],
                company_name=(r.get("buyer") or {}).get("name"),
                url=f"https://www.find-tender.service.gov.uk/Notice/{r.get('id')}",
                posted_at=r.get("date"),
                deadline=(t.get("tenderPeriod") or {}).get("endDate"),
                budget_max=value.get("amount"),
                currency=value.get("currency", "GBP"),
                skills_required=[f"CPV {c}" for c in cpv[:3]],
                metadata={
                    "ocid": r.get("ocid"),
                    "country": contact["country"],
                    "locality": contact["locality"],
                    "buyer_email": contact["email"],
                    "buyer_phone": contact["phone"],
                    "buyer_contact_name": contact["contact_name"],
                    "notice_stage": stage,
                    "cpv_codes": cpv[:5],
                    "lots_count": len(t.get("lots") or []) or 1,
                    "incumbent": incumbent,
                    "award_date": award_date,
                },
            )
        )
    return items


class UkFindATenderConnector(BaseConnector):
    source_name = "uk_fts"
    terms_url = "https://www.find-tender.service.gov.uk/apidocumentation"
    automation_level = "L0"
    rate_limit_per_minute = 10
    max_fetch = 50

    def fetch(self, query: Optional[str] = None, limit: int = 50, org_id: Optional[str] = None) -> List[OpportunityItem]:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")
        url, items, pages = f"{URL}?limit=100&stages=tender&updatedFrom={since}", [], 0
        while url and len(items) < limit and pages < 4:
            status, text, _ = SafeFetcher.safe_get(url, timeout=30, max_bytes=20_000_000)
            if status != 200:
                raise RuntimeError(f"Find a Tender returned HTTP {status}")
            data = json.loads(text)
            items += parse_releases(data)
            url, pages = (data.get("links") or {}).get("next"), pages + 1
        return items[:limit]
