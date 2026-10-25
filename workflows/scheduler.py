"""
Sequence scheduler: multi-day cadences with stop-on-reply, send windows, jitter and retries.

State lives in the database (sequences, sequence_enrollments, outbound_drafts), so it survives restarts and can run
in the API process (AGENCYBD_SCHEDULER=on) or as a separate worker (`python scripts/run_scheduler.py`). Running two
workers is safe: an enrollment is claimed with a conditional UPDATE before it is processed.
"""

import json
import logging
import os
import random
import re
import threading
from core import metrics
from workflows import controls
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database.db import get_db
from workflows.sequence import OutreachSequenceWorkflow, SequenceStep

logger = logging.getLogger("AgencyBD.scheduler")

MAX_ATTEMPTS = 3
RETRY_DELAY = timedelta(hours=1)
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
FMT = "%Y-%m-%d %H:%M:%S"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(FMT)


def send_window() -> tuple:
    """(start_hour, end_hour) UTC for weekday sends. Env AGENCYBD_SEND_WINDOW='8-18'."""
    raw = os.getenv("AGENCYBD_SEND_WINDOW", "8-18")
    try:
        start, end = (int(x) for x in raw.split("-"))
        if 0 <= start < end <= 24:
            return start, end
    except ValueError:
        pass
    return 8, 18


def next_send_time(at: datetime) -> datetime:
    """Moves `at` forward to the next weekday business window (UTC). Cold email at 3 a.m. Sunday looks like spam."""
    start, end = send_window()
    at = at.astimezone(timezone.utc)
    while True:
        if at.weekday() >= 5:
            at = (at + timedelta(days=1)).replace(hour=start, minute=0, second=0)
        elif at.hour < start:
            at = at.replace(hour=start, minute=0, second=0)
        elif at.hour >= end:
            at = (at + timedelta(days=1)).replace(hour=start, minute=0, second=0)
        else:
            return at


def jitter() -> timedelta:
    return timedelta(minutes=random.randint(7, 18))


def render(template: str, name: str, company: str) -> str:
    first = (name or "").split(" ")[0] if name else ""
    return template.replace("{first_name}", first or "there").replace("{company}", company or "your team")


class SequenceScheduler:
    # ------------------------------------------------------------ definitions
    @staticmethod
    def create_sequence(org_id: str, name: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not name.strip() or not steps:
            raise ValueError("A sequence needs a name and at least one step.")
        clean = []
        for i, s in enumerate(steps, 1):
            subject, body = str(s.get("subject", "")).strip(), str(s.get("body", "")).strip()
            delay = int(s.get("delay_days", 0 if i == 1 else 3))
            if not subject or not body:
                raise ValueError(f"Step {i} needs a subject and a body.")
            if delay < 0 or delay > 60:
                raise ValueError(f"Step {i}: delay_days must be between 0 and 60.")
            if len(body.split()) > 300:
                raise ValueError(f"Step {i} is longer than 300 words.")
            clean.append({"step_number": i, "delay_days": delay, "subject": subject, "body": body})
        with get_db() as db:
            cur = db.execute("INSERT INTO sequences (org_id, name, steps_json) VALUES (?, ?, ?)", (org_id, name.strip(), json.dumps(clean)))
            db.commit()
            return {"id": cur.lastrowid, "name": name.strip(), "steps": clean, "status": "active"}

    @staticmethod
    def list_sequences(org_id: str) -> List[Dict[str, Any]]:
        with get_db() as db:
            rows = db.execute("SELECT * FROM sequences WHERE org_id = ? ORDER BY id DESC", (org_id,)).fetchall()
        return [{"id": r["id"], "name": r["name"], "status": r["status"], "steps": json.loads(r["steps_json"])} for r in rows]

    @staticmethod
    def get_sequence(org_id: str, sequence_id: int) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            r = db.execute("SELECT * FROM sequences WHERE id = ? AND org_id = ?", (sequence_id, org_id)).fetchone()
        return {"id": r["id"], "name": r["name"], "status": r["status"], "steps": json.loads(r["steps_json"])} if r else None

    # ------------------------------------------------------------ enrollments
    @staticmethod
    def enroll(org_id: str, sequence_id: int, recipient_email: str, country_code: str, lead_id: Optional[int] = None,
               recipient_name: str = "", company_name: str = "", deal_value: Optional[float] = None,
               start_at: Optional[datetime] = None) -> Dict[str, Any]:
        seq = SequenceScheduler.get_sequence(org_id, sequence_id)
        if not seq or seq["status"] != "active":
            raise LookupError("Sequence not found")
        if not country_code or not country_code.strip():
            raise ValueError("country_code is required: outreach rules depend on the recipient's jurisdiction.")
        email = recipient_email.strip().lower()
        with get_db() as db:
            dup = db.execute("SELECT id FROM sequence_enrollments WHERE org_id = ? AND recipient_email = ? "
                             "AND status IN ('active', 'awaiting_approval')", (org_id, email)).fetchone()
            if dup:
                raise ValueError("This recipient is already in an active sequence.")
            first_delay = timedelta(days=seq["steps"][0]["delay_days"])
            run_at = next_send_time((start_at or _now()) + first_delay)
            cur = db.execute("""
                INSERT INTO sequence_enrollments (org_id, sequence_id, lead_id, recipient_email, recipient_name, company_name,
                    country_code, deal_value, current_step, next_run_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 'active')
            """, (org_id, sequence_id, lead_id, email, recipient_name, company_name, country_code.upper(), deal_value, _fmt(run_at)))
            db.commit()
            return SequenceScheduler.get_enrollment(org_id, cur.lastrowid)

    @staticmethod
    def get_enrollment(org_id: str, enrollment_id: int) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            r = db.execute("SELECT * FROM sequence_enrollments WHERE id = ? AND org_id = ?", (enrollment_id, org_id)).fetchone()
        return dict(r) if r else None

    @staticmethod
    def list_enrollments(org_id: str, status: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        with get_db() as db:
            q, params = "SELECT * FROM sequence_enrollments WHERE org_id = ?", [org_id]
            if status:
                q += " AND status = ?"
                params.append(status)
            return [dict(r) for r in db.execute(q + " ORDER BY id DESC LIMIT ?", (*params, limit)).fetchall()]

    @staticmethod
    def stop(org_id: str, enrollment_id: int, reason: str = "stopped by user") -> bool:
        with get_db() as db:
            cur = db.execute("UPDATE sequence_enrollments SET status = 'stopped', stop_reason = ? WHERE id = ? AND org_id = ? "
                             "AND status IN ('active', 'awaiting_approval')", (reason, enrollment_id, org_id))
            db.commit()
            return cur.rowcount > 0

    # ------------------------------------------------------------ execution
    @classmethod
    def advance_after_send(cls, org_id: str, enrollment_id: int, now: Optional[datetime] = None) -> None:
        """Called after any step of an enrollment is sent (by the scheduler or after a human-approved send)."""
        now = now or _now()
        enr = cls.get_enrollment(org_id, enrollment_id)
        if not enr or enr["status"] not in ("active", "awaiting_approval"):
            return
        seq = cls.get_sequence(org_id, enr["sequence_id"])
        with get_db() as db:
            if enr["current_step"] >= len(seq["steps"]):
                db.execute("UPDATE sequence_enrollments SET status = 'completed', stop_reason = 'all steps sent' WHERE id = ?", (enrollment_id,))
            else:
                nxt = seq["steps"][enr["current_step"]]  # zero-based index of the next step
                run_at = next_send_time(now + timedelta(days=nxt["delay_days"]) + jitter())
                db.execute("UPDATE sequence_enrollments SET current_step = current_step + 1, status = 'active', attempts = 0, "
                           "next_run_at = ? WHERE id = ?", (_fmt(run_at), enrollment_id))
            db.commit()

    @classmethod
    def run_due(cls, now: Optional[datetime] = None, limit: int = 50, workflow: Optional[OutreachSequenceWorkflow] = None) -> List[Dict[str, Any]]:
        now = now or _now()
        workflow = workflow or OutreachSequenceWorkflow()
        with get_db() as db:
            due = [dict(r) for r in db.execute("""
                SELECT * FROM sequence_enrollments WHERE status = 'active' AND next_run_at <= ?
                ORDER BY next_run_at ASC LIMIT ?""", (_fmt(now), limit)).fetchall()]
        results = []
        for enr in due:
            if controls.is_halted(enr["org_id"]):      # kill switch: leave it due, send nothing
                results.append({"enrollment_id": enr["id"], "outcome": "halted"})
                continue
            # Outside the send window: push it forward instead of sending
            window_start = next_send_time(now)
            if window_start > now:
                with get_db() as db:
                    db.execute("UPDATE sequence_enrollments SET next_run_at = ? WHERE id = ?", (_fmt(window_start), enr["id"]))
                    db.commit()
                results.append({"enrollment_id": enr["id"], "outcome": "deferred_outside_send_window"})
                continue
            # Claim: only one worker processes a given enrollment run
            with get_db() as db:
                claimed = db.execute("UPDATE sequence_enrollments SET next_run_at = ? WHERE id = ? AND status = 'active' AND next_run_at = ?",
                                     (_fmt(now + timedelta(minutes=10)), enr["id"], enr["next_run_at"])).rowcount
                db.commit()
            if claimed:
                results.append(cls._process(enr, workflow, now))
        return results

    @classmethod
    def _process(cls, enr: Dict[str, Any], workflow: OutreachSequenceWorkflow, now: datetime) -> Dict[str, Any]:
        org = enr["org_id"]
        seq = cls.get_sequence(org, enr["sequence_id"])
        if not seq or seq["status"] != "active":
            cls.stop(org, enr["id"], "sequence inactive")
            return {"enrollment_id": enr["id"], "outcome": "stopped", "reason": "sequence inactive"}
        step_def = seq["steps"][enr["current_step"] - 1]
        subject = render(step_def["subject"], enr["recipient_name"], enr["company_name"])
        body = render(step_def["body"], enr["recipient_name"], enr["company_name"])
        if PLACEHOLDER.search(subject + body):
            cls.stop(org, enr["id"], "unrendered placeholder in template")
            return {"enrollment_id": enr["id"], "outcome": "stopped", "reason": "unrendered placeholder"}

        res = workflow.execute_step(
            org_id=org, recipient_email=enr["recipient_email"], country_code=enr["country_code"], lead_id=enr["lead_id"],
            recipient_name=enr["recipient_name"] or "", company_name=enr["company_name"] or "", deal_value=enr["deal_value"],
            step=SequenceStep(step_number=enr["current_step"], delay_days=step_def["delay_days"], subject=subject, body=body),
            enrollment_id=enr["id"], created_by="sequence_scheduler")

        with get_db() as db:
            if res.status == "sent":
                pass  # advance below
            elif res.status == "pending_approval":
                db.execute("UPDATE sequence_enrollments SET status = 'awaiting_approval' WHERE id = ?", (enr["id"],))
            elif res.status in ("no_mailbox", "failed"):
                attempts = enr["attempts"] + 1
                if attempts >= MAX_ATTEMPTS:
                    db.execute("UPDATE sequence_enrollments SET status = 'stopped', stop_reason = ?, attempts = ? WHERE id = ?",
                               (f"gave up after {attempts} attempts: {res.reason}"[:200], attempts, enr["id"]))
                else:
                    db.execute("UPDATE sequence_enrollments SET attempts = ?, next_run_at = ? WHERE id = ?",
                               (attempts, _fmt(next_send_time(now + RETRY_DELAY)), enr["id"]))
            else:  # blocked_by_policy | suppressed | stopped_on_reply | unverified
                db.execute("UPDATE sequence_enrollments SET status = 'stopped', stop_reason = ? WHERE id = ?",
                           (f"{res.status}: {res.reason}"[:200], enr["id"]))
            db.commit()
        if res.status == "sent":
            cls.advance_after_send(org, enr["id"], now)
        return {"enrollment_id": enr["id"], "outcome": res.status, "reason": res.reason, "draft_id": res.draft_id}


# ---------------------------------------------------------------- background runner

class SchedulerThread:
    """Polls run_due() while the API is up. Enabled with AGENCYBD_SCHEDULER=on."""
    def __init__(self, interval_seconds: int = 60):
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="sequence-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                outcomes = SequenceScheduler.run_due()
                if outcomes:
                    logger.info("scheduler processed %d enrollment(s)", len(outcomes))
            except Exception:
                logger.exception("scheduler tick failed")
                metrics.BACKGROUND_FAILURES.labels("scheduler").inc()
            try:
                from workflows import rescan
                done = rescan.run_if_due()
                if done is not None:
                    logger.info("nightly re-scan finished for %d tenant(s)", len(done))
            except Exception:
                logger.exception("nightly re-scan failed")
                metrics.BACKGROUND_FAILURES.labels("rescan").inc()
