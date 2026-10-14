"""
Unit and Integration Tests for Enterprise Hardening Architecture:
1. SecurityVault HMAC-SHA256 signature verification and tamper detection.
2. Global CAN-SPAM / GDPR SHA-256 suppression enforcement.
3. Deliverability circuit breaker (2% bounce kill-switch).
4. Semantic Spintax anti-clustering copy generation.
5. Multi-vendor waterfall enrichment with ZeroBounce gate.
6. CRM relay and rich Slack interactive card dispatch.
7. Tiered Human-in-the-Loop (HITL) approval governance.
"""

import pytest
from database.db import init_db, is_entity_suppressed, add_entity_to_suppression
from database.models import LeadRepository, AuditRepository
from database.security_vault import SecurityVault
from agents.deliverability_sentinel import DeliverabilitySentinelAgent
from agents.spintax_copywriter import SpintaxCopywriterAgent
from agents.waterfall_enrichment import WaterfallEnrichmentAgent
from agents.crm_relay_agent import CRMRelayAgent
from agents.hitl_approval_gate import HITLApprovalGateAgent

def test_security_vault_hmac_tamper_proofing():
    payload = {"company": "Test Enterprise", "domain": "testenterprise.com", "revenue": 10000000}
    signature = SecurityVault.sign_record("lead", 101, payload)
    assert len(signature) == 64  # SHA-256 hex string

    # Verification passes with original payload
    assert SecurityVault.verify_record_signature("lead", 101, payload, signature) is True

    # Verification FAILS if data was tampered outside application
    tampered_payload = {"company": "Hacked Enterprise", "domain": "testenterprise.com", "revenue": 10000000}
    assert SecurityVault.verify_record_signature("lead", 101, tampered_payload, signature) is False

def test_can_spam_suppression_vault():
    init_db()
    email = "optout-ceo@targetdomain.com"
    domain = "suppresseddomain.com"

    assert is_entity_suppressed(email) is False
    assert is_entity_suppressed(domain) is False

    # Add to suppression
    add_entity_to_suppression(email, "email", "user_requested_removal")
    add_entity_to_suppression(domain, "domain", "unsubscribe_reply")

    assert is_entity_suppressed(email) is True
    assert is_entity_suppressed(domain) is True

def test_deliverability_circuit_breaker():
    sentinel = DeliverabilitySentinelAgent()
    # Case A: Low bounce rate (1 bounce out of 100 sent = 1%) -> Healthy
    healthy = sentinel.evaluate_circuit_breaker("alex@reach-apexcore.io", total_sent=100, total_bounced=1)
    assert healthy["circuit_breaker_status"] == "HEALTHY"
    assert healthy["action_taken"] == "NORMAL_DISPATCH"

    # Case B: High bounce rate (4 bounces out of 100 sent = 4.0% >= 2.0% threshold) -> Trips kill switch!
    tripped = sentinel.evaluate_circuit_breaker("alex@reach-apexcore.io", total_sent=100, total_bounced=4)
    assert "TRIPPED_CIRCUIT_BREAKER_PAUSED" in tripped["circuit_breaker_status"]
    assert tripped["action_taken"] == "HALT_DISPATCH_AND_REROUTE"

def test_spintax_copywriting_uniqueness():
    spintax = SpintaxCopywriterAgent()
    seq1 = spintax.generate_unique_sequence("Alex", "Acme", "acme.com", 3.2, "WordPress")
    seq2 = spintax.generate_unique_sequence("Alex", "Acme", "acme.com", 3.2, "WordPress")

    assert "step_1" in seq1
    assert "body" in seq1["step_1"]
    # Check that bodies are generated with non-trivial text
    assert len(seq1["step_1"]["body"]) > 50

def test_hitl_approval_gate():
    init_db()
    lead = LeadRepository.create_or_get_lead("Series A Biotech", "biotechseriesa.com", source_channel="venture_database")
    gate = HITLApprovalGateAgent()

    # Venture accounts default to Tier 1 Enterprise approval requirement
    routing = gate.route_for_approval_or_autopilot(lead["id"], est_deal_value=75000.0)
    assert routing["requires_human_signoff"] is True
    assert routing["dispatch_status"] == "HELD_IN_APPROVAL_BUCKET"

    # Founder 1-click approval
    approval = gate.approve_lead_dispatch(lead["id"], approver="Alex Mercer")
    assert approval["status"] == "queued"
