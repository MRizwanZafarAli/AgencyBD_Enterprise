"""
Sovereign Account IQ Synthesizer.
Generates a LinkedIn Sales Navigator-grade Account IQ brief for any CRM client
from measured site audits, tech stack, decision makers, hiring signals, and Smart Link telemetry.
"""

import json
from typing import Any, Dict, List

from database.db import get_db


def build_account_iq(org_id: str, lead_id: int) -> Dict[str, Any]:
    with get_db() as conn:
        lead = conn.execute(
            "SELECT * FROM leads WHERE id = ? AND org_id = ?",
            (lead_id, org_id),
        ).fetchone()
        if not lead:
            raise LookupError("Lead not found")
        lead_d = dict(lead)

        audit = conn.execute(
            "SELECT * FROM audit_runs WHERE org_id = ? AND LOWER(domain) = LOWER(?) ORDER BY id DESC LIMIT 1",
            (org_id, lead_d.get("domain") or ""),
        ).fetchone()
        audit_d = dict(audit) if audit else None

        findings: List[Dict[str, Any]] = []
        if audit_d:
            f_rows = conn.execute(
                "SELECT category, check_id, severity, finding, fix FROM audit_findings WHERE audit_run_id = ? ORDER BY id ASC",
                (audit_d["id"],),
            ).fetchall()
            findings = [dict(fr) for fr in f_rows]

        contacts = conn.execute(
            "SELECT first_name, last_name, title, email, verification_status, linkedin_url FROM decision_makers WHERE lead_id = ? ORDER BY id DESC LIMIT 10",
            (lead_id,),
        ).fetchall()

        opps = conn.execute(
            "SELECT title, source, url, fit_score FROM opportunities WHERE org_id = ? AND LOWER(COALESCE(company_name,'')) = LOWER(?) ORDER BY id DESC LIMIT 5",
            (org_id, lead_d.get("company_name") or ""),
        ).fetchall()

        views = conn.execute(
            "SELECT report_type, COUNT(*) AS views, MAX(viewed_at) AS last_viewed_at FROM smart_link_events WHERE org_id = ? AND lead_id = ? GROUP BY report_type",
            (org_id, lead_id),
        ).fetchall()

    high_findings = [f for f in findings if f.get("severity") in ("critical", "high")]
    contact_list = [dict(c) for c in contacts]
    verified_contacts = [c for c in contact_list if c.get("verification_status") == "verified"]

    # Determine primary pitch angle from real measured evidence
    if high_findings:
        primary_angle = f"Lead with {len(high_findings)} critical/high technical findings (e.g., {high_findings[0].get('finding', 'site issue')})."
    elif opps:
        primary_angle = f"Reference active {dict(opps[0]).get('source', 'hiring')} signal: '{dict(opps[0]).get('title', '')}'."
    elif not verified_contacts:
        primary_angle = "No verified executive email yet — use Universal Scraper or Sales Nav Companion to capture a decision maker."
    else:
        primary_angle = "Website baseline is healthy — pitch growth, conversion optimization, or engineering capacity."

    return {
        "lead_id": lead_id,
        "company_name": lead_d.get("company_name"),
        "domain": lead_d.get("domain"),
        "stage": lead_d.get("stage"),
        "audit_score": audit_d.get("overall_score") if audit_d else None,
        "critical_findings_count": len(high_findings),
        "top_findings": high_findings[:4],
        "decision_makers_count": len(contact_list),
        "verified_contacts_count": len(verified_contacts),
        "decision_makers": contact_list[:5],
        "active_signals": [dict(o) for o in opps],
        "smart_link_engagement": [dict(v) for v in views],
        "recommended_angle": primary_angle,
    }
