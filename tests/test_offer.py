"""Fixed-price offer: built from measured findings and your own prices; blanks stay blank and are listed."""

import pytest

from config.settings import settings
from database.db import get_db
from database.models import AuditRunRepository, CompanyRepository, EvidenceRepository
from intel.services import ServiceCatalog
from proposals.offer import build_offer

ORG = "org_offer"


def checked(name="Acme Dental", domain="acme.example", findings=(("tls_certificate_expiring", "high", "The certificate expires in 9 days.", "Renew and automate the certificate.", "security_hardening"),), org=ORG):
    c = CompanyRepository.create_or_get(name, domain, org_id=org)
    rows = []
    for check, sev, text, fix, svc in findings:
        ev = EvidenceRepository.record_evidence("audit", c["id"], "x", "v", "auditors.security", f"https://{domain}", 1.0, org)
        rows.append({"category": "security", "check_id": check, "severity": sev, "finding": text, "fix": fix, "estimated_impact": "i", "service_id": svc,
                     "evidence_value": "v", "confidence": 0.9, "evidence_id": ev["id"]})
    AuditRunRepository.record_run(domain=domain, overall_score=60, summary="s", findings=rows, company_id=c["id"], org_id=org, status="completed")
    return c["id"]


@pytest.fixture(autouse=True)
def agency(monkeypatch):
    monkeypatch.setattr(settings.agency, "name", "Future Builders")
    monkeypatch.setattr(settings.agency, "founder_name", "Rizwan Zafar")
    monkeypatch.setattr(settings.agency, "booking_link", "")
    monkeypatch.setattr(settings.agency, "case_study_metric", "")


def test_an_offer_needs_a_completed_check():
    c = CompanyRepository.create_or_get("Unchecked", "unchecked.example", org_id=ORG)
    with pytest.raises(Exception) as e:
        build_offer(ORG, c["id"])
    assert "Audit this company first" in str(e.value)
    with pytest.raises(LookupError):
        build_offer(ORG, 99999)


def test_prices_you_set_appear_and_prices_you_did_not_set_stay_blank_and_are_listed():
    cid = checked()
    out = build_offer(ORG, cid)
    md = out["markdown"]
    assert "Fixed-price offer for Acme Dental" in md and "From Future Builders, Rizwan Zafar" in md and "The certificate expires in 9 days." in md
    assert "Price: [your fixed price]" in md and "**Total:** [add the total]" in md and "[add your delivery time]" in md
    assert any("Your price for Security hardening" in n for n in out["needs"]) and any("total" in n for n in out["needs"]) and any("booking link" in n for n in out["needs"])
    ServiceCatalog.upsert(ORG, "security_hardening", "Security hardening", "Renew, automate and monitor your certificate.", price_band="EUR 250")
    settings.agency.booking_link = "https://cal.com/future/intro"
    out = build_offer(ORG, cid)
    assert "Renew, automate and monitor your certificate." in out["markdown"] and "Price: EUR 250" in out["markdown"] and "https://cal.com/future/intro" in out["markdown"]
    assert not any("Your price" in n or "booking link" in n for n in out["needs"]) and "[your fixed price]" not in out["markdown"]
    assert any("total" in n for n in out["needs"])                    # it never adds prices for you


def test_the_work_description_falls_back_to_the_measured_fix_not_an_invented_one():
    out = build_offer(ORG, checked("Fix Co", "fix.example"))
    assert "Renew and automate the certificate." in out["markdown"]
    assert any("What you would do for Security hardening" in n for n in out["needs"])


def test_only_the_top_three_services_are_offered_and_info_findings_never_are():
    cid = checked("Big Co", "big.example", findings=(
        ("a", "high", "Finding A.", "Fix A.", "security_hardening"), ("b", "high", "Finding B.", "Fix B.", "performance_engineering"),
        ("c", "medium", "Finding C.", "Fix C.", "seo_optimization"), ("d", "low", "Finding D.", "Fix D.", "a11y_compliance"), ("e", "info", "Just a note.", "None.", "mobile_optimization")))
    out = build_offer(ORG, cid)
    assert out["items"] == 3 and "Just a note." not in out["markdown"] and "Finding D." not in out["markdown"]


def test_a_check_with_nothing_above_info_level_refuses_to_sell():
    cid = checked("Clean Co", "clean.example", findings=(("n", "info", "Nothing much.", "", "seo_optimization"),))
    with pytest.raises(Exception) as e:
        build_offer(ORG, cid)
    assert "nothing honest to sell" in str(e.value)


def test_a_quoted_result_appears_only_when_it_is_set(monkeypatch):
    cid = checked("Proof Co", "proof.example")
    assert "Recent result" not in build_offer(ORG, cid)["markdown"]
    monkeypatch.setattr(settings.agency, "case_study_metric", "Cut load time from 4.1 s to 1.3 s for Brightside Dental")
    assert "Cut load time from 4.1 s to 1.3 s" in build_offer(ORG, cid)["markdown"]


def test_the_api_is_tenant_scoped_and_explains_missing_checks(client, make_key):
    cid = checked("Api Co", "api.example")
    mine, other = make_key("growth_lead", ORG), make_key("growth_lead", "org_offer_other")
    assert client.get(f"/api/companies/{cid}/offer").status_code == 401
    ok = client.get(f"/api/companies/{cid}/offer", headers=mine)
    assert ok.status_code == 200 and ok.json()["filename"] == "Offer_Api_Co.md" and ok.json()["needs"]
    assert client.get(f"/api/companies/{cid}/offer", headers=other).status_code == 404
    bare = CompanyRepository.create_or_get("Bare", "bare.example", org_id=ORG)
    r = client.get(f"/api/companies/{bare['id']}/offer", headers=mine)
    assert r.status_code == 422 and "Audit this company first" in r.text
