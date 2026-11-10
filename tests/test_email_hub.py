"""
Comprehensive QA and Engineering Test Suite for Email Sending Hub & Outbound Command Center.
Verifies RFC 5322 syntax validation, DNS MX verification, disposable/spamtrap filtering,
killswitch enforcement, content guards, direct dispatch, and approval queue lifecycle.
"""

import pytest
from database.db import get_db
from workflows import controls
from outbound.providers.registry import MailboxRegistry


def test_email_verify_invalid_syntax(client, admin_headers):
    """Refuses malformed, empty or broken syntax."""
    res = client.post("/api/email/verify", json={"email": "bad@@format"}, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "invalid"
    assert data["is_deliverable"] is False
    assert data["syntax_valid"] is False


def test_email_verify_disposable_domain(client, admin_headers):
    """Blocks throwaway and temporary disposable burner domains."""
    res = client.post("/api/email/verify", json={"email": "lead@mailinator.com"}, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "disposable"
    assert data["is_deliverable"] is False
    assert data["is_disposable"] is True


def test_email_verify_spamtrap_prefix(client, admin_headers):
    """Flags honeypot and abuse trap prefixes."""
    res = client.post("/api/email/verify", json={"email": "abuse@company.com"}, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "spamtrap"
    assert data["is_deliverable"] is False
    assert data["is_spamtrap"] is True


@pytest.mark.network
def test_email_verify_valid_domain_with_mx(client, admin_headers):
    """Positively validates deliverable email with real MX records when network is enabled."""
    res = client.post("/api/email/verify", json={"email": "contact@google.com"}, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "verified"
    assert data["is_deliverable"] is True
    assert data["has_mx"] is True
    assert len(data["mx_records"]) > 0


def test_email_send_blocked_when_halted(client, admin_headers):
    """Master killswitch halts all email sends."""
    controls.set_halted("org_default", True, "Emergency halt test")
    try:
        res = client.post(
            "/api/email/send",
            json={
                "to_email": "contact@google.com",
                "subject": "Engineering partnership inquiry",
                "body": "Hello team, reaching out regarding our recent digital architecture benchmark.",
            },
            headers=admin_headers,
        )
        assert res.status_code == 403
        assert "halted" in res.json()["detail"].lower()
    finally:
        controls.set_halted("org_default", False, "")


def test_email_send_content_guard_blocks_threats(client, admin_headers):
    """Content guard blocks aggressive fear-inducing or threatening language."""
    res = client.post(
        "/api/email/send",
        json={
            "to_email": "contact@google.com",
            "subject": "URGENT: Your site is hacked and malware found",
            "body": "You were hacked by attackers and your customer data was stolen. Fix this within 24 hours.",
        },
        headers=admin_headers,
    )
    assert res.status_code == 400
    assert "alarming security language" in res.json()["detail"].lower()


def test_email_send_saves_as_draft(client, admin_headers):
    """as_draft=True queues email into outbound_drafts for review."""
    res = client.post(
        "/api/email/send",
        json={
            "to_email": "contact@google.com",
            "subject": "Technical Teardown for Review",
            "body": "Hi there, we reviewed your architecture and prepared a brief review.",
            "as_draft": True,
        },
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["status"] == "pending_approval"
    draft_id = data["draft_id"]

    # Verify draft in database
    with get_db() as db:
        row = db.execute("SELECT * FROM outbound_drafts WHERE id = ?", (draft_id,)).fetchone()
        assert row is not None
        assert row["recipient_email"] == "contact@google.com"
        assert row["status"] == "pending_approval"


@pytest.mark.network
def test_email_direct_dispatch_and_history(client, admin_headers):
    """Direct email send dispatches, records event in outreach_events, and updates metrics."""
    # Ensure a mailbox exists
    MailboxRegistry.register_mailbox(
        org_id="org_default",
        email="alex@apexcore.ai",
        display_name="Alex Mercer",
        daily_cap=50,
        skip_warmup=True,
    )

    with get_db() as db:
        initial_events = db.execute("SELECT COUNT(*) FROM outreach_events WHERE org_id = 'org_default'").fetchone()[0]

    res = client.post(
        "/api/email/send",
        json={
            "to_email": "contact@google.com",
            "subject": "Performance Benchmarks Teardown",
            "body": "Hi Alex, we compiled a complete performance overview for your engineering team.",
            "recipient_name": "Alex Mercer",
            "company_name": "Google LLC",
            "country_code": "US",
        },
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["status"] == "sent"
    assert data["recipient"] == "contact@google.com"
    assert "message_id" in data

    # Verify event logged in outreach_events
    with get_db() as db:
        new_events = db.execute("SELECT COUNT(*) FROM outreach_events WHERE org_id = 'org_default'").fetchone()[0]
        assert new_events == initial_events + 1

    # Verify endpoint history returns it
    hist_res = client.get("/api/email/history?limit=10", headers=admin_headers)
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert len(hist) > 0
    assert any(h["recipient_email"] == "contact@google.com" for h in hist)


def test_email_overview_and_templates(client, admin_headers):
    """Overview returns fleet and queue KPIs; templates return proven cold copies."""
    ov_res = client.get("/api/email/overview", headers=admin_headers)
    assert ov_res.status_code == 200
    ov = ov_res.json()
    assert "fleet" in ov
    assert "metrics_7d" in ov
    assert "queue" in ov

    tmpl_res = client.get("/api/email/templates", headers=admin_headers)
    assert tmpl_res.status_code == 200
    tmpls = tmpl_res.json()
    assert len(tmpls) >= 4
    assert any(t["id"] == "audit_teardown" for t in tmpls)
