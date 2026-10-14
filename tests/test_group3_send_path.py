"""
Fix group 3: a send path that cannot bypass the guards (P0-4), real verification and per-mailbox credentials (P0-6),
and a scheduler that runs multi-day sequences (P1-5).

No network: SMTP, DNS and the verifier vendors are stubbed. The point is to prove the guards, not the providers.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import outbound.providers.registry as registry
import outbound.providers.smtp as smtp_mod
import outbound.verify as verify_mod
from compliance.suppression import KeyedSuppressionVault
from database.db import get_db
from database.models import ApprovalRepository
from net.fetcher import SafeFetcher
from outbound.providers.base import OutboundMessage, SendProvider, SendResult
from outbound.providers.registry import MailboxRegistry, ramp_cap, classify_esp
from outbound.verify import EmailVerificationGate, VerificationResult, VerifierVendor, ZeroBounceVendor, MillionVerifierVendor
from policy.engine import PolicyEngine
from security.crypto import decrypt_secret
from workflows.scheduler import SequenceScheduler, next_send_time
from workflows.sequence import OutreachSequenceWorkflow, SequenceStep

ORG = "org_send"


# ------------------------------------------------------------------ test doubles

class FakeProvider(SendProvider):
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def send(self, message: OutboundMessage) -> SendResult:
        if self.fail:
            return SendResult(success=False, provider="fake", status="failed", error="relay down")
        self.sent.append(message)
        return SendResult(success=True, provider="fake", provider_message_id=f"<m{len(self.sent)}@fake>", status="sent")

    def health_check(self):
        return {"ready": True}


class FakeGate:
    """Verifies everything except addresses containing 'bad' or 'risky'."""
    def verify(self, email):
        status = "unverified" if "bad" in email else "risky" if "risky" in email else "verified"
        return VerificationResult(email, status, status == "verified", "fake", 1.0, status)


@pytest.fixture
def box(monkeypatch):
    """A tenant with one warmed mailbox that has (encrypted) SMTP credentials."""
    monkeypatch.setattr(SafeFetcher, "resolve_and_validate_hostname", staticmethod(lambda host: "93.184.216.34"))
    monkeypatch.setattr(registry, "lookup_mx", lambda d: ["mx.example.net"])
    return MailboxRegistry.register_mailbox(ORG, "sender@agency.example", "Alex", daily_cap=50, skip_warmup=True,
                                            smtp_host="smtp.mailhost.test", smtp_username="sender@agency.example",
                                            smtp_password="s3cret-pass")


@pytest.fixture
def wf():
    return OutreachSequenceWorkflow(provider=FakeProvider(), verification_gate=FakeGate())


def step(n=1, subject="Quick question about your site", body="Hi, we ran a check on your site and found two things worth a look."):
    return SequenceStep(step_number=n, delay_days=0, subject=subject, body=body)


def l3(org=ORG):
    PolicyEngine.set_tenant_policy(org, "outbound_first_touch", "L3")
    PolicyEngine.set_tenant_policy(org, "outbound_followup", "L3")


# ================================================================== P0-4: the send path cannot bypass the guards

def test_unknown_country_is_blocked_not_assumed_to_be_the_us(box, wf):
    assert wf.execute_step(ORG, "a@acme.example", step(), country_code=None).status == "blocked_by_policy"
    assert wf.execute_step(ORG, "a@acme.example", step(), country_code="").status == "blocked_by_policy"
    assert wf.execute_step(ORG, "a@acme.example", step(), country_code="CA").status == "blocked_by_policy"
    assert wf.provider.sent == []


def test_first_touch_requires_approval_then_sends_the_stored_text(box, wf):
    res = wf.execute_step(ORG, "dana@acme.example", step(), country_code="US")
    assert res.status == "pending_approval" and res.draft_id
    assert wf.provider.sent == [], "nothing may leave the building before a human approves"
    pending = [a for a in ApprovalRepository.list_pending(ORG) if a["subject_type"] == "outbound_draft"]
    assert pending and pending[0]["draft_recipient"] == "dana@acme.example" and "ran a check" in pending[0]["draft_body"]

    # not approved yet: still cannot be sent
    assert wf.send_approved_draft(ORG, res.draft_id).status == "blocked_by_policy"

    ApprovalRepository.decide(pending[0]["id"], "approved", "founder", org_id=ORG)
    sent = wf.send_approved_draft(ORG, res.draft_id)
    assert sent.status == "sent" and sent.mailbox_used == "sender@agency.example"
    msg = wf.provider.sent[0]
    assert msg.to_email == "dana@acme.example" and "ran a check" in msg.body_text
    assert msg.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click" and "token=" in msg.headers["List-Unsubscribe"]
    assert "unsubscribe" in msg.body_text.lower()
    # sending twice is not possible
    assert wf.send_approved_draft(ORG, res.draft_id).status == "blocked_by_policy"
    assert len(wf.provider.sent) == 1


def test_rejected_draft_is_never_sent(box, wf):
    res = wf.execute_step(ORG, "dana@acme.example", step(), country_code="US")
    approval = [a for a in ApprovalRepository.list_pending(ORG) if a["subject_id"] == res.draft_id][0]
    ApprovalRepository.decide(approval["id"], "rejected", "founder", org_id=ORG)
    assert wf.send_approved_draft(ORG, res.draft_id).status == "blocked_by_policy"
    assert wf.provider.sent == []


def test_guards_are_rechecked_at_send_time(box, wf):
    res = wf.execute_step(ORG, "dana@acme.example", step(), country_code="US")
    approval = [a for a in ApprovalRepository.list_pending(ORG) if a["subject_id"] == res.draft_id][0]
    ApprovalRepository.decide(approval["id"], "approved", "founder", org_id=ORG)
    KeyedSuppressionVault.suppress("dana@acme.example", org_id=ORG)          # unsubscribed after approval
    out = wf.send_approved_draft(ORG, res.draft_id)
    assert out.status == "suppressed" and wf.provider.sent == []


def test_reply_after_approval_stops_the_send(box, wf):
    res = wf.execute_step(ORG, "dana@acme.example", step(), country_code="US")
    approval = [a for a in ApprovalRepository.list_pending(ORG) if a["subject_id"] == res.draft_id][0]
    ApprovalRepository.decide(approval["id"], "approved", "founder", org_id=ORG)
    MailboxRegistry.record_event(ORG, "dana@acme.example", "replied")
    assert wf.send_approved_draft(ORG, res.draft_id).status == "stopped_on_reply"


def test_delegated_level_sends_immediately_but_guards_still_apply(box, wf):
    l3()
    assert wf.execute_step(ORG, "ok@acme.example", step(), country_code="US").status == "sent"
    assert wf.execute_step(ORG, "bad@acme.example", step(), country_code="US").status == "unverified"
    assert wf.execute_step(ORG, "risky@acme.example", step(), country_code="US").status == "unverified"
    KeyedSuppressionVault.suppress("opt@acme.example", org_id=ORG)
    assert wf.execute_step(ORG, "opt@acme.example", step(), country_code="US").status == "suppressed"
    assert wf.execute_step(ORG, "x@acme.example", step(), country_code="DE").status == "blocked_by_policy"
    assert [m.to_email for m in wf.provider.sent] == ["ok@acme.example"]


def test_high_value_deal_still_needs_a_human_at_any_level(box, wf):
    l3()
    res = wf.execute_step(ORG, "big@acme.example", step(), country_code="US", deal_value=25000)
    assert res.status == "pending_approval" and wf.provider.sent == []


def test_every_attempt_leaves_an_auditable_draft(box, wf):
    l3()
    res = wf.execute_step(ORG, "ok@acme.example", step(), country_code="US")
    draft = wf.get_draft(ORG, res.draft_id)
    assert draft["status"] == "sent" and draft["policy_rule"] and draft["sent_at"]
    assert json.loads(draft["send_result_json"])["mailbox"] == "sender@agency.example"


def test_provider_failure_is_recorded_not_hidden(box):
    wf = OutreachSequenceWorkflow(provider=FakeProvider(fail=True), verification_gate=FakeGate())
    l3()
    res = wf.execute_step(ORG, "ok@acme.example", step(), country_code="US")
    assert res.status == "failed" and "relay down" in res.reason
    assert wf.get_draft(ORG, res.draft_id)["status"] == "failed"
    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM outreach_events WHERE event_type = 'sent'").fetchone()[0] == 0


def test_stop_reason_covers_all_negative_signals():
    for event in ("replied", "bounced", "complaint", "unsubscribed"):
        MailboxRegistry.record_event(ORG, f"{event}@acme.example", event)
        assert OutreachSequenceWorkflow.stop_reason(ORG, f"{event}@acme.example") == f"prospect {event}"
    assert OutreachSequenceWorkflow.stop_reason(ORG, "fresh@acme.example") is None
    assert OutreachSequenceWorkflow.stop_reason("other_org", "replied@acme.example") is None


# ================================================================== mailboxes: credentials, caps, warm-up

def test_credentials_are_encrypted_and_never_returned(box, client, make_key):
    with get_db() as db:
        stored = db.execute("SELECT password_enc FROM mailbox_credentials").fetchone()[0]
    assert "s3cret-pass" not in stored and decrypt_secret(stored) == "s3cret-pass"
    listed = MailboxRegistry.list_mailboxes(ORG)[0]
    assert listed["has_credentials"] is True and "password" not in json.dumps(listed).lower().replace("has_credentials", "")
    api = client.get("/api/outbound/mailboxes", headers=make_key("growth_lead", org_id=ORG)).text
    assert "s3cret-pass" not in api and "password_enc" not in api


def test_private_relay_hosts_are_refused(client, make_key):
    res = client.post("/api/outbound/mailboxes", headers=make_key("growth_lead"), json={
        "email": "x@agency.example", "smtp_host": "127.0.0.1", "smtp_username": "u", "smtp_password": "p"})
    assert res.status_code == 400 and "blocked" in res.json()["detail"].lower()


def test_each_mailbox_logs_in_with_its_own_credentials(monkeypatch):
    monkeypatch.setattr(SafeFetcher, "resolve_and_validate_hostname", staticmethod(lambda host: "93.184.216.34"))
    monkeypatch.setattr(registry, "lookup_mx", lambda d: ["mx.example.net"])
    for n in (1, 2):
        MailboxRegistry.register_mailbox(ORG, f"box{n}@agency.example", skip_warmup=True, smtp_host=f"smtp{n}.mailhost.test",
                                         smtp_username=f"user{n}", smtp_password=f"pass{n}")
    logins = []

    class FakeServer:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context=None): pass
        def login(self, user, pw): logins.append((user, pw))
        def sendmail(self, frm, to, body): pass

    monkeypatch.setattr(smtp_mod, "open_smtp", lambda creds, timeout=15: FakeServer())
    provider = smtp_mod.SmtpProvider()
    for n in (1, 2):
        out = provider.send(OutboundMessage(to_email="a@b.example", from_email=f"box{n}@agency.example", subject="s",
                                            body_text="b", org_id=ORG))
        assert out.success
    assert logins == [("user1", "pass1"), ("user2", "pass2")]


def test_sending_without_credentials_fails_honestly():
    MailboxRegistry.register_mailbox(ORG, "nocreds@agency.example", skip_warmup=True)
    res = smtp_mod.SmtpProvider().send(OutboundMessage(to_email="a@b.example", from_email="nocreds@agency.example",
                                                       subject="s", body_text="b", org_id=ORG))
    assert not res.success and res.status == "not_configured"


def test_mailbox_without_credentials_is_not_selected_in_real_mode(wf):
    MailboxRegistry.register_mailbox(ORG, "nocreds@agency.example", skip_warmup=True)
    l3()
    res = wf.execute_step(ORG, "ok@acme.example", step(), country_code="US")
    assert res.status == "no_mailbox"


def test_header_injection_is_blocked(monkeypatch):
    monkeypatch.setattr(smtp_mod, "open_smtp", lambda c, timeout=15: pytest.fail("must not connect"))
    p = smtp_mod.SmtpProvider(host="smtp.mailhost.test", username="u", password="p")
    out = p.send(OutboundMessage(to_email="a@b.example", from_email="x@y.example", subject="s", body_text="b",
                                 headers={"X-Evil": "a\r\nBcc: victim@evil.example"}, org_id=ORG))
    assert not out.success and "injection" in out.error.lower()


def test_warmup_ramp_and_rolling_cap(monkeypatch):
    monkeypatch.setattr(SafeFetcher, "resolve_and_validate_hostname", staticmethod(lambda host: "93.184.216.34"))
    monkeypatch.setattr(registry, "lookup_mx", lambda d: ["mx.example.net"])
    fresh = MailboxRegistry.register_mailbox("org_ramp", "new@agency.example", daily_cap=35, smtp_host="s.mailhost.test",
                                             smtp_username="u", smtp_password="p")
    now = datetime.now(timezone.utc)
    iso = lambda days: (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    assert ramp_cap(iso(0), 35, False) == 5 and ramp_cap(iso(4), 35, False) == 10
    assert ramp_cap(iso(10), 35, False) == 20 and ramp_cap(iso(18), 35, False) == 30 and ramp_cap(iso(30), 35, False) == 35
    assert ramp_cap(iso(0), 35, True) == 35 and ramp_cap(iso(0), 3, False) == 3
    # the cap is enforced from real 'sent' events in the last 24h
    for i in range(5):
        MailboxRegistry.record_send("org_ramp", fresh["id"], f"p{i}@x.example")
    assert MailboxRegistry.select_best_mailbox("org_ramp", require_credentials=True) is None
    with get_db() as db:   # yesterday's sends no longer count: no daily reset job needed
        db.execute("UPDATE outreach_events SET created_at = datetime('now', '-25 hours')")
        db.commit()
    assert MailboxRegistry.select_best_mailbox("org_ramp", require_credentials=True)["email"] == "new@agency.example"


def test_esp_classification_from_mx():
    assert classify_esp(["aspmx.l.google.com", "alt1.aspmx.l.google.com"]) == "google"
    assert classify_esp(["acme-com.mail.protection.outlook.com"]) == "microsoft"
    assert classify_esp(["mail.zoho.com"]) == "other" and classify_esp([]) == "unknown" and classify_esp(None) == "unknown"


# ================================================================== P0-6: real verification, fail closed

class StubResp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status
    def json(self): return self._d
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def mx_ok(monkeypatch):
    monkeypatch.setattr(verify_mod, "lookup_mx", lambda d: ["mx.example.net"])


@pytest.mark.parametrize("vendor_status,expected", [("valid", "verified"), ("invalid", "invalid"), ("spamtrap", "invalid"),
                                                    ("abuse", "invalid"), ("do_not_mail", "invalid"), ("catch-all", "risky"),
                                                    ("unknown", "unverified")])
def test_zerobounce_mapping(monkeypatch, mx_ok, vendor_status, expected):
    monkeypatch.setattr(verify_mod.requests, "get", lambda *a, **k: StubResp({"status": vendor_status, "sub_status": ""}))
    out = EmailVerificationGate(vendor=ZeroBounceVendor("key")).verify("someone@acme.example")
    assert out.status == expected and out.is_deliverable is (expected == "verified")


@pytest.mark.parametrize("result,expected", [("ok", "verified"), ("invalid", "invalid"), ("disposable", "invalid"),
                                             ("catch_all", "risky"), ("unknown", "unverified"), ("error", "unverified")])
def test_millionverifier_mapping(monkeypatch, mx_ok, result, expected):
    monkeypatch.setattr(verify_mod.requests, "get", lambda *a, **k: StubResp({"result": result}))
    out = EmailVerificationGate(vendor=MillionVerifierVendor("key")).verify("someone@acme.example")
    assert out.status == expected


def test_a_configured_key_does_not_approve_everything(monkeypatch, mx_ok):
    """The old gate returned 'verified' for any address once a key existed, without calling the vendor."""
    monkeypatch.setenv("ZEROBOUNCE_API_KEY", "key-1234567890")
    calls = []
    monkeypatch.setattr(verify_mod.requests, "get", lambda *a, **k: calls.append(1) or StubResp({"status": "invalid"}))
    out = EmailVerificationGate().verify("ghost@acme.example")
    assert calls and out.status == "invalid" and not EmailVerificationGate().allows_send("ghost@acme.example")


@pytest.mark.parametrize("failure", ["timeout", "http500", "vendor_error", "garbage"])
def test_vendor_failures_fail_closed(monkeypatch, mx_ok, failure):
    def fake(*a, **k):
        if failure == "timeout":
            raise TimeoutError("slow")
        if failure == "http500":
            return StubResp({}, 500)
        if failure == "vendor_error":
            return StubResp({"error": "Invalid API key"})
        return StubResp({"unexpected": True})
    monkeypatch.setattr(verify_mod.requests, "get", fake)
    out = EmailVerificationGate(vendor=ZeroBounceVendor("k")).verify("a@acme.example")
    assert out.status == "unverified" and out.is_deliverable is False


def test_results_are_cached_and_failures_are_not(monkeypatch, mx_ok):
    calls = []
    monkeypatch.setattr(verify_mod.requests, "get", lambda *a, **k: calls.append(1) or StubResp({"status": "valid"}))
    gate = EmailVerificationGate(vendor=ZeroBounceVendor("k"))
    assert gate.verify("a@acme.example").status == "verified"
    again = gate.verify("a@acme.example")
    assert again.status == "verified" and "cached" in again.provider and len(calls) == 1
    monkeypatch.setattr(verify_mod.requests, "get", lambda *a, **k: StubResp({"status": "unknown"}))
    gate.verify("b@acme.example")
    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM email_verifications").fetchone()[0] == 1, "'unknown' must not be cached"


def test_cache_does_not_store_plain_email_addresses(monkeypatch, mx_ok):
    monkeypatch.setattr(verify_mod.requests, "get", lambda *a, **k: StubResp({"status": "valid"}))
    EmailVerificationGate(vendor=ZeroBounceVendor("k")).verify("secret.person@acme.example")
    with get_db() as db:
        blob = json.dumps([tuple(r) for r in db.execute("SELECT * FROM email_verifications")])
    assert "secret.person" not in blob


def test_no_vendor_means_nothing_is_verified(monkeypatch, mx_ok):
    for var in ("ZEROBOUNCE_API_KEY", "MILLIONVERIFIER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    out = EmailVerificationGate().verify("a@acme.example")
    assert out.status == "unverified" and "No email verifier configured" in out.reason


def test_dns_checks_come_first(monkeypatch):
    monkeypatch.setattr(verify_mod.requests, "get", lambda *a, **k: pytest.fail("vendor must not be billed for a dead domain"))
    gate = EmailVerificationGate(vendor=ZeroBounceVendor("k"))
    monkeypatch.setattr(verify_mod, "lookup_mx", lambda d: [])
    assert gate.verify("a@no-mx.example").status == "invalid"
    monkeypatch.setattr(verify_mod, "lookup_mx", lambda d: None)
    assert gate.verify("a@dns-down.example").status == "unverified"


# ================================================================== P1-5: multi-day sequences

def tuesday_10am():
    d = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    while d.weekday() != 1:
        d += timedelta(days=1)
    return d + timedelta(days=7)


def make_sequence(org=ORG, delays=(0, 3, 5)):
    return SequenceScheduler.create_sequence(org, "Site audit outreach", [
        {"subject": f"Step {i + 1} for {{company}}", "body": f"Hi {{first_name}}, this is step {i + 1} of the note about {{company}}.", "delay_days": d}
        for i, d in enumerate(delays)])


def test_three_step_sequence_runs_over_days(box, wf):
    l3()
    seq, t0 = make_sequence(), tuesday_10am()
    enr = SequenceScheduler.enroll(ORG, seq["id"], "dana@acme.example", "US", recipient_name="Dana Lee", company_name="Acme", start_at=t0)
    assert enr["next_run_at"] == t0.strftime("%Y-%m-%d %H:%M:%S")

    assert SequenceScheduler.run_due(t0, workflow=wf)[0]["outcome"] == "sent"
    assert SequenceScheduler.run_due(t0 + timedelta(days=1), workflow=wf) == [], "step 2 is not due yet"
    assert SequenceScheduler.run_due(t0, workflow=wf) == [], "running again must not double-send"
    e = SequenceScheduler.get_enrollment(ORG, enr["id"])
    assert e["current_step"] == 2 and e["status"] == "active"
    assert datetime.strptime(e["next_run_at"], "%Y-%m-%d %H:%M:%S") >= (t0 + timedelta(days=3)).replace(tzinfo=None)

    def due_time():
        e = SequenceScheduler.get_enrollment(ORG, enr["id"])
        return datetime.strptime(e["next_run_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) + timedelta(minutes=1)

    for _ in range(2):   # steps 2 and 3, each run exactly when it falls due (always inside a weekday window)
        assert SequenceScheduler.run_due(due_time(), workflow=wf)[0]["outcome"] == "sent"
    assert SequenceScheduler.get_enrollment(ORG, enr["id"])["status"] == "completed"
    assert [m.subject for m in wf.provider.sent] == ["Step 1 for Acme", "Step 2 for Acme", "Step 3 for Acme"]
    assert "Hi Dana," in wf.provider.sent[0].body_text


def test_a_reply_stops_the_rest_of_the_sequence(box, wf):
    l3()
    seq, t0 = make_sequence(), tuesday_10am()
    enr = SequenceScheduler.enroll(ORG, seq["id"], "dana@acme.example", "US", start_at=t0)
    SequenceScheduler.run_due(t0, workflow=wf)
    MailboxRegistry.record_event(ORG, "dana@acme.example", "replied")
    out = SequenceScheduler.run_due(t0 + timedelta(days=3, hours=1), workflow=wf)
    assert out[0]["outcome"] == "stopped_on_reply"
    e = SequenceScheduler.get_enrollment(ORG, enr["id"])
    assert e["status"] == "stopped" and "replied" in e["stop_reason"] and len(wf.provider.sent) == 1


def test_unsubscribe_mid_sequence_stops_it(box, wf):
    l3()
    seq, t0 = make_sequence(), tuesday_10am()
    enr = SequenceScheduler.enroll(ORG, seq["id"], "dana@acme.example", "US", start_at=t0)
    SequenceScheduler.run_due(t0, workflow=wf)
    KeyedSuppressionVault.suppress("dana@acme.example", org_id=ORG)
    assert SequenceScheduler.run_due(t0 + timedelta(days=3, hours=1), workflow=wf)[0]["outcome"] == "suppressed"
    assert SequenceScheduler.get_enrollment(ORG, enr["id"])["status"] == "stopped"


def test_default_policy_pauses_for_approval_then_resumes(box, wf):
    seq, t0 = make_sequence(), tuesday_10am()
    enr = SequenceScheduler.enroll(ORG, seq["id"], "dana@acme.example", "US", start_at=t0)
    out = SequenceScheduler.run_due(t0, workflow=wf)
    assert out[0]["outcome"] == "pending_approval" and wf.provider.sent == []
    assert SequenceScheduler.get_enrollment(ORG, enr["id"])["status"] == "awaiting_approval"
    assert SequenceScheduler.run_due(t0 + timedelta(days=30), workflow=wf) == [], "waiting for a human, not retrying"

    approval = [a for a in ApprovalRepository.list_pending(ORG) if a["subject_id"] == out[0]["draft_id"]][0]
    ApprovalRepository.decide(approval["id"], "approved", "founder", org_id=ORG)
    assert wf.send_approved_draft(ORG, out[0]["draft_id"]).status == "sent"
    SequenceScheduler.advance_after_send(ORG, enr["id"], now=t0)
    e = SequenceScheduler.get_enrollment(ORG, enr["id"])
    assert e["status"] == "active" and e["current_step"] == 2


def test_rejecting_a_draft_stops_the_enrollment(box, wf):
    seq, t0 = make_sequence(), tuesday_10am()
    enr = SequenceScheduler.enroll(ORG, seq["id"], "dana@acme.example", "US", start_at=t0)
    out = SequenceScheduler.run_due(t0, workflow=wf)
    approval = [a for a in ApprovalRepository.list_pending(ORG) if a["subject_id"] == out[0]["draft_id"]][0]
    ApprovalRepository.decide(approval["id"], "rejected", "founder", org_id=ORG)
    e = SequenceScheduler.get_enrollment(ORG, enr["id"])
    assert e["status"] == "stopped" and "rejected" in e["stop_reason"]


def test_nothing_is_sent_outside_the_weekday_window(box, wf):
    l3()
    seq = make_sequence()
    saturday = tuesday_10am() + timedelta(days=4)
    assert saturday.weekday() == 5
    SequenceScheduler.enroll(ORG, seq["id"], "dana@acme.example", "US", start_at=saturday)
    with get_db() as db:
        db.execute("UPDATE sequence_enrollments SET next_run_at = ?", (saturday.strftime("%Y-%m-%d %H:%M:%S"),))
        db.commit()
    out = SequenceScheduler.run_due(saturday, workflow=wf)
    assert out[0]["outcome"] == "deferred_outside_send_window" and wf.provider.sent == []
    assert next_send_time(saturday).weekday() == 0 and next_send_time(saturday).hour == 8
    assert next_send_time(tuesday_10am().replace(hour=22)).day == (tuesday_10am() + timedelta(days=1)).day


def test_transient_failures_retry_then_give_up(box):
    wf = OutreachSequenceWorkflow(provider=FakeProvider(fail=True), verification_gate=FakeGate())
    l3()
    seq, t0 = make_sequence(), tuesday_10am()
    enr = SequenceScheduler.enroll(ORG, seq["id"], "dana@acme.example", "US", start_at=t0)
    now = t0
    for attempt in range(1, 4):
        out = SequenceScheduler.run_due(now, workflow=wf)
        assert out and out[0]["outcome"] == "failed"
        e = SequenceScheduler.get_enrollment(ORG, enr["id"])
        now = datetime.strptime(e["next_run_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) + timedelta(minutes=1)
    assert e["status"] == "stopped" and "gave up" in e["stop_reason"] and e["attempts"] == 3


def test_unknown_placeholders_never_reach_a_prospect(box, wf):
    l3()
    seq = SequenceScheduler.create_sequence(ORG, "Bad template", [{"subject": "Hello {first_name}", "body": "Hi {first_name}, about {mystery_var} today.", "delay_days": 0}])
    t0 = tuesday_10am()
    enr = SequenceScheduler.enroll(ORG, seq["id"], "dana@acme.example", "US", recipient_name="Dana", start_at=t0)
    assert SequenceScheduler.run_due(t0, workflow=wf)[0]["outcome"] == "stopped"
    assert wf.provider.sent == [] and "placeholder" in SequenceScheduler.get_enrollment(ORG, enr["id"])["stop_reason"]


def test_sequence_and_enrollment_validation():
    for bad in ([], [{"subject": "", "body": "x"}], [{"subject": "s", "body": "w " * 400}], [{"subject": "s", "body": "b", "delay_days": 99}]):
        with pytest.raises(ValueError):
            SequenceScheduler.create_sequence(ORG, "x", bad)
    seq = make_sequence()
    with pytest.raises(ValueError):
        SequenceScheduler.enroll(ORG, seq["id"], "a@acme.example", "")                       # country is mandatory
    SequenceScheduler.enroll(ORG, seq["id"], "a@acme.example", "US")
    with pytest.raises(ValueError):
        SequenceScheduler.enroll(ORG, seq["id"], "A@acme.example", "US")                     # no double enrolment
    with pytest.raises(LookupError):
        SequenceScheduler.enroll("other_org", seq["id"], "z@acme.example", "US")             # another tenant's sequence


# ================================================================== API surface

@pytest.fixture
def api_box(monkeypatch, box):
    """API-level flow with the REAL SmtpProvider and verifier gate, stubbing only the wire."""
    sent, server_logins = [], []

    class FakeServer:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context=None): pass
        def login(self, user, pw): server_logins.append((user, pw))
        def sendmail(self, frm, to, body): sent.append((frm, to, body))

    monkeypatch.setattr(smtp_mod, "open_smtp", lambda creds, timeout=15: FakeServer())
    monkeypatch.setattr(verify_mod, "lookup_mx", lambda d: ["mx.example.net"])
    monkeypatch.setattr(verify_mod.requests, "get", lambda *a, **k: StubResp({"status": "valid"}))
    monkeypatch.setenv("ZEROBOUNCE_API_KEY", "key-1234567890")
    return sent, server_logins


def test_full_api_flow_approval_then_send(client, make_key, api_box):
    sent, logins = api_box
    lead = make_key("growth_lead", org_id=ORG)
    body = {"recipient_email": "dana@acme.example", "country_code": "US", "subject": "A quick note",
            "body": "Hi Dana, we found two issues on your site that are worth a look.", "step_number": 1}
    res = client.post("/api/outbound/sequence/step", headers=lead, json=body).json()
    assert res["status"] == "pending_approval" and sent == []

    pending = client.get("/api/approvals/pending", headers=lead).json()
    item = [p for p in pending if p["subject_type"] == "outbound_draft"][0]
    assert item["draft_recipient"] == "dana@acme.example"
    assert client.post(f"/api/outbound/drafts/{res['draft_id']}/send", headers=lead).json()["status"] == "blocked_by_policy"
    assert client.post(f"/api/approvals/{item['id']}/decide", headers=lead, json={"decision": "approved", "reason": "ok"}).status_code == 200
    done = client.post(f"/api/outbound/drafts/{res['draft_id']}/send", headers=lead).json()
    assert done["status"] == "sent" and sent and sent[0][1] == ["dana@acme.example"]
    assert logins == [("sender@agency.example", "s3cret-pass")]


def test_api_requires_country_and_proper_roles(client, make_key):
    lead = make_key("growth_lead", org_id=ORG)
    ok = {"recipient_email": "a@acme.example", "subject": "s", "body": "Long enough body text here.", "step_number": 1}
    assert client.post("/api/outbound/sequence/step", headers=lead, json=ok).status_code == 422          # no country
    assert client.post("/api/outbound/sequence/step", headers=make_key("sdr_rep", org_id=ORG),
                       json={**ok, "country_code": "US"}).status_code == 403
    assert client.post("/api/outbound/sequence/step", headers=make_key("auditor", org_id=ORG),
                       json={**ok, "country_code": "US"}).status_code == 403


def test_drafts_and_sequences_are_tenant_scoped(client, make_key, box, api_box):
    a, b = make_key("growth_lead", org_id=ORG), make_key("growth_lead", org_id="org_other")
    r = client.post("/api/outbound/sequence/step", headers=a, json={
        "recipient_email": "dana@acme.example", "country_code": "US", "subject": "s", "body": "A body that is long enough."}).json()
    assert client.get("/api/outbound/drafts", headers=b).json() == []
    assert client.post(f"/api/outbound/drafts/{r['draft_id']}/send", headers=b).status_code == 404
    seq = client.post("/api/sequences", headers=a, json={"name": "S", "steps": [{"subject": "s", "body": "Body text is here.", "delay_days": 0}]}).json()
    assert client.get("/api/sequences", headers=b).json() == []
    assert client.post(f"/api/sequences/{seq['id']}/enroll", headers=b, json={"recipient_email": "x@acme.example", "country_code": "US"}).status_code == 404


def test_sequence_api_roundtrip(client, make_key, box):
    lead = make_key("growth_lead", org_id=ORG)
    seq = client.post("/api/sequences", headers=lead, json={"name": "S", "steps": [
        {"subject": "Hi {first_name}", "body": "Body for {company} is long enough.", "delay_days": 0}]})
    assert seq.status_code == 200
    enr = client.post(f"/api/sequences/{seq.json()['id']}/enroll", headers=lead, json={
        "recipient_email": "dana@acme.example", "country_code": "us", "recipient_name": "Dana Lee", "company_name": "Acme"})
    assert enr.status_code == 200 and enr.json()["country_code"] == "US"
    assert client.post(f"/api/sequences/{seq.json()['id']}/enroll", headers=lead, json={
        "recipient_email": "dana@acme.example", "country_code": "US"}).status_code == 400
    assert len(client.get("/api/sequences/enrollments", headers=lead).json()) == 1
    assert client.post(f"/api/sequences/enrollments/{enr.json()['id']}/stop", headers=lead).status_code == 200
    assert client.post(f"/api/sequences/enrollments/{enr.json()['id']}/stop", headers=lead).status_code == 404


# ================================================================== P1-8: per-tenant webhook secrets

def _signed_for(secret, payload, org=None, ts=None):
    import time as _t
    from security.webhook_verifier import WebhookSecurity
    body = json.dumps(payload).encode()
    ts = ts or int(_t.time())
    headers = {"X-AgencyBD-Timestamp": str(ts), "X-AgencyBD-Signature": WebhookSecurity.sign_payload(body, secret=secret, timestamp=ts),
               "Content-Type": "application/json"}
    if org:
        headers["X-AgencyBD-Org"] = org
    return body, headers


REPLY = {"from": "prospect@acme.example", "to": "sdr@agency.example", "subject": "Re: hi", "text": "Sounds interesting, let us talk Tuesday."}


def test_each_tenant_gets_its_own_secret_shown_once(client, make_key):
    a = client.post("/api/security/webhook_secret", headers=make_key("growth_lead", org_id="org_a")).json()
    b = client.post("/api/security/webhook_secret", headers=make_key("growth_lead", org_id="org_b")).json()
    assert a["webhook_secret"] != b["webhook_secret"] and len(a["webhook_secret"]) >= 32
    with get_db() as db:
        stored = [r[0] for r in db.execute("SELECT secret_enc FROM webhook_secrets")]
    assert a["webhook_secret"] not in " ".join(stored), "encrypted at rest"
    assert client.post("/api/security/webhook_secret", headers=make_key("auditor", org_id="org_a")).status_code == 403


def test_webhooks_are_verified_with_the_sending_tenants_secret_and_attributed_to_it(client, make_key):
    secret_a = client.post("/api/security/webhook_secret", headers=make_key("growth_lead", org_id="org_a")).json()["webhook_secret"]
    secret_b = client.post("/api/security/webhook_secret", headers=make_key("growth_lead", org_id="org_b")).json()["webhook_secret"]
    body, headers = _signed_for(secret_a, REPLY, org="org_a")
    res = client.post("/api/webhooks/inbound", content=body, headers=headers)
    assert res.status_code == 200 and res.json()["org_id"] == "org_a"
    # tenant B's secret cannot speak for tenant A, and vice versa
    body, headers = _signed_for(secret_b, REPLY, org="org_a")
    assert client.post("/api/webhooks/inbound", content=body, headers=headers).status_code == 401
    # an org with no secret is indistinguishable from a bad signature
    body, headers = _signed_for("x" * 40, REPLY, org="org_unknown")
    assert client.post("/api/webhooks/inbound", content=body, headers=headers).status_code == 401
    # rotating invalidates the old secret
    client.post("/api/security/webhook_secret", headers=make_key("growth_lead", org_id="org_a"))
    body, headers = _signed_for(secret_a, REPLY, org="org_a")
    assert client.post("/api/webhooks/inbound", content=body, headers=headers).status_code == 401


def test_per_tenant_webhooks_still_enforce_replay_protection(client, make_key):
    import time as _t
    secret = client.post("/api/security/webhook_secret", headers=make_key("growth_lead", org_id="org_a")).json()["webhook_secret"]
    body, headers = _signed_for(secret, REPLY, org="org_a", ts=int(_t.time()) - 3600)
    assert client.post("/api/webhooks/inbound", content=body, headers=headers).status_code == 401


# ================================================================== system readiness

def test_system_status_reports_what_is_missing_and_never_leaks_secrets(client, make_key, monkeypatch):
    for v in ("ANTHROPIC_API_KEY", "OLLAMA_HOST", "ZEROBOUNCE_API_KEY", "MILLIONVERIFIER_API_KEY", "PAGESPEED_API_KEY", "GOOGLE_PLACES_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SAM_GOV_API_KEY", "super-secret-sam-key-12345")
    h = make_key("growth_lead", org_id="org_sys")
    out = client.get("/api/system/status", headers=h).json()
    by = {c["key"]: c for c in out["checks"]}
    assert by["llm"]["status"] == "missing" and "ANTHROPIC_API_KEY" in by["llm"]["fix"]
    assert by["verifier"]["status"] == "missing" and by["mailbox"]["status"] == "missing"
    assert by["pagespeed"]["status"] == "optional_missing" and by["sam_gov"]["status"] == "ok"
    assert out["ready_to_send_email"] is False and out["required_missing"] >= 4
    assert "super-secret-sam-key" not in json.dumps(out)
    # configuring things flips the right checks
    monkeypatch.setenv("ZEROBOUNCE_API_KEY", "zb-key-123456")
    monkeypatch.setattr(SafeFetcher, "resolve_and_validate_hostname", staticmethod(lambda host: "93.184.216.34"))
    monkeypatch.setattr(registry, "lookup_mx", lambda d: ["mx.example.net"])
    MailboxRegistry.register_mailbox("org_sys", "s@agency.example", smtp_host="smtp.mailhost.test", smtp_username="u", smtp_password="p")
    PortfolioLibrary_add("org_sys")
    monkeypatch.setenv("AGENCYBD_SENDER_ADDRESS", "1 Main St, Austin TX")
    monkeypatch.setenv("AGENCYBD_PUBLIC_BASE_URL", "https://agency.example")
    out = client.get("/api/system/status", headers=h).json()
    by = {c["key"]: c for c in out["checks"]}
    assert by["portfolio"]["status"] == "ok" and by["mailbox"]["status"] == "ok" and by["verifier"]["status"] == "ok"
    assert out["ready_to_send_email"] is True
    other = {c["key"]: c for c in client.get("/api/system/status", headers=make_key("growth_lead", org_id="org_sys2")).json()["checks"]}
    assert other["portfolio"]["status"] == "missing" and other["mailbox"]["status"] == "missing", "readiness is per workspace"


def PortfolioLibrary_add(org):
    from portfolio.library import PortfolioLibrary
    PortfolioLibrary.add_asset(org, "Case", "Rebuilt a booking platform for a logistics client and cut page load from 4.1 to 1.2 seconds after launch.")


def test_roles_endpoint_and_dns_endpoints(client, make_key, monkeypatch):
    h = make_key("growth_lead", org_id="org_sys")
    roles = client.get("/api/security/roles", headers=h).json()
    assert roles["roles"]["auditor"] and roles["you"]["role"] == "growth_lead" and "apikeys:manage" not in roles["roles"]["growth_lead"]
    rec = client.post("/api/outbound/dns/records", headers=h, json={"domain": "send.example.com"}).json()
    assert rec["dkim"]["value"] is None and "p=none" in rec["dmarc"]["value"]
    assert client.post("/api/outbound/dns/records", headers=h, json={"domain": "-x"}).status_code == 400
    assert client.post("/api/outbound/dns/audit", headers=make_key("auditor", org_id="org_sys"), json={"domain": "send.example.com"}).status_code == 403
    assert client.post("/api/outbound/dns/audit", headers=h, json={"domain": "send.example.com"}).json()["spf_active"] is None   # DNS unavailable in tests


# ================================================================== kill switch (server side)

def test_kill_switch_blocks_manual_sends_and_pauses_the_scheduler_without_losing_state(box, wf):
    from workflows import controls
    l3()
    seq, t0 = make_sequence(), tuesday_10am()
    enr = SequenceScheduler.enroll(ORG, seq["id"], "dana@acme.example", "US", start_at=t0)

    controls.set_halted(ORG, True, "founder", "bounce spike")
    assert wf.execute_step(ORG, "x@acme.example", step(), country_code="US").status == "halted"
    assert SequenceScheduler.run_due(t0, workflow=wf)[0]["outcome"] == "halted"
    assert wf.provider.sent == []
    assert SequenceScheduler.get_enrollment(ORG, enr["id"])["status"] == "active"      # not stopped, not advanced

    controls.set_halted(ORG, False, "founder")                                          # releasing resumes it
    assert SequenceScheduler.run_due(t0, workflow=wf)[0]["outcome"] == "sent"


def test_kill_switch_is_per_tenant_and_permissioned(client, make_key):
    from workflows import controls
    growth = make_key("growth_lead", "org_a")
    assert client.post("/api/controls/outbound", json={"halted": True}).status_code == 401
    assert client.post("/api/controls/outbound", headers=make_key("sdr_rep", "org_a"), json={"halted": True}).status_code == 403
    res = client.post("/api/controls/outbound", headers=growth, json={"halted": True, "reason": "test"})
    assert res.status_code == 200 and res.json()["halted"] is True
    assert controls.is_halted("org_a") and not controls.is_halted("org_b")
    assert client.get("/api/controls/outbound", headers=make_key("auditor", "org_b")).json()["halted"] is False
    controls.set_halted("org_a", False, "cleanup")
