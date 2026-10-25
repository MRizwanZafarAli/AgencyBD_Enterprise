"""
Load and soak checks that run in the normal suite at small scale (a regression guard) and bigger with AGENCYBD_SOAK=1:

    AGENCYBD_SOAK=1 python3 -m pytest tests/test_load_and_soak.py -q

They use the in-process fake internet, so they measure our code (parsing, scoring, database, locking), not the network.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

import outbound.providers.registry as registry
from auditors.engine import WebsiteDoctorEngine
from database.db import get_db
from net.fetcher import SafeFetcher
from outbound.providers.registry import MailboxRegistry
from policy.engine import PolicyEngine
from webfake import page
from workflows.scheduler import SequenceScheduler
from workflows.sequence import OutreachSequenceWorkflow

from test_group3_send_path import FakeGate, FakeProvider, tuesday_10am

SOAK = os.getenv("AGENCYBD_SOAK") == "1"
SITES = 300 if SOAK else 40
ENROLLMENTS = 1000 if SOAK else 150
ORG = "org_load"


def test_many_concurrent_audits_all_complete_and_are_stored_consistently(web):
    for i in range(SITES):
        web[f"site{i}.example"] = {"html": page(title=f"Site {i}", desc="A site.", h1="Hello", body="Welcome to our site. " * 40), "headers": {"Server": "nginx"}}
    started = time.time()
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda i: WebsiteDoctorEngine.run_audit(f"site{i}.example", org_id=ORG), range(SITES)))
    elapsed = time.time() - started
    assert all(r["status"] == "completed" for r in results)
    assert len({r["audit_id"] for r in results}) == SITES                       # no two audits shared a row
    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM audit_runs WHERE org_id = ?", (ORG,)).fetchone()[0] == SITES
        stored = db.execute("SELECT COUNT(*) FROM audit_findings WHERE org_id = ?", (ORG,)).fetchone()[0]
    assert stored == sum(r["findings_count"] for r in results)                  # every finding was persisted exactly once
    assert elapsed < (120 if SOAK else 30), f"{SITES} audits took {elapsed:.1f}s"


def test_scheduler_sends_each_step_exactly_once_even_with_two_racing_workers(monkeypatch):
    monkeypatch.setattr(SafeFetcher, "resolve_and_validate_hostname", staticmethod(lambda host: "93.184.216.34"))
    monkeypatch.setattr(registry, "lookup_mx", lambda d: ["mx.example.net"])
    MailboxRegistry.register_mailbox(ORG, "sender@agency.example", "Sender", daily_cap=5000, skip_warmup=True, smtp_host="smtp.mailhost.test",
                                     smtp_username="sender@agency.example", smtp_password="pw-1234567890")
    PolicyEngine.set_tenant_policy(ORG, "outbound_first_touch", "L3")
    PolicyEngine.set_tenant_policy(ORG, "outbound_followup", "L3")
    provider = FakeProvider()
    lock = threading.Lock()
    original_send = provider.send

    def locked_send(message):
        with lock:
            return original_send(message)
    provider.send = locked_send
    workflow = OutreachSequenceWorkflow(provider=provider, verification_gate=FakeGate())

    seq = SequenceScheduler.create_sequence(ORG, "Load", [{"subject": "Hello {company}", "body": "Hi {first_name}, a short note about {company}.", "delay_days": 0}])
    t0 = tuesday_10am()
    for i in range(ENROLLMENTS):
        SequenceScheduler.enroll(ORG, seq["id"], f"person{i}@co{i}.example", "US", recipient_name=f"Person {i}", company_name=f"Co{i}", start_at=t0)

    outcomes = []
    def worker():
        while True:
            out = SequenceScheduler.run_due(t0, limit=25, workflow=workflow)
            if not out:
                return
            outcomes.extend(out)
    threads = [threading.Thread(target=worker) for _ in range(2)]
    started = time.time()
    [t.start() for t in threads]
    [t.join(timeout=120) for t in threads]
    elapsed = time.time() - started

    recipients = [m.to_email for m in provider.sent]
    assert len(recipients) == ENROLLMENTS and len(set(recipients)) == ENROLLMENTS, "a recipient was emailed twice or skipped"
    assert all(o["outcome"] == "sent" for o in outcomes)
    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM sequence_enrollments WHERE org_id = ? AND status = 'completed'", (ORG,)).fetchone()[0] == ENROLLMENTS
    assert elapsed < (180 if SOAK else 40), f"{ENROLLMENTS} sends took {elapsed:.1f}s"


def test_kill_switch_stops_a_large_backlog_instantly(monkeypatch):
    from workflows import controls
    seq = SequenceScheduler.create_sequence("org_load2", "Halt", [{"subject": "Hi", "body": "Hi {first_name}.", "delay_days": 0}])
    t0 = tuesday_10am()
    for i in range(30):
        SequenceScheduler.enroll("org_load2", seq["id"], f"p{i}@c{i}.example", "US", start_at=t0)
    controls.set_halted("org_load2", True, "test")
    provider = FakeProvider()
    out = SequenceScheduler.run_due(t0, limit=100, workflow=OutreachSequenceWorkflow(provider=provider, verification_gate=FakeGate()))
    assert provider.sent == [] and out and all(o["outcome"] == "halted" for o in out)
    controls.set_halted("org_load2", False, "test")
