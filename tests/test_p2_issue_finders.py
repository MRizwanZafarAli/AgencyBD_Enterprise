"""P2: passive issue-finder agents. Network sources are stubbed; the behaviour under test is the matching, wording and safety."""

import pytest
from bs4 import BeautifulSoup

from auditors.context import SiteContext
from auditors.exposure import ExposureAuditor
from auditors.vuln import VulnAuditor
from intel.vuln import matcher, sources
from intel.vuln.fingerprint import fingerprint
from intel.vuln.matcher import VulnMatch


def ctx(headers=None, html="<html><title>Acme</title><body>hi</body></html>", **kw):
    return SiteContext(domain="acme.example", url="https://acme.example/", scheme=kw.pop("scheme", "https"), status_code=200, headers=headers or {},
                       html=html, soup=BeautifulSoup(html, "html.parser"), ttfb_ms=100, total_ms=200, **kw)


# ------------------------------------------------------------------ fingerprinting

def test_fingerprint_reads_headers_meta_and_library_urls():
    html = ('<meta name="generator" content="WordPress 6.2.1">'
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>'
            '<script src="/js/bootstrap-4.3.1.min.js"></script>')
    found = {(t.label, t.version): t for t in fingerprint({"Server": "nginx/1.18.0", "X-Powered-By": "PHP/8.1.2"}, html)}
    assert set(found) == {("nginx", "1.18.0"), ("PHP", "8.1.2"), ("WordPress", "6.2.1"), ("jQuery", "3.3.1"), ("Bootstrap", "4.3.1")}
    assert found[("PHP", "8.1.2")].confidence == 0.7


def test_distribution_builds_lower_confidence_because_fixes_are_backported():
    (apache,) = fingerprint({"Server": "Apache/2.4.41 (Ubuntu)"}, "")
    assert apache.backport_risk and apache.confidence < 0.5


def test_nothing_is_reported_when_nothing_is_visible():
    assert fingerprint({"Server": "cloudflare"}, "<html></html>") == []


# ------------------------------------------------------------------ matching and wording

CVES = [{"cve_id": "CVE-2024-4577", "summary": "In PHP versions 8.1.* before 8.1.29 a flaw allows remote code execution.", "cvss": 9.8, "severity": "critical",
         "published": "2024-06-09", "url": "https://nvd.nist.gov/vuln/detail/CVE-2024-4577"},
        {"cve_id": "CVE-2020-0001", "summary": "Minor.", "cvss": 4.3, "severity": "medium", "published": "2020-01-01", "url": "u"},
        {"cve_id": "CVE-2022-9999", "summary": "Old but exploited.", "cvss": 5.0, "severity": "medium", "published": "2022-01-01", "url": "u"}]


@pytest.fixture
def stub_sources(monkeypatch):
    monkeypatch.setattr(sources, "nvd_cves", lambda v, p, ver: CVES if p == "php" else [])
    monkeypatch.setattr(sources, "osv_vulns", lambda e, p, v: [])
    monkeypatch.setattr(sources, "kev_ids", lambda: {"CVE-2022-9999"})


def test_only_exploited_or_high_scoring_cves_are_reported_and_ranked(stub_sources):
    out = matcher.match(fingerprint({"X-Powered-By": "PHP/8.1.2"}, ""))
    ids = [m.cve_id for m in out["matches"]]
    assert ids == ["CVE-2022-9999", "CVE-2024-4577"] and "CVE-2020-0001" not in ids       # KEV first, then CVSS
    assert out["unchecked"] == []


def test_severity_never_reaches_critical_from_a_version_match_alone(stub_sources):
    sev = {m.cve_id: m.severity() for m in matcher.match(fingerprint({"X-Powered-By": "PHP/8.1.2"}, ""))["matches"]}
    assert set(sev.values()) <= {"high", "medium", "low"}


def test_backport_risk_lowers_severity():
    m = VulnMatch("CVE-1", "s", 9.8, False, "PHP", "7.4.3", "sig", 0.4, True, "u", "2024-01-01")
    assert m.severity() == "medium"
    assert VulnMatch("CVE-1", "s", 9.8, False, "PHP", "7.4.3", "sig", 0.7, False, "u", "2024-01-01").severity() == "high"


def test_lookup_failure_is_reported_as_unknown_not_clean(monkeypatch):
    monkeypatch.setattr(sources, "nvd_cves", lambda *a: None)
    monkeypatch.setattr(sources, "kev_ids", lambda: None)
    findings = VulnAuditor.audit(ctx({"X-Powered-By": "PHP/8.1.2"}))
    assert [f.check_id for f in findings] == ["vuln_lookup_unavailable", "vuln_lookup_unavailable"]
    assert all(f.severity == "info" and "not a clean result" in f.estimated_impact for f in findings)


def test_vuln_findings_say_potentially_affected_and_cite_the_signal(stub_sources):
    findings = VulnAuditor.audit(ctx({"X-Powered-By": "PHP/8.1.2"}))
    top = next(f for f in findings if f.check_id == "cve_cve-2024-4577")
    assert "potentially affected" in top.estimated_impact.lower() and "X-Powered-By header" in top.evidence_value
    for f in findings:
        for banned in ("is vulnerable", "hacked", "breach", "compromised"):
            assert banned not in (f.finding + f.fix + f.estimated_impact).lower()


def test_sources_only_talk_to_their_three_fixed_hosts():
    with pytest.raises(ValueError):
        sources._get_json("https://evil.example/cves", "k")


# ------------------------------------------------------------------ exposure (passive)

def test_exposure_findings():
    robots = "User-agent: *\nDisallow: /admin/\nDisallow: /backup\nDisallow: /cart"
    found = {f.check_id: f for f in ExposureAuditor.audit(ctx({"Server": "Apache/2.4.41 (Ubuntu)", "Set-Cookie": "sid=abc; Path=/"},
                                                              html="<html><title>Index of /</title></html>", robots_txt=robots, security_txt=False))}
    assert set(found) == {"version_disclosure", "missing_security_txt", "robots_lists_sensitive_paths", "directory_listing", "cookie_flags"}
    assert found["directory_listing"].severity == "high" and "/admin" in found["robots_lists_sensitive_paths"].evidence_value


def test_exposure_is_silent_when_unknown_or_clean():
    assert ExposureAuditor.audit(ctx({"Server": "cloudflare", "Set-Cookie": "sid=a; Secure; HttpOnly; SameSite=Lax"}, security_txt=None, robots_txt=None)) == []


# ------------------------------------------------------------------ content guard, drafter, advisor, report

def test_content_guard_blocks_alarming_or_certain_security_language():
    from compliance.content_guard import check_outreach_text as chk
    assert chk("Quick note", "Your server runs PHP 8.1.2, which is listed in public vulnerability records. Worth confirming the patch level.") is None
    for body in ("Hackers could breach your site.", "Your website is vulnerable to attack.", "You are currently vulnerable.",
                 "Fix this within 48 hours before it's too late.", "Ransomware gangs target sites like yours."):
        assert chk("Heads up", body), body


def test_workflow_refuses_to_send_alarming_text(monkeypatch):
    from workflows.sequence import OutreachSequenceWorkflow, SequenceStep
    res = OutreachSequenceWorkflow().execute_step("org_x", "a@b.example", SequenceStep(1, 0, "Urgent", "Hackers will breach you."), country_code="US")
    assert res.status == "blocked_by_policy" and "alarming" in res.reason


def test_drafter_hedges_vulnerability_findings_and_never_copies_public_record_text():
    from agents.outreach_drafter import draft_from_brief
    brief = {"digital_health": {"top_findings": [
        {"finding": "PHP 8.1.2 (seen in X-Powered-By header: PHP/8.1.2) is listed as affected by CVE-2024-4577: an attacker can run code.",
         "severity": "high", "measured": "X-Powered-By | CVE-2024-4577 (https://nvd.nist.gov/vuln/detail/CVE-2024-4577)", "evidence_ids": [1]}]}}
    d = draft_from_brief(brief, "Dana", "acme.example")
    assert "may already be patched" in d["body"] and "CVE-2024-4577" in d["body"] and "attacker" not in d["body"]
    from compliance.content_guard import check_outreach_text
    assert check_outreach_text(d["subject"], d["body"]) is None


def _seed_audit(org, domain="acme.example"):
    from database.models import AuditRunRepository, CompanyRepository, EvidenceRepository
    company = CompanyRepository.create_or_get("Acme", domain, org_id=org)
    findings = []
    for cid, sev, svc, text in (("missing_csp", "medium", "security_hardening", "No Content-Security-Policy header."),
                                ("slow_ttfb", "high", "performance_engineering", "Slow first byte."),
                                ("x", "info", "devops_sre", "Informational.")):
        ev = EvidenceRepository.record_evidence("audit", company["id"], text, "m", "auditors.x", f"https://{domain}", 1.0, org)
        findings.append({"category": "security", "check_id": cid, "severity": sev, "finding": text, "fix": "Fix it.", "estimated_impact": "i",
                         "service_id": svc, "evidence_value": "m", "confidence": 1.0, "evidence_id": ev["id"]})
    AuditRunRepository.record_run(domain=domain, overall_score=70, summary="s", findings=findings, company_id=company["id"], org_id=org, status="completed")
    return company


def test_advisor_groups_findings_by_service_and_cites_evidence():
    from intel import advisor
    c = _seed_audit("org_adv")
    out = advisor.recommendations(c["id"], "org_adv")
    keys = [r["service_key"] for r in out["recommendations"]]
    assert keys == ["performance_engineering", "security_hardening"]            # info findings excluded, higher score first
    assert all(r["evidence_ids"] and r["price_band"] is None for r in out["recommendations"])   # no invented prices


def test_advisor_requires_an_audit():
    from config.honesty import PreconditionFailedError
    from database.models import CompanyRepository
    from intel import advisor
    c = CompanyRepository.create_or_get("Unaudited", "unaudited.example", org_id="org_adv")
    with pytest.raises(PreconditionFailedError):
        advisor.recommendations(c["id"], "org_adv")


def test_ai_advice_drops_uncited_and_off_catalog_items(monkeypatch):
    import json
    from intel import advisor
    from llm.client import LLMGateway
    c = _seed_audit("org_adv2")
    ids = [f["evidence_id"] for r in advisor.recommendations(c["id"], "org_adv2")["recommendations"] for f in r["findings"]]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-1234567890")
    reply = {"recommendations": [
        {"title": "Harden security headers", "why_it_matters": "Browsers get no policy.", "evidence_ids": [ids[0]], "service_key": "security_hardening"},
        {"title": "Invented win", "why_it_matters": "x", "evidence_ids": [99999], "service_key": "security_hardening"},
        {"title": "Unknown service", "why_it_matters": "x", "evidence_ids": [ids[0]], "service_key": "time_travel"}]}
    monkeypatch.setattr(LLMGateway, "_call_anthropic", classmethod(lambda cls, p, s, m, t, mx: {"text": json.dumps(reply), "tokens_in": 1, "tokens_out": 1, "model": "t", "provider": "anthropic"}))
    out = advisor.advise(c["id"], "org_adv2")
    assert [r["title"] for r in out["ai_recommendations"]] == ["Harden security headers"] and out["ai_dropped"] == 2


def test_advice_endpoints_are_tenant_scoped(client, make_key):
    c = _seed_audit("org_adv3")
    assert client.get(f"/api/companies/{c['id']}/advice", headers=make_key("auditor", "org_adv3")).status_code == 200
    assert client.get(f"/api/companies/{c['id']}/advice", headers=make_key("auditor", "org_other")).status_code == 422   # no audit visible to another tenant


def test_report_lists_cve_findings_under_security_watch(tmp_path):
    from datetime import datetime, timezone
    from reports.client_report import ClientReport
    audit = {"status": "completed", "domain": "acme.example", "overall_score": 60, "audit_id": 1, "checks_run": ["vulnerability_watch"], "checks_skipped": [], "summary": "s",
             "findings": [{"category": "security", "check_id": "cve_cve-2024-4577", "severity": "high", "finding": "PHP 8.1.2 is listed as affected by CVE-2024-4577.",
                           "fix": "Update.", "evidence_value": "X-Powered-By header", "service_id": "security_hardening", "confidence": 0.7}]}
    r = ClientReport(str(tmp_path))
    vulns = [{"cve_id": "CVE-2024-4577", "severity": "high", "summary": audit["findings"][0]["finding"], "signal": "X-Powered-By header"}]
    html = r.render_html({"audit": audit, "comparison": None, "vulnerabilities": vulns, "generated_at": datetime.now(timezone.utc)}, "org_adv")
    assert "Security watch" in html and "Potentially affected, not confirmed" in html


# ------------------------------------------------------------------ nightly re-scan

def _lead_with_baseline(org, cves=()):
    from database.models import AuditRunRepository, CompanyRepository, EvidenceRepository, LeadRepository
    lead = LeadRepository.create_or_get_lead("Acme", "acme.example", source_channel="hiring_intent", org_id=org)
    company = CompanyRepository.create_or_get("Acme", "acme.example", org_id=org)
    findings = []
    for cve in cves:
        ev = EvidenceRepository.record_evidence("audit", company["id"], "x", "v", "auditors.security", "https://acme.example", 1.0, org)
        findings.append({"category": "security", "check_id": f"cve_{cve.lower()}", "severity": "high", "finding": "f", "fix": "x", "estimated_impact": "i",
                         "service_id": "security_hardening", "evidence_value": "v", "confidence": 0.7, "evidence_id": ev["id"]})
    AuditRunRepository.record_run(domain="acme.example", overall_score=80, summary="s", findings=findings, company_id=company["id"], org_id=org, status="completed")
    return lead


def _fake_audit(monkeypatch, cves, kev_text=""):
    from auditors.engine import WebsiteDoctorEngine
    findings = [{"category": "security", "check_id": f"cve_{c.lower()}", "severity": "high", "finding": f"PHP 8.1.2 is listed as affected by {c}.",
                 "estimated_impact": kev_text + "Potentially affected.", "fix": "x", "evidence_value": "v", "service_id": "security_hardening"} for c in cves]
    monkeypatch.setattr(WebsiteDoctorEngine, "run_audit", classmethod(lambda cls, d, company_id=None, org_id="org_default": {"status": "completed", "findings": findings}))


def test_rescan_opens_a_work_item_only_for_a_newly_matching_cve(monkeypatch):
    from workflows import rescan
    from workflows.inbox import WorkItemRepository
    _lead_with_baseline("org_rs", cves=["CVE-2024-0001"])
    _fake_audit(monkeypatch, ["CVE-2024-0001", "CVE-2026-9999"], kev_text="Listed by CISA as exploited in the wild. ")
    out = rescan.rescan_org("org_rs", delay=0)
    assert [a["cve"] for a in out["alerts"]] == ["CVE-2026-9999"] and out["alerts"][0]["kev"] is True
    item = WorkItemRepository.list_open("org_rs")[0]
    assert item["kind"] == "new_cve" and item["priority"] == 90 and "confirm the real patch level" in item["detail"]
    assert rescan.rescan_org("org_rs", delay=0)["alerts"] == []         # running again does not duplicate


def test_rescan_never_alerts_on_a_baseline_or_an_unreachable_site(monkeypatch):
    from auditors.engine import WebsiteDoctorEngine
    from database.models import CompanyRepository, LeadRepository
    from workflows import rescan
    LeadRepository.create_or_get_lead("NoBaseline", "nobase.example", org_id="org_rs2")
    CompanyRepository.create_or_get("NoBaseline", "nobase.example", org_id="org_rs2")
    out = rescan.rescan_org("org_rs2", delay=0)
    assert out["alerts"] == [] and out["skipped"][0]["reason"] == "no completed baseline audit"
    _lead_with_baseline("org_rs3")
    monkeypatch.setattr(WebsiteDoctorEngine, "run_audit", classmethod(lambda cls, d, company_id=None, org_id="x": {"status": "unreachable", "findings": []}))
    out = rescan.rescan_org("org_rs3", delay=0)
    assert out["alerts"] == [] and out["skipped"][0]["reason"] == "unreachable this time"


def test_rescan_runs_at_most_once_per_day(monkeypatch):
    from workflows import rescan
    monkeypatch.setattr(rescan, "rescan_org", lambda org, **kw: {"org_id": org, "scanned": 0, "alerts": [], "skipped": []})
    assert rescan.run_if_due() is not None
    assert rescan.run_if_due() is None
    import time
    assert rescan.run_if_due(now=time.time() + 25 * 3600) is not None
