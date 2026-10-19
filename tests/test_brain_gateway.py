import pytest
from engines.brain_gateway import BrainGateway


def test_brain_gateway_default_tier_detection():
    gateway = BrainGateway(ollama_host=None, anthropic_api_key=None, groq_api_key=None)
    active = gateway.detect_active_brain()
    assert active["tier"] == "TIER_4_SOVEREIGN_EMBEDDED"
    assert active["sovereign"] is True
    assert active["cost"] == "$0.00 (Built-In Sovereign)"


def test_brain_gateway_anthropic_byok_detection():
    gateway = BrainGateway(ollama_host=None, anthropic_api_key="sk-ant-test-key-12345")
    active = gateway.detect_active_brain()
    assert active["provider"] == "anthropic_claude"
    assert active["tier"] == "TIER_3_FRONTIER_BYOK"


def test_brain_gateway_ollama_tier_detection():
    gateway = BrainGateway(ollama_host="http://127.0.0.1:11434")
    active = gateway.detect_active_brain()
    assert active["provider"] == "ollama_local"
    assert active["tier"] == "TIER_1_SOVEREIGN_LOCAL"


def test_brain_gateway_think_and_plan():
    gateway = BrainGateway()
    plan = gateway.think_and_plan("Find Series A enterprise SaaS companies with slow mobile paint")
    assert plan["status"] == "success"
    assert len(plan["chain_of_thought"]) > 0
    assert len(plan["execution_plan"]) == 5
    assert plan["execution_plan"][0]["phase"] == "HYPOTHESIS_FORMATION"
    assert plan["execution_plan"][1]["phase"] == "SURGICAL_AUDIT"
    assert plan["execution_plan"][2]["phase"] == "WATERFALL_DEANONYMIZATION"


def test_brain_gateway_triage_objection():
    gateway = BrainGateway()
    
    # 1. Budget objection
    t1 = gateway.triage_objection("Your services are way too expensive for our current budget")
    assert t1["category"] == "BUDGET_PRICING"
    assert "lost conversions" in t1["draft_reply"].lower()

    # 2. In-house objection
    t2 = gateway.triage_objection("We already have an internal engineering team in SF")
    assert t2["category"] == "INTERNAL_CAPABILITY"
    assert "burst pod" in t2["draft_reply"].lower()

    # 3. Timing objection
    t3 = gateway.triage_objection("Bad timing right now, please reach back out next quarter")
    assert t3["category"] == "TIMING_PRIORITY"


def test_brain_gateway_proposal_artifact():
    gateway = BrainGateway()
    lead = {"company_name": "Acme Fintech", "domain": "acmefintech.com", "contact_name": "Jordan Lee"}
    audit = {"detected_stack": ["Next.js", "Tailwind CSS"], "lcp_seconds": 3.9}
    metrics = {"monthly_financial_loss_usd": 3100.0, "expected_value_usd": 55000.0}

    res = gateway.generate_proposal_artifact(lead, audit, metrics)
    assert res["status"] == "success"
    md = res["artifact_markdown"]
    assert "Acme Fintech" in md
    assert "KaTeX" not in md # KaTeX formula is rendered directly
    assert "$$ \\Delta \\text{Conversion}" in md or "$$\\Delta \\text{Conversion}" in md
    assert "3.9s" in md
    assert "$3,100.00 USD" in md
    assert "Week 1: Sprint Zero" in md


def test_brain_gateway_chat_copilot():
    gateway = BrainGateway()
    
    # 1. Sourcing intent
    r1 = gateway.chat_copilot([{"role": "user", "content": "Find 5 newly funded AI startups"}])
    assert r1["status"] == "success"
    assert r1["intent"] == "SOURCING_DISPATCH"

    # 2. Audit intent
    r2 = gateway.chat_copilot([{"role": "user", "content": "Audit stripe.com with headless browser"}])
    assert r2["status"] == "success"
    assert r2["intent"] == "SITE_AUDIT"

    # 3. Objection intent
    r3 = gateway.chat_copilot([{"role": "user", "content": "Prospect said: we already have an internal engineering team"}])
    assert r3["status"] == "success"
    assert r3["intent"] == "OBJECTION_TRIAGE"
