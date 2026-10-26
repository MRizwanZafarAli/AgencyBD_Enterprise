"""Settings: the agency profile (editable, proof-gated, installation-wide) and tenant-scoped data exports."""

import csv
import io
import os

import pytest

from config import agency_profile as profile
from config.settings import settings


@pytest.fixture(autouse=True)
def restore_profile_state(monkeypatch):
    """The profile mutates the live settings object and os.environ; put everything back after each test."""
    attrs = {a: getattr(settings.agency, a) for a in ("name", "founder_name", "founder_title", "tagline", "booking_link", "primary_domain", "case_study_metric", "core_services")}
    envs = {f.env: os.environ.get(f.env) for f in profile.FIELDS if f.env}
    yield
    for a, v in attrs.items():
        setattr(settings.agency, a, v)
    for e, v in envs.items():
        os.environ.pop(e, None) if v is None else os.environ.__setitem__(e, v)
    profile._original_env.clear()
    profile._original_attr.clear()


def test_only_the_super_admin_may_change_the_profile_but_anyone_signed_in_may_read_it(client, make_key):
    admin, lead = make_key("super_admin", "org_ws"), make_key("growth_lead", "org_ws")
    assert client.get("/api/workspace/profile").status_code == 401
    assert client.get("/api/workspace/profile", headers=lead).json()["can_edit"] is False
    assert client.put("/api/workspace/profile/name", headers=lead, json={"value": "Evil Co"}).status_code == 403
    assert client.delete("/api/workspace/profile/name", headers=lead).status_code == 403
    assert client.put("/api/workspace/profile/name", headers=admin, json={"value": "Acme Web Studio"}).status_code == 200
    assert client.get("/api/workspace/profile", headers=admin).json()["can_edit"] is True


def test_a_saved_value_takes_effect_immediately_and_reset_restores_env(client, make_key, monkeypatch):
    admin = make_key("super_admin", "org_ws")
    monkeypatch.setenv("AGENCYBD_SENDER_COMPANY", "From Env Ltd")
    settings.agency.name = "From Env Ltd"
    f = client.put("/api/workspace/profile/name", headers=admin, json={"value": "  Acme   Web Studio "}).json()
    assert f["value"] == "Acme Web Studio" and f["source"] == "settings"
    assert settings.agency.name == "Acme Web Studio" and os.environ["AGENCYBD_SENDER_COMPANY"] == "Acme Web Studio"      # the rest of the app reads these
    out = client.delete("/api/workspace/profile/name", headers=admin).json()
    assert out["reset"] is True and settings.agency.name == "From Env Ltd" and os.environ["AGENCYBD_SENDER_COMPANY"] == "From Env Ltd"
    assert out["field"]["source"] == "env"


def test_it_survives_a_restart(client, make_key):
    admin = make_key("super_admin", "org_ws")
    client.put("/api/workspace/profile/booking_link", headers=admin, json={"value": "cal.com/me/intro"})
    settings.agency.booking_link = ""                       # as if the process had just started with an empty .env
    assert profile.apply_all() >= 1 and settings.agency.booking_link == "https://cal.com/me/intro"


@pytest.mark.parametrize("key,value,message", [
    ("name", "x", "required"), ("sender_name", "", "cannot be blank"), ("booking_link", "ftp://x.com", "web address"), ("booking_link", "notaurl", "web address"),
    ("primary_domain", "not a domain", "domain"), ("sender_address", "short", "required|short"), ("sender_address", "Main Street Leeds", "street number"),
    ("public_base_url", "http://bd.example.com", "https://"), ("core_services", ",".join(f"s{i}" for i in range(15)), "up to 12"),
    ("tagline", "Your site is definitely vulnerable and hacked", "alarming|vulnerable"), ("name", "a\nb", "single line"),
])
def test_values_are_validated(client, make_key, key, value, message):
    admin = make_key("super_admin", "org_ws")
    r = client.put(f"/api/workspace/profile/{key}", headers=admin, json={"value": value})
    assert r.status_code == 422 and any(m in r.json()["detail"] for m in message.split("|"))
    assert client.put("/api/workspace/profile/nonsense", headers=admin, json={"value": "x"}).status_code == 422


def test_the_quoted_result_needs_proof_and_clearing_the_proof_withdraws_it(client, make_key):
    admin = make_key("super_admin", "org_ws")
    r = client.put("/api/workspace/profile/case_study_metric", headers=admin, json={"value": "Cut load time from 4s to 1s for Brightside Dental"})
    assert r.status_code == 422 and "proven" in r.json()["detail"] and settings.agency.case_study_metric != "Cut load time from 4s to 1s for Brightside Dental"
    assert client.put("/api/workspace/profile/case_study_proof", headers=admin, json={"value": "short"}).status_code == 422
    client.put("/api/workspace/profile/case_study_proof", headers=admin, json={"value": "https://acme.example/work/brightside"})
    ok = client.put("/api/workspace/profile/case_study_metric", headers=admin, json={"value": "Cut load time from 4s to 1s for Brightside Dental"})
    assert ok.status_code == 200 and settings.agency.case_study_metric.startswith("Cut load time")
    client.delete("/api/workspace/profile/case_study_proof", headers=admin)                                      # proof removed: the result stops being quoted
    assert settings.agency.case_study_metric == "" and os.environ["AGENCYBD_CASE_STUDY"] == ""
    assert client.put("/api/workspace/profile/case_study_metric", headers=admin, json={"value": "Guaranteed 10x leads"}).status_code == 422


def test_an_unproven_result_from_env_is_flagged_and_can_be_cleared_from_the_page(client, make_key, monkeypatch):
    admin = make_key("super_admin", "org_ws")
    monkeypatch.setenv("AGENCYBD_CASE_STUDY", "Reduced mobile bounce rates by 34%")
    settings.agency.case_study_metric = "Reduced mobile bounce rates by 34%"
    f = next(x for x in client.get("/api/workspace/profile", headers=admin).json()["fields"] if x["key"] == "case_study_metric")
    assert f["warning"] and "no proof" in f["warning"] and f["source"] == "env"
    cleared = client.put("/api/workspace/profile/case_study_metric", headers=admin, json={"value": ""}).json()            # an explicit blank beats .env
    assert cleared["value"] == "" and settings.agency.case_study_metric == "" and cleared["source"] == "settings"


def test_filling_the_legal_footer_clears_the_setup_check_and_reaches_the_footer(client, make_key, monkeypatch):
    admin = make_key("super_admin", "org_ws")
    monkeypatch.delenv("AGENCYBD_SENDER_ADDRESS", raising=False)
    monkeypatch.delenv("AGENCYBD_PUBLIC_BASE_URL", raising=False)
    check = lambda: next(c for c in client.get("/api/system/status", headers=admin).json()["checks"] if c["key"] == "sender_identity")
    assert check()["status"] == "missing" and "Agency profile" in check()["fix"]
    assert client.get("/api/workspace/profile", headers=admin).json()["ready_to_send"] is False
    client.put("/api/workspace/profile/sender_address", headers=admin, json={"value": "12 High Street, Leeds LS1 4AB, UK"})
    client.put("/api/workspace/profile/public_base_url", headers=admin, json={"value": "https://bd.acme.example/"})
    assert check()["status"] == "ok" and os.environ["AGENCYBD_PUBLIC_BASE_URL"] == "https://bd.acme.example"
    assert client.get("/api/workspace/profile", headers=admin).json()["ready_to_send"] is True
    from compliance.footer import ComplianceFooterBuilder
    plain, _, _ = ComplianceFooterBuilder.build_footer(recipient_email="a@b.example", org_id="org_ws", include_lia=False)
    assert "12 High Street" in plain


# ---------------------------------------------------------------- data

def _lead(org, name, domain):
    from database.models import LeadRepository
    return LeadRepository.create_or_get_lead(company_name=name, domain=domain, org_id=org)["id"]


def test_exports_contain_only_this_workspaces_rows_and_defuse_spreadsheet_formulas(client, make_key):
    a, b = make_key("growth_lead", "org_x1"), make_key("growth_lead", "org_x2")
    mine = _lead("org_x1", "=HYPERLINK(\"http://evil\")", "mine.example")
    _lead("org_x2", "Other Tenant Ltd", "theirs.example")
    client.post(f"/api/clients/{mine}/notes", headers=a, json={"kind": "note", "body": "+cmd|' /C calc'!A0"})
    client.post("/api/channels/upwork/records", headers=a, json={"type": "link", "data": {"title": "My saved search", "url": "https://upwork.com/x"}})
    for kind in ("clients", "notes", "channels", "audits"):
        r = client.get(f"/api/workspace/data/export/{kind}", headers=a)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and f"agencybd-{kind}-" in r.headers["content-disposition"]
        assert "Other Tenant" not in r.text and "theirs.example" not in r.text
    rows = list(csv.reader(io.StringIO(client.get("/api/workspace/data/export/clients", headers=a).text)))
    assert rows[0][:3] == ["id", "company", "website"] and rows[1][1].startswith("'=HYPERLINK")                    # formula neutralised
    notes = list(csv.reader(io.StringIO(client.get("/api/workspace/data/export/notes", headers=a).text)))
    assert notes[1][2].startswith("'+cmd")
    assert "My saved search" in client.get("/api/workspace/data/export/channels", headers=a).text
    assert "Other Tenant" in client.get("/api/workspace/data/export/clients", headers=b).text
    assert client.get("/api/workspace/data/export/passwords", headers=a).status_code == 404
    assert client.get("/api/workspace/data/export/clients").status_code == 401


def test_data_summary_counts_this_workspace_and_shows_installation_details_only_to_the_admin(client, make_key):
    a, admin = make_key("growth_lead", "org_x3"), make_key("super_admin", "org_x3")
    _lead("org_x3", "One", "one.example")
    _lead("org_x3", "Two", "two.example")
    _lead("org_x4", "Elsewhere", "elsewhere.example")
    s = client.get("/api/workspace/data/summary", headers=a).json()
    assert s["counts"]["clients"] == 2 and "installation" not in s and set(s["exports"]) == {"clients", "notes", "channels", "audits"}
    inst = client.get("/api/workspace/data/summary", headers=admin).json()["installation"]
    assert inst["database_bytes"] > 0 and "backup_db.py" in inst["backup_command"] and "backups" in inst
