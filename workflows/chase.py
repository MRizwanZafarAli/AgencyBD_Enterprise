"""Who to chase today: clients in a live stage that have gone quiet and have no follow-up planned. Dates come from your own notes,
sent emails, replies and stage moves; nothing is guessed, and a client with a future follow-up task is left alone."""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from database.db import get_db

QUIET_AFTER_DAYS = {"proposal_sent": 3, "meeting_booked": 2, "sequence_active": 4}
STAGE_LABEL = {"proposal_sent": "Proposal sent", "meeting_booked": "Meeting booked", "sequence_active": "In outreach"}
STAGE_RANK = {"proposal_sent": 0, "meeting_booked": 1, "sequence_active": 2}       # closest to a decision first


def _parse(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        return datetime.strptime(v[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def to_chase(org_id: str, today: Optional[date] = None, limit: int = 20) -> List[Dict[str, Any]]:
    today = today or datetime.now(timezone.utc).date()
    now = datetime(today.year, today.month, today.day, 23, 59, tzinfo=timezone.utc)
    marks = ",".join("?" for _ in QUIET_AFTER_DAYS)
    with get_db() as db:
        leads = db.execute(f"SELECT id, company_name, status, created_at FROM leads WHERE org_id = ? AND status IN ({marks})", (org_id, *QUIET_AFTER_DAYS)).fetchall()
        out = []
        for l in leads:
            planned = db.execute("SELECT 1 FROM client_notes WHERE org_id = ? AND lead_id = ? AND kind = 'task' AND done_at IS NULL AND due_date >= ? LIMIT 1",
                                 (org_id, l["id"], today.isoformat())).fetchone()
            if planned:
                continue
            stamps = [l["created_at"]]
            stamps += [r[0] for r in db.execute("SELECT MAX(created_at) FROM client_notes WHERE org_id = ? AND lead_id = ?", (org_id, l["id"]))]
            stamps += [r[0] for r in db.execute("SELECT MAX(done_at) FROM client_notes WHERE org_id = ? AND lead_id = ?", (org_id, l["id"]))]
            stamps += [r[0] for r in db.execute("SELECT MAX(created_at) FROM outreach_events WHERE org_id = ? AND lead_id = ? AND event_type IN ('sent', 'replied')", (org_id, l["id"]))]
            stamps += [r[0] for r in db.execute("SELECT MAX(created_at) FROM inbound_replies WHERE lead_id = ?", (l["id"],))]
            stamps += [r[0] for r in db.execute("SELECT MAX(created_at) FROM audit_trail WHERE org_id = ? AND lead_id = ? AND action = 'STAGE_UPDATED'", (org_id, l["id"]))]
            last = max((d for d in map(_parse, stamps) if d), default=None)
            if not last:
                continue
            quiet = (now - last).days
            if quiet < QUIET_AFTER_DAYS[l["status"]]:
                continue
            out.append({"lead_id": l["id"], "company": l["company_name"], "stage": l["status"], "stage_label": STAGE_LABEL[l["status"]], "days_quiet": quiet,
                        "reason": f"{STAGE_LABEL[l['status']]}, and nothing has happened for {quiet} day{'s' if quiet != 1 else ''}. No follow-up is planned."})
    out.sort(key=lambda i: (STAGE_RANK[i["stage"]], -i["days_quiet"]))
    return out[:limit]
