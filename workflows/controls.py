"""Per-tenant operational controls. Currently one: the outbound kill switch.

When halted, nothing is sent for that tenant: manual sends are refused and the scheduler leaves enrollments untouched
(they resume exactly where they were when the switch is released)."""

from typing import Any, Dict

from core import metrics
from database.db import get_db


def halt_state(org_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM org_controls WHERE org_id = ?", (org_id,)).fetchone()
    return {"halted": bool(row and row["outbound_halted"]), "reason": row["reason"] if row else None,
            "changed_by": row["changed_by"] if row else None, "changed_at": row["changed_at"] if row else None}


def is_halted(org_id: str) -> bool:
    return halt_state(org_id)["halted"]


def set_halted(org_id: str, halted: bool, changed_by: str, reason: str = "") -> Dict[str, Any]:
    with get_db() as conn:
        conn.execute("""INSERT INTO org_controls (org_id, outbound_halted, reason, changed_by, changed_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(org_id) DO UPDATE SET outbound_halted = excluded.outbound_halted, reason = excluded.reason,
                        changed_by = excluded.changed_by, changed_at = CURRENT_TIMESTAMP""",
                     (org_id, int(halted), reason[:200] or None, changed_by))
        conn.commit()
    metrics.SENDING_HALTED.labels(org_id).set(int(halted))
    return halt_state(org_id)
