"""
Unit & Integration Tests for BD Skill Framework (`core/skills.py`).
"""

import pytest
from pydantic import BaseModel
from core.skills import (
    BaseSkill,
    SkillRegistry,
    skill_registry,
    register_skill,
    SkillExecutionError,
    DomainWhoisDnsSkill,
    DeliverabilityGateSkill,
    ObjectionClassifierSkill,
)
from database.db import init_db, get_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_skill_registry_listing():
    skills = skill_registry.list_skills()
    skill_names = [s["name"] for s in skills]
    assert "domain_whois_dns" in skill_names
    assert "deliverability_gate" in skill_names
    assert "objection_classifier" in skill_names

def test_domain_whois_skill_execution(monkeypatch):
    from unittest.mock import patch
    skill = skill_registry.get("domain_whois_dns")
    assert skill is not None

    with patch("net.dns_records.lookup_mx", return_value=["aspmx.l.google.com"]):
        with patch("net.dns_records.lookup_txt", return_value=["v=spf1 include:_spf.google.com ~all"]):
            output = skill.run({"domain": "google.com"}, org_id="org_default")
            assert output.domain == "google.com"
            assert output.has_mx is True
            assert output.has_spf is True
            assert output.deliverability_risk in ["low", "medium", "high"]

def test_deliverability_gate_skill():
    skill = skill_registry.get("deliverability_gate")
    assert skill is not None

    clean_output = skill.run({
        "recipient_email": "test_buyer@enterprise.com",
        "subject": "Quick inquiry regarding site performance",
        "body": "Hi John, noticed your page speed dropped recently on mobile.",
    })
    assert clean_output.allowed is True
    assert clean_output.is_suppressed is False

def test_objection_classifier_skill():
    skill = skill_registry.get("objection_classifier")
    assert skill is not None

    output = skill.run({
        "reply_body": "We don't have budget for this right now, maybe in Q4."
    })
    assert output.category in ["timing", "pricing", "competitor", "not_interested", "no_budget", "in_house_team"]
    assert output.reframe_recommendation is not None

def test_skill_validation_error():
    class DummyInput(BaseModel):
        num: int

    class DummyOutput(BaseModel):
        doubled: int

    class DummySkill(BaseSkill):
        name = "dummy"
        input_schema = DummyInput
        output_schema = DummyOutput
        def _execute(self, params, org_id="org_default"):
            return {"doubled": params.num * 2}

    dummy = DummySkill()
    res = dummy.run({"num": 5})
    assert res.doubled == 10

    # Test invalid input raises ValueError
    with pytest.raises(ValueError):
        dummy.run("invalid_string_not_dict")
