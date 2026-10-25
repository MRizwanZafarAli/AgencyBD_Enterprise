"""
Work items: things a person needs to do, produced by automation (find a decision maker, review a lead, a new CVE matched a client).

Automation never fills the gap itself. When it lacks something real (a contact, a domain, a measurement) it opens a work item
and stops. `dedupe_key` makes it safe to run the same automation again: an open item with the same key is not duplicated.
"""

import sqlite3
from typing import Any, Dict, List, Optional

from database.db import get_db

KINDS = {"find_contact", "review_lead", "fix_setup", "new_cve", "reply", "custom"}


class WorkItemRepository:
    @staticmethod
    def add(org_id: str, kind: str, title: str, detail: str = "", entity_type: Optional[str] = None, entity_id: Optional[int] = None,
            priority: int = 50, dedupe_key: Optional[str] = None) -> Dict[str, Any]:
        if kind not in KINDS:
            raise ValueError(f"Unknown work item kind '{kind}'")
        with get_db() as db:
            try:
                cur = db.execute("""INSERT INTO work_items (org_id, kind, title, detail, entity_type, entity_id, priority, dedupe_key)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                 (org_id, kind, title[:200], detail[:1000], entity_type, entity_id, max(0, min(100, priority)), dedupe_key))
                db.commit()
                row = db.execute("SELECT * FROM work_items WHERE id = ?", (cur.lastrowid,)).fetchone()
                return {**dict(row), "created": True}
            except sqlite3.IntegrityError:        # an open item with this dedupe_key already exists
                row = db.execute("SELECT * FROM work_items WHERE org_id = ? AND dedupe_key = ? AND status = 'open'", (org_id, dedupe_key)).fetchone()
                return {**dict(row), "created": False}

    @staticmethod
    def list_open(org_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with get_db() as db:
            rows = db.execute("SELECT * FROM work_items WHERE org_id = ? AND status = 'open' ORDER BY priority DESC, id DESC LIMIT ?",
                              (org_id, limit)).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def resolve(org_id: str, item_id: int, status: str = "done") -> bool:
        if status not in ("done", "dismissed"):
            raise ValueError("status must be 'done' or 'dismissed'")
        with get_db() as db:
            n = db.execute("UPDATE work_items SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ? AND org_id = ? AND status = 'open'",
                           (status, item_id, org_id)).rowcount
            db.commit()
        return n > 0
