"""
Unit & Integration Tests for the Autonomous Agent Swarm & Reactive Waterfall Pipeline (`agents/swarm.py`).
"""

import time
import uuid
import pytest
from agents.swarm import swarm_controller, AgentSwarmController
from database.db import init_db
from database.models import (
    LeadRepository,
    AuditRepository,
    ContactRepository,
    OutreachRepository,
)
from core.hooks import event_bus, HOOK_KILLSWITCH_ENGAGED, HOOK_REPLY_RECEIVED

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_swarm_controller_telemetry():
    controller = AgentSwarmController("org_test")
    controller.activate_swarm()
    telemetry = controller.get_telemetry()

    assert telemetry["swarm_active"] is True
    assert telemetry["total_agents"] == 8
    agent_names = [a["name"] for a in telemetry["agents"]]
    assert "scout_agent" in agent_names
    assert "diagnostician_agent" in agent_names
    assert "investigator_agent" in agent_names
    assert "copywriter_agent" in agent_names
    assert "outbound_operator" in agent_names
    assert "objection_challenger" in agent_names
    assert "revops_commander" in agent_names

def test_autonomous_reactive_waterfall_pipeline():
    # Activate global swarm controller
    swarm_controller.activate_swarm()

    # Step 1: Sourcing a new lead
    unique_domain = f"waterfall-{uuid.uuid4().hex[:8]}.com"
    lead = LeadRepository.create_or_get_lead(
        company_name="Apex Autonomous Systems",
        domain=unique_domain,
        org_id="org_default",
    )
    lead_id = lead["id"]
    assert lead_id is not None

    # Wait briefly for asynchronous agents to react through the waterfall chain
    # DiagnosticianAgent -> InvestigatorAgent -> CopywriterAgent
    audit = None
    for _ in range(20):
        audit = AuditRepository.get_audit_by_lead(lead_id, org_id="org_default")
        if audit:
            break
        time.sleep(0.1)

    assert audit is not None, "DiagnosticianAgent should have automatically audited the newly sourced lead"
    assert audit.get("calculated_pitch_angle") is not None

    # Step 2: Verify Decision Makers were added by InvestigatorAgent
    contacts = None
    for _ in range(20):
        contacts = ContactRepository.get_contacts_by_lead(lead_id, org_id="org_default")
        if contacts:
            break
        time.sleep(0.1)

    assert contacts is not None and len(contacts) > 0, "InvestigatorAgent should have enriched decision makers"

    # Step 3: Verify 3-touch sequence was drafted by CopywriterAgent
    sequences = None
    for _ in range(20):
        sequences = OutreachRepository.get_sequences_by_lead(lead_id, org_id="org_default")
        if sequences:
            break
        time.sleep(0.1)

    assert sequences is not None and len(sequences) == 3, "CopywriterAgent should have drafted 3 sequence steps"
    assert "Quick question regarding" in sequences[0]["subject"]
    assert "Permission to close the loop" in sequences[2]["subject"]

def test_revops_commander_killswitch_reaction():
    controller = AgentSwarmController("org_test")
    controller.activate_swarm()
    
    # Emitting killswitch hook should execute without error
    event_bus.emit(HOOK_KILLSWITCH_ENGAGED, {"reason": "User triggered manual killswitch"}, org_id="org_test", sync=True)
    status = controller.revops_commander.get_status()
    assert status["state"] == "idle"
