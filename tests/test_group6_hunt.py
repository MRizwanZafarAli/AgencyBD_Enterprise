"""Local client hunt, Reddit/GitHub connectors (recorded real responses), grounded LLM reasoning, and the digest."""

import json
from pathlib import Path

import pytest

from config.honesty import NotConfiguredError
from connectors.github_bounties import parse_issues
from connectors.reddit import parse_feed
from database.models import LeadRepository, OpportunityRepository
from intel import local_hunt, places
from llm import reasoning
from llm.client import LLMGateway
from portfolio.library import PortfolioLibrary
from workflows import digest

FIX = Path(__file__).parent / "fixtures"


# ------------------------------------------------------------------ connectors (real recorded data)

def test_reddit_keeps_only_hiring_posts_and_reads_budgets():
    items = parse_feed((FIX / "reddit_forhire.xml").read_text(encoding="utf-8"))
    assert items and all(i.source == "reddit" and i.url.startswith("https://www.reddit.com/") for i in items)
    assert not any(i.title.lower().startswith("for hire") for i in items)
    assert any(i.budget_max == 1500.0 for i in items)   # "$1,500 Fixed"


def test_github_keeps_only_issues_with_a_stated_dollar_reward():
    items = parse_issues(json.loads((FIX / "github_bounty.json").read_text(encoding="utf-8")))
    assert items and all(i.budget_min and i.budget_min > 0 and i.url.startswith("https://github.com/") for i in items)


# ------------------------------------------------------------------ local hunt

def raw(name, website=None, provider="google", reviews=0, rating=None, phone=None, **extra):
    return {"provider": provider, "place_id": f"id-{name}", "name": name, "website": website, "address": "1 Main St", "phone": phone,
            "rating": rating, "reviews": reviews, "maps_url": "https://maps.example/x", "category": "dentist", "business_status": "OPERATIONAL", **extra}


@pytest.fixture
def fake_places(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-places-key-123")
    rows = [raw("Smile Dental", None, reviews=120, rating=4.7, phone="555-0100"),
            raw("Page Dental", "https://facebook.com/pagedental", reviews=30, rating=4.2),
            raw("Slow Dental", "https://slowdental.example", reviews=10),
            raw("Closed Dental", None, reviews=500, business_status="CLOSED_PERMANENTLY")]
    rows[3]["business_status"] = "CLOSED_PERMANENTLY"
    monkeypatch.setattr(places, "search_google", lambda q, c, n: rows)

    from net.fetcher import FetchResult, SafeFetcher

    def fake_fetch(cls, url, timeout=10, **kw):
        assert "slowdental.example" in url
        return FetchResult(status_code=200, text="<html><body><p>" + "Family dentistry in Austin with friendly staff and flexible hours. " * 5 + "</p></body></html>", headers={}, final_url="http://slowdental.example/", elapsed_ms=10)
    monkeypatch.setattr(SafeFetcher, "safe_fetch", classmethod(fake_fetch))
    return rows


def test_hunt_ranks_no_website_with_reviews_first_and_drops_closed_businesses(fake_places):
    out = local_hunt.hunt("dentist", "Austin", provider="google")
    names = [r["name"] for r in out["results"]]
    assert names[0] == "Smile Dental" and "Closed Dental" not in names
    top = out["results"][0]
    assert top["classification"] == "no_website_listed" and top["verified_absence"] is True
    assert any("120 Google reviews" in r for r in top["reasons"])
    by = {r["name"]: r for r in out["results"]}
    assert by["Page Dental"]["classification"] == "social_only"
    slow = by["Slow Dental"]
    assert slow["classification"] == "has_site" and "site is not served over HTTPS" in slow["issues"]
    assert slow["score"] < by["Page Dental"]["score"]      # a working site is less urgent than no site


def test_osm_absence_is_not_called_verified(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.setattr(places, "search_osm", lambda c, city, n: [raw("Corner Cafe", None, provider="osm")])
    out = local_hunt.hunt("cafe", "Leeds")
    r = out["results"][0]
    assert out["provider"] == "osm" and r["classification"] == "no_website_in_osm" and r["verified_absence"] is False
    assert out["notes"]


def test_google_without_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    with pytest.raises(NotConfiguredError):
        local_hunt.hunt("dentist", "Austin", provider="google")


def test_nominatim_rows_are_parsed_with_website_phone_and_socials():
    rows = [{"osm_type": "node", "osm_id": 5, "name": "Smile Stylist", "extratags": {"contact:website": "https://s.example", "phone": "+44 1"},
             "address": {"house_number": "4", "road": "High St", "city": "Manchester"}},
            {"osm_type": "way", "osm_id": 6, "name": "Bupa", "extratags": {"contact:facebook": "https://facebook.com/b"}, "address": {}}]
    a, b = places.parse_nominatim(rows, "dentist")
    assert a["website"] == "https://s.example" and a["phone"] == "+44 1" and a["address"] == "4 High St, Manchester"
    assert b["website"] is None and b["facebook"] and b["maps_url"].endswith("/way/6")


def test_hunt_endpoints_require_permission_and_save_leads(client, fake_places, growth_headers, make_key):
    assert client.post("/api/hunt/local", json={"category": "dentist", "city": "Austin"}).status_code == 401
    assert client.post("/api/hunt/local", headers=make_key("auditor"), json={"category": "dentist", "city": "Austin"}).status_code == 403
    res = client.post("/api/hunt/local", headers=growth_headers, json={"category": "dentist", "city": "Austin", "provider": "google"})
    assert res.status_code == 200 and res.json()["results"][0]["name"] == "Smile Dental"
    top = res.json()["results"][0]
    saved = client.post("/api/hunt/local/save", headers=growth_headers, json={
        "name": top["name"], "city": "Austin", "phone": top["phone"], "reviews": top["reviews"], "rating": top["rating"],
        "classification": top["classification"], "place_id": top["place_id"], "category": "dentist"})
    assert saved.status_code == 200 and "no_website_listed" in saved.json()["notes"]
    again = client.post("/api/hunt/local/save", headers=growth_headers, json={
        "name": top["name"], "city": "Austin", "classification": top["classification"], "place_id": top["place_id"]})
    assert again.json()["id"] == saved.json()["id"]          # saving twice does not duplicate


# ------------------------------------------------------------------ grounded LLM reasoning

JOB = "We need a senior engineer to rebuild our legacy PHP booking dashboard in React. Budget is $8,000 and we want it done in six weeks."


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-1234567890")
    state = {"reply": {}}

    def fake(cls, prompt, system, model, temperature, max_tokens):
        return {"text": json.dumps(state["reply"]), "tokens_in": 10, "tokens_out": 10, "model": "claude-test", "provider": "anthropic"}
    monkeypatch.setattr(LLMGateway, "_call_anthropic", classmethod(fake))
    return state


def test_fit_analysis_drops_points_without_a_real_quote(llm):
    opp = OpportunityRepository.create_opportunity("marketplace", "upwork", "Booking dashboard rebuild", JOB, org_id="org_default")
    llm["reply"] = {"verdict": "pursue", "summary": "Good fit.",
                    "reasons": [{"point": "Clear budget", "quote": "Budget is $8,000"},
                                {"point": "Famous client", "quote": "Fortune 500 company with huge budget"}],
                    "risks": [{"point": "Tight deadline", "quote": "done in six weeks"}], "questions_to_ask": ["Who owns the PHP code?"]}
    out = reasoning.analyze_fit(opp["id"], "org_default")
    assert [r["point"] for r in out["reasons"]] == ["Clear budget"] and out["risks"][0]["point"] == "Tight deadline"
    assert out["unsupported_points_dropped"] == 1 and out["verdict"] == "pursue"


def test_fit_analysis_endpoint_503_without_model_and_404_for_unknown(client, growth_headers, monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "OLLAMA_HOST"):
        monkeypatch.delenv(var, raising=False)
    opp = OpportunityRepository.create_opportunity("marketplace", "upwork", "x job", JOB, org_id="org_default")
    assert client.post(f"/api/opportunities/{opp['id']}/analyze", headers=growth_headers).status_code == 503
    assert client.post("/api/opportunities/99999/analyze", headers=growth_headers).status_code == 404


def test_brief_summary_keeps_only_cited_sentences(llm):
    brief = {"company_name": "Acme", "evidence": [{"id": 7, "claim": "Homepage title", "value": "Acme Plumbing"},
                                                  {"id": 8, "claim": "LCP", "value": "4.1s"}]}
    llm["reply"] = {"sentences": [{"text": "Acme is a plumbing business.", "evidence_ids": [7]},
                                  {"text": "Acme raised $10M.", "evidence_ids": [99]},
                                  {"text": "No citation at all.", "evidence_ids": []}],
                    "best_pitch": {"text": "Their mobile load is slow (4.1s).", "evidence_ids": [8]}}
    out = reasoning.summarize_brief(brief, "org_default")
    assert [s["text"] for s in out["sentences"]] == ["Acme is a plumbing business."] and out["dropped"] == 2
    assert out["best_pitch"]["evidence_ids"] == [8]


# ------------------------------------------------------------------ digest

def test_digest_lists_best_new_opportunities_and_requires_slack(monkeypatch):
    OpportunityRepository.create_opportunity("marketplace", "upwork", "Great job", JOB, org_id="org_default", fit_score=0.9)
    OpportunityRepository.create_opportunity("marketplace", "upwork", "Weak job", "meh", org_id="org_default", fit_score=0.1)
    LeadRepository.create_or_get_lead("Smile Dental", "nosite-smile.invalid", phone="555-0100", reviews_count=120, notes="WEB PRESENCE: no_website_listed", org_id="org_default")
    d = digest.build_digest("org_default", limit=5, min_score=0.5)
    assert d["lead_count"] == 1 and "Smile Dental" in d["text"]
    assert d["opportunity_count"] == 1 and "Great job" in d["text"] and "90%" in d["text"] and "Weak job" not in d["text"]
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with pytest.raises(NotConfiguredError):
        digest.send_to_slack(d["text"])


def test_digest_is_tenant_scoped():
    OpportunityRepository.create_opportunity("marketplace", "upwork", "Other tenant job", JOB, org_id="org_other", fit_score=0.99)
    assert digest.build_digest("org_default")["opportunity_count"] == 0


def test_site_checks_never_call_a_blocked_or_broken_site_down(monkeypatch):
    import requests
    from net.fetcher import FetchResult, HostUnreachableError, SafeFetcher

    def run(behaviour):
        def fake(cls, url, timeout=10, **kw):
            r = behaviour(url)
            if isinstance(r, Exception):
                raise r
            return r
        monkeypatch.setattr(SafeFetcher, "safe_fetch", classmethod(fake))
        return local_hunt._site_signals("https://x.example", "X")

    ok = lambda code: FetchResult(status_code=code, text="<html></html>", headers={}, final_url="https://x.example/", elapsed_ms=1)
    blocked = run(lambda u: ok(403))
    assert blocked["classification"] == "has_site" and blocked["issues"] == [] and "blocked" in blocked["check_note"]
    assert run(lambda u: requests.exceptions.SSLError("bad cert"))["classification"] == "tls_broken"
    assert run(lambda u: HostUnreachableError("DNS resolution failure for host 'x.example'"))["classification"] == "domain_unreachable"
    inconclusive = run(lambda u: requests.exceptions.ReadTimeout("slow"))
    assert inconclusive["classification"] == "has_site" and "inconclusive" in inconclusive["check_note"]
    assert run(lambda u: ok(404))["issues"] == ["homepage returns HTTP 404"]


def test_hunt_generates_pitch_strategy_and_coordinates(fake_places, client, growth_headers):
    res = client.post("/api/hunt/local", headers=growth_headers, json={"category": "dentist", "city": "Austin", "provider": "google"})
    assert res.status_code == 200
    data = res.json()
    assert "results" in data and len(data["results"]) > 0
    top = data["results"][0]
    assert "pitch_strategy" in top
    ps = top["pitch_strategy"]
    assert "angle" in ps and "value_estimate" in ps and "deliverables" in ps and "cold_pitch_hook" in ps
    assert ps["angle"] == "Build a website customers can find and book from"
    assert ps["value_estimate"] is None and ps["deliverables"] == []        # no price or deliverables unless YOUR catalog defines them
    assert "doesn't list a website" in ps["cold_pitch_hook"] and not any(ch.isdigit() and "%" in ps["cold_pitch_hook"] for ch in ps["cold_pitch_hook"])

    # Batch save
    batch_res = client.post("/api/hunt/local/batch_save", headers=growth_headers, json=[
        {"name": top["name"], "city": "Austin", "classification": top["classification"], "place_id": top["place_id"], "pitch_strategy": ps}
    ])
    assert batch_res.status_code == 200
    assert batch_res.json()["saved_count"] == 1


def test_pitch_strategy_uses_the_catalog_price_band_and_never_invents_statistics():
    from intel.local_hunt import generate_pitch_strategy
    from intel.services import ServiceCatalog
    ServiceCatalog.upsert("org_pitch", "presence_rescue", "Website build", "Design; Build; Launch", price_band="GBP 2,000-3,500")
    ps = generate_pitch_strategy({"name": "Smile", "classification": "social_only", "facebook": "https://facebook.com/x", "reasons": ["Phone number available"]}, "dentist", "Leeds", "org_pitch")
    assert ps["value_estimate"] == "GBP 2,000-3,500" and ps["deliverables"] == ["Design", "Build", "Launch"]
    blob = " ".join([ps["cold_pitch_hook"]] + ps["actionable_teardown"])
    assert "Facebook" in ps["cold_pitch_hook"] and "%" not in blob and "$" not in blob
