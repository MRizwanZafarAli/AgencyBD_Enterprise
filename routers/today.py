"""Today: the numbers, focus list and recent activity for the home screen. Everything is read from this workspace's own data."""

import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from database.db import get_db
from database.models import LeadRepository
from routers.system import build_checks
from security.auth import Principal, require_permission
from workflows import channels as ch
from workflows import client_notes as cn
from workflows.inbox import WorkItemRepository

router = APIRouter(prefix="/api/today", tags=["Today"])

LABELS = {"LEAD_CREATED": "Added a lead", "STATUS_UPDATED": "Changed a client's stage", "DEAL_STAGE_UPDATED": "Moved a client", "AUDIT_COMPLETED": "Audited a website"}


def _count(db, sql: str, params: tuple) -> int:
    return db.execute(sql, params).fetchone()[0]


@router.get("/summary")
def today_summary(principal: Principal = Depends(require_permission("leads:read"))) -> Dict[str, Any]:
    org = principal.org_id
    with get_db() as db:
        def week(table: str, col: str, extra: str = "") -> Dict[str, int]:
            q = f"SELECT COUNT(*) FROM {table} WHERE org_id = ? {extra} AND {col} >= datetime('now', ?) AND {col} < datetime('now', ?)"
            return {"now": _count(db, q, (org, "-7 days", "+1 day")), "before": _count(db, q, (org, "-14 days", "-7 days"))}
        leads = week("leads", "created_at")
        audits = week("audit_runs", "created_at")
        sent = week("outbound_drafts", "sent_at", "AND status = 'sent'")
        replies = week("outreach_events", "created_at", "AND event_type = 'replied'")
        pending = _count(db, "SELECT COUNT(*) FROM approvals WHERE org_id = ? AND decision = 'pending'", (org,))
        hot = _count(db, "SELECT COUNT(*) FROM lead_scores s WHERE s.org_id = ? AND s.band = 'hot' AND s.id = (SELECT MAX(id) FROM lead_scores WHERE lead_id = s.lead_id AND org_id = s.org_id)", (org,))
        rows = db.execute("SELECT t.action, t.actor, t.created_at, t.lead_id, l.company_name FROM audit_trail t LEFT JOIN leads l ON l.id = t.lead_id "
                          "WHERE t.org_id = ? ORDER BY t.id DESC LIMIT 12", (org,)).fetchall()
    activity = [{"at": r["created_at"], "what": LABELS.get(r["action"], r["action"].replace("_", " ").capitalize()), "actor": r["actor"], "lead_id": r["lead_id"], "company": r["company_name"]} for r in rows]

    pipe = LeadRepository.get_pipeline(org)
    items = WorkItemRepository.list_open(org, 50)
    channels = ch.overview(org)
    due = sum(c["followups_due"] for c in channels)
    waiting = [c for c in channels if c["unanswered"]]
    tasks = cn.followups(org)["due"]
    missing = [c for c in build_checks(org) if c["status"] == "missing" and c["required"]]

    focus: List[Dict[str, Any]] = []
    if pending:
        focus.append({"priority": 95, "title": f"Review {pending} draft{'s' if pending != 1 else ''} waiting for approval", "detail": "Nothing is sent until you approve.", "target": {"surface": "today", "anchor": "inbox"}})
    cve = next((w for w in items if w["kind"] == "new_cve"), None)
    if cve:
        focus.append({"priority": 90, "title": cve["title"], "detail": "A reason to get in touch. Confirm the real patch level first.", "target": {"surface": "clients", "lead_id": cve["entity_id"]}})
    if tasks:
        first = tasks[0]
        focus.append({"priority": 88, "title": f"{len(tasks)} client follow-up{'s' if len(tasks) != 1 else ''} due" + (f": {first['body'][:60]} ({first['company']})" if len(tasks) == 1 else ""),
                      "detail": "Tasks you set on client pages.", "target": {"surface": "clients", "lead_id": first["lead_id"]}})
    if waiting:
        focus.append({"priority": 85, "title": "Reply to " + ", ".join(f"{c['label']} ({c['unanswered']})" for c in waiting[:3]), "detail": "Fast replies are what buyers notice.", "target": {"surface": "channels"}})
    if due:
        focus.append({"priority": 80, "title": f"{due} follow-up{'s' if due != 1 else ''} due on your channels", "detail": "From the dates you set in Channels.", "target": {"surface": "channels"}})
    contact = next((w for w in items if w["kind"] == "find_contact"), None)
    if contact:
        focus.append({"priority": 70, "title": contact["title"], "detail": "Your highest-priority lead without a contact.", "target": {"surface": "clients", "lead_id": contact["entity_id"]}})
    if missing:
        focus.append({"priority": 60, "title": f"Finish setup: {missing[0]['label']}", "detail": missing[0].get("fix") or "", "target": {"surface": "settings", "section": "setup"}})
    focus.sort(key=lambda f: -f["priority"])

    return {"kpis": {"new_leads": leads, "audits": audits, "emails_sent": sent, "replies": replies, "pending_approvals": pending, "open_tasks": len(items), "hot_leads": hot,
                     "pipeline_value": pipe["total_pipeline_value"], "win_rate_percent": pipe["win_rate_percent"], "unvalued_deals": pipe["unvalued_deals_count"], "client_followups_due": len(tasks)},
            "focus": focus[:3], "activity": activity, "channels": channels,
            "note": "Weekly numbers compare the last 7 days with the 7 days before. Pipeline value counts only values you entered."}
