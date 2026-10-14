"""Learning loop: no verdicts without data, honest costs, and a way to feed it outcomes."""

import pytest

from analytics.learning_loop import LearningLoopEngine, two_proportion_p_value
from database.db import get_db
from database.models import OpportunityRepository, ProposalRepository, AgentRunRepository
from outbound.providers.registry import MailboxRegistry

ORG = "org_learn"


def proposals(variant, won, lost, org=ORG):
    opp = OpportunityRepository.create_opportunity("marketplace", "upwork", f"job {variant}{won}{lost}", "d " * 20, org_id=org, external_id=f"{variant}{won}{lost}{org}")
    for i in range(won + lost):
        p = ProposalRepository.create_proposal(opp["id"], "body " * 40, variant=variant, org_id=org, queue_for_approval=False)
        ProposalRepository.update_status(p["id"], "won" if i < won else "lost", org_id=org)


def test_z_test_matches_known_values():
    assert two_proportion_p_value(20, 30, 10, 30) == pytest.approx(0.0098, abs=0.0005)
    assert two_proportion_p_value(10, 30, 10, 30) == 1.0
    assert two_proportion_p_value(0, 0, 5, 10) is None
    assert two_proportion_p_value(5, 10, 5, 10) == 1.0 and two_proportion_p_value(0, 10, 0, 10) == 1.0


def test_an_empty_workspace_gets_no_made_up_verdicts():
    r = LearningLoopEngine.generate_learning_report("org_nothing")
    assert r["deliverability_health"] == "NO_DATA"
    assert r["summary"]["cost_per_meeting_usd"] is None and r["summary"]["cost_per_won_proposal_usd"] is None
    assert r["variant_comparison"]["status"] == "insufficient_data"
    assert "Not enough won/lost outcomes" in r["strategic_recommendations"][0]
    assert "Increase Variant" not in str(r)


def test_a_winner_needs_enough_data_and_a_real_difference():
    proposals("A", 3, 2)
    proposals("B", 0, 5)
    r = LearningLoopEngine.generate_learning_report(ORG)
    assert r["variant_comparison"]["status"] == "insufficient_data", "5 decided each is too few"

    proposals("A", 7, 3)       # A: 10 won / 5 lost ... decided 15
    proposals("B", 1, 9)       # B: 1 won / 14 lost ... decided 15
    r = LearningLoopEngine.generate_learning_report(ORG)
    assert r["variant_comparison"]["status"] == "compared" and r["variant_comparison"]["p_value"] < 0.1
    assert any("Variant A wins more often" in x and "directional" in x for x in r["strategic_recommendations"])


def test_no_winner_when_the_difference_is_noise():
    proposals("A", 6, 6, org="org_noise")
    proposals("B", 5, 7, org="org_noise")
    r = LearningLoopEngine.generate_learning_report("org_noise")
    assert any("No significant difference" in x for x in r["strategic_recommendations"])
    assert not any("wins more often" in x for x in r["strategic_recommendations"])


def test_deliverability_health_reflects_real_events(monkeypatch):
    import outbound.providers.registry as reg
    monkeypatch.setattr(reg, "lookup_mx", lambda d: ["mx.example.net"])
    box = MailboxRegistry.register_mailbox("org_dlv", "s@agency.example", skip_warmup=True)
    for i in range(10):
        MailboxRegistry.record_send("org_dlv", box["id"], f"p{i}@x.example")
    assert LearningLoopEngine.generate_learning_report("org_dlv")["deliverability_health"] == "HEALTHY_LOW_VOLUME"
    MailboxRegistry.record_event("org_dlv", "p1@x.example", "bounced")
    assert LearningLoopEngine.generate_learning_report("org_dlv")["deliverability_health"] == "CIRCUIT_BREAKER_ACTIVE"   # 10% bounces
    r = LearningLoopEngine.generate_learning_report("org_dlv")
    assert r["summary"]["bounce_rate_percent"] == 10.0 and any("CRITICAL" in x for x in r["strategic_recommendations"])


def test_costs_include_llm_spend_and_say_what_is_not_tracked():
    AgentRunRepository.log_run("ProposalStudio", "claude-sonnet-5-5", 1000, 500, 0.0105, 900, org_id="org_cost")
    AgentRunRepository.log_run("ProposalStudio", "claude-sonnet-5-5", 1000, 500, 0.0105, 900, org_id="org_cost")
    r = LearningLoopEngine.generate_learning_report("org_cost")
    assert r["expense_breakdown"]["llm"] == pytest.approx(0.021) and r["summary"]["llm_calls"] == 2
    assert "Upwork Connects" in r["costs_not_tracked"] and "email verification credits" in r["costs_not_tracked"]


# ---------------- API ----------------

def test_outcomes_can_only_be_recorded_after_approval(client, make_key):
    lead = make_key("growth_lead", org_id=ORG)
    opp = OpportunityRepository.create_opportunity("marketplace", "upwork", "j", "d " * 20, org_id=ORG)
    p = ProposalRepository.create_proposal(opp["id"], "body " * 40, org_id=ORG, queue_for_approval=False)
    assert client.post(f"/api/proposals/{p['id']}/outcome", headers=lead, json={"status": "won"}).status_code == 409
    assert client.post(f"/api/proposals/{p['id']}/outcome", headers=lead, json={"status": "bogus"}).status_code == 400
    ProposalRepository.update_status(p["id"], "approved", org_id=ORG)
    assert client.post(f"/api/proposals/{p['id']}/outcome", headers=lead, json={"status": "submitted"}).status_code == 200
    assert client.post(f"/api/proposals/{p['id']}/outcome", headers=lead, json={"status": "won", "reason": "client replied in an hour"}).status_code == 200
    with get_db() as db:
        row = db.execute("SELECT status, outcome_reason FROM proposals WHERE id = ?", (p["id"],)).fetchone()
    assert (row["status"], row["outcome_reason"]) == ("won", "client replied in an hour")
    assert client.post(f"/api/proposals/{p['id']}/outcome", headers=make_key("growth_lead", org_id="org_other"), json={"status": "lost"}).status_code == 404
    assert client.post(f"/api/proposals/{p['id']}/outcome", headers=make_key("auditor", org_id=ORG), json={"status": "lost"}).status_code == 403


def test_manual_expenses_feed_the_report(client, make_key):
    lead = make_key("growth_lead", org_id="org_exp")
    assert client.post("/api/analytics/expenses", headers=lead, json={"expense_type": "upwork_connects", "amount_usd": 12.5}).status_code == 200
    assert client.post("/api/analytics/expenses", headers=lead, json={"expense_type": "x", "amount_usd": -1}).status_code == 422
    assert client.post("/api/analytics/expenses", headers=make_key("auditor", org_id="org_exp"), json={"expense_type": "x", "amount_usd": 1}).status_code == 403
    report = client.get("/api/analytics/learning_report", headers=lead).json()
    assert report["expense_breakdown"]["upwork_connects"] == 12.5 and report["summary"]["total_spend_usd"] == 12.5
    assert client.get("/api/analytics/learning_report", headers=make_key("growth_lead", org_id="org_exp2")).json()["summary"]["total_spend_usd"] == 0
