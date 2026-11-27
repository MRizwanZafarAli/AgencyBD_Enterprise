"""Today: the numbers, focus list and recent activity for the home screen. Everything is read from this workspace's own data."""

import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from database.db import get_db
from database.models import LeadRepository
from routers.system import build_checks
from security.auth import Principal, require_permission
from workflows import channels as ch
from workflows import chase as chase_mod
from workflows import partners as partners_mod
from workflows import client_notes as cn
from alertdesk import engine as alert_engine
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
    waiting_msgs = alert_engine.list_messages(org, "new", limit=50)
    missing = [c for c in build_checks(org) if c["status"] == "missing" and c["required"]]

    focus: List[Dict[str, Any]] = []
    if pending:
        focus.append({"priority": 95, "title": f"Review {pending} draft{'s' if pending != 1 else ''} waiting for approval", "detail": "Nothing is sent until you approve.", "target": {"surface": "today", "anchor": "inbox"}})
    cve = next((w for w in items if w["kind"] == "new_cve"), None)
    if cve:
        focus.append({"priority": 90, "title": cve["title"], "detail": "A reason to get in touch. Confirm the real patch level first.", "target": {"surface": "clients", "lead_id": cve["entity_id"]}})
    if waiting_msgs:
        m = waiting_msgs[0]
        focus.append({"priority": 99, "title": f"{len(waiting_msgs)} client message{'s' if len(waiting_msgs) != 1 else ''} waiting for a reply" + (f": {m['sender']} on {m['platform']}" if len(waiting_msgs) == 1 else ""),
                      "detail": "A fast answer is what clients notice most.", "target": {"surface": "channels"}})
    if tasks:
        first = tasks[0]
        focus.append({"priority": 88, "title": f"{len(tasks)} client follow-up{'s' if len(tasks) != 1 else ''} due" + (f": {first['body'][:60]} ({first['company']})" if len(tasks) == 1 else ""),
                      "detail": "Tasks you set on client pages.", "target": {"surface": "clients", "lead_id": first["lead_id"]}})
    chase_list = chase_mod.to_chase(org)
    if chase_list:
        c0 = chase_list[0]
        focus.append({"priority": 87, "title": f"{len(chase_list)} client{'s' if len(chase_list) != 1 else ''} to chase" + (f": {c0['company']}" if len(chase_list) == 1 else f", starting with {c0['company']} ({c0['stage_label'].lower()})"),
                      "detail": "Gone quiet with no follow-up planned. Set a date or follow up now.", "target": {"surface": "clients", "lead_id": c0["lead_id"]}})
    partner_attn = [p for p in partners_mod.list_partners(org)["partners"] if p["attention"]]
    if partner_attn:
        focus.append({"priority": 70, "title": f"{len(partner_attn)} partner{'s need' if len(partner_attn) != 1 else ' needs'} a nudge" + (f": {partner_attn[0]['name']}" if len(partner_attn) == 1 else ""),
                      "detail": partner_attn[0]["attention"], "target": {"surface": "clients", "tab": "partners"}})
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
                     "pipeline_value": pipe["total_pipeline_value"], "win_rate_percent": pipe["win_rate_percent"], "unvalued_deals": pipe["unvalued_deals_count"], "client_followups_due": len(tasks), "client_messages_waiting": len(waiting_msgs), "clients_to_chase": len(chase_list)},
            "focus": focus[:3], "activity": activity, "channels": channels,
            "note": "Weekly numbers compare the last 7 days with the 7 days before. Pipeline value counts only values you entered."}


@router.get("/scorecard")
def scorecard(principal: Principal = Depends(require_permission("leads:read"))) -> Dict[str, Any]:
    from workflows import scorecard as sc
    return sc.scorecard(principal.org_id)


@router.get("/briefing")
def today_briefing(principal: Principal = Depends(require_permission("leads:read"))) -> Dict[str, Any]:
    """Automated Daily BD Executive Briefing: synthesizes pipeline, tasks, intent and top actions."""
    org = principal.org_id
    summary = today_summary(principal)
    kpis = summary["kpis"]
    focus = summary["focus"]
    channels = summary["channels"]

    from datetime import datetime, timezone
    today_str = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")

    with get_db() as db:
        # Check recent corporate visitor signals
        visitor_count = _count(db, "SELECT COUNT(*) FROM visitor_intent_events WHERE org_id = ? AND created_at >= datetime('now', '-24 hours')", (org,))

    pipe_val = kpis["pipeline_value"] or 0
    val_str = f"${int(pipe_val):,}" if pipe_val else "$0"
    win_rate = f"{kpis['win_rate_percent']}%" if kpis['win_rate_percent'] is not None else "N/A"

    lines = [
        f"# ⚡ AgencyBD Executive Morning Briefing",
        f"**Date:** {today_str} | **Workspace:** {org}",
        "",
        f"### 📊 Pipeline & Revenue Velocity",
        f"- **Active Pipeline Value:** {val_str} ({kpis.get('unvalued_deals', 0)} unvalued in play)",
        f"- **Historical Win Rate:** {win_rate}",
        f"- **Overdue Follow-ups:** {kpis.get('client_followups_due', 0)} client tasks due",
        f"- **Pending Approval Queue:** {kpis.get('pending_approvals', 0)} outbound drafts waiting",
        f"- **Website Intent Signals:** {visitor_count} website visits recorded in the last 24h (companies are not identified)",
        "",
        f"### 🎯 Top 3 Priority Actions for Today"
    ]

    for i, f in enumerate(focus, 1):
        lines.append(f"{i}. **{f['title']}** — {f['detail']}")

    lines.append("")
    lines.append(f"### 🚀 Channel Pacing")
    for c in channels[:3]:
        lines.append(f"- **{c['label']}:** {c.get('streak_days', 0)}d routine streak | {c.get('followups_due', 0)} follow-ups due")

    return {
        "headline": f"Daily Briefing: {today_str}",
        "date": today_str,
        "pipeline_value_str": val_str,
        "followups_due": kpis.get("client_followups_due", 0),
        "pending_approvals": kpis.get("pending_approvals", 0),
        "overnight_visitors": visitor_count,
        "focus_items": focus,
        "markdown": "\n".join(lines)
    }


STAGE_WEIGHTS = {
    "new": 0.15,
    "discovered": 0.15,
    "qualified": 0.25,
    "proposal_sent": 0.50,
    "negotiating": 0.75,
    "won": 1.0,
}


@router.get("/command-center")
def today_command_center(days: int = 14, principal: Principal = Depends(require_permission("leads:read"))) -> Dict[str, Any]:
    """Unified Today Command Center payload: AI Morning Briefing, weighted KPIs, tabbed Action Queue, Top Signals, and Attribution."""
    org = principal.org_id
    days = max(7, min(90, int(days or 14)))
    pipe = LeadRepository.get_pipeline(org)
    items = WorkItemRepository.list_open(org, 40)
    channels = ch.overview(org)
    tasks_due = cn.followups(org)["due"]
    waiting_msgs = alert_engine.list_messages(org, "new", limit=30)
    chase_list = chase_mod.to_chase(org)
    checks = build_checks(org)
    missing_checks = [c for c in checks if c["status"] == "missing" and c["required"]]

    with get_db() as db:
        # 1. Weighted pipeline & bottlenecks (proposals/leads idle 7+ days)
        deal_rows = pipe.get("deals") or []
        weighted_forecast = 0.0
        for dr in deal_rows:
            val = float(dr.get("deal_value") or dr.get("value") or 0)
            st = (dr.get("deal_stage") or dr.get("stage") or "new").lower()
            if st not in ("lost", "archived"):
                weighted_forecast += val * STAGE_WEIGHTS.get(st, 0.25)
        if not deal_rows and pipe.get("total_pipeline_value"):
            weighted_forecast = float(pipe["total_pipeline_value"]) * 0.40

        bottlenecks = [
            {
                "lead_id": r["id"],
                "company_name": r["company_name"],
                "deal_stage": r["status"],
                "deal_value": 0.0,
                "updated_at": r["updated_at"],
            }
            for r in db.execute(
                "SELECT id, company_name, status, updated_at FROM leads "
                "WHERE org_id = ? AND COALESCE(status, 'new') IN ('proposal_sent', 'negotiating', 'qualified', 'contacted') "
                "AND updated_at < datetime('now', '-7 days') ORDER BY updated_at ASC LIMIT 6",
                (org,),
            ).fetchall()
        ]

        # 2. Deliverability & Replies
        sent_7d = _count(db, "SELECT COUNT(*) FROM outbound_drafts WHERE org_id = ? AND status = 'sent' AND sent_at >= datetime('now', '-7 days')", (org,))
        sent_total = _count(db, "SELECT COUNT(*) FROM outbound_drafts WHERE org_id = ? AND status = 'sent'", (org,))
        replies_7d = _count(db, "SELECT COUNT(*) FROM outreach_events WHERE org_id = ? AND event_type = 'replied' AND created_at >= datetime('now', '-7 days')", (org,))
        bounces_total = _count(db, "SELECT COUNT(*) FROM outreach_events WHERE org_id = ? AND event_type = 'bounced'", (org,))
        delivered_pct = round(max(0.0, 100.0 - ((bounces_total / sent_total) * 100.0 if sent_total else 0.0)), 1)
        bounce_pct = round((bounces_total / sent_total) * 100.0, 1) if sent_total else 0.0
        reply_rate_pct = round((replies_7d / sent_7d) * 100.0, 1) if sent_7d else 0.0

        # 3. Pending Approvals (HITL)
        pending_approvals = [
            dict(r)
            for r in db.execute(
                "SELECT a.id AS approval_id, a.subject_id AS draft_id, d.lead_id, d.subject, d.body, l.company_name, d.created_at "
                "FROM approvals a LEFT JOIN outbound_drafts d ON d.id = a.subject_id LEFT JOIN leads l ON l.id = d.lead_id "
                "WHERE a.org_id = ? AND a.decision = 'pending' ORDER BY a.id DESC LIMIT 20",
                (org,),
            ).fetchall()
        ]

        # 4. Urgent Deadlines (Tenders < 7d + Watching hits)
        urgent_tenders = [
            dict(r)
            for r in db.execute(
                "SELECT id, source, title, company_name, url, deadline, fit_score FROM opportunities "
                "WHERE org_id = ? AND type = 'tender' AND deadline IS NOT NULL AND deadline >= date('now') AND deadline <= date('now', '+7 days') "
                "ORDER BY deadline ASC LIMIT 10",
                (org,),
            ).fetchall()
        ]
        watch_hits = [
            dict(r)
            for r in db.execute(
                "SELECT h.id, h.title, h.detail, h.url, h.first_seen_at, s.name AS search_name, s.source AS search_source "
                "FROM lead_hits h JOIN lead_searches s ON s.id = h.search_id "
                "WHERE h.org_id = ? AND h.status = 'new' ORDER BY h.id DESC LIMIT 10",
                (org,),
            ).fetchall()
        ]

        # 5. Top Signals across Find tabs
        top_signals = [
            dict(r)
            for r in db.execute(
                "SELECT id, type, source, title, company_name, url, fit_score, deadline, posted_at "
                "FROM opportunities WHERE org_id = ? AND status != 'dismissed' "
                "ORDER BY (fit_score IS NULL), fit_score DESC, id DESC LIMIT 8",
                (org,),
            ).fetchall()
        ]

        # 6. Velocity Series (last N days)
        sent_by_day = {
            r["d"]: r["c"]
            for r in db.execute(
                "SELECT date(sent_at) AS d, COUNT(*) AS c FROM outbound_drafts WHERE org_id = ? AND status = 'sent' AND sent_at >= date('now', ?) GROUP BY date(sent_at)",
                (org, f"-{days} days"),
            ).fetchall()
        }
        rep_by_day = {
            r["d"]: r["c"]
            for r in db.execute(
                "SELECT date(created_at) AS d, COUNT(*) AS c FROM outreach_events WHERE org_id = ? AND event_type = 'replied' AND created_at >= date('now', ?) GROUP BY date(created_at)",
                (org, f"-{days} days"),
            ).fetchall()
        }
        from datetime import datetime, timedelta, timezone
        today_dt = datetime.now(timezone.utc).date()
        velocity_series = []
        for i in range(min(days, 30) - 1, -1, -1):
            ds = (today_dt - timedelta(days=i)).isoformat()
            velocity_series.append({"date": ds[5:], "sent": int(sent_by_day.get(ds, 0)), "replies": int(rep_by_day.get(ds, 0))})

        # 7. 5-Channel Pipeline & Source Attribution Matrix
        opp_counts = {
            r["t"]: r["c"]
            for r in db.execute(
                "SELECT CASE WHEN type = 'tender' THEN 'tenders' WHEN source LIKE 'social%' THEN 'social' ELSE 'jobs' END AS t, COUNT(*) AS c "
                "FROM opportunities WHERE org_id = ? GROUP BY t",
                (org,),
            ).fetchall()
        }
        watch_count = _count(db, "SELECT COUNT(*) FROM lead_hits WHERE org_id = ?", (org,))
        lead_stats = {
            r["ch"]: {"saved": r["saved"], "val": 0.0}
            for r in db.execute(
                "SELECT COALESCE(source_channel, 'local') AS ch, COUNT(*) AS saved "
                "FROM leads WHERE org_id = ? GROUP BY ch",
                (org,),
            ).fetchall()
        }
        attribution_matrix = [
            {
                "channel": "local",
                "label": "Local Businesses",
                "surface": "find",
                "signals_found": lead_stats.get("local", {}).get("saved", 0) + lead_stats.get("local_hunt", {}).get("saved", 0),
                "saved_to_crm": lead_stats.get("local", {}).get("saved", 0) + lead_stats.get("local_hunt", {}).get("saved", 0),
                "replied": 0,
                "pipeline_value": lead_stats.get("local", {}).get("val", 0) + lead_stats.get("local_hunt", {}).get("val", 0),
            },
            {
                "channel": "jobs",
                "label": "Jobs & Projects",
                "surface": "find",
                "signals_found": opp_counts.get("jobs", 0),
                "saved_to_crm": lead_stats.get("opportunity", {}).get("saved", 0),
                "replied": 0,
                "pipeline_value": lead_stats.get("opportunity", {}).get("val", 0),
            },
            {
                "channel": "social",
                "label": "Social Intent",
                "surface": "find",
                "signals_found": opp_counts.get("social", 0),
                "saved_to_crm": lead_stats.get("social", {}).get("saved", 0),
                "replied": 0,
                "pipeline_value": lead_stats.get("social", {}).get("val", 0),
            },
            {
                "channel": "tenders",
                "label": "Public Tenders",
                "surface": "find",
                "signals_found": opp_counts.get("tenders", 0),
                "saved_to_crm": lead_stats.get("tender", {}).get("saved", 0),
                "replied": 0,
                "pipeline_value": lead_stats.get("tender", {}).get("val", 0),
            },
            {
                "channel": "watching",
                "label": "Watching Monitors",
                "surface": "find",
                "signals_found": watch_count,
                "saved_to_crm": lead_stats.get("lead_finder", {}).get("saved", 0),
                "replied": 0,
                "pipeline_value": lead_stats.get("lead_finder", {}).get("val", 0),
            },
        ]

    # 8. AI Morning Briefing (3-bullet executive pulse)
    briefing_bullets = [
        f"{len(watch_hits)} unread monitor signal(s) in Watching and {len(urgent_tenders)} tender(s) closing within 7 days.",
        f"{len(pending_approvals)} outbound draft(s) awaiting HITL approval · {len(waiting_msgs)} client message(s) waiting for reply.",
        (
            f"{len(bottlenecks)} idle deal(s) (${int(sum(b['deal_value'] for b in bottlenecks)):,}) untouched for 7+ days — queue bump follow-ups."
            if bottlenecks
            else f"Pipeline stands at ${int(pipe['total_pipeline_value'] or 0):,} (${int(weighted_forecast):,} weighted) · {delivered_pct}% delivered."
        ),
    ]

    return {
        "briefing_bullets": briefing_bullets,
        "setup": {
            "total": len(checks),
            "completed": len(checks) - len(missing_checks),
            "required_missing": len(missing_checks),
            "next_fix": missing_checks[0] if missing_checks else None,
        },
        "kpis": {
            "pipeline_value": pipe["total_pipeline_value"],
            "weighted_forecast": round(weighted_forecast, 2),
            "replies_7d": replies_7d,
            "reply_rate_pct": reply_rate_pct,
            "pending_approvals": len(pending_approvals),
            "open_tasks": len(items) + len(tasks_due),
            "sent_7d": sent_7d,
            "sent_total": sent_total,
            "delivered_pct": delivered_pct,
            "bounce_pct": bounce_pct,
        },
        "action_queue": {
            "replies_followups": [
                *[{"kind": "message", "id": m["id"], "title": f"Reply to {m['sender']} on {m['platform']}", "detail": m.get("preview") or "", "lead_id": m.get("lead_id")} for m in waiting_msgs[:10]],
                *[{"kind": "followup", "id": t["id"], "title": f"Follow up: {t['company']}", "detail": t["body"], "lead_id": t["lead_id"]} for t in tasks_due[:10]],
            ],
            "pending_approvals": pending_approvals,
            "urgent_deadlines": [
                *[{"kind": "tender", "id": t["id"], "title": t["title"], "company": t["company_name"], "deadline": t["deadline"], "url": t["url"]} for t in urgent_tenders],
                *[{"kind": "watch", "id": w["id"], "title": w["title"], "company": w["search_name"], "deadline": w["first_seen_at"][:10], "url": w["url"]} for w in watch_hits[:6]],
            ],
            "crm_tasks": [
                *[{"kind": "work_item", "id": w["id"], "title": w["title"], "detail": w.get("detail") or "", "lead_id": w.get("entity_id")} for w in items[:10]],
                *[{"kind": "chase", "id": c["lead_id"], "title": f"Chase {c['company']} ({c['stage_label']})", "detail": "No follow-up scheduled", "lead_id": c["lead_id"]} for c in chase_list[:8]],
            ],
            "bottlenecks": bottlenecks,
        },
        "top_signals": top_signals,
        "velocity_series": velocity_series,
        "attribution_matrix": attribution_matrix,
        "channels": channels,
    }
