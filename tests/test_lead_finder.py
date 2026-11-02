"""Lead Finder: saved searches that find only real, new things, tell the person once, and never invent a website or contact."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from alertdesk import channels, engine as alerts
from database.db import get_db
from database.models import CompanyRepository
from leadfinder import engine, sources

ORG = "org_lf"
NOW = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)      # 15:00 in Karachi


class Resp:
    def __init__(self, status=200, text="{}"):
        self.status_code, self.text = status, text


def opp(title, description="", source="hn", ext="1", fit=0.5):
    with get_db() as db:
        db.execute("INSERT INTO opportunities (org_id, type, source, external_id, title, description, fit_score) VALUES (?, 'hiring_signal', ?, ?, ?, ?, ?)",
                   (ORG, source, ext, title, description, fit))
        db.commit()


# ---------------------------------------------------------------- validation

def test_options_are_checked_with_plain_sentences():
    with pytest.raises(ValueError, match="at least one word"):
        engine.create_search(ORG, "x", "hiring", {"keywords": []})
    with pytest.raises(ValueError, match="1 and 30"):
        engine.create_search(ORG, "x", "new_companies", {"days": 90})
    with pytest.raises(ValueError, match="4 or 5 digits"):
        engine.create_search(ORG, "x", "new_companies", {"sic_codes": ["web"]})
    with pytest.raises(ValueError, match="at least one thing"):
        engine.create_search(ORG, "x", "site_signals", {"signals": ["bogus"]})
    with pytest.raises(ValueError, match="Unknown source"):
        engine.create_search(ORG, "x", "linkedin_scrape", {})
    with pytest.raises(ValueError, match="short name"):
        engine.create_search(ORG, " ", "hiring", {"keywords": ["react"]})
    with pytest.raises(ValueError, match="1 to 168"):
        engine.create_search(ORG, "x", "hiring", {"keywords": ["react"]}, every_hours=0)


def test_a_workspace_can_only_keep_so_many_searches():
    for i in range(engine.MAX_SEARCHES):
        engine.create_search(ORG, f"s{i}", "hiring", {"keywords": ["react"]})
    with pytest.raises(ValueError, match="up to 30"):
        engine.create_search(ORG, "one too many", "hiring", {"keywords": ["react"]})


# ---------------------------------------------------------------- hiring

def test_hiring_matches_whole_words_and_only_reports_what_is_new():
    opp("Senior React developer", ext="a")
    opp("Reactor technician", ext="b")                       # contains "react" but is not the word
    opp("Need a site", "looking for react native help", ext="c")
    s = engine.create_search(ORG, "React work", "hiring", {"keywords": ["react"]})
    first = engine.run_search(ORG, s["id"])
    assert first["total"] == 2 and first["new"] == 2 and first["first_run"]
    assert {h["title"] for h in engine.list_hits(ORG)} == {"Senior React developer", "Need a site"}
    opp("Another React role", ext="d")
    second = engine.run_search(ORG, s["id"])
    assert second["total"] == 3 and second["new"] == 1 and not second["first_run"]       # nothing is announced twice


def test_minimum_fit_filters_weak_matches():
    opp("React lead", ext="a", fit=0.9)
    opp("React helper", ext="b", fit=0.2)
    s = engine.create_search(ORG, "Strong React", "hiring", {"keywords": ["react"], "min_fit": 50})
    assert engine.run_search(ORG, s["id"])["total"] == 1


# ---------------------------------------------------------------- Companies House

REGISTER = {"items": [
    {"company_name": "NORTHERN DENTAL LTD", "company_number": "15000001", "date_of_creation": "2026-10-30", "sic_codes": ["86230"],
     "registered_office_address": {"locality": "Leeds", "postal_code": "LS1 4AB"}},
    {"company_name": "NO NUMBER LTD"},                     # incomplete rows are skipped, never guessed
]}


def test_new_companies_need_a_key_and_say_so(monkeypatch):
    monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)
    s = engine.create_search(ORG, "New UK firms", "new_companies", {"days": 7})
    r = engine.run_search(ORG, s["id"])
    assert r["status"] == "error" and "free Companies House key" in r["detail"] and engine.list_hits(ORG) == []
    assert engine.get_search(ORG, s["id"])["last_status"] == "error"


def test_new_companies_request_and_results(monkeypatch):
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "ch-secret-key-000")
    seen = {}

    def fake(url, timeout=20, headers=None, method="GET", json_body=None, form_body=None, max_bytes=0):
        seen.update(url=url, headers=headers)
        return Resp(200, json.dumps(REGISTER))
    monkeypatch.setattr(sources.SafeFetcher, "safe_fetch", staticmethod(fake))
    s = engine.create_search(ORG, "New UK firms", "new_companies", {"days": 7, "sic_codes": ["86230"], "location": "Leeds"})
    r = engine.run_search(ORG, s["id"])
    assert r["status"] == "ok" and r["new"] == 1
    assert "incorporated_from=" in seen["url"] and "sic_codes=86230" in seen["url"] and "company_status=active" in seen["url"] and seen["headers"]["Authorization"].startswith("Basic ")
    hit = engine.list_hits(ORG)[0]
    assert hit["title"] == "Northern Dental Ltd" and "no website or email is listed" in hit["detail"] and hit["url"].endswith("/company/15000001")
    assert "ch-secret-key" not in json.dumps(engine.list_hits(ORG)) and "ch-secret-key" not in json.dumps(engine.list_searches(ORG))


@pytest.mark.parametrize("status,word", [(401, "rejected the key"), (429, "slow down"), (500, "500")])
def test_register_errors_are_explained(monkeypatch, status, word):
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "k")
    monkeypatch.setattr(sources.SafeFetcher, "safe_fetch", staticmethod(lambda *a, **k: Resp(status)))
    s = engine.create_search(ORG, "x", "new_companies", {})
    r = engine.run_search(ORG, s["id"])
    assert r["status"] == "error" and word in r["detail"]


# ---------------------------------------------------------------- Ireland (open data, no key)

IRISH = {"success": True, "result": {"records": [
    {"company_num": "829320", "company_name": "BARCODEX  LIMITED", "company_type": "LTD", "company_reg_date": "2026-10-29T00:00:00", "company_address_2": None,
     "company_address_3": "Clonlara Road", "company_address_4": "Dublin, Ireland", "eircode": "D22 PK59", "nace_v2_code": "6201"},
    {"company_num": None, "company_name": "NO NUMBER"}, {"company_num": "1", "company_name": " "}]}}


def test_irish_search_text_is_built_only_from_validated_values(monkeypatch):
    seen = {}
    monkeypatch.setattr(sources.SafeFetcher, "safe_fetch", staticmethod(lambda url, **k: (seen.update(url=url, headers=k.get("headers")) or Resp(200, json.dumps(IRISH)))))
    s = engine.create_search(ORG, "Irish", "new_companies_ie", {"days": 7, "sic_codes": ["6201"], "location": "Dublin"})
    r = engine.run_search(ORG, s["id"])
    assert r["status"] == "ok" and r["new"] == 1
    from urllib.parse import parse_qs, urlparse
    sql = parse_qs(urlparse(seen["url"]).query)["sql"][0]
    assert "company_status LIKE 'Normal%'" in sql and "nace_v2_code IN ('6201')" in sql and "ILIKE '%Dublin%'" in sql and "COALESCE" not in sql      # the register's firewall refuses COALESCE
    assert "AgencyBD" in seen["headers"]["User-Agent"]                      # says plainly what it is
    hit = engine.list_hits(ORG)[0]
    assert hit["title"] == "Barcodex Limited" and "CRO number 829320" in hit["detail"] and "no website or email" in hit["detail"] and hit["url"] is None and hit["key"] == "IE:829320"


@pytest.mark.parametrize("bad", ["x' OR 1=1 --", "Dublin'; DROP TABLE t;--", "a%b", "Dub\\lin", "x\n y"])
def test_irish_place_cannot_carry_sql(bad):
    with pytest.raises(ValueError, match="letters, numbers, spaces and hyphens"):
        engine.create_search(ORG, "x", "new_companies_ie", {"location": bad})


def test_irish_codes_and_days_are_checked():
    for bad in (["62012"], ["x"], ["6201'--"]):
        with pytest.raises(ValueError, match="4 digits"):
            engine.create_search(ORG, "x", "new_companies_ie", {"sic_codes": bad})
    with pytest.raises(ValueError, match="1 and 30"):
        engine.create_search(ORG, "x", "new_companies_ie", {"days": 0 or 31})


def test_irish_register_trouble_is_reported_not_hidden(monkeypatch):
    s = engine.create_search(ORG, "Irish", "new_companies_ie", {})
    monkeypatch.setattr(sources.SafeFetcher, "safe_fetch", staticmethod(lambda *a, **k: Resp(403)))
    r = engine.run_search(ORG, s["id"])
    assert r["status"] == "error" and "HTTP 403" in r["detail"] and engine.list_hits(ORG) == []
    monkeypatch.setattr(sources.SafeFetcher, "safe_fetch", staticmethod(lambda *a, **k: Resp(200, json.dumps({"success": False}))))
    assert "could not answer" in engine.run_search(ORG, s["id"])["detail"]


# ---------------------------------------------------------------- site signals from stored checks

def stored_audit(domain, checks, status="completed"):
    company = CompanyRepository.create_or_get(name=domain.split(".")[0].title(), domain=domain, org_id=ORG)
    with get_db() as db:
        run = db.execute("INSERT INTO audit_runs (org_id, company_id, domain, status) VALUES (?, ?, ?, ?)", (ORG, company["id"], domain, status)).lastrowid
        for check, text in checks:
            db.execute("INSERT INTO audit_findings (org_id, audit_run_id, category, check_id, severity, finding) VALUES (?, ?, 'security', ?, 'high', ?)", (ORG, run, check, text))
        db.commit()
    return company


def test_site_signals_read_the_latest_stored_check_of_each_site():
    a = stored_audit("slowdental.ie", [("tls_certificate_expiring", "The certificate expires in 9 days.")])
    stored_audit("fine.ie", [("missing_csp", "No CSP.")])
    stored_audit("old.ie", [("cve_2022_31629", "PHP 7.4 has known vulnerabilities.")])
    s = engine.create_search(ORG, "Fixable", "site_signals", {"signals": ["certificate", "outdated_software"]})
    r = engine.run_search(ORG, s["id"])
    assert r["new"] == 2
    by_title = {h["title"]: h for h in engine.list_hits(ORG)}
    assert set(by_title) == {"Slowdental", "Old"} and "expires in 9 days" in by_title["Slowdental"]["detail"] and by_title["Slowdental"]["data"]["company_id"] == a["id"]
    assert by_title["Slowdental"]["url"] == "https://slowdental.ie"


def test_site_signals_ignore_a_newer_check_that_is_clean_and_unfinished_checks():
    c = stored_audit("fixed.ie", [("no_https", "Plain HTTP.")])
    with get_db() as db:                                                # the site was fixed and re-checked
        db.execute("INSERT INTO audit_runs (org_id, company_id, domain, status) VALUES (?, ?, 'fixed.ie', 'completed')", (ORG, c["id"]))
        db.commit()
    stored_audit("half.ie", [("no_https", "Plain HTTP.")], status="failed")
    s = engine.create_search(ORG, "HTTP", "site_signals", {"signals": ["no_https"]})
    assert engine.run_search(ORG, s["id"])["total"] == 0


# ---------------------------------------------------------------- hits become clients, never with a made-up website

def test_saving_a_hit_without_a_website_keeps_it_and_creates_no_client():
    opp("React developer wanted", ext="z")
    s = engine.create_search(ORG, "React", "hiring", {"keywords": ["react"]})
    engine.run_search(ORG, s["id"])
    hit = engine.list_hits(ORG)[0]
    out = engine.save_to_clients(ORG, hit["id"])
    assert out["lead_id"] is None                                       # no website, so no invented one
    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM leads WHERE org_id = ?", (ORG,)).fetchone()[0] == 0
    assert engine.list_hits(ORG, status="saved")[0]["id"] == hit["id"]
    assert engine.dismiss(ORG, hit["id"]) is False                      # a saved lead cannot be dismissed by accident


def test_attaching_a_website_you_typed_makes_a_client_and_bad_ones_are_refused():
    opp("React developer wanted", ext="z")
    s = engine.create_search(ORG, "React", "hiring", {"keywords": ["react"]})
    engine.run_search(ORG, s["id"])
    hit = engine.list_hits(ORG)[0]
    for bad in ("not a site", "http://", "localhost", "a@b.com"):
        with pytest.raises(ValueError, match="website address"):
            engine.save_to_clients(ORG, hit["id"], bad)
    assert engine.list_hits(ORG, status="new")[0]["id"] == hit["id"]    # a refused attempt changes nothing
    out = engine.save_to_clients(ORG, hit["id"], "https://www.Acme-Dental.ie/contact")
    with get_db() as db:
        lead = db.execute("SELECT * FROM leads WHERE id = ?", (out["lead_id"],)).fetchone()
    assert lead["domain"] == "acme-dental.ie" and lead["source_channel"] == "lead_finder" and lead["source_query"] == "React"


def test_saving_a_site_signal_uses_the_website_your_own_check_already_knows():
    stored_audit("keep.ie", [("no_https", "Plain HTTP.")])
    s = engine.create_search(ORG, "HTTP", "site_signals", {"signals": ["no_https"]})
    engine.run_search(ORG, s["id"])
    out = engine.save_to_clients(ORG, engine.list_hits(ORG)[0]["id"])
    with get_db() as db:
        assert db.execute("SELECT domain FROM leads WHERE id = ?", (out["lead_id"],)).fetchone()["domain"] == "keep.ie"


def test_dismissed_hits_stay_dismissed_when_the_search_runs_again():
    opp("React developer", ext="q")
    s = engine.create_search(ORG, "React", "hiring", {"keywords": ["react"]})
    engine.run_search(ORG, s["id"])
    hit = engine.list_hits(ORG)[0]
    assert engine.dismiss(ORG, hit["id"])
    assert engine.run_search(ORG, s["id"])["new"] == 0
    assert engine.list_hits(ORG, status="new") == [] and engine.list_hits(ORG, status="dismissed")[0]["id"] == hit["id"]


# ---------------------------------------------------------------- schedule and telling the person

def test_a_search_is_due_when_never_run_or_after_its_interval():
    s = engine.create_search(ORG, "React", "hiring", {"keywords": ["react"]}, every_hours=6)
    assert [d["id"] for d in engine.due(NOW)] == [s["id"]]
    engine.run_search(ORG, s["id"])
    ran = datetime.now(timezone.utc)
    assert engine.due(ran + timedelta(hours=5)) == [] and len(engine.due(ran + timedelta(hours=7))) == 1
    engine.update_search(ORG, s["id"], {"active": False})
    assert engine.due(ran + timedelta(hours=7)) == []


@pytest.fixture
def pings(monkeypatch):
    sent = []
    monkeypatch.setattr(channels, "send_ntfy", lambda cfg, text, title="", urgent=False: (sent.append(("ntfy", text, title, urgent)) or (True, "Sent to ntfy.")))
    monkeypatch.setattr(channels, "send_telegram", lambda cfg, text, message_id=None: (sent.append(("telegram", text)) or (True, "ok")))
    monkeypatch.setattr(channels, "ntfy_configured", lambda cfg: True)
    monkeypatch.setattr(channels, "telegram_configured", lambda cfg: False)
    return sent


def test_new_hits_are_announced_once_in_one_short_message(pings):
    for i in range(7):
        opp(f"React job {i}", ext=str(i))
    engine.create_search(ORG, "React", "hiring", {"keywords": ["react"]})
    engine.cycle(NOW)
    assert len(pings) == 1 and "7 new leads" in pings[0][1] and "…and 2 more" in pings[0][1] and pings[0][3] is False        # calm, never urgent
    engine.cycle(NOW + timedelta(minutes=5))
    assert len(pings) == 1                                                                                                      # not repeated


def test_quiet_hours_hold_the_message_until_morning_and_nothing_is_lost(pings):
    opp("React job", ext="1")
    alerts.save_settings(ORG, {"quiet_hours": {"enabled": True, "start": "22:00", "end": "07:00"}})
    engine.create_search(ORG, "React", "hiring", {"keywords": ["react"]})
    night = datetime(2026, 11, 2, 18, 30, tzinfo=timezone.utc)                  # 23:30 in Karachi
    engine.cycle(night)
    assert pings == []
    engine.cycle(night + timedelta(hours=9))                                   # 08:30 in Karachi
    assert len(pings) == 1 and "React job" in pings[0][1]


def test_a_search_with_notifications_off_stays_silent(pings):
    opp("React job", ext="1")
    s = engine.create_search(ORG, "React", "hiring", {"keywords": ["react"]}, notify=False)
    engine.cycle(NOW)
    assert pings == [] and engine.get_search(ORG, s["id"])["new_hits"] == 1


def test_failed_delivery_is_retried_and_without_a_channel_hits_still_appear(monkeypatch):
    opp("React job", ext="1")
    engine.create_search(ORG, "React", "hiring", {"keywords": ["react"]})
    monkeypatch.setattr(channels, "ntfy_configured", lambda cfg: False)
    monkeypatch.setattr(channels, "telegram_configured", lambda cfg: False)
    engine.cycle(NOW)
    assert len(engine.list_hits(ORG, status="new")) == 1 and engine.notify_new(ORG, NOW)["sent"] == 0
    monkeypatch.setattr(channels, "ntfy_configured", lambda cfg: True)
    monkeypatch.setattr(channels, "send_ntfy", lambda *a, **k: (False, "Could not reach ntfy"))
    assert engine.notify_new(ORG, NOW)["sent"] == 0
    monkeypatch.setattr(channels, "send_ntfy", lambda *a, **k: (True, "ok"))
    assert engine.notify_new(ORG, NOW)["sent"] == 1


# ---------------------------------------------------------------- LinkedIn-style links

def test_search_links_are_only_links_and_say_what_they_do():
    links = sources.xray_links("Practice manager", "dental", "Dublin")
    assert len(links) == 5 and all(l["url"].startswith("https://") and l["note"] for l in links)
    assert "site%3Alinkedin.com/in" in links[0]["url"] and "%22Practice%20manager%22" in links[0]["url"]
    with pytest.raises(ValueError, match="who you are looking for"):
        sources.xray_links("  ")


# ---------------------------------------------------------------- API: permissions and tenancy

def test_api_permissions_tenancy_and_errors(client, make_key):
    a, b = make_key("growth_lead", ORG), make_key("growth_lead", "org_lf_other")
    viewer = make_key("auditor", ORG)
    assert client.get("/api/leadfinder/searches").status_code == 401
    made = client.post("/api/leadfinder/searches", headers=a, json={"name": "React", "source": "hiring", "params": {"keywords": ["react"]}})
    assert made.status_code == 200
    sid = made.json()["id"]
    assert client.post("/api/leadfinder/searches", headers=viewer, json={"name": "x", "source": "hiring", "params": {"keywords": ["x"]}}).status_code == 403
    assert client.post("/api/leadfinder/searches", headers=a, json={"name": "x", "source": "hiring", "params": {}}).status_code == 422
    assert client.get("/api/leadfinder/searches", headers=b).json()["searches"] == []
    assert client.post(f"/api/leadfinder/searches/{sid}/run", headers=b).status_code == 404
    assert client.put(f"/api/leadfinder/searches/{sid}", headers=b, json={"active": False}).status_code == 404
    assert client.delete(f"/api/leadfinder/searches/{sid}", headers=b).status_code == 404
    opp("React job", ext="1")
    run = client.post(f"/api/leadfinder/searches/{sid}/run", headers=a).json()
    assert run["new"] == 1
    hits = client.get("/api/leadfinder/hits", headers=a).json()["hits"]
    assert len(hits) == 1 and client.get("/api/leadfinder/hits", headers=b).json()["hits"] == []
    assert client.post(f"/api/leadfinder/hits/{hits[0]['id']}/save", headers=b).status_code == 404
    assert client.get("/api/leadfinder/hits?status=bogus", headers=a).status_code == 422
    assert client.post(f"/api/leadfinder/hits/{hits[0]['id']}/save", headers=a, json={"website": "nope"}).status_code == 422
    assert client.post(f"/api/leadfinder/hits/{hits[0]['id']}/save", headers=a).status_code == 200
    assert client.post(f"/api/leadfinder/hits/{hits[0]['id']}/dismiss", headers=a).status_code == 404
    assert client.put(f"/api/leadfinder/searches/{sid}", headers=a, json={"name": "Renamed", "every_hours": 12}).json()["every_hours"] == 12
    assert client.delete(f"/api/leadfinder/searches/{sid}", headers=a).status_code == 200
    assert client.get("/api/leadfinder/hits", headers=a).json()["hits"] == []


def test_sources_listing_says_which_need_a_key_without_showing_it(client, make_key, monkeypatch):
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "ch-secret-key-000")
    body = client.get("/api/leadfinder/sources", headers=make_key("auditor", ORG))
    assert body.status_code == 200 and "ch-secret-key" not in body.text
    by_id = {s["id"]: s for s in body.json()["sources"]}
    assert by_id["new_companies"]["ready"] and by_id["new_companies"]["needs_key"] == "COMPANIES_HOUSE_API_KEY" and by_id["hiring"]["ready"]
    monkeypatch.delenv("COMPANIES_HOUSE_API_KEY")
    assert not {s["id"]: s for s in client.get("/api/leadfinder/sources", headers=make_key("auditor", ORG)).json()["sources"]}["new_companies"]["ready"]


def test_xray_endpoint_validates(client, make_key):
    h = make_key("auditor", ORG)
    assert client.get("/api/leadfinder/xray?role=owner&industry=dental", headers=h).json()["links"]
    assert client.get("/api/leadfinder/xray?role=%20", headers=h).status_code == 422


def test_places_to_look_are_plain_https_links_with_a_reason(client, make_key):
    body = client.get("/api/leadfinder/places", headers=make_key("auditor", ORG)).json()["places"]
    assert body and all(p["url"].startswith("https://") and p["note"] and p["region"] for p in body)
    assert {p["region"] for p in body} >= {"Pakistan", "Ireland", "Everywhere"}
    assert client.get("/api/leadfinder/places").status_code == 401
