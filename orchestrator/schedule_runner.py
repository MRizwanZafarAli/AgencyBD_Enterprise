"""
Scheduled Autopilot Runner, Round-Robin Rep Assignment & Risk-Tiered Autonomy.
Enables 1-2 operators to cover 10+ BD reps' prospecting output with compliance guardrails.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from compliance.content_guard import check_outreach_text
from compliance.country_policy import CountryComplianceEngine
from database.db import get_db

logger = logging.getLogger("AgencyBD.schedule_runner")


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def list_schedules(org_id: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM autopilot_schedules WHERE org_id = ? ORDER BY id DESC",
            (org_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_schedule(
    *,
    org_id: str,
    name: str,
    channel: str,
    query: str = "",
    location: str = "",
    limit_per_run: int = 5,
    cadence_hours: int = 24,
    assign_mode: str = "round_robin",
    auto_send_tier_a: bool = False,
) -> Dict[str, Any]:
    if channel not in ("hiring", "local", "sec_edgar", "social", "radar_scan"):
        raise ValueError("Unsupported channel for schedule")
    next_run = _utc_iso(datetime.now(timezone.utc))
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO autopilot_schedules
            (org_id, name, channel, query, location, limit_per_run, cadence_hours, assign_mode, auto_send_tier_a, enabled, next_run_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                org_id,
                name.strip(),
                channel,
                query.strip(),
                location.strip(),
                max(1, min(int(limit_per_run), 25)),
                max(1, min(int(cadence_hours), 168)),
                assign_mode,
                1 if auto_send_tier_a else 0,
                next_run,
            ),
        )
        sid = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM autopilot_schedules WHERE id = ?", (sid,)).fetchone()
    return dict(row)


def toggle_schedule(org_id: str, schedule_id: int, enabled: bool) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE autopilot_schedules SET enabled = ? WHERE id = ? AND org_id = ?",
            (1 if enabled else 0, schedule_id, org_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise LookupError("Schedule not found")
        row = conn.execute("SELECT * FROM autopilot_schedules WHERE id = ?", (schedule_id,)).fetchone()
    return dict(row)


def delete_schedule(org_id: str, schedule_id: int) -> None:
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM autopilot_schedules WHERE id = ? AND org_id = ?",
            (schedule_id, org_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise LookupError("Schedule not found")


def assign_round_robin(org_id: str, lead_id: int, reps: Optional[List[str]] = None) -> str:
    """Distributes leads evenly across active BD reps using deterministic modulo rotation."""
    from database.db import log_audit_trail
    pool = reps or ["sdr_rep", "growth_lead"]
    owner = pool[lead_id % len(pool)]
    log_audit_trail(lead_id, "autopilot", "round_robin_assigned", {"org_id": org_id, "owner": owner})
    return owner


def evaluate_tier_a_auto_approve(
    *,
    subject: str,
    body: str,
    country_code: str,
    mx_verified: bool,
    fit_score: float,
) -> Dict[str, Any]:
    """
    Risk-Tiered Autonomy Gate:
    Only allows Tier-A auto-approval when MX is verified, fit >= 0.80,
    country compliance passes, and content guard flags zero issues.
    """
    reasons: List[str] = []
    if not mx_verified:
        reasons.append("Contact MX not verified")
    if fit_score < 0.80:
        reasons.append(f"Fit score {fit_score:.2f} below 0.80 Tier-A threshold")

    decision = CountryComplianceEngine.evaluate(country_code or "")
    if not decision.allowed:
        reasons.append(decision.reason or "Country compliance blocked")

    guard = check_outreach_text(subject, body)
    if isinstance(guard, dict):
        if not guard.get("ok", True):
            reasons.append("; ".join(guard.get("reasons", ["Content guard failed"])))
    elif guard:
        reasons.append(str(guard))

    return {
        "eligible": len(reasons) == 0,
        "reasons": reasons,
    }


def run_due_schedules(org_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Triggers any enabled schedule whose next_run_at has arrived."""
    from orchestrator import jobs

    now_dt = datetime.now(timezone.utc)
    now_str = _utc_iso(now_dt)
    triggered: List[Dict[str, Any]] = []

    with get_db() as conn:
        if org_id:
            rows = conn.execute(
                "SELECT * FROM autopilot_schedules WHERE org_id = ? AND enabled = 1 AND (next_run_at IS NULL OR next_run_at <= ?)",
                (org_id, now_str),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM autopilot_schedules WHERE enabled = 1 AND (next_run_at IS NULL OR next_run_at <= ?)",
                (now_str,),
            ).fetchall()

    for r in rows:
        sched = dict(r)
        try:
            res = jobs.start(
                sched["org_id"],
                {
                    "channel": sched["channel"],
                    "query": sched["query"] or "",
                    "location": sched["location"] or "",
                    "limit": sched["limit_per_run"],
                },
                user="scheduled_autopilot",
            )
            next_dt = _utc_iso(now_dt + timedelta(hours=int(sched["cadence_hours"] or 24)))
            with get_db() as conn:
                conn.execute(
                    "UPDATE autopilot_schedules SET last_run_at = ?, next_run_at = ? WHERE id = ?",
                    (now_str, next_dt, sched["id"]),
                )
                conn.commit()
            triggered.append({"schedule_id": sched["id"], "name": sched["name"], "run": res})
        except Exception as exc:
            logger.warning(f"Failed schedule {sched['id']}: {exc}")
            triggered.append({"schedule_id": sched["id"], "name": sched["name"], "error": str(exc)})

    return triggered
