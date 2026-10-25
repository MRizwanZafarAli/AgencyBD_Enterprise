"""
Fix group 4: resolver, evidence-grounded briefs and honest presence checks (P1-1, P1-2).

A fake web serves canned homepages through the SSRF-safe client, so every scenario is deterministic and offline.
"""

import pytest

from database.db import get_db
from database.models import CompanyRepository, EvidenceRepository, OpportunityRepository
from intel import places, resolver
from intel.company_brief import CompanyBriefEngine
from intel.presence import PresenceRescueEngine
from intel.resolver import CompanyResolver, candidate_domains, name_tokens, score_homepage
from intel.services import ServiceCatalog
from intel.site_profile import extract_profile
from net.fetcher import FetchResult, HostUnreachableError, SafeFetcher, SSRFSecurityError


from webfake import page


# ============================ site profile ============================

def test_profile_extracts_verifiable_facts():
    html = page("Acme Plumbing | Austin", "Emergency plumbing in Austin.", "Acme Plumbing", "© 2026 Acme Plumbing LLC", extra=(
        '<script type="application/ld+json">{"@graph":[{"@type":"LocalBusiness","name":"Acme Plumbing","telephone":"+1 512 555 0100",'
        '"address":{"streetAddress":"1 Main St","addressLocality":"Austin"},"sameAs":["https://facebook.com/acmeplumbing"]}]}</script>'))
    p = extract_profile(html, "https://acme.example/")
    assert p["title"].startswith("Acme Plumbing") and p["copyright_holder"].startswith("Acme Plumbing LLC")
    assert p["org_jsonld"]["name"] == "Acme Plumbing" and "Austin" in p["org_jsonld"]["address"]
    assert "https://facebook.com/acmeplumbing" in p["social_profiles"] and "LocalBusiness" in p["schema_types"]
    assert p["is_parked"] is False


def test_profile_detects_parked_and_empty_pages():
    assert extract_profile("<html><body>This domain may be for sale. Buy this domain today.</body></html>")["is_parked"]
    assert extract_profile("<html><title>x</title><body>hi</body></html>")["is_parked"]
    assert extract_profile("not even html <<<")["is_parked"]


# ============================ resolver ============================

def test_name_tokens_and_candidates():
    assert name_tokens("Acme Plumbing Holdings Inc.") == ["acme", "plumbing"]
    cands = candidate_domains("Acme Plumbing")
    assert "acmeplumbing.com" in cands and "acme-plumbing.com" in cands and len(cands) <= 14
    assert candidate_domains("!!!") == []


def test_resolves_a_company_only_when_the_homepage_names_it(web):
    web["stripe.com"] = page("Stripe | Payment Processing", "Online payments.", "Stripe", "© 2026 Stripe, Inc.")
    web["stripe.io"] = page("Totally Different Co")
    out = CompanyResolver.resolve_domain_from_name("Stripe", org_id="org_a")
    assert out["status"] == "resolved" and out["domain"] == "stripe.com" and out["confidence"] >= 0.8
    assert CompanyRepository.get_by_id(out["company_id"], "org_a")["domain"] == "stripe.com"
    ev = EvidenceRepository.get_by_ids(out["evidence_ids"], "org_a")
    assert ev and list(ev.values())[0]["source_url"].startswith("https://stripe.com")


def test_nonsense_names_stay_unresolved(web):
    out = CompanyResolver.resolve_domain_from_name("Zxqv Plumbing Holdings", org_id="org_a")
    assert out["status"] == "unresolved" and out["domain"] is None and out["evidence_ids"] == []
    assert "no site" in out["note"].lower() or "no website" in out["note"].lower()


def test_a_live_site_that_is_not_the_company_is_not_a_match(web):
    web["acmeplumbing.com"] = page("Best Pizza in Town", h1="Pizza", footer="© 2026 Luigi's")
    assert CompanyResolver.resolve_domain_from_name("Acme Plumbing", org_id="org_a")["status"] == "unresolved"


def test_parked_domains_are_rejected(web):
    web["acmeplumbing.com"] = page("Acme Plumbing", body="This domain is for sale. Buy this domain now at HugeDomains.")
    assert CompanyResolver.resolve_domain_from_name("Acme Plumbing", org_id="org_a")["status"] == "unresolved"


def test_two_equally_good_sites_are_ambiguous_not_guessed(web):
    web["acmeplumbing.com"] = page("Acme Plumbing | Austin", h1="Acme Plumbing")
    web["acme-plumbing.net"] = page("Acme Plumbing Supply | Dallas", h1="Acme Plumbing")
    out = CompanyResolver.resolve_domain_from_name("Acme Plumbing", org_id="org_a")
    assert out["status"] == "ambiguous" and out["domain"] is None and len(out["candidates"]) == 2


def test_search_suggestions_are_verified_like_any_other_candidate(web, monkeypatch):
    monkeypatch.setattr(resolver, "search_configured", lambda: True)
    monkeypatch.setattr(resolver, "search_candidates", lambda q: ["lookalike-scam.example", "real-acme.example"])
    web["lookalike-scam.example"] = page("Free Prizes!!!")
    web["real-acme.example"] = page("Acme Robotics | Official", h1="Acme Robotics", footer="© 2026 Acme Robotics")
    out = CompanyResolver.resolve_domain_from_name("Acme Robotics", org_id="org_a")
    assert out["status"] == "resolved" and out["domain"] == "real-acme.example"


def test_user_supplied_domains_are_verified_too(web):
    web["acme.example"] = page("Acme", h1="Acme")
    assert CompanyResolver.resolve_domain_from_name("Acme", hint_domain="https://Acme.example/about", org_id="o")["status"] == "resolved"
    assert CompanyResolver.resolve_domain_from_name("Acme", hint_domain="gone.example", org_id="o")["status"] == "domain_unreachable"
    web["parked.example"] = page("x", body="This domain may be for sale")
    assert CompanyResolver.resolve_domain_from_name("Acme", hint_domain="parked.example", org_id="o")["status"] == "domain_parked"


def test_internal_addresses_cannot_be_resolved():
    with pytest.raises(SSRFSecurityError):
        CompanyResolver.resolve_domain_from_name("Internal", hint_domain="127.0.0.1", org_id="o")


def test_same_company_name_is_separate_per_tenant(web):
    web["acme.example"] = page("Acme", h1="Acme")
    a = CompanyResolver.resolve_domain_from_name("Acme", hint_domain="acme.example", org_id="org_a")
    b = CompanyResolver.resolve_domain_from_name("Acme", hint_domain="acme.example", org_id="org_b")
    assert a["company_id"] != b["company_id"]
    assert CompanyRepository.get_by_id(a["company_id"], "org_b") is None


def test_score_homepage_requires_the_name_on_the_page():
    p = extract_profile(page("Acme Plumbing", h1="We fix pipes"), "https://x/")
    assert score_homepage(["acme", "plumbing"], "x", p) == 1.0
    assert score_homepage(["acme", "robotics"], "x", p) == 0.5
    assert score_homepage(["zzz"], "x", p) == 0.0


# ============================ briefs ============================

GOOD_SITE = page("Acme Plumbing | Austin", "Emergency and commercial plumbing across Austin, TX.", "Acme Plumbing",
                 "© 2026 Acme Plumbing LLC",
                 extra='<meta name="generator" content="WordPress 5.8"><link rel="stylesheet" href="/wp-content/themes/x.css">',
                 body="We repair pipes. " * 20)


@pytest.fixture
def company(web):
    web["acmeplumbing.com"] = GOOD_SITE
    r = CompanyResolver.resolve_domain_from_name("Acme Plumbing", org_id="org_a")
    assert r["status"] == "resolved"
    return r


def test_brief_without_a_domain_invents_nothing(web):
    c = CompanyResolver.resolve_domain_from_name("Zxqv Holdings", org_id="org_a")
    brief = CompanyBriefEngine.generate_brief(c["company_id"], "org_a", refresh=True)
    assert brief["status"] == "no_domain" and brief["digital_health"] is None and brief["pitch_kit"] is None
    assert brief["what_they_do"] is None and brief["evidence_count"] == 0 and brief["next_steps"]
    assert "operates digital infrastructure" not in str(brief)


def test_brief_is_read_only_until_refreshed(company):
    brief = CompanyBriefEngine.generate_brief(company["company_id"], "org_a", refresh=False)
    assert brief["status"] != "ok" and brief["refreshed"] is False
    n = len(EvidenceRepository.get_for_entity("company", company["company_id"], "org_a"))
    CompanyBriefEngine.generate_brief(company["company_id"], "org_a", refresh=False)
    assert len(EvidenceRepository.get_for_entity("company", company["company_id"], "org_a")) == n


def collect(node, key):
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            out += v if k == key and isinstance(v, list) else collect(v, key)
    elif isinstance(node, list):
        for x in node:
            out += collect(x, key)
    return out


def test_every_statement_in_a_refreshed_brief_has_evidence(company):
    brief = CompanyBriefEngine.generate_brief(company["company_id"], "org_a", refresh=True)
    assert brief["status"] == "ok" and brief["refreshed"] is True
    assert "Emergency and commercial plumbing" in brief["what_they_do"]["text"]
    assert brief["what_they_do"]["evidence_ids"] and brief["identity"]["evidence_ids"]
    assert isinstance(brief["digital_health"]["score"], int) and brief["digital_health"]["findings_total"] > 0
    for t in brief["digital_health"]["top_findings"]:
        assert t["evidence_ids"] and t["measured"]
    for t in brief["pitch_kit"]["talking_points"]:
        assert t["evidence_ids"]
    assert brief["pitch_kit"]["angle"]["evidence_ids"]
    shown = {e["id"] for e in brief["evidence"]}
    assert set(collect(brief, "evidence_ids")) <= shown, "every cited evidence id must be returned with its source"
    assert all(e["source_url"] and e["observed_at"] for e in brief["evidence"])
    assert "WordPress" in (brief["tech_stack"]["technologies"] or [])
    assert "Company size and revenue" in brief["unknown"] and "Funding" in brief["unknown"]


def test_prices_come_only_from_the_agency_catalog(company):
    brief = CompanyBriefEngine.generate_brief(company["company_id"], "org_a", refresh=True)
    assert brief["pitch_kit"]["price_band"] is None and "Add one under Services" in brief["pitch_kit"]["price_band_note"]
    for key in ("performance_engineering", "seo_optimization", "security_hardening", "a11y_compliance", "geo_ai_readiness"):
        ServiceCatalog.upsert("org_a", key, key, "Offer text; second component", price_band="$7,000 - $9,000")
    again = CompanyBriefEngine.generate_brief(company["company_id"], "org_a", refresh=False)
    assert again["pitch_kit"]["price_band"] == "$7,000 - $9,000"
    assert "$18,000" not in str(again) and "$35,000" not in str(again)


def test_unreachable_site_gets_a_status_not_a_score(web):
    web["acmeplumbing.com"] = GOOD_SITE
    c = CompanyResolver.resolve_domain_from_name("Acme Plumbing", org_id="org_a")
    del web["acmeplumbing.com"]   # site goes down
    brief = CompanyBriefEngine.generate_brief(c["company_id"], "org_a", refresh=True)
    assert brief["status"] == "unreachable" and brief["digital_health"]["score"] is None and brief["pitch_kit"] is None


def test_briefs_are_tenant_scoped(company):
    with pytest.raises(LookupError):
        CompanyBriefEngine.generate_brief(company["company_id"], "org_b")


def test_signals_are_real_radar_rows_only(company):
    assert CompanyBriefEngine.generate_brief(company["company_id"], "org_a", refresh=True)["signals"] == []
    OpportunityRepository.create_opportunity("marketplace", "remoteok", "Acme Plumbing hiring a developer", "x " * 20,
                                             external_id="a1", org_id="org_a")
    sig = CompanyBriefEngine.generate_brief(company["company_id"], "org_a", refresh=False)["signals"]
    assert len(sig) == 1 and sig[0]["source"] == "remoteok"


def test_grounding_filter_drops_unsupported_statements():
    brief = {"what_they_do": {"text": "Sells widgets", "evidence_ids": []}, "identity": {"text": "ok", "evidence_ids": [1]},
             "social_presence": None, "tech_stack": {"technologies": ["x"], "evidence_ids": []},
             "digital_health": {"top_findings": [{"finding": "a", "evidence_ids": []}, {"finding": "b", "evidence_ids": [2]}]},
             "pitch_kit": {"talking_points": [{"text": "claim", "evidence_ids": []}], "angle": {"text": "x", "evidence_ids": []}}}
    out = CompanyBriefEngine.enforce_grounding(brief)
    assert out["what_they_do"] is None and out["tech_stack"] is None and out["identity"]["text"] == "ok"
    assert [t["finding"] for t in out["digital_health"]["top_findings"]] == ["b"]
    assert out["pitch_kit"]["talking_points"] == [] and out["pitch_kit"]["angle"] is None


def test_brief_api_flow_and_permissions(client, make_key, web):
    web["acmeplumbing.com"] = GOOD_SITE
    lead, auditor = make_key("growth_lead", org_id="org_a"), make_key("auditor", org_id="org_a")
    cid = client.post("/api/companies/resolve", headers=lead, json={"company_name": "Acme Plumbing"}).json()["company_id"]
    assert client.get(f"/api/companies/{cid}/brief", headers=auditor).json()["status"] == "needs_refresh"
    assert client.post(f"/api/companies/{cid}/brief", headers=auditor).status_code == 403
    done = client.post(f"/api/companies/{cid}/brief", headers=lead).json()
    assert done["status"] == "ok" and done["evidence_count"] > 0
    assert client.get(f"/api/companies/{cid}/brief", headers=auditor).json()["status"] == "ok"
    assert client.get(f"/api/companies/{cid}/brief", headers=make_key("growth_lead", org_id="org_b")).status_code == 404


# ============================ presence ============================

def test_presence_with_a_live_domain(web):
    web["acme.example"] = page("Acme", h1="Acme")
    out = PresenceRescueEngine.evaluate_presence("Acme", "Austin", "acme.example")
    assert out["classification"] == "has_site" and out["verified"] is True


def test_unreachable_domain_is_not_called_directory_only(web):
    out = PresenceRescueEngine.evaluate_presence("Acme", "Austin", "gone.example")
    assert out["classification"] == "domain_unreachable" and "didn't load" in out["offer"]["cold_call_hook"]
    web["p.example"] = page("x", body="This domain is for sale")
    assert PresenceRescueEngine.evaluate_presence("Acme", "Austin", "p.example")["classification"] == "domain_parked"


def test_without_places_a_missing_site_is_only_not_found_never_proven(web, monkeypatch):
    monkeypatch.setattr("intel.presence.places_configured", lambda: False)
    out = PresenceRescueEngine.evaluate_presence("Bob's Local Plumbing", "Austin, TX")
    assert out["classification"] == "not_found" and out["verified"] is False and out["limitations"]
    assert any("skipped" in c["outcome"] for c in out["checks_performed"])
    assert "couldn't find one" in out["offer"]["cold_call_hook"] and "no_web_presence" not in str(out)


@pytest.mark.parametrize("website,expected", [(None, "no_website_listed"), ("https://facebook.com/bobs", "social_only"),
                                              ("https://bobsplumbing.example", "has_site")])
def test_presence_uses_google_profile_when_configured(web, monkeypatch, website, expected):
    web["bobsplumbing.example"] = page("Bob's Plumbing", h1="Bob's Plumbing")
    monkeypatch.setattr("intel.presence.places_configured", lambda: True)
    monkeypatch.setattr("intel.presence.find_business", lambda n, c: {"place_id": "pid1", "name": n, "website": website, "address": "1 Main", "business_status": "OPERATIONAL"})
    out = PresenceRescueEngine.evaluate_presence("Bob's Plumbing", "Austin")
    assert out["classification"] == expected and out["verified"] is True and out["place_id"] == "pid1"


def test_presence_price_band_comes_from_the_catalog(web, monkeypatch):
    monkeypatch.setattr("intel.presence.places_configured", lambda: False)
    first = PresenceRescueEngine.evaluate_presence("Bob", "Austin", org_id="org_p")["offer"]
    assert first["price_band"] is None and "Add one under Services" in first["price_note"]
    ServiceCatalog.upsert("org_p", "presence_rescue", "Presence bundle", "Website; Google profile; review funnel", "$3,000 - $4,000")
    second = PresenceRescueEngine.evaluate_presence("Bob", "Austin", org_id="org_p")["offer"]
    assert second["price_band"] == "$3,000 - $4,000" and second["components"] == ["Website", "Google profile", "review funnel"]


def test_places_client_requests_only_needed_fields(monkeypatch):
    seen = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"places": [{"id": "p1", "displayName": {"text": "Bob's"}, "formattedAddress": "1 Main", "businessStatus": "OPERATIONAL"}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.update(url=url, headers=headers, body=json)
        return R()

    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "k-123456789")
    monkeypatch.setattr(places.requests, "post", fake_post)
    out = places.find_business("Bob's", "Austin")
    assert out == {"place_id": "p1", "name": "Bob's", "website": None, "address": "1 Main", "business_status": "OPERATIONAL"}
    assert seen["url"].startswith("https://places.googleapis.com/") and "places.websiteUri" in seen["headers"]["X-Goog-FieldMask"]
    assert "reviews" not in seen["headers"]["X-Goog-FieldMask"] and "photos" not in seen["headers"]["X-Goog-FieldMask"]


# ============================ services API ============================

def test_services_api(client, make_key):
    lead = make_key("growth_lead", org_id="org_s")
    body = {"service_key": "seo_optimization", "name": "SEO", "offer": "Audit; fixes; reporting", "price_band": "$2,000 - $4,000"}
    assert client.post("/api/services", headers=lead, json=body).status_code == 200
    assert client.post("/api/services", headers=lead, json={**body, "price_band": "$3,000"}).json()["price_band"] == "$3,000"
    assert len(client.get("/api/services", headers=lead).json()) == 1
    assert client.get("/api/services", headers=make_key("growth_lead", org_id="org_t")).json() == []
    assert client.post("/api/services", headers=make_key("sdr_rep", org_id="org_s"), json=body).status_code == 403
    assert client.delete("/api/services/seo_optimization", headers=lead).status_code == 200
    assert client.delete("/api/services/seo_optimization", headers=lead).status_code == 404


# ============================ site clinic ============================

def test_clinic_history_change_and_teardown_use_only_measured_data(web, client, make_key):
    from auditors.engine import WebsiteDoctorEngine
    web["acmeplumbing.com"] = GOOD_SITE
    c = CompanyResolver.resolve_domain_from_name("Acme Plumbing", org_id="org_a")
    k, other = make_key("growth_lead", "org_a"), make_key("growth_lead", "org_b")
    cid = c["company_id"]
    assert client.get(f"/api/companies/{cid}/teardown", headers=k).status_code == 422                      # nothing examined yet: nothing written
    assert client.get(f"/api/companies/{cid}/audit_history", headers=k).json() == {"audits": [], "change": None}
    first = WebsiteDoctorEngine.run_audit("acmeplumbing.com", cid, org_id="org_a")
    assert client.get(f"/api/companies/{cid}/audit_history", headers=k).json()["change"] is None               # one check: nothing to compare
    web["acmeplumbing.com"] = GOOD_SITE.replace("</head>", '<meta name="viewport" content="width=device-width, initial-scale=1"></head>') if "</head>" in GOOD_SITE else GOOD_SITE
    second = WebsiteDoctorEngine.run_audit("acmeplumbing.com", cid, org_id="org_a")
    h = client.get(f"/api/companies/{cid}/audit_history", headers=k).json()
    assert [a["audit_id"] for a in h["audits"]] == [second["audit_id"], first["audit_id"]]
    assert h["change"]["previous_audit_id"] == first["audit_id"] and h["change"]["latest_audit_id"] == second["audit_id"]
    t = client.get(f"/api/companies/{cid}/teardown", headers=k).json()
    md = t["markdown"]
    assert "Acme Plumbing" in md and "## Findings" in md and "## Not measured" in md and t["filename"] == "Teardown_Acme_Plumbing.md"
    assert "$" not in md and "ROI" not in md and "weeks" not in md.lower()                                     # no invented price, result or timeline
    assert client.get(f"/api/companies/{cid}/teardown", headers=other).status_code == 404                      # another tenant's company
    assert client.get(f"/api/companies/{cid}/audit_history", headers=other).json() == {"audits": [], "change": None}


# ============================ a site that refuses robots is not graded on its block page ============================

AKAMAI_BLOCK = {"status": 403, "html": "<HTML><HEAD><TITLE>Access Denied</TITLE></HEAD><BODY>Reference #18.abc</BODY></HTML>", "headers": {"Server": "AkamaiGHost", "Content-Type": "text/html"}}


def test_a_blocked_site_is_never_graded_on_its_block_page(web):
    from auditors.engine import WebsiteDoctorEngine
    web["blocked.example"] = AKAMAI_BLOCK
    out = WebsiteDoctorEngine.run_audit("blocked.example", org_id="org_blk")
    assert out["status"] == "blocked" and out["overall_score"] is None and out["blocked"]["status_code"] == 403 and out["blocked"]["server"] == "AkamaiGHost"
    ids = {f["check_id"] for f in out["findings"]}
    assert "access_blocked" in ids
    assert not ids & {"missing_meta_description", "missing_viewport_tag", "thin_content", "missing_open_graph", "missing_csp"}      # nothing about the block page's own markup
    assert "tls" in out["checks_run"] and any("refused automated access" in s for s in out["checks_skipped"])


@pytest.mark.parametrize("entry", [
    {"status": 200, "html": "<html><head><title>Just a moment...</title></head><body>Checking your browser</body></html>"},
    {"status": 200, "html": "<html><body>ok</body></html>", "headers": {"cf-mitigated": "challenge"}},
    {"status": 429, "html": "slow down"},
])
def test_challenge_pages_and_rate_limits_count_as_blocked(web, entry):
    from auditors.engine import WebsiteDoctorEngine
    web["challenge.example"] = entry
    assert WebsiteDoctorEngine.run_audit("challenge.example", org_id="o")["status"] == "blocked"


def test_an_error_page_is_not_audited_as_if_it_were_the_site(web):
    from auditors.engine import WebsiteDoctorEngine
    web["broken.example"] = {"status": 500, "html": "<html><body>Internal error</body></html>"}
    out = WebsiteDoctorEngine.run_audit("broken.example", org_id="o")
    assert out["status"] == "unreachable" and out["overall_score"] is None and "HTTP 500" in out["findings"][0]["evidence_value"]


def test_a_domain_you_give_that_blocks_us_resolves_as_existing_but_unread(web):
    web["blocked.example"] = AKAMAI_BLOCK
    r = CompanyResolver.resolve_domain_from_name("blocked.example", org_id="org_blk")
    assert r["status"] == "resolved" and r["access"] == "blocked" and r["domain"] == "blocked.example" and r["confidence"] == 0.5
    assert "refuses automated access" in r["note"] and "do not try to get around" in r["note"]
    ev = EvidenceRepository.get_by_ids(r["evidence_ids"], "org_blk")
    assert "refuses automated access" in next(iter(ev.values()))["claim"] and "not matched" in next(iter(ev.values()))["value"]
    brief_status = CompanyBriefEngine.generate_brief(r["company_id"], "org_blk", refresh=True)
    assert brief_status["status"] == "blocked" and brief_status["pitch_kit"] is None and brief_status["digital_health"]["score"] is None


def test_a_normal_404_homepage_probe_is_still_unreachable_not_blocked(web):
    web["gone.example"] = {"status": 404, "html": "nope"}
    assert CompanyResolver.resolve_domain_from_name("Acme", hint_domain="gone.example", org_id="o")["status"] == "domain_unreachable"
