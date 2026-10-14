"""
Comprehensive Tests for Phase 4 & Phase 5:
- Outbound Sending Providers (SMTP, Smartlead)
- Mailbox Registry & Load Balancer
- Fail-Closed Email Verification Gate
- Compliance & Jurisdiction Engine
- Keyed Cryptographic Suppression Vault
- Sequence Cadence Workflow & Stop-on-Reply Guard
- Reply Agent Objection & Unsubscribe Triage
- Enterprise Autonomy Policy Engine
- Strategic Learning Loop & A/B Reports
- FastAPI REST Endpoints for Outbound & Governance
"""

import pytest
from fastapi.testclient import TestClient

from api import app
from outbound.providers.smtp import SmtpProvider
from outbound.providers.smartlead import SmartleadProvider
from outbound.providers.registry import MailboxRegistry
from outbound.providers.base import OutboundMessage
from outbound.verify import EmailVerificationGate
from compliance.country_policy import CountryComplianceEngine
from compliance.footer import ComplianceFooterBuilder
from compliance.suppression import KeyedSuppressionVault
from workflows.sequence import OutreachSequenceWorkflow, SequenceStep
from agents.reply_agent import ReplyAgent
from policy.engine import PolicyEngine
from analytics.learning_loop import LearningLoopEngine

def test_mailbox_registry(monkeypatch):
    import outbound.providers.registry as reg
    org = "test_mb_org"
    mx = {"agency.com": ["mx.agency.com"], "client-google.com": ["aspmx.l.google.com"],
          "enterprise-outlook.com": ["corp-com.mail.protection.outlook.com"]}
    monkeypatch.setattr(reg, "lookup_mx", lambda d: mx.get(d, ["mail.other.net"]))
    mb1 = MailboxRegistry.register_mailbox(org_id=org, email="outbound1@agency.com", display_name="Rep 1", daily_cap=35)
    assert mb1["email"] == "outbound1@agency.com" and mb1["daily_cap"] == 35
    # A fresh mailbox is capped by the organic ramp-up, not its configured cap
    assert mb1["effective_daily_cap"] == 5

    monkeypatch.setattr(reg, "lookup_mx", lambda d: ["aspmx.l.google.com"] if d == "agency.com" else ["x.protection.outlook.com"])
    g = MailboxRegistry.register_mailbox(org_id=org, email="g@agency.com", daily_cap=35, skip_warmup=True)
    monkeypatch.setattr(reg, "lookup_mx", lambda d: mx.get(d, ["x.protection.outlook.com"]))
    m = MailboxRegistry.register_mailbox(org_id=org, email="m@other-ms.com", daily_cap=35, skip_warmup=True)
    assert g["esp"] == "google" and m["esp"] == "microsoft"

    boxes = MailboxRegistry.list_mailboxes(org)
    assert len(boxes) >= 3

    # ESP matching uses the recipient's REAL MX, not words in the domain name
    monkeypatch.setattr(reg, "lookup_mx", lambda d: mx.get(d, ["mail.other.net"]))
    assert MailboxRegistry.select_best_mailbox(org, recipient_domain="client-google.com")["esp"] == "google"
    assert MailboxRegistry.select_best_mailbox(org, recipient_domain="enterprise-outlook.com")["esp"] == "microsoft"

    # Record send and event
    MailboxRegistry.record_send(org, mb1["id"], "lead@test.com", message_id="msg-101")
    updated_mb1 = MailboxRegistry.get_mailbox(mb1["id"])
    assert updated_mb1["sent_today"] >= 1

    # Reset daily caps
    reset_count = MailboxRegistry.reset_daily_caps(org)
    assert reset_count >= 1

def test_email_verification_gate(monkeypatch):
    import outbound.verify as ov
    monkeypatch.setattr(ov, "lookup_mx", lambda d: ["mx.example.net"])
    gate = EmailVerificationGate()

    # 1. Invalid syntax
    res1 = gate.verify("not-valid-email")
    assert res1.status == "invalid"
    assert gate.allows_send("not-valid-email") is False

    # 2. Spam trap / role
    res2 = gate.verify("abuse@domain.com")
    assert res2.status == "spamtrap"
    assert gate.allows_send("abuse@domain.com") is False

    # 3. Disposable domain
    res3 = gate.verify("temp@mailinator.com")
    assert res3.status == "disposable"
    assert gate.allows_send("temp@mailinator.com") is False

    # 4. A well-formed address with no verifier configured fails closed
    res4 = gate.verify("founder@resend.com")
    assert res4.status == "unverified"
    assert gate.allows_send("founder@resend.com") is False

def test_compliance_and_jurisdiction():
    # 1. Country policy
    us_decision = CountryComplianceEngine.evaluate("US")
    assert us_decision.allowed is True
    assert us_decision.requires_lia is False

    gb_decision = CountryComplianceEngine.evaluate("GB")
    assert gb_decision.allowed is True
    assert gb_decision.requires_lia is True

    ca_decision = CountryComplianceEngine.evaluate("CA")
    assert ca_decision.allowed is False
    assert "CASL" in ca_decision.reason

    de_decision = CountryComplianceEngine.evaluate("DE")
    assert de_decision.allowed is False

    # 2. Compliance footer
    plain, html, headers = ComplianceFooterBuilder.build_footer(
        recipient_email="target@company.co",
        org_id="test_org",
        include_lia=True
    )
    assert "List-Unsubscribe" in headers
    assert "One-Click" in headers["List-Unsubscribe-Post"]
    assert "unsubscribe" in plain
    assert "GDPR" in html

    # 3. Keyed suppression vault
    email_to_block = "optout-user@nowhere.com"
    assert KeyedSuppressionVault.is_suppressed(email_to_block) is False

    KeyedSuppressionVault.suppress(email_to_block, reason="user_request", org_id="test_org")
    assert KeyedSuppressionVault.is_suppressed(email_to_block) is True

def test_reply_agent_triage(monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings.agency, "booking_link", "https://cal.com/me/intro")
    agent = ReplyAgent()
    org = "reply_test_org"

    # 1. Unsubscribe triage
    res_unsub = agent.handle_inbound_reply(
        raw_body="Please unsubscribe me and stop emailing.",
        sender_email="prospect-stop@biz.com",
        org_id=org
    )
    assert res_unsub["action"] == "auto_suppressed"
    assert KeyedSuppressionVault.is_suppressed("prospect-stop@biz.com") is True

    # 2. Objection triage
    res_obj = agent.handle_inbound_reply(
        raw_body="Your pricing is way too high for our budget right now.",
        sender_email="prospect-budget@biz.com",
        org_id=org
    )
    assert res_obj["classification"] == "objection"
    assert res_obj["draft_response"] is not None

    # 3. Interested triage
    res_int = agent.handle_inbound_reply(
        raw_body="Sounds interesting, please send more info or a calendar link.",
        sender_email="prospect-interested@biz.com",
        org_id=org
    )
    assert res_int["classification"] == "interested"
    assert "cal.com/me/intro" in res_int["draft_response"]

def test_policy_engine():
    org = "policy_test_org"

    # 1. Hard invariant: marketplace submission is NEVER auto
    dec_upwork = PolicyEngine.evaluate(org, "marketplace_submit", {"platform": "upwork"})
    assert dec_upwork.autonomy_level == "NEVER"
    assert dec_upwork.requires_human_approval is True

    # 2. Hard invariant: LinkedIn actions are NEVER auto
    dec_li = PolicyEngine.evaluate(org, "linkedin_action", {})
    assert dec_li.autonomy_level == "NEVER"

    # 3. Unverified email is blocked
    dec_unver = PolicyEngine.evaluate(org, "outbound_send", {"email_verification_status": "unverified"})
    assert dec_unver.allowed is False
    assert dec_unver.autonomy_level == "NEVER"

    # 4. High deal value escalation
    dec_deal = PolicyEngine.evaluate(org, "outbound_send", {
        "email_verification_status": "verified",
        "is_suppressed": False,
        "jurisdiction_allowed": True,
        "deal_value": 15000,
        "high_value_threshold": 5000
    })
    assert dec_deal.autonomy_level == "L1"
    assert dec_deal.requires_human_approval is True

    # 5. Tenant configured L2 policy
    PolicyEngine.set_tenant_policy(org, "sequence_followup", "L2")
    dec_l2 = PolicyEngine.evaluate(org, "sequence_followup", {
        "email_verification_status": "verified",
        "is_suppressed": False,
        "jurisdiction_allowed": True
    })
    assert dec_l2.autonomy_level == "L2"
    assert dec_l2.requires_human_approval is False

def test_learning_loop_engine():
    report = LearningLoopEngine.generate_learning_report("test_org")
    assert "summary" in report
    assert "proposal_variant_performance" in report
    assert "deliverability_health" in report
    assert len(report["strategic_recommendations"]) > 0

def test_fastapi_outbound_and_policy_endpoints(client: TestClient, admin_headers: dict):
    # 1. Register mailbox
    resp = client.post("/api/outbound/mailboxes", json={
        "email": "growth-rep@agency-test.com",
        "display_name": "Test Rep",
        "provider_type": "smtp",
        "daily_cap": 40
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "growth-rep@agency-test.com"

    # 2. List mailboxes
    resp_list = client.get("/api/outbound/mailboxes", headers=admin_headers)
    assert resp_list.status_code == 200
    assert len(resp_list.json()) > 0

    # 3. Verify email
    resp_verify = client.post("/api/outbound/verify", json={"email": "lead@company.co"}, headers=admin_headers)
    assert resp_verify.status_code == 200
    assert "status" in resp_verify.json()

    # 4. Jurisdiction check
    resp_jur_us = client.get("/api/compliance/country/US", headers=admin_headers)
    assert resp_jur_us.status_code == 200
    assert resp_jur_us.json()["allowed"] is True

    resp_jur_ca = client.get("/api/compliance/country/CA", headers=admin_headers)
    assert resp_jur_ca.status_code == 200
    assert resp_jur_ca.json()["allowed"] is False

    # 5. Suppression check
    resp_supp = client.get("/api/compliance/suppression/check?email=safe@company.co", headers=admin_headers)
    assert resp_supp.status_code == 200
    assert "is_suppressed" in resp_supp.json()

    # 6. Unsubscribe endpoint (public, but only for a signed link; see test_group1_security_fixes.py)
    assert client.get("/api/compliance/unsubscribe?email=unsub-test@client.com").status_code == 400
    link = ComplianceFooterBuilder.build_unsubscribe_url("unsub-test@client.com", "org_default", "http://testserver")
    resp_unsub = client.post(link.replace("http://testserver", ""))
    assert resp_unsub.status_code == 200
    assert "You have been unsubscribed" in resp_unsub.text

    # 7. Policy rules
    resp_pol_set = client.post("/api/policy/rules", json={
        "rule_name": "crm_sync",
        "level": "L2"
    }, headers=admin_headers)
    assert resp_pol_set.status_code == 200

    resp_pol_eval = client.post("/api/policy/evaluate", json={
        "action_type": "crm_sync",
        "context": {"record_id": 12}
    }, headers=admin_headers)
    assert resp_pol_eval.status_code == 200
    assert resp_pol_eval.json()["allowed"] is True

    # 8. Learning report
    resp_lr = client.get("/api/analytics/learning_report", headers=admin_headers)
    assert resp_lr.status_code == 200
    assert "deliverability_health" in resp_lr.json()

    # 9. Reply triage
    resp_triage = client.post("/api/replies/inbound", json={
        "raw_body": "Can you share pricing details for web redesign?",
        "sender_email": "inquiry@client.com"
    }, headers=admin_headers)
    assert resp_triage.status_code == 200
    assert "draft_response" in resp_triage.json()


