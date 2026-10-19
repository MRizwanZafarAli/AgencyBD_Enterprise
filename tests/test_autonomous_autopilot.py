"""
Integration Tests for AutonomousAutopilot controller.
Verifies end-to-end multi-agent orchestration without external paid API keys.
"""

import pytest
from orchestrator.autonomous_autopilot import AutonomousAutopilot


def test_autonomous_autopilot_cycle(monkeypatch):
    autopilot = AutonomousAutopilot()

    # Fast fixture for SEC EDGAR venture stream
    monkeypatch.setattr(
        autopilot.sourcing,
        "source_sec_edgar_venture",
        lambda funding_stage, limit, org_id: [
            {
                "id": 101,
                "company_name": "Sovereign Health AI",
                "domain": "sovereignhealth.internal",
                "source_channel": "sec_edgar_form_d"
            },
            {
                "id": 102,
                "company_name": "Nexus Cloud Systems",
                "domain": "nexuscloud.internal",
                "source_channel": "sec_edgar_form_d"
            }
        ]
    )

    result = autopilot.run_autopilot_cycle(channel="sec_edgar", limit=2, auto_enroll=True)
    assert result["status"] == "completed"
    assert result["total_processed"] == 2
    assert result["total_expected_pipeline_usd"] > 0
    assert result["average_p_close_percent"] >= 50.0
    assert len(result["execution_log"]) > 10
    
    first_lead = result["leads"][0]
    assert first_lead["company_name"] == "Sovereign Health AI"
    assert "p_close_percent" in first_lead
    assert "expected_deal_value_usd" in first_lead
    assert "email_preview" in first_lead
    assert "dispatch_status" in first_lead
