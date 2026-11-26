"""
Tests for Phase 1-5 Enterprise Upgrades:
1. Two-Way Master Inbox ingest & sequence auto-pause
2. Scheduled Autopilot, Round-Robin Assignment & Risk-Tiered Autonomy Gate
3. Social Intent Radar connector
4. Sales Navigator Companion lead capture & Account IQ
5. Interactive Proposals & Smart Links view/e-sign telemetry
"""

import pytest
from fastapi.testclient import TestClient

from api import app
from database.db import get_db, init_db
from database.models import LeadRepository
from orchestrator.schedule_runner import (
    assign_round_robin,
    create_schedule,
    evaluate_tier_a_auto_approve,
    list_schedules,
    toggle_schedule,
)
from security.auth import SecurityService


@pytest.fixture(autouse=True)
def _db_ready():
    init_db()


def _headers(role: str = "super_admin", org_id: str = "org_ent_test") -> dict:
    tok = SecurityService.create_jwt_token(user_id=f"test_{role}", role=role, org_id=org_id)
    return {"Authorization": f"Bearer {tok}"}


def test_master_inbox_ingest_and_sequence_auto_pause():
    client = TestClient(app)
    org = "org_ent_inbox"
    lead = LeadRepository.create_or_get_lead("Acme Inbox Co", "acmeinbox.example", org_id=org)

    with get_db() as conn:
        seq_id = conn.execute(
            "INSERT INTO sequences (org_id, name, steps_json) VALUES (?, ?, ?)",
            (org, "Seq1", '[{"subject":"hi","body":"hello","delay_days":0}]'),
        ).lastrowid
        conn.execute(
            """
            INSERT INTO sequence_enrollments (org_id, sequence_id, lead_id, recipient_email, country_code, next_run_at, status)
            VALUES (?, ?, ?, 'ceo@acmeinbox.example', 'US', CURRENT_TIMESTAMP, 'active')
            """,
            (org, seq_id, lead["id"]),
        )
        conn.commit()

    res = client.post(
        "/api/email/inbox/ingest",
        headers=_headers("growth_lead", org),
        json={
            "sender_email": "ceo@acmeinbox.example",
            "recipient_email": "outreach@agencybd.enterprise",
            "subject": "Re: Audit",
            "body": "Sounds interesting, can we talk Tuesday?",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ingested"
    assert body["lead_id"] == lead["id"]

    # Sequence must be auto-paused ('replied')
    with get_db() as conn:
        st = conn.execute(
            "SELECT status FROM sequence_enrollments WHERE org_id = ? AND recipient_email = 'ceo@acmeinbox.example'",
            (org,),
        ).fetchone()["status"]
        assert st == "replied"

    inbox_res = client.get("/api/email/inbox", headers=_headers("growth_lead", org))
    assert inbox_res.status_code == 200
    assert len(inbox_res.json()["messages"]) >= 1


def test_scheduled_autopilot_and_tier_a_gate():
    org = "org_ent_sched"
    s = create_schedule(org_id=org, name="Morning React Hunt", channel="hiring", query="react", cadence_hours=12)
    assert s["enabled"] == 1
    assert any(x["id"] == s["id"] for x in list_schedules(org))

    toggled = toggle_schedule(org, s["id"], False)
    assert toggled["enabled"] == 0

    lead = LeadRepository.create_or_get_lead("RR Co", "rrco.example", org_id=org)
    owner = assign_round_robin(org, lead["id"])
    assert owner in ("sdr_rep", "growth_lead")

    good = evaluate_tier_a_auto_approve(
        subject="Quick question about your site",
        body="Hi there, I noticed your site lacks a meta description and has slow LCP.",
        country_code="US",
        mx_verified=True,
        fit_score=0.85,
    )
    assert good["eligible"] is True

    bad = evaluate_tier_a_auto_approve(
        subject="Quick question",
        body="Hi there, checking in.",
        country_code="US",
        mx_verified=False,
        fit_score=0.60,
    )
    assert bad["eligible"] is False and len(bad["reasons"]) >= 2


def test_account_iq_proposals_and_smart_links():
    client = TestClient(app)
    org = "org_ent_prop"
    lead = LeadRepository.create_or_get_lead("SmartLink Co", "smartlink.example", org_id=org)

    iq = client.get(f"/api/clients/{lead['id']}/account-iq", headers=_headers("growth_lead", org))
    assert iq.status_code == 200
    assert iq.json()["company_name"] == "SmartLink Co"

    prop_res = client.post(
        "/api/proposals/create",
        headers=_headers("growth_lead", org),
        json={
            "lead_id": lead["id"],
            "title": "Modernization Scope",
            "summary": "Fix performance & security.",
            "scope_items": ["Fix TLS", "Improve LCP"],
            "price_amount": 4500,
        },
    )
    assert prop_res.status_code == 200
    token = prop_res.json()["proposal"]["token"]

    # Public view logs Smart Link telemetry
    view_res = client.get(f"/p/{token}")
    assert view_res.status_code == 200 and "Modernization Scope" in view_res.text

    # Public e-sign acceptance marks proposal accepted & lead won
    accept_res = client.post(f"/p/{token}/accept", data={"signed_by": "Jane CEO"})
    assert accept_res.status_code == 200 and "Proposal Accepted" in accept_res.text

    list_res = client.get(f"/api/proposals/lead/{lead['id']}", headers=_headers("growth_lead", org))
    assert list_res.status_code == 200
    assert list_res.json()["proposals"][0]["status"] == "accepted"
    assert list_res.json()["smart_link_views"][0]["view_count"] >= 1


def test_sales_nav_companion_capture():
    client = TestClient(app)
    org = "org_ent_sn"
    res = client.post(
        "/api/v1/browser/session/capture-leads",
        headers=_headers("growth_lead", org),
        json={
            "leads": [
                {
                    "company_name": "NavCapture Corp",
                    "domain": "navcapture.example",
                    "contact_name": "Sam Founder",
                    "contact_title": "CEO",
                    "linkedin_url": "https://www.linkedin.com/in/sam-founder",
                }
            ]
        },
    )
    assert res.status_code == 200
    assert res.json()["captured_count"] == 1


def test_email_hub_ai_writer_templates_crud_and_bulk_send():
    client = TestClient(app)
    org = "org_ent_email_ai"
    sdr_headers = _headers("sdr_rep", org)

    # 1. AI Writer offline structured fallback works without paid keys
    ai_res = client.post(
        "/api/email/ai-draft",
        headers=sdr_headers,
        json={
            "provider": "auto",
            "recipient_name": "Sarah Jenkins",
            "company_name": "Acme Health",
            "goal": "15-min performance teardown",
            "tone": "consultative",
        },
    )
    assert ai_res.status_code == 200
    assert "Sarah" in ai_res.json()["body"]
    assert ai_res.json()["provider_used"] == "structured_fallback"

    # 2. Custom Templates CRUD
    c_res = client.post(
        "/api/email/templates",
        headers=sdr_headers,
        json={"name": "Custom Pitch", "subject": "Hello {{company}}", "body": "Hi {{first_name}}, quick note."},
    )
    assert c_res.status_code == 200
    db_id = c_res.json()["db_id"]
    list_res = client.get("/api/email/templates", headers=sdr_headers)
    assert any(t["name"] == "Custom Pitch" for t in list_res.json())
    d_res = client.delete(f"/api/email/templates/{db_id}", headers=sdr_headers)
    assert d_res.status_code == 200

    # 3. Bulk send queues drafts with merge tags & spintax
    b_res = client.post(
        "/api/email/bulk-send",
        headers=sdr_headers,
        json={
            "recipients": [
                {"email": "a@example.com", "name": "Alice Smith", "company": "AlphaCo"},
                {"email": "bad-email", "name": "Bad", "company": "None"},
            ],
            "subject": "{Hi|Hello} {{company}}",
            "body": "Hey {{first_name}}, let's chat.",
            "as_draft": True,
        },
    )
    assert b_res.status_code == 200
    assert b_res.json()["processed"] == 1
    assert len(b_res.json()["skipped"]) == 1
