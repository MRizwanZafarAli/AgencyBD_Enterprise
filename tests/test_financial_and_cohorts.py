"""
Unit and Integration Tests for Financial Cost Ledger & Spintax A/B Cohorts.
"""

import pytest
from database.db import init_db
from database.models import LeadRepository, BookingRepository
from analytics.financial_ledger import FinancialLedger
from analytics.ab_testing_cohorts import SpintaxABOptimizer

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_financial_ledger_unit_economics():
    org = "org_finance_test"
    
    # 1. Create 5 leads
    leads = []
    for i in range(5):
        l = LeadRepository.create_or_get_lead(f"Client {i}", f"client{i}.io", org_id=org)
        leads.append(l)
        # Log expenses
        FinancialLedger.log_agent_step_cost(org, l["id"], "deep_site_crawl")
        FinancialLedger.log_agent_step_cost(org, l["id"], "apollo_enrichment")
        FinancialLedger.log_agent_step_cost(org, l["id"], "gpt4o_audit_analysis")

    # 2. Book 1 meeting
    BookingRepository.create_booking(
        lead_id=leads[0]["id"],
        decision_maker_id=None,
        booking_time="2026-10-20 10:00",
        cal_link="https://cal.com/apexcore/demo",
        founder_prep_brief="Ready",
        org_id=org
    )

    # 3. Calculate metrics
    econ = FinancialLedger.get_unit_economics(org_id=org, pipeline_deal_size=35000.0)

    assert econ["total_leads_sourced"] >= 5
    assert econ["total_meetings_booked"] >= 1
    assert econ["total_agent_cost_usd"] > 0
    assert econ["cost_per_qualified_lead_usd"] > 0
    assert econ["estimated_pipeline_value_usd"] == 35000.0
    assert econ["sdr_roi_multiple"] > 100  # Massive positive ROI

def test_spintax_cohort_optimization_and_bandit():
    import uuid
    org = f"org_bandit_{uuid.uuid4().hex[:8]}"
    
    candidates = [
        {"key": "subj_a", "text": "Quick question regarding your site speed"},
        {"key": "subj_b", "text": "Teardown of your Next.js architecture"}
    ]

    # Populate variant A: 50 impressions, 1 positive reply
    for _ in range(50):
        SpintaxABOptimizer.record_cohort_impression(org, "subj_a", "subject")
    SpintaxABOptimizer.record_cohort_event(org, "subj_a", "positive_reply")

    # Populate variant B: 50 impressions, 10 positive replies (Clear Winner!)
    for _ in range(50):
        SpintaxABOptimizer.record_cohort_impression(org, "subj_b", "subject")
    for _ in range(10):
        SpintaxABOptimizer.record_cohort_event(org, "subj_b", "positive_reply")

    # In pure exploitation mode (epsilon=0.0), bandit MUST choose subj_b
    winner = SpintaxABOptimizer.select_best_variant(org, candidates, epsilon=0.0)
    assert winner["key"] == "subj_b"

    # Verify cohort report
    report = SpintaxABOptimizer.get_cohort_report(org)
    assert len(report) >= 2
    assert report[0]["variant_key"] == "subj_b"
    assert report[0]["positive_replies"] == 10
    assert report[0]["conversion_rate_pct"] == 20.0
