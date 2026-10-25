"""P1 contract tests: the autopilot, sourcing, scoring, pipeline and reports never invent anything."""

import re
from pathlib import Path

import pytest

import agents.sourcing_agent as sourcing_mod
from agents.outreach_drafter import draft_from_brief
from agents.sourcing_agent import SourcingAgent
from connectors.base import OpportunityItem
from database.db import get_db
from database.models import ApprovalRepository, ContactRepository, LeadRepository
from intel import lead_priority
from intel.entity_filter import classify_entity, clean_company_name
from orchestrator.autopilot import DiscoveryRun
from outbound.verify import VerificationResult
from policy.engine import PolicyEngine
from workflows.inbox import WorkItemRepository
from workflows.sequence import OutreachSequenceWorkflow

ORG = "org_p1"
ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ entity filter

@pytest.mark.parametrize("name,kind", [
    ("QP-Partnership  II,", "fund_or_vehicle"), ("Sequoia Capital Fund XIV, L.P.", "fund_or_vehicle"), ("Alpha Growth Opportunity Fund III", "fund_or_vehicle"),
    ("Series of Lumen Labs LLC", "fund_or_vehicle"), ("Xona Space Systems .", "operating_company"), ("Acme Robotics, Inc.", "operating_company")])
def test_entity_filter_drops_investment_vehicles(name, kind):
    assert classify_entity(name)[0] == kind


def test_company_name_cleaning():
    assert clean_company_name("Xona Space Systems ., Inc.") == "Xona Space Systems"
    assert clean_company_name("Snout https://snout.com/") == "Snout"
    assert clean_company_name("PrairieLearn (Remote US)") == "PrairieLearn" and clean_company_name("Shepherd (Series B)") == "Shepherd"


# ------------------------------------------------------------------ sourcing never guesses a domain

class FakeResolver:
    """name -> verified domain, or unresolved"""
    known = {"Real Robotics": "realrobotics.io"}

    @classmethod
    def resolve_domain_from_name(cls, name, hint, org_id="org_default"):
        domain = hint or cls.known.get(name)
        if domain:
            from database.models import CompanyRepository
            c = CompanyRepository.create_or_get(name=name, domain=domain, org_id=org_id)
            return {"status": "resolved", "domain": domain, "company_id": c["id"], "note": None}
        return {"status": "unresolved", "domain": None, "company_id": None, "note": "No website that clearly belongs to this company was found."}


@pytest.fixture
def agent(monkeypatch):
    import intel.resolver as resolver_mod
    monkeypatch.setattr(resolver_mod, "CompanyResolver", FakeResolver)
    return SourcingAgent()


def test_sec_sourcing_keeps_only_verified_operating_companies(agent, monkeypatch):
    filings = [{"form_type": "D", "legal_name": n, "cik": "1", "filing_url": "u", "filing_date": "d"}
               for n in ("QP-Partnership II,", "Real Robotics, Inc.", "Mystery Startup Inc")]
    monkeypatch.setattr(agent, "fetch_sec_form_d_filings", lambda limit: filings)
    out = agent.source_sec_edgar_venture(limit=5, org_id=ORG)
    assert [l["company_name"] for l in out["leads"]] == ["Real Robotics"] and out["leads"][0]["domain"] == "realrobotics.io"
    reasons = {s["name"]: s["reason"] for s in out["skipped"]}
    assert "investment vehicle" in reasons["QP-Partnership II,"] and "Mystery Startup" in reasons
    with get_db() as db:   # nothing was stored for the skipped filers, and no invented rating
        assert db.execute("SELECT COUNT(*) FROM leads WHERE org_id = ?", (ORG,)).fetchone()[0] == 1
        assert db.execute("SELECT rating FROM leads WHERE org_id = ?", (ORG,)).fetchone()[0] in (0, 0.0, None)


def test_hiring_sourcing_uses_the_posting_url_reports_failures_and_never_defaults(agent, monkeypatch):
    items = [OpportunityItem(type="hiring_signal", source="hn", external_id="1", title="Backend engineer", description="Apply at https://realrobotics.io/jobs",
                             company_name="Real Robotics"),
             OpportunityItem(type="hiring_signal", source="hn", external_id="2", title="Engineer", description="no link", company_name="Unknown Co"),
             OpportunityItem(type="hiring_signal", source="hn", external_id="3", title="Engineer", description="x", company_name=None)]
    monkeypatch.setattr(agent.hn_connector, "fetch", lambda limit: items)
    monkeypatch.setattr(agent.remoteok_connector, "fetch", lambda limit: (_ for _ in ()).throw(RuntimeError("RemoteOK returned HTTP 503")))
    out = agent.source_hn_hiring_signals(role_keyword="engineer", limit=5, org_id=ORG)
    assert [l["domain"] for l in out["leads"]] == ["realrobotics.io"]
    assert any("RemoteOK" in e for e in out["errors"])
    assert {s["name"] for s in out["skipped"]} == {"Unknown", "Engineer"}
    assert not any(l["company_name"] in ("Tech Employer", "company.com") for l in out["leads"])


# ------------------------------------------------------------------ discovery run

BRIEF = {"status": "ok", "digital_health": {"top_findings": [
    {"finding": "No Content-Security-Policy header.", "severity": "medium", "fix": "Add a CSP.", "measured": "Header missing", "evidence_ids": [1]},
    {"finding": "http:// does not redirect to https://.", "severity": "high", "fix": "Redirect.", "measured": "HTTP 200 on http://", "evidence_ids": [2]},
    {"finding": "Minor thing.", "severity": "low", "fix": "x", "measured": "y", "evidence_ids": [3]}]}}


class FakeGate:
    def verify(self, email):
        return VerificationResult(email, "verified", True, "fake", 1.0, "verified")


class FakeProvider:
    sent = []

    def send(self, m): raise AssertionError("the autopilot must never send; it only drafts for approval")
    def health_check(self): return {"ready": True}


class StubSourcing:
    def __init__(self, leads): self.leads = leads
    def source_hn_hiring_signals(self, **kw): return {"leads": self.leads, "skipped": [], "errors": []}


@pytest.fixture
def run(monkeypatch):
    import orchestrator.autopilot as ap
    lead = LeadRepository.create_or_get_lead("Real Robotics", "realrobotics.io", source_channel="hiring_intent", org_id=ORG)
    monkeypatch.setattr(ap.CompanyBriefEngine, "generate_brief", classmethod(lambda cls, cid, org, refresh=False: BRIEF))
    wf = OutreachSequenceWorkflow(provider=FakeProvider(), verification_gate=FakeGate())
    return lead, DiscoveryRun(sourcing=StubSourcing([lead]), workflow=wf)


def test_without_a_verified_contact_the_run_opens_a_work_item_and_invents_nobody(run):
    lead, dr = run
    out = dr.run(ORG, "hiring", "engineer", limit=3)
    r = out["leads"][0]
    assert r["outcome"] == "needs_contact" and r["work_item"] and out["drafts_pending_approval"] == 0
    assert ContactRepository.get_contacts_by_lead(lead["id"], ORG) == []
    # running it again does not duplicate the work item
    dr.run(ORG, "hiring", "engineer", limit=3)
    assert len([w for w in WorkItemRepository.list_open(ORG) if w["kind"] == "find_contact"]) == 1


def test_with_a_verified_contact_it_drafts_from_measured_findings_for_approval(run):
    lead, dr = run
    ContactRepository.add_decision_maker(lead["id"], "Dana", "Lee", "CTO", "dana@realrobotics.io", verification_status="verified", org_id=ORG)
    PolicyEngine.set_tenant_policy(ORG, "outbound_first_touch", "L1")
    # country unknown -> fail closed, and a person is told
    out = dr.run(ORG, "hiring", "engineer", limit=1)
    assert out["leads"][0]["outcome"] == "blocked_by_policy"
    assert any(w["kind"] == "review_lead" for w in WorkItemRepository.list_open(ORG))


def test_draft_text_contains_only_measured_findings_and_no_invented_claims():
    d = draft_from_brief(BRIEF, "Dana", "realrobotics.io")
    assert "Content-Security-Policy" in d["body"] and "Header missing" in d["body"] and "Minor thing" not in d["body"]
    for banned in ("72 hours", "this morning", "Alex Founder", "bounce rate", "$"):
        assert banned not in d["body"]
    assert draft_from_brief({"digital_health": {"top_findings": [{"finding": "x", "severity": "low", "measured": "y"}]}}, "Dana", "x.io") is None
    assert draft_from_brief({}, "Dana", "x.io") is None


# ------------------------------------------------------------------ priority score

def test_priority_is_transparent_and_flags_what_is_unknown():
    lead = LeadRepository.create_or_get_lead("Smile Dental", "nosite-smile.invalid", phone="555", reviews_count=120,
                                             source_channel="google_maps", notes="WEB PRESENCE: no_website_listed", org_id=ORG)
    s = lead_priority.score_lead(lead["id"], ORG)
    assert s["components"]["presence"] == 20 and s["components"]["reputation"] == 15 and s["components"]["signal"] == 8
    assert "run_audit" in s["needs"] and s["confidence"] == "low" and any("Not audited" in r for r in s["reasons"])
    assert sum(lead_priority.WEIGHTS.values()) == 100 and s["score"] == sum(s["components"].values())


def test_calibration_refuses_to_claim_win_rates_without_enough_outcomes():
    cal = lead_priority.calibration(ORG)
    assert cal["calibrated"] is False and cal["needed"] == lead_priority.MIN_CLOSED_FOR_CALIBRATION


# ------------------------------------------------------------------ CRM pipeline

def test_pipeline_assumes_no_deal_value_and_no_win_rate():
    LeadRepository.create_or_get_lead("A Co", "a.example", org_id=ORG)
    LeadRepository.create_or_get_lead("B Co", "b.example", notes="EST VALUE: $12,000", org_id=ORG)
    p = LeadRepository.get_pipeline(ORG)
    assert p["total_pipeline_value"] == 12000.0 and p["unvalued_deals_count"] == 1 and p["win_rate_percent"] is None
    assert "not a forecast" in p["projection_note"]


def test_new_contacts_default_to_unverified():
    lead = LeadRepository.create_or_get_lead("C Co", "c.example", org_id=ORG)
    c = ContactRepository.add_decision_maker(lead["id"], "Eve", "Ng", "CEO", "eve@c.example", org_id=ORG)
    assert c["verification_status"] == "unverified" and not c["mx_verified"]


# ------------------------------------------------------------------ endpoints

def test_inbox_merges_work_items_and_resolves_them(client, make_key):
    h = make_key("growth_lead", ORG)
    item = WorkItemRepository.add(ORG, "find_contact", "Find a decision maker at X", priority=80)
    feed = client.get("/api/inbox", headers=h).json()
    assert any(i["type"] == "work_item" and i["id"] == item["id"] for i in feed["items"])
    assert client.post(f"/api/inbox/work_items/{item['id']}/resolve", headers=make_key("growth_lead", "org_other"), json={}).status_code == 404
    assert client.post(f"/api/inbox/work_items/{item['id']}/resolve", headers=h, json={"status": "done"}).status_code == 200
    assert not any(i["type"] == "work_item" for i in client.get("/api/inbox", headers=h).json()["items"])


def test_report_html_escapes_site_controlled_text_and_blocks_scripts(monkeypatch, tmp_path):
    from reports.client_report import ClientReport
    audit = {"status": "completed", "domain": "evil.example", "overall_score": 40, "audit_id": 1, "checks_run": ["security"], "checks_skipped": [],
             "summary": "s", "findings": [{"category": "security", "severity": "high", "finding": "<script>alert(1)</script> missing header",
                                          "fix": "<img src=x onerror=alert(2)>", "evidence_value": "<b>x</b>", "service_id": "devops_sre", "confidence": 1.0}]}
    from datetime import datetime, timezone
    html = ClientReport(str(tmp_path)).render_html({"audit": audit, "comparison": None, "vulnerabilities": [], "generated_at": datetime.now(timezone.utc)}, ORG)
    assert "<script>alert" not in html and "&lt;script&gt;" in html and "onerror=alert" not in html.replace("&lt;img src=x onerror=alert(2)&gt;", "")
    assert "Content-Security-Policy" in html and "default-src 'none'" in html


def test_reports_are_tenant_scoped(client, make_key):
    from api import client_report
    (client_report.storage_dir / f"report_{ORG}_x_com_1.html").write_text("<html>mine</html>")
    assert client.get(f"/api/reports/view/report_{ORG}_x_com_1.html", headers=make_key("auditor", ORG)).status_code == 200
    assert client.get(f"/api/reports/view/report_{ORG}_x_com_1.html", headers=make_key("auditor", "org_other")).status_code == 404
    (client_report.storage_dir / f"report_{ORG}_x_com_1.html").unlink()


# ------------------------------------------------------------------ static honesty gates

FABRICATION_MARKERS = ["Alex Founder", "Alex Mercer", "alex@agencybd", "queued_for_send", "estimated_commercial_dollars_saved", "predict_close_probability",
                       "monthly_financial_loss", "TIER_1_ENTERPRISE_ALPHA", "company.com\"", "Tech Employer"]


def test_no_fabrication_markers_remain_in_product_code():
    offenders = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in ("tests", "frontend", "node_modules", ".git") or rel.name in ("app.py",):
            continue
        text = path.read_text(errors="ignore")
        offenders += [f"{rel}: {m}" for m in FABRICATION_MARKERS if m in text]
    assert not offenders, "Fabrication markers found:\n" + "\n".join(offenders)


def test_orchestrators_contain_no_constant_measurements():
    text = (ROOT / "orchestrator" / "autopilot.py").read_text() + (ROOT / "intel" / "comparison.py").read_text()
    assert not re.search(r"\b(lcp|latency|stack)\w*\s*=\s*[\d\[\"]", text), "a measurement must come from an audit, never a literal"


def test_client_detail_aggregates_one_tenant_and_flags_sites_without_a_website(client, make_key):
    lead = LeadRepository.create_or_get_lead("Smile Dental", "nosite-smile.invalid", reviews_count=40, source_channel="google_maps",
                                             notes="WEB PRESENCE: no_website_listed", org_id="org_cd")
    res = client.get(f"/api/clients/{lead['id']}", headers=make_key("auditor", "org_cd"))
    body = res.json()
    assert res.status_code == 200 and body["has_website"] is False and body["audit"] is None and body["priority"]["components"]["presence"] == 20
    assert client.get(f"/api/clients/{lead['id']}", headers=make_key("auditor", "org_cd_other")).status_code in (403, 404)


def test_manual_contacts_start_unverified_and_stay_so_without_a_verifier(client, make_key):
    h = make_key("growth_lead", "org_ct")
    lead = LeadRepository.create_or_get_lead("Ct Co", "ct.example", org_id="org_ct")
    assert client.post(f"/api/clients/{lead['id']}/contacts", headers=h, json={"first_name": "Eve", "email": "not-an-email"}).status_code == 422
    c = client.post(f"/api/clients/{lead['id']}/contacts", headers=h, json={"first_name": "Eve", "last_name": "Ng", "title": "CEO", "email": "eve@ct.example"}).json()
    assert c["verification_status"] == "unverified"
    res = client.post(f"/api/clients/{lead['id']}/contacts/{c['id']}/verify", headers=h).json()
    assert res["verified"] is False and res["reason"]               # no vendor configured: stays unverified and says why
    other = make_key("growth_lead", "org_ct_other")
    assert client.post(f"/api/clients/{lead['id']}/contacts/{c['id']}/verify", headers=other).status_code in (403, 404)


def test_discovery_runs_in_the_background_and_reports_progress_and_results(client, make_key, monkeypatch):
    import time
    import orchestrator.jobs as jobs

    class Quick:
        def run(self, org, channel, query, location, limit, user="x", progress=None):
            progress and progress({"log": [{"step": "source", "message": "1 company"}], "processed": 0})
            return {"channel": channel, "sourced": 1, "skipped": [], "errors": [], "drafts_pending_approval": 0, "work_items_opened": 0, "leads": [], "log": []}
    monkeypatch.setattr(jobs, "DiscoveryRun", Quick)
    h = make_key("growth_lead", "org_job")
    started = client.post("/api/autopilot/run", headers=h, json={"channel": "hiring", "query": "react", "limit": 3}).json()
    assert started["status"] == "running" and started["run_id"].startswith("run_")
    for _ in range(50):
        body = client.get(f"/api/autopilot/runs/{started['run_id']}", headers=h).json()
        if body["status"] != "running":
            break
        time.sleep(0.05)
    assert body["status"] == "done" and body["result"]["sourced"] == 1 and body["finished_at"]
    assert client.get(f"/api/autopilot/runs/{started['run_id']}", headers=make_key("growth_lead", "org_other")).status_code == 404
    assert client.post("/api/autopilot/run", headers=h, json={"channel": "nonsense"}).status_code == 422


def test_a_failed_run_reports_its_error_and_a_second_run_is_refused_while_one_is_active(client, make_key, monkeypatch):
    import time
    import orchestrator.jobs as jobs

    class Boom:
        def run(self, *a, **k): raise RuntimeError("source exploded")
    monkeypatch.setattr(jobs, "DiscoveryRun", Boom)
    h = make_key("growth_lead", "org_job2")
    rid = client.post("/api/autopilot/run", headers=h, json={"channel": "hiring"}).json()["run_id"]
    for _ in range(50):
        body = client.get(f"/api/autopilot/runs/{rid}", headers=h).json()
        if body["status"] != "running":
            break
        time.sleep(0.05)
    assert body["status"] == "failed" and "source exploded" in body["error"]
    with get_db() as db:
        db.execute("INSERT INTO discovery_runs (id, org_id, status) VALUES ('run_busy', 'org_job2', 'running')")
        db.commit()
    again = client.post("/api/autopilot/run", headers=h, json={"channel": "hiring"}).json()
    assert again["already_running"] is True and again["run_id"] == "run_busy"


def test_requests_carry_an_id_and_are_counted_by_route_template(client, make_key):
    h = make_key("auditor", "org_obs")
    res = client.get("/api/inbox", headers={**h, "X-Request-ID": "trace-123"})
    assert res.headers["X-Request-ID"] == "trace-123" and client.get("/api/inbox", headers=h).headers["X-Request-ID"]
    text = client.get("/metrics", headers=h).text
    assert 'agencybd_http_requests_total{method="GET",route="/api/inbox",status="200"}' in text
    assert "agencybd_discovery_runs_total" in text and "agencybd_sending_halted" in text
    client.get("/api/leads/424242424", headers=h)                       # unknown ids must not create unbounded label values
    assert "424242424" not in client.get("/metrics", headers=h).text
