"""
Opportunity Radar: connectors parse REAL recorded API responses (tests/fixtures/*, captured from the live public APIs on
2026-10-13), fit scoring is transparent, scans log every outcome, and the Upwork OAuth flow is exercised end to end
against a fake Upwork.
"""

import json
import time
from pathlib import Path

import pytest

from connectors import oauth, upwork
from connectors.base import ConnectorNotConfigured, OpportunityItem
from connectors.hn import HackerNewsConnector, latest_hiring_thread, parse_thread
from connectors.oauth import TokenStore, sign_state, verify_state
from connectors.remoteok import RemoteOKConnector, parse_rows
from connectors.sam_gov import SamGovConnector, parse_notices as parse_sam
from connectors.ted import TedConnector, parse_notices as parse_ted
from connectors.uk_fts import UkFindATenderConnector, parse_releases
from connectors.upwork import UpworkConnector, parse_graphql
from connectors.wwr import WeWorkRemotelyConnector, parse_feed
from database.db import get_db
from database.models import OpportunityRepository
from net.fetcher import FetchResult
from portfolio.library import PortfolioLibrary
from radar.engine import OpportunityRadarEngine, purge_expired
from radar.fit import agency_profile_terms, score_opportunity

FIX = Path(__file__).parent / "fixtures"
load = lambda name: json.loads((FIX / name).read_text())


# ============================ Hacker News ============================

def test_hn_picks_the_newest_hiring_thread_not_the_hired_thread_or_an_old_one():
    threads = load("hn.json")["threads"]
    latest = latest_hiring_thread(threads)
    assert latest["title"] == "Ask HN: Who is hiring? (October 2026)"
    assert latest_hiring_thread({"hits": []}) is None
    assert latest_hiring_thread({"hits": [{"title": "Ask HN: Who wants to be hired? (October 2026)", "created_at": "2026-10-01"}]}) is None


def test_hn_turns_each_comment_into_one_clean_posting():
    items = parse_thread(load("hn.json")["thread"], limit=50)
    assert len(items) == 5 and all(i.type == "hiring_signal" and i.source == "hn" for i in items)
    first = items[0]
    assert first.company_name.startswith("PrairieLearn") and first.url.startswith("https://news.ycombinator.com/item?id=")
    assert "&#x2F;" not in first.description and "<p>" not in first.description and "https://www.prairielearn.com" in first.description
    assert all(i.external_id.startswith("hn_") and i.posted_at for i in items)
    assert any(i.budget_max for i in items), "salary ranges such as '$170k to $230k' should be parsed"
    assert len(parse_thread(load("hn.json")["thread"], limit=2)) == 2


def test_hn_connector_reads_the_thread_through_the_safe_client(web):
    fx = load("hn.json")
    web["hn.algolia.com/api/v1/search_by_date"] = json.dumps(fx["threads"])
    web[f"hn.algolia.com/api/v1/items/{fx['thread']['id']}"] = json.dumps(fx["thread"])
    items = HackerNewsConnector().fetch()
    assert len(items) == 5 and items[0].metadata["thread"].startswith("Ask HN: Who is hiring?")


# ============================ We Work Remotely / RemoteOK ============================

def test_wwr_feed():
    items = parse_feed((FIX / "wwr.xml").read_text())
    assert len(items) == 2 and all(i.source == "wwr" and i.url.startswith("https://weworkremotely.com/remote-jobs/") for i in items)
    assert items[0].company_name and ":" not in items[0].title[:1] and items[0].posted_at.startswith("2026-")
    assert "<img" not in items[0].description


def test_wwr_connector_dedupes_across_feeds(web):
    for feed in ("remote-programming-jobs", "remote-devops-sysadmin-jobs", "remote-full-stack-programming-jobs"):
        web[f"weworkremotely.com/categories/{feed}.rss"] = (FIX / "wwr.xml").read_text()
    assert len(WeWorkRemotelyConnector().fetch()) == 2


def test_remoteok_rows():
    rows = load("remoteok.json")
    items = parse_rows(rows)
    assert len(items) == 2, "the legal-notice row is skipped"
    assert all(i.type == "hiring_signal" and i.fit_score is None and i.url for i in items), "connectors never invent a fit score"
    assert "<" not in items[0].description and "RemoteOK" in items[0].metadata["attribution"]


# ============================ tenders ============================

def test_ted_prefers_english_and_flags_other_languages():
    items = parse_ted(load("ted.json"))
    assert len(items) == 3 and all(i.type == "tender" and i.source == "ted" and i.url.startswith("https://ted.europa.eu/en/notice/") for i in items)
    assert any("non_english_notice" in i.risk_flags for i in items) or all(i.metadata["language"] == "eng" for i in items)
    english = parse_ted({"notices": [{"publication-number": "1-2026", "notice-title": {"fra": "Titre", "eng": "English title"},
                                      "buyer-name": {"eng": ["City Council"]}, "deadline-receipt-tender-date-lot": ["2026-12-01+01:00"],
                                      "estimated-value-lot": [250000.0], "classification-cpv": ["72200000"]}]})[0]
    assert english.title == "English title" and english.company_name == "City Council" and english.budget_max == 250000.0 and english.risk_flags == []
    assert english.deadline == "2026-12-01+01:00" and english.skills_required == ["CPV 72200000"]


def test_ted_connector_posts_a_cpv_72_query(web, monkeypatch):
    sent = {}
    from net.fetcher import SafeFetcher
    orig = SafeFetcher.safe_fetch.__func__

    def spy(cls, url, **kw):
        sent.update(kw, url=url)
        return orig(cls, url, **kw)
    monkeypatch.setattr(SafeFetcher, "safe_fetch", classmethod(spy))
    web["api.ted.europa.eu/v3/notices/search"] = json.dumps(load("ted.json"))
    assert len(TedConnector().fetch()) == 3
    assert sent["method"] == "POST" and "classification-cpv=72*" in sent["json_body"]["query"] and "publication-date>=" in sent["json_body"]["query"]


def test_uk_find_a_tender_only_keeps_it_services():
    data = load("fts.json")
    assert parse_releases(data) == [], "the sample notices are healthcare tenders (CPV 85...), correctly excluded"
    every = parse_releases(data, only_it=False)
    assert len(every) == 3
    first = every[0]
    assert first.url == f"https://www.find-tender.service.gov.uk/Notice/{data['releases'][0]['id']}" and first.currency == "GBP"
    assert first.budget_max and first.deadline and first.company_name
    synthetic = {"releases": [{"id": "000001-2026", "ocid": "ocds-x-1", "date": "2026-10-12", "buyer": {"name": "Council"},
                               "tender": {"title": "Website rebuild", "description": "d", "items": [{"classification": {"id": "72212000"}}],
                                          "value": {"amount": 90000, "currency": "GBP"}, "tenderPeriod": {"endDate": "2026-11-01T12:00:00Z"}}}]}
    assert [i.title for i in parse_releases(synthetic)] == ["Website rebuild"]


def test_uk_connector_follows_pagination(web):
    page1 = {"releases": [{"id": "1-2026", "tender": {"title": "A", "items": [{"classification": {"id": "72000000"}}]}}],
             "links": {"next": "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?cursor=abc"}}
    web["www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"] = json.dumps(page1)
    assert [i.title for i in UkFindATenderConnector().fetch(limit=50)][:1] == ["A"]


def test_sam_gov_needs_a_key_and_sends_the_required_parameters(web, monkeypatch):
    monkeypatch.delenv("SAM_GOV_API_KEY", raising=False)
    with pytest.raises(ConnectorNotConfigured):
        SamGovConnector().fetch()
    monkeypatch.setenv("SAM_GOV_API_KEY", "key-1234567890")
    seen = []
    from net.fetcher import SafeFetcher
    monkeypatch.setattr(SafeFetcher, "safe_get", classmethod(lambda cls, url, **kw: (seen.append(url) or (200, json.dumps({"opportunitiesData": []}), {}))))
    SamGovConnector().fetch()
    assert len(seen) == 3 and all("postedFrom=" in u and "postedTo=" in u and "ncode=5415" in u for u in seen)


def test_sam_gov_parsing_follows_the_documented_shape():
    items = parse_sam({"opportunitiesData": [{"noticeId": "abc123", "title": "Cloud migration support", "solicitationNumber": "W911-26-R-0001",
                                              "fullParentPathName": "DEPT OF DEFENSE.ARMY", "postedDate": "2026-10-05", "type": "Solicitation",
                                              "naicsCode": "541512", "responseDeadLine": "2026-11-05T17:00:00-05:00", "uiLink": "https://sam.gov/opp/abc123/view",
                                              "officeAddress": {"city": "Fort Eustis", "state": "VA"},
                                              "pointOfContact": [{"fullName": "A. Officer", "email": "a@army.mil"}],
                                              "description": "https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=abc123"}]})
    assert items[0].title == "Cloud migration support" and items[0].deadline.startswith("2026-11-05") and "requires_sam_registration" in items[0].risk_flags
    assert "Fort Eustis" in items[0].description and items[0].metadata["description_url"].startswith("https://api.sam.gov")


# ============================ fit scoring ============================

def test_no_profile_means_no_score_not_a_fake_one():
    fit = score_opportunity("React dashboard", "We need a React and Python dashboard built with clear tests, docs, weekly demos and a fixed spring deadline.", "marketplace", None, set())
    assert fit.score is None and "add services and portfolio" in fit.reasons[0]


def test_fit_comes_from_the_agencys_own_profile():
    profile = {"react", "python", "fastapi"}
    strong = score_opportunity("React + FastAPI dashboard", "We need senior engineers for a React frontend and FastAPI backend with Python services, "
                               "solid testing, clear documentation, weekly demos and a fixed deadline in spring.", "marketplace", 9000, profile)
    weak = score_opportunity("Wedding photographer", "Looking for a photographer for a summer wedding with flowers, cake, music, decorations, "
                             "catering and a lively dance floor for all our guests.", "marketplace", None, profile)
    assert strong.score > weak.score and "react" in strong.reasons[0] and "Nothing in the post matches" in weak.reasons[0]
    assert strong.risk_flags == []


@pytest.mark.parametrize("text,flag", [("Pay outside the platform via WhatsApp please", "off_platform_contact"),
                                       ("This is unpaid but great for exposure", "unpaid_or_equity_only"),
                                       ("Need it done within 24 hours", "unrealistic_timeline"),
                                       ("Guaranteed returns on this crypto airdrop", "scam_signals"),
                                       ("Candidates must be located in Texas, US citizens only", "requires_local_presence")])
def test_risk_flags_reduce_the_score(text, flag):
    base = "We need a Python developer to build an API with careful testing and documentation for our team. "
    clean = score_opportunity("Python API", base, "marketplace", 5000, {"python", "api"})
    risky = score_opportunity("Python API", base + text, "marketplace", 5000, {"python", "api"})
    assert flag in risky.risk_flags and risky.score < clean.score


def test_generic_words_do_not_count_as_skill_matches():
    PortfolioLibrary.add_asset("org_gen", "Case", "Built web development services and software engineering solutions for a client with strong measurable results.",
                               services=["web development"], tech=["FastAPI"])
    terms = agency_profile_terms("org_gen")
    assert "fastapi" in terms and not ({"development", "web", "software", "engineering", "services"} & terms)
    fit = score_opportunity("Senior software engineer", "Senior software development engineer needed for web services work on our platform with strong experience " * 2, "hiring_signal", None, terms)
    assert fit.score == 0.0 and "Nothing in the post matches" in fit.reasons[0]


def test_salaries_on_job_posts_are_not_presented_as_budgets():
    fit = score_opportunity("Python dev", "Python engineer wanted for our product team, salary $170k to $230k, with benefits and equity included today.", "hiring_signal", 230000, {"python"})
    assert any("employee pay" in r for r in fit.reasons) and not any(r.startswith("Budget stated") for r in fit.reasons)
    project = score_opportunity("Python API", "Need a Python API built with tests and docs, budget $9,000, delivered over six weeks by a small team.", "marketplace", 9000, {"python"})
    assert any(r.startswith("Budget stated") for r in project.reasons)


def test_vague_posts_and_budget_floor(monkeypatch):
    assert "vague_scope" in score_opportunity("Dev needed", "Need dev asap", "marketplace", None, {"dev"}).risk_flags
    assert "vague_scope" not in score_opportunity("RFP", "short", "tender", None, {"dev"}).risk_flags, "tenders are formal, terse notices"
    monkeypatch.setenv("AGENCYBD_MIN_PROJECT_BUDGET", "5000")
    assert "below_budget_floor" in score_opportunity("API", "Build a python api with tests and docs for our team today now please " * 2, "marketplace", 800, {"python"}).risk_flags


def test_profile_terms_come_from_services_and_portfolio():
    from intel.services import ServiceCatalog
    assert agency_profile_terms("org_fit") == set()
    PortfolioLibrary.add_asset("org_fit", "Booking rebuild", "Rebuilt a legacy booking platform with FastAPI and Next.js for a logistics client, cutting load time.",
                               services=["web development"], tech=["FastAPI", "Next.js"])
    ServiceCatalog.upsert("org_fit", "seo_optimization", "SEO", "Technical audit; schema markup")
    terms = agency_profile_terms("org_fit")
    assert {"fastapi", "next.js", "schema", "markup"} <= terms
    assert agency_profile_terms("org_other") == set(), "profiles are per tenant"


# ============================ radar engine ============================

class Fake:
    def __init__(self, name, items=None, error=None, max_fetch=100):
        self.source_name, self._items, self._error, self.max_fetch = name, items or [], error, max_fetch

    def fetch(self, query=None, limit=20, org_id=None):
        if self._error:
            raise self._error
        return self._items

    def check_health(self, org_id=None):
        return {"source": self.source_name, "status": "ready"}


def job(i, text, source="remoteok", **kw):
    return OpportunityItem(type=kw.pop("type", "hiring_signal"), source=source, external_id=f"id{i}", title=f"Job {i}", description=text, url=f"https://x.example/{i}", **kw)


def test_scan_keeps_the_best_fits_and_explains_them():
    PortfolioLibrary.add_asset("org_r", "Case", "Built a Python and React analytics dashboard for a logistics client and cut report time significantly.", tech=["Python", "React"])
    items = [job(1, "wedding photography with flowers and cake for guests " * 3), job(2, "senior python and react engineer for analytics dashboards " * 3), job(3, "react python team " * 8)]
    out = OpportunityRadarEngine([Fake("remoteok", items)]).scan_all_sources(limit_per_source=2, org_id="org_r")
    assert [o["title"] for o in out] == ["Job 2", "Job 3"] or [o["title"] for o in out] == ["Job 3", "Job 2"]
    assert all(o["fit_score"] > 0 and o["fit_reasons"] and o["url"].startswith("https://x.example/") for o in out)
    listed = OpportunityRepository.list_opportunities(org_id="org_r")
    assert [o["fit_score"] for o in listed] == sorted((o["fit_score"] for o in listed), reverse=True)


def test_scan_without_a_profile_stores_unscored_items_in_source_order():
    out = OpportunityRadarEngine([Fake("remoteok", [job(i, "some description " * 10) for i in range(5)])]).scan_all_sources(limit_per_source=3, org_id="org_np")
    assert len(out) == 3 and all(o["fit_score"] is None for o in out) and "add services" in out[0]["fit_reasons"][0]


def test_every_outcome_is_logged_and_nothing_is_swallowed():
    engine = OpportunityRadarEngine([Fake("hn", [job(1, "x " * 30, source="hn")]), Fake("ted", error=RuntimeError("TED returned HTTP 503")),
                                     Fake("sam_gov", error=ConnectorNotConfigured("Set SAM_GOV_API_KEY")), Fake("wwr", []),
                                     Fake("upwork", error=ConnectorNotConfigured("Upwork is not connected for this workspace."))])
    engine.scan_all_sources(org_id="org_log")
    status = {s["source"]: s["last_run"] for s in OpportunityRadarEngine.source_status("org_log", engine.connectors)}
    assert status["hn"]["status"] == "ok" and status["hn"]["stored"] == 1
    assert status["ted"]["status"] == "error" and "503" in status["ted"]["detail"]
    assert status["sam_gov"]["status"] == "not_configured" and "SAM_GOV_API_KEY" in status["sam_gov"]["detail"]
    assert status["wwr"]["status"] == "empty" and status["upwork"]["status"] == "not_connected"


def test_one_failing_source_does_not_stop_the_others():
    engine = OpportunityRadarEngine([Fake("ted", error=RuntimeError("down")), Fake("hn", [job(1, "x " * 30, source="hn")])])
    assert len(engine.scan_all_sources(org_id="org_iso")) == 1


def test_rescans_do_not_duplicate_and_no_invented_rows_exist():
    engine = OpportunityRadarEngine([Fake("remoteok", [job(1, "x " * 30)])])
    a, b = engine.scan_all_sources(org_id="org_idem"), engine.scan_all_sources(org_id="org_idem")
    assert a[0]["id"] == b[0]["id"] and len(OpportunityRepository.list_opportunities(org_id="org_idem")) == 1


def test_upwork_cache_window_is_enforced():
    fresh = OpportunityRepository.create_opportunity("marketplace", "upwork", "fresh", "d", external_id="u1", org_id="org_pw")
    old = OpportunityRepository.create_opportunity("marketplace", "upwork", "old", "d", external_id="u2", org_id="org_pw")
    kept = OpportunityRepository.create_opportunity("marketplace", "upwork", "old but drafted", "d", external_id="u3", org_id="org_pw")
    other = OpportunityRepository.create_opportunity("hiring_signal", "remoteok", "old other source", "d", external_id="r1", org_id="org_pw")
    with get_db() as db:
        db.execute("UPDATE opportunities SET created_at = datetime('now', '-30 hours') WHERE id IN (?, ?, ?)", (old["id"], kept["id"], other["id"]))
        db.execute("UPDATE opportunities SET status = 'drafted' WHERE id = ?", (kept["id"],))
        db.commit()
    assert purge_expired("org_pw") == 1
    titles = {o["title"] for o in OpportunityRepository.list_opportunities(org_id="org_pw")}
    assert titles == {"fresh", "old but drafted", "old other source"}


# ============================ Upwork OAuth ============================

@pytest.fixture
def upwork_env(monkeypatch):
    monkeypatch.setenv("UPWORK_CLIENT_ID", "client-abc")
    monkeypatch.setenv("UPWORK_CLIENT_SECRET", "secret-xyz")
    monkeypatch.setenv("UPWORK_REDIRECT_URI", "https://agency.example/api/connectors/upwork/callback")


@pytest.fixture
def fake_upwork(web, upwork_env, monkeypatch):
    """Serves Upwork's token endpoint and GraphQL; records what we sent."""
    calls = []
    from net.fetcher import SafeFetcher
    orig = SafeFetcher.safe_fetch.__func__

    def spy(cls, url, **kw):
        if "upwork.com/api/v3/oauth2/token" in url:
            calls.append(("token", kw["form_body"]))
            n = len([c for c in calls if c[0] == "token"])
            return FetchResult(200, json.dumps({"access_token": f"access-{n}", "refresh_token": f"refresh-{n}", "expires_in": 3600, "scope": "r"}), {}, url, 50)
        if "api.upwork.com/graphql" in url:
            calls.append(("graphql", kw))
            return FetchResult(200, json.dumps(calls_state["graphql"]), {}, url, 80)
        return orig(cls, url, **kw)
    calls_state = {"graphql": {"data": {"marketplaceJobPostingsSearch": {"edges": [
        {"node": {"id": "j1", "title": "Build FastAPI backend", "description": "Need a senior Python engineer " * 4, "createdDateTime": "2026-10-13T09:00:00Z",
                  "ciphertext": "~01abc", "amount": {"rawValue": "4000", "currency": "USD"}, "skills": [{"name": "Python"}, {"name": "FastAPI"}]}}]}}}}
    monkeypatch.setattr(SafeFetcher, "safe_fetch", classmethod(spy))
    return calls, calls_state


def test_state_is_signed_expiring_and_bound_to_the_provider(monkeypatch):
    state = sign_state("org_a", "upwork")
    assert verify_state(state, "upwork") == "org_a"
    assert verify_state(state, "other") is None
    assert verify_state(state[:-2] + "00", "upwork") is None and verify_state("garbage", "upwork") is None
    monkeypatch.setattr(oauth.time, "time", lambda: time.time() + 3600)
    assert verify_state(state, "upwork") is None


def test_unconfigured_upwork_is_reported_not_faked(monkeypatch):
    for v in ("UPWORK_CLIENT_ID", "UPWORK_CLIENT_SECRET", "UPWORK_REDIRECT_URI"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(ConnectorNotConfigured):
        UpworkConnector().fetch(org_id="org_u")
    assert UpworkConnector().check_health("org_u")["status"] == "not_configured"


def test_upwork_requires_a_connection_per_tenant(upwork_env):
    with pytest.raises(ConnectorNotConfigured, match="not connected"):
        UpworkConnector().fetch(org_id="org_u")
    assert UpworkConnector().check_health("org_u")["status"] == "not_connected"


def test_full_upwork_oauth_flow_and_search(fake_upwork):
    calls, _ = fake_upwork
    url = UpworkConnector.authorize_url("org_u")
    assert "client_id=client-abc" in url and "response_type=code" in url and "state=" in url
    UpworkConnector.exchange_code("org_u", "auth-code-1")
    assert calls[0][1]["grant_type"] == "authorization_code" and calls[0][1]["code"] == "auth-code-1"
    with get_db() as db:
        row = db.execute("SELECT * FROM oauth_tokens WHERE org_id = 'org_u'").fetchone()
    assert "access-1" not in row["access_enc"] and "refresh-1" not in str(row["refresh_enc"]), "tokens are encrypted at rest"
    assert UpworkConnector().check_health("org_u")["status"] == "connected"

    items = UpworkConnector().fetch(query="python fastapi", org_id="org_u")
    gql = [c for c in calls if c[0] == "graphql"][0][1]
    assert gql["headers"]["Authorization"] == "Bearer access-1" and gql["json_body"]["variables"] == {"q": "python fastapi"}
    assert items[0].title == "Build FastAPI backend" and items[0].url == "https://www.upwork.com/jobs/~01abc" and items[0].budget_max == 4000.0
    assert items[0].skills_required == ["Python", "FastAPI"] and items[0].fit_score is None
    with pytest.raises(ConnectorNotConfigured, match="not connected"):
        UpworkConnector().fetch(query="x", org_id="org_other_tenant")   # another workspace has no connection


def test_expiring_tokens_are_refreshed(fake_upwork):
    calls, _ = fake_upwork
    UpworkConnector.exchange_code("org_u", "c")
    with get_db() as db:
        db.execute("UPDATE oauth_tokens SET expires_at = datetime('now', '-1 minute')")
        db.commit()
    assert UpworkConnector.access_token("org_u") == "access-2"
    assert calls[-1][1]["grant_type"] == "refresh_token" and calls[-1][1]["refresh_token"] == "refresh-1"
    assert TokenStore.load("org_u", "upwork")["refresh"] == "refresh-2"


def test_graphql_errors_are_surfaced_not_hidden(fake_upwork):
    _, state = fake_upwork
    UpworkConnector.exchange_code("org_u", "c")
    state["graphql"] = {"errors": [{"message": "Field 'marketplaceJobPostingsSearch' is not defined"}]}
    with pytest.raises(RuntimeError, match="is not defined"):
        UpworkConnector().fetch(query="python", org_id="org_u")
    assert parse_graphql({"data": {"marketplaceJobPostingsSearch": {"edges": []}}}) == []


def test_upwork_search_terms_default_to_the_agency_profile(fake_upwork):
    calls, _ = fake_upwork
    PortfolioLibrary.add_asset("org_u", "Case", "Built a Python and FastAPI service for a client with measurable results and long enough text.", tech=["Python", "FastAPI"])
    UpworkConnector.exchange_code("org_u", "c")
    UpworkConnector().fetch(org_id="org_u")
    q = [c for c in calls if c[0] == "graphql"][0][1]["json_body"]["variables"]["q"]
    assert "python" in q and "fastapi" in q


def test_upwork_http_api_flow(client, make_key, fake_upwork):
    lead = make_key("growth_lead", org_id="org_u")
    url = client.get("/api/connectors/upwork/authorize", headers=lead).json()["authorize_url"]
    state = url.split("state=")[1].split("&")[0]
    from urllib.parse import unquote
    state = unquote(state)
    assert client.get("/api/connectors/upwork/callback", params={"code": "c", "state": "forged"}).status_code == 400
    assert client.get("/api/connectors/upwork/callback", params={"code": "c", "state": state}).status_code == 200   # public, but state-bound
    sources = {s["source"]: s for s in client.get("/api/connectors", headers=lead).json()}
    assert sources["upwork"]["status"] == "connected" and set(sources) >= {"upwork", "hn", "remoteok", "wwr", "ted", "uk_fts", "sam_gov"}
    assert "terms_url" in sources["hn"] and sources["upwork"]["automation_level"] == "L1"
    other = {s["source"]: s for s in client.get("/api/connectors", headers=make_key("growth_lead", org_id="org_z")).json()}
    assert other["upwork"]["status"] == "not_connected", "connections are per tenant"
    assert client.delete("/api/connectors/upwork", headers=lead).status_code == 200
    assert client.delete("/api/connectors/upwork", headers=lead).status_code == 404
    assert client.get("/api/connectors/upwork/authorize", headers=make_key("auditor", org_id="org_u")).status_code == 403


def test_opportunities_api_exposes_links_reasons_and_flags(client, make_key, monkeypatch):
    import api
    items = [job(1, "A python react analytics dashboard with whatsapp payments " * 3)]
    monkeypatch.setattr("radar.engine.default_connectors", lambda: [Fake("remoteok", items)])
    lead = make_key("growth_lead", org_id="org_api")
    PortfolioLibrary.add_asset("org_api", "Case", "Built a Python and React analytics dashboard for a client with measurable results over time.", tech=["Python", "React"])
    scanned = client.post("/api/radar/scan", headers=lead).json()
    assert scanned and scanned[0]["url"] == "https://x.example/1"
    row = client.get("/api/opportunities", headers=lead).json()[0]
    assert row["fit_reasons"] and "off_platform_contact" in row["risk_flags"] and row["url"] == "https://x.example/1"
    assert OpportunityRepository.list_opportunities(org_id="org_zz") == [], "another tenant sees nothing"
