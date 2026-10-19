"""
Tests for SwarmPods (Specialist Multi-Agent Teaming & Pod Controller).
"""

from unittest.mock import MagicMock, patch
from agents.swarm_pods import (
    SourcingScoutPod,
    ForensicsEngineerPod,
    DealStrategistPod,
    DeliverabilitySentinelPod,
    ObjectionNegotiatorPod,
    SwarmPodController,
)


def test_sourcing_scout_pod():
    pod = SourcingScoutPod()
    with patch.object(pod.sourcing, "source_sec_edgar_venture", return_value=[{"company": "Apex Corp", "domain": "apex.io"}]):
        res = pod.run(limit=1)
        assert res["pod"] == "SourcingScoutPod"
        assert res["leads_found"] == 1
        assert res["prospects"][0]["company"] == "Apex Corp"


def test_forensics_engineer_pod():
    mock_browser = MagicMock()
    mock_browser.render_spa_dom.return_value = {
        "status": "success",
        "domain": "target.io",
        "title": "Target Tech",
        "detected_stack": ["Next.js", "React"],
        "emails": ["cto@target.io"],
        "phones": [],
    }
    pod = ForensicsEngineerPod(browser_service=mock_browser)
    res = pod.run("target.io")
    assert res["pod"] == "ForensicsEngineerPod"
    assert res["domain"] == "target.io"
    assert "Next.js" in res["detected_stack"]
    assert res["measured_lcp_seconds"] >= 3.0
    assert "cto@target.io" in res["emails_discovered"]


def test_deal_strategist_pod():
    mock_diff = MagicMock()
    mock_diff.compare_domains.return_value = {
        "target": {
            "domain": "target.io",
            "detected_stack": ["Next.js"],
            "lcp_seconds": 4.0,
        },
        "competitor": {
            "domain": "stripe.com",
            "detected_stack": ["React"],
            "lcp_seconds": 1.4,
        },
        "differential": {
            "latency_gap_seconds": 2.6,
            "monthly_conversion_deficit_usd": 8500.0,
            "competitive_pitch_hook": "Target lags Stripe by 2.6s.",
        },
    }
    pod = DealStrategistPod(diff_engine=mock_diff)
    res = pod.run("target.io", "stripe.com")
    assert res["pod"] == "DealStrategistPod"
    assert res["p_close_percent"] > 0
    assert res["monthly_conversion_deficit_usd"] == 8500.0


def test_deliverability_sentinel_pod():
    pod = DeliverabilitySentinelPod()
    res = pod.run(day_number=14, max_capacity=50)
    assert res["pod"] == "DeliverabilitySentinelPod"
    assert res["day_number"] == 14
    assert res["safe_daily_dispatch_volume"] > 0
    assert res["safe_daily_dispatch_volume"] <= 50
    assert res["status"] == "HEALTHY_OPTIMAL"


def test_objection_negotiator_pod():
    mock_brain = MagicMock()
    mock_brain.triage_objection.return_value = {
        "category": "IN_HOUSE_TEAM",
        "rebuttal_strategy": "Highlight burst capacity and specialized differential audits.",
        "draft_reply": "Hi Lead, totally understand having internal resources...",
    }
    pod = ObjectionNegotiatorPod(brain=mock_brain)
    res = pod.run("We have in-house devs", prospect_name="Alex", company="Acme")
    assert res["pod"] == "ObjectionNegotiatorPod"
    assert res["category"] == "IN_HOUSE_TEAM"
    assert "burst capacity" in res["rebuttal_strategy"]


def test_swarm_pod_controller():
    controller = SwarmPodController()
    with patch.object(controller.scout, "run", return_value={"pod": "SourcingScoutPod", "leads_found": 3}), \
         patch.object(controller.forensics, "run", return_value={"pod": "ForensicsEngineerPod", "measured_lcp_seconds": 3.8}), \
         patch.object(controller.strategist, "run", return_value={"pod": "DealStrategistPod", "p_close_percent": 82.5}), \
         patch.object(controller.sentinel, "run", return_value={"pod": "DeliverabilitySentinelPod", "safe_daily_dispatch_volume": 42}):
        cycle = controller.run_full_pod_cycle("apexlabs.internal", "stripe.com")
        assert cycle["status"] == "completed"
        assert cycle["active_pods"] == 5
        assert cycle["sourcing"]["leads_found"] == 3
        assert cycle["deal_strategy"]["p_close_percent"] == 82.5
