"""
Unit Tests for MathPipelineEngine.
Tests Bayesian Logistic probability, expected value, cost of delay, and warmup capacity curves.
"""

import pytest
from engines.math_pipeline_engine import MathPipelineEngine


def test_calculate_intent_score():
    score_fresh = MathPipelineEngine.calculate_intent_score("sec_edgar_form_d", days_old=1.0)
    score_old = MathPipelineEngine.calculate_intent_score("sec_edgar_form_d", days_old=60.0)
    assert score_fresh > score_old
    assert 0.70 <= score_fresh <= 1.0


def test_calculate_tech_debt_score():
    score_slow = MathPipelineEngine.calculate_tech_debt_score(lcp_seconds=4.5, detected_stack=["WordPress", "PHP"], missing_headers_count=4)
    score_fast = MathPipelineEngine.calculate_tech_debt_score(lcp_seconds=1.2, detected_stack=["Next.js", "Cloudflare"], missing_headers_count=0)
    assert score_slow > score_fast
    assert score_slow >= 0.50
    assert score_fast <= 0.30


def test_calculate_authority_score():
    assert MathPipelineEngine.calculate_authority_score("Founder & CEO") == 1.0
    assert MathPipelineEngine.calculate_authority_score("Chief Technology Officer") == 0.95
    assert MathPipelineEngine.calculate_authority_score("VP of Engineering") == 0.95
    assert MathPipelineEngine.calculate_authority_score("Marketing Specialist") <= 0.60


def test_predict_close_probability_and_valuation():
    res = MathPipelineEngine.predict_close_probability(
        source_channel="sec_edgar_form_d",
        title="CEO",
        lcp_seconds=3.8,
        detected_stack=["WordPress"],
        email_confidence=95,
        catch_all_decoded=True
    )
    assert res["p_close"] >= 0.75
    assert res["tier"] == "TIER_1_ENTERPRISE_ALPHA"
    assert "factors" in res
    assert res["logit"] > 0

    deal = MathPipelineEngine.calculate_expected_deal_value(res["p_close"], "sec_edgar_form_d", ["WordPress"])
    assert deal["contract_acv_usd"] == 65000.0
    assert deal["expected_value_usd"] > 40000.0


def test_calculate_cost_of_delay():
    delay = MathPipelineEngine.calculate_cost_of_delay(lcp_seconds=4.0, monthly_visitors=20000, avg_transaction_usd=100.0)
    assert delay["excess_latency_seconds"] == 1.5
    assert delay["monthly_financial_loss_usd"] > 0
    assert "pitch_hook" in delay
    assert "/mo" in delay["pitch_hook"]
    assert "$" in delay["pitch_hook"]


def test_sigmoid_warmup_capacity():
    d1 = MathPipelineEngine.calculate_sigmoid_warmup_capacity(1)
    d7 = MathPipelineEngine.calculate_sigmoid_warmup_capacity(7)
    d14 = MathPipelineEngine.calculate_sigmoid_warmup_capacity(14)
    d28 = MathPipelineEngine.calculate_sigmoid_warmup_capacity(28)
    assert d1 <= d7 <= d14 <= d28
    assert d1 == 5
    assert d28 >= 48
