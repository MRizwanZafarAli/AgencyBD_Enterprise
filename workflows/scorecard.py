"""Weekly scorecard: what happened this week and last week, counted from real records. A rate is shown only when there is something to divide by;
nothing is estimated, and the 'where winners came from' list only names sources of clients you actually marked won."""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from database.db import get_db

METRICS = [
    ("found", "New leads found", "Leads added or found by your watches"),
    ("sent", "Emails sent", "Outreach emails sent through the app"),
    ("replies", "Replies", "Replies to those emails"),
    ("meetings", "Calls booked", "Meetings booked through the app"),
    ("proposals", "Proposals sent", "Clients moved to Proposal sent"),
    ("wins", "Clients won", "Clients moved to Won"),
    ("messages", "Client messages", "Messages the Alert Desk saw"),
    ("referrals", "Clients sent by partners", "Referrals you logged"),
    ("followups", "Follow-ups done", "Tasks you ticked off"),
]


def week_bounds(today: date) -> Tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=7)


def _count(db, sql: str, args: tuple) -> int:
    return int(db.execute(sql, args).fetchone()[0])


def _week(db, org_id: str, start: date, end: date) -> Dict[str, int]:
    a, b = start.isoformat(), end.isoformat()
    w = (org_id, a, b)
    stage = lambda name: sum(1 for r in db.execute("SELECT metadata_json FROM audit_trail WHERE org_id = ? AND action = 'STAGE_UPDATED' AND created_at >= ? AND created_at < ?", w)
                             if (json.loads(r[0] or "{}")).get("new_stage") == name)
    return {
        "found": _count(db, "SELECT COUNT(*) FROM lead_hits WHERE org_id = ? AND first_seen_at >= ? AND first_seen_at < ?", w)
                 + _count(db, "SELECT COUNT(*) FROM leads WHERE org_id = ? AND source_channel != 'lead_finder' AND created_at >= ? AND created_at < ?", w),   # a hit you kept is already counted as a hit
        "sent": _count(db, "SELECT COUNT(*) FROM outreach_events WHERE org_id = ? AND event_type = 'sent' AND created_at >= ? AND created_at < ?", w),
        "replies": _count(db, "SELECT COUNT(*) FROM outreach_events WHERE org_id = ? AND event_type = 'replied' AND created_at >= ? AND created_at < ?", w),
        "meetings": _count(db, "SELECT COUNT(*) FROM meeting_bookings WHERE lead_id IN (SELECT id FROM leads WHERE org_id = ?) AND created_at >= ? AND created_at < ?", w),
        "proposals": stage("proposal_sent"),
        "wins": stage("won"),
        "messages": _count(db, "SELECT COUNT(*) FROM client_messages WHERE org_id = ? AND received_at >= ? AND received_at < ?", w),
        "referrals": _count(db, "SELECT COUNT(*) FROM partner_events WHERE org_id = ? AND kind = 'referral_in' AND at >= ? AND at < ?", w),
        "followups": _count(db, "SELECT COUNT(*) FROM client_notes WHERE org_id = ? AND kind = 'task' AND done_at >= ? AND done_at < ?", w),
    }


def scorecard(org_id: str, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    s, e = week_bounds(today)
    ps, pe = s - timedelta(days=7), s
    with get_db() as db:
        this, last = _week(db, org_id, s, e), _week(db, org_id, ps, pe)
        winners = [dict(r) for r in db.execute("SELECT source_channel AS source, COUNT(*) AS n FROM leads WHERE org_id = ? AND status = 'won' GROUP BY source_channel ORDER BY n DESC LIMIT 6", (org_id,))]
    rate = lambda a, b: round(100 * a / b) if b else None
    return {
        "week_start": s.isoformat(), "last_week_start": ps.isoformat(),
        "rows": [{"key": k, "label": label, "hint": hint, "this_week": this[k], "last_week": last[k]} for k, label, hint in METRICS],
        "reply_rate_percent": rate(this["replies"], this["sent"]), "last_reply_rate_percent": rate(last["replies"], last["sent"]),
        "winners_by_source": winners,
        "note": "Counted from your own records. A rate appears only when there is something to divide by, and small numbers move a lot from week to week.",
    }
