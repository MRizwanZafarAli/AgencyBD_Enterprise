"""Notes and follow-up tasks on a client, written by your team. Nothing here is generated or inferred."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database.db import get_db
from database.models import LeadRepository

KINDS = ("note", "task")
REVIEW_AFTER_DAYS = 7


def _lead_or_none(org_id: str, lead_id: int) -> Optional[Dict[str, Any]]:
    return LeadRepository.get_lead(lead_id, org_id)


def _day(v: Any) -> Optional[str]:
    if v in (None, ""):
        return None
    if not isinstance(v, str):
        raise ValueError("due_date must be a date like 2026-10-25.")
    try:
        date.fromisoformat(v)
    except ValueError:
        raise ValueError("due_date must be a date like 2026-10-25.")
    return v


def _body(v: Any) -> str:
    v = (v or "").strip() if isinstance(v, str) or v is None else ""
    if not v:
        raise ValueError("Write something first.")
    if len(v) > 2000:
        raise ValueError("That is too long (max 2000 characters).")
    return v


def add(org_id: str, lead_id: int, kind: str, body: str, due_date: Optional[str], user: str) -> Optional[Dict[str, Any]]:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if not _lead_or_none(org_id, lead_id):
        return None
    body, due = _body(body), _day(due_date)
    if kind == "note" and due:
        raise ValueError("Only tasks have a due date.")
    with get_db() as db:
        cur = db.execute("INSERT INTO client_notes (org_id, lead_id, kind, body, due_date, created_by) VALUES (?, ?, ?, ?, ?, ?)", (org_id, lead_id, kind, body, due, user))
        db.commit()
        return dict(db.execute("SELECT * FROM client_notes WHERE id = ?", (cur.lastrowid,)).fetchone())


def list_for(org_id: str, lead_id: int) -> Optional[List[Dict[str, Any]]]:
    if not _lead_or_none(org_id, lead_id):
        return None
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM client_notes WHERE org_id = ? AND lead_id = ? ORDER BY id DESC", (org_id, lead_id)).fetchall()]


def update(org_id: str, lead_id: int, note_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with get_db() as db:
        row = db.execute("SELECT * FROM client_notes WHERE id = ? AND org_id = ? AND lead_id = ?", (note_id, org_id, lead_id)).fetchone()
        if not row:
            return None
        body = _body(data["body"]) if "body" in data else row["body"]
        due = _day(data["due_date"]) if "due_date" in data else row["due_date"]
        if row["kind"] == "note" and due:
            raise ValueError("Only tasks have a due date.")
        done = row["done_at"]
        if "done" in data:
            if row["kind"] != "task":
                raise ValueError("Only tasks can be marked done.")
            done = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if data["done"] else None
        db.execute("UPDATE client_notes SET body = ?, due_date = ?, done_at = ? WHERE id = ?", (body, due, done, note_id))
        db.commit()
        return dict(db.execute("SELECT * FROM client_notes WHERE id = ?", (note_id,)).fetchone())


def delete(org_id: str, lead_id: int, note_id: int) -> bool:
    with get_db() as db:
        n = db.execute("DELETE FROM client_notes WHERE id = ? AND org_id = ? AND lead_id = ?", (note_id, org_id, lead_id)).rowcount
        db.commit()
    return n > 0


def timeline(org_id: str, lead_id: int) -> List[Dict[str, Any]]:
    """System events for this client (audits, stage moves) read from the audit trail."""
    with get_db() as db:
        rows = db.execute("SELECT action, actor, created_at FROM audit_trail WHERE org_id = ? AND lead_id = ? ORDER BY id DESC LIMIT 30", (org_id, lead_id)).fetchall()
    return [{"at": r["created_at"], "what": r["action"].replace("_", " ").capitalize(), "actor": r["actor"]} for r in rows]


def followups(org_id: str, today: Optional[date] = None, limit: int = 50) -> Dict[str, Any]:
    """Open tasks across all clients: overdue or due today, and the next few upcoming."""
    today_s = (today or date.today()).isoformat()
    with get_db() as db:
        rows = db.execute("SELECT n.id, n.lead_id, n.body, n.due_date, l.company_name FROM client_notes n JOIN leads l ON l.id = n.lead_id AND l.org_id = n.org_id "
                          "WHERE n.org_id = ? AND n.kind = 'task' AND n.done_at IS NULL ORDER BY (n.due_date IS NULL), n.due_date, n.id LIMIT ?", (org_id, limit)).fetchall()
    items = [{"id": r["id"], "lead_id": r["lead_id"], "company": r["company_name"], "body": r["body"], "due_date": r["due_date"]} for r in rows]
    return {"due": [i for i in items if i["due_date"] and i["due_date"] <= today_s], "upcoming": [i for i in items if not i["due_date"] or i["due_date"] > today_s]}


def ask_for_review(org_id: str, lead_id: int, company: str, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """When a client is won, plan one task to ask for a review and one introduction. Only once per client; the date is a suggestion you can change."""
    prefix = "Ask for a review and one introduction"
    with get_db() as db:
        if db.execute("SELECT 1 FROM client_notes WHERE org_id = ? AND lead_id = ? AND kind = 'task' AND body LIKE ?", (org_id, lead_id, prefix + "%")).fetchone():
            return None
    due = ((today or date.today()) + timedelta(days=REVIEW_AFTER_DAYS)).isoformat()
    return add(org_id, lead_id, "task", f"{prefix}: {company}", due, "system")
