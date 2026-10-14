"""
Opportunity Radar and Approval Inbox tests. Proposal generation is covered in test_group2_honesty_and_proposals.py.
Connectors are stubbed so the suite never depends on the internet.
"""

from connectors.base import OpportunityItem
from radar.engine import OpportunityRadarEngine
from database.models import OpportunityRepository, ProposalRepository, ApprovalRepository


class _FakeConnector:
    source_name = "remoteok"

    def fetch(self, query=None, limit=10, org_id=None):
        return [
            OpportunityItem(type="marketplace", source="remoteok", external_id="x1", title="Senior React engineer",
                            description="Build a dashboard in React and Python.", budget_min=None, budget_max=None,
                            currency="USD", fit_score=0.7, risk_flags=[]),
        ]


def test_opportunity_radar_scan_is_idempotent(monkeypatch):
    engine = OpportunityRadarEngine()
    engine.connectors = [_FakeConnector()]
    first = engine.scan_all_sources(limit_per_source=5, org_id="org_r")
    second = engine.scan_all_sources(limit_per_source=5, org_id="org_r")
    assert len(first) == 1 and first[0]["source"] == "remoteok"
    assert first[0]["id"] == second[0]["id"], "re-scanning must not duplicate opportunities"
    assert len(OpportunityRepository.list_opportunities(org_id="org_r")) == 1


def test_radar_with_no_results_stays_empty_in_real_mode():
    engine = OpportunityRadarEngine()
    engine.connectors = []
    assert engine.scan_all_sources(org_id="org_empty") == []


def test_approval_decision_is_tenant_scoped():
    opp = OpportunityRepository.create_opportunity("marketplace", "upwork", "Job", "Desc " * 20, org_id="org_a")
    prop = ProposalRepository.create_proposal(opp["id"], "Body " * 40, org_id="org_a")
    approval = [a for a in ApprovalRepository.list_pending("org_a") if a["subject_id"] == prop["id"]][0]
    # another tenant tries to decide it: must be a no-op
    ApprovalRepository.decide(approval["id"], "approved", "mallory", org_id="org_b")
    assert [a for a in ApprovalRepository.list_pending("org_a") if a["id"] == approval["id"]], "still pending"
    ApprovalRepository.decide(approval["id"], "approved", "owner", org_id="org_a")
    assert not [a for a in ApprovalRepository.list_pending("org_a") if a["id"] == approval["id"]]
