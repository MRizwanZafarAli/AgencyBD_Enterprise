"""Daily digest (fit scores are 0.0-1.0): the best open opportunities and untouched local leads, as Markdown, optionally posted to Slack."""

import os
from datetime import datetime, timezone
from typing import Any, Dict

from config.honesty import NotConfiguredError
from database.db import get_db
from database.models import OpportunityRepository


def build_digest(org_id: str, limit: int = 10, min_score: float = 0.0)  -> Dict[str, Any]:
    opps = [o for o in OpportunityRepository.list_opportunities(limit=300, org_id=org_id)
            if o.get("status") in ("discovered", "qualified") and (o.get("fit_score") or 0) >= min_score][:limit]
    with get_db() as conn:
        leads = [dict(r) for r in conn.execute(
            "SELECT company_name, domain, phone, rating, reviews_count, notes FROM leads WHERE org_id = ? AND status = 'sourced' "
            "AND source_channel = 'google_maps' ORDER BY reviews_count DESC, id DESC LIMIT 5", (org_id,)).fetchall()]
    lines = [f"*AgencyBD digest, {datetime.now(timezone.utc).strftime('%Y-%m-%d')}*", ""]
    if opps:
        lines.append(f"*Top {len(opps)} opportunities*")
        for o in opps:
            budget = f" (up to {o['currency']} {o['budget_max']:,.0f})" if o.get("budget_max") else ""
            lines.append(f"• [{(o.get('fit_score') or 0) * 100:.0f}%] {o['title'][:90]}{budget}, {o['source']} {o.get('url') or ''}".rstrip())
    else:
        lines.append("No new opportunities above your threshold. Run a radar scan.")
    if leads:
        lines += ["", "*Local leads waiting for outreach*"]
        for l in leads:
            lines.append(f"• {l['company_name']}, {l.get('phone') or 'no phone'}, {l.get('notes') or ''}".rstrip(", "))
    return {"opportunity_count": len(opps), "lead_count": len(leads), "text": "\n".join(lines), "opportunities": opps, "leads": leads}


def send_to_slack(text: str) -> bool:
    from adapters.vendor_connectors import VendorConnectors
    url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not url or "mock" in url:
        raise NotConfiguredError("slack", "Set SLACK_WEBHOOK_URL to a Slack incoming-webhook URL to receive the digest.")
    return VendorConnectors.slack_send_alert(text, webhook_url=url)
