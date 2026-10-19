"""
Integration tests for the FastAPI REST layer: authentication, authorization,
tenant isolation, webhook signing and core endpoint behaviour.
"""

import json
import time

import pytest

from security.webhook_verifier import WebhookSecurity
from database.models import LeadRepository

# Every route below must refuse anonymous callers.
PROTECTED_ROUTES = [
    ("GET", "/api/auth/me"),
    ("GET", "/api/metrics"),
    ("GET", "/metrics"),
    ("GET", "/api/leads"),
    ("GET", "/api/leads/1"),
    ("POST", "/api/sourcing/run"),
    ("POST", "/api/sourcing/linkedin/people"),
    ("POST", "/api/enrich/site_crawl"),
    ("POST", "/api/audit/run"),
    ("POST", "/api/enrich/run"),
    ("POST", "/api/sequence/generate"),
    ("POST", "/api/dispatch/send"),
    ("POST", "/api/pipeline/run"),
    ("POST", "/api/replies/triage"),
    ("POST", "/api/booking/create"),
    ("GET", "/api/geo/countries"),
    ("GET", "/api/geo/states?country=United States"),
    ("GET", "/api/geo/cities?country=United States&state=California"),
    ("GET", "/api/geo/search?query=aus"),
    ("POST", "/api/intelligence/recommend_markets"),
    ("GET", "/api/analytics/unit_economics"),
    ("GET", "/api/analytics/spintax_cohorts"),
    ("GET", "/api/tasks/dead_letters"),
    ("POST", "/api/tasks/retry_dead_letter"),
    ("POST", "/api/security/create_key"),
    ("GET", "/api/security/list_keys"),
    ("POST", "/api/security/revoke_key"),
    ("POST", "/api/native/verify_email"),
    ("POST", "/api/native/fingerprint_tech"),
    ("POST", "/api/native/deanonymize_visitor"),
    ("POST", "/api/native/analyze_sales_call"),
    ("POST", "/api/native/generate_video_storyboard"),
    ("POST", "/api/native/score_copy"),
    ("POST", "/api/native/waterfall_enrich"),
    ("POST", "/api/native/route_smartlead"),
    ("POST", "/api/native/parse_spintax"),
    ("GET", "/api/portfolio/assets"),
    ("POST", "/api/portfolio/assets"),
    ("DELETE", "/api/portfolio/assets/1"),
    ("POST", "/api/proposals/draft"),
    ("GET", "/api/approvals/pending"),
    ("POST", "/api/approvals/1/decide"),
    ("GET", "/api/outbound/mailboxes"),
    ("POST", "/api/outbound/mailboxes"),
    ("POST", "/api/outbound/verify"),
    ("POST", "/api/outbound/sequence/step"),
    ("GET", "/api/outbound/drafts"),
    ("POST", "/api/outbound/drafts/1/send"),
    ("GET", "/api/outbound/events"),
    ("POST", "/api/sequences"),
    ("GET", "/api/sequences"),
    ("POST", "/api/sequences/1/enroll"),
    ("GET", "/api/sequences/enrollments"),
    ("POST", "/api/sequences/enrollments/1/stop"),
    ("POST", "/api/sequences/run_due"),
    ("GET", "/api/policy/rules"),
    ("GET", "/api/analytics/learning_report"),
    ("GET", "/api/compliance/country/US"),
    ("GET", "/api/system/status"),
    ("GET", "/api/security/roles"),
    ("GET", "/api/connectors"),
    ("GET", "/api/connectors/upwork/authorize"),
    ("DELETE", "/api/connectors/upwork"),
    ("POST", "/api/outbound/dns/records"),
    ("POST", "/api/outbound/dns/audit"),
    ("POST", "/api/security/webhook_secret"),
    ("POST", "/api/proposals/1/outcome"),
    ("POST", "/api/analytics/expenses"),
    ("GET", "/api/services"),
    ("POST", "/api/services"),
    ("DELETE", "/api/services/x"),
    ("POST", "/api/companies/1/brief"),
    ("GET", "/api/companies/1/brief"),
    ("POST", "/api/browser/interactive/navigate"),
    ("POST", "/api/browser/interactive/action"),
    ("POST", "/api/browser/interactive/headed-window"),
    ("POST", "/api/swarm/pods/run"),
    ("POST", "/api/teardown/deck/export"),
    ("GET", "/api/teardown/deck/view/sample.html"),
    ("GET", "/api/system/updater/status"),
    ("POST", "/api/system/updater/apply"),
    ("POST", "/api/system/seed_demo_pipeline"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_anonymous_requests_are_rejected(client, method, path):
    res = client.request(method, path, json={} if method == "POST" else None)
    assert res.status_code == 401, f"{method} {path} answered {res.status_code} without credentials"


def test_forged_key_rejected(client):
    res = client.get("/api/leads", headers={"X-API-Key": "agy_live_not_a_real_key"})
    assert res.status_code == 401


def test_public_probes_stay_open(client):
    assert client.get("/healthz/live").json()["status"] == "alive"
    ready = client.get("/healthz/ready")
    assert ready.status_code == 200 and ready.json()["status"] == "ready"


def test_whoami_reports_identity(client, make_key):
    res = client.get("/api/auth/me", headers=make_key("auditor", org_id="org_x", user_id="aud1"))
    assert res.status_code == 200
    body = res.json()
    assert (body["user_id"], body["org_id"], body["role"]) == ("aud1", "org_x", "auditor")


def test_prometheus_metrics_endpoint(client, make_key):
    res = client.get("/metrics", headers=make_key("auditor"))
    assert res.status_code == 200
    assert "agencybd_" in res.text


def test_role_permissions_enforced(client, make_key):
    auditor = make_key("auditor")
    sdr = make_key("sdr_rep")
    # auditor is read-only
    assert client.get("/api/leads", headers=auditor).status_code == 200
    assert client.post("/api/sourcing/run", json={"channel": "venture_database", "query": "Series A", "limit": 1},
                       headers=auditor).status_code == 403
    # sdr cannot dispatch or read business metrics
    assert client.post("/api/dispatch/send", json={"lead_id": 1}, headers=sdr).status_code == 403
    assert client.get("/api/metrics", headers=sdr).status_code == 403


def test_key_management_is_super_admin_only(client, make_key):
    body = {"name": "k", "user_id": "u", "role": "growth_lead"}
    assert client.post("/api/security/create_key", json=body, headers=make_key("growth_lead")).status_code == 403
    assert client.get("/api/security/list_keys", headers=make_key("growth_lead")).status_code == 403
    assert client.post("/api/security/create_key", json=body, headers=make_key("super_admin")).status_code == 200


def test_security_keys_endpoints(client, admin_headers):
    create_res = client.post("/api/security/create_key", headers=admin_headers, json={
        "name": "Integration Test Key",
        "user_id": "test_runner",
        "role": "growth_lead",
        "org_id": "org_api_test"
    })
    assert create_res.status_code == 200
    new_key = create_res.json()["api_key"]
    assert new_key.startswith("agy_live_")

    # The new key authenticates, bound to the org it was minted for
    me = client.get("/api/auth/me", headers={"X-API-Key": new_key}).json()
    assert me["org_id"] == "org_api_test" and me["role"] == "growth_lead"

    listed = client.get("/api/security/list_keys?org_id=org_api_test", headers=admin_headers)
    assert listed.status_code == 200
    key_id = listed.json()["keys"][0]["id"]
    assert "key_hash" not in listed.json()["keys"][0]

    revoke = client.post("/api/security/revoke_key", headers=admin_headers,
                         json={"key_id": key_id, "org_id": "org_api_test"})
    assert revoke.json()["revoked"] is True
    assert client.get("/api/auth/me", headers={"X-API-Key": new_key}).status_code == 401


def test_create_key_rejects_unknown_role(client, admin_headers):
    res = client.post("/api/security/create_key", headers=admin_headers,
                      json={"name": "k", "user_id": "u", "role": "root"})
    assert res.status_code == 400


# ---------------- Tenant isolation ----------------

def test_tenants_cannot_see_each_others_leads(client, make_key):
    alpha = make_key("growth_lead", org_id="org_alpha")
    beta = make_key("growth_lead", org_id="org_beta")

    leads = [LeadRepository.create_or_get_lead(f"Alpha Co {i}", f"alpha{i}.example.org", org_id="org_alpha") for i in range(2)]
    alpha_lead_id = leads[0]["id"]

    assert len(client.get("/api/leads", headers=alpha).json()) == 2
    assert client.get("/api/leads", headers=beta).json() == []

    # IDOR: knowing the id is not enough
    assert client.get(f"/api/leads/{alpha_lead_id}", headers=beta).status_code == 404
    for path in ("/api/audit/run", "/api/enrich/run", "/api/pipeline/run", "/api/dispatch/send"):
        assert client.post(path, headers=beta, json={"lead_id": alpha_lead_id}).status_code == 404

    # A tenant cannot ask for another tenant's data through the org_id parameter
    assert client.get("/api/leads?org_id=org_alpha", headers=beta).status_code == 403
    assert client.get("/api/analytics/unit_economics?org_id=org_alpha", headers=beta).status_code == 403


def test_metrics_are_tenant_scoped(client, make_key):
    alpha = make_key("growth_lead", org_id="org_alpha")
    beta = make_key("growth_lead", org_id="org_beta")
    for i in range(3):
        LeadRepository.create_or_get_lead(f"Alpha Co {i}", f"alpha{i}.example.org", org_id="org_alpha")
    assert client.get("/api/metrics", headers=alpha).json()["total_leads"] == 3
    assert client.get("/api/metrics", headers=beta).json()["total_leads"] == 0


def test_super_admin_can_cross_tenants(client, admin_headers, make_key):
    alpha = make_key("growth_lead", org_id="org_alpha")
    LeadRepository.create_or_get_lead("Alpha Co", "alpha.example.org", org_id="org_alpha")
    assert len(client.get("/api/leads?org_id=org_alpha", headers=admin_headers).json()) == 1


# ---------------- Webhook ----------------

def _signed(payload: dict, ts: int = None):
    body = json.dumps(payload).encode()
    ts = ts if ts is not None else int(time.time())
    return body, {
        "X-AgencyBD-Timestamp": str(ts),
        "X-AgencyBD-Signature": WebhookSecurity.sign_payload(body, timestamp=ts),
        "Content-Type": "application/json",
    }


WEBHOOK_PAYLOAD = {
    "from": "prospect@acmecorp.com",
    "to": "sdr@apexcore.ai",
    "subject": "Re: Discussion",
    "text": "Sounds very interesting, let us schedule a time next Tuesday."
}


def test_inbound_webhook_accepts_valid_signature(client):
    body, headers = _signed(WEBHOOK_PAYLOAD)
    res = client.post("/api/webhooks/inbound", content=body, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed"
    assert data["sentiment"] == "positive"
    assert "auto_rebuttal" in data


def test_inbound_webhook_rejects_unsigned_forged_and_replayed(client):
    body = json.dumps(WEBHOOK_PAYLOAD).encode()
    # no signature at all (the previous implementation accepted this)
    assert client.post("/api/webhooks/inbound", content=body,
                       headers={"Content-Type": "application/json"}).status_code == 401
    # signature but no timestamp
    sig = WebhookSecurity.sign_payload(body)
    assert client.post("/api/webhooks/inbound", content=body,
                       headers={"X-AgencyBD-Signature": sig, "Content-Type": "application/json"}).status_code == 401
    # forged signature
    _, headers = _signed(WEBHOOK_PAYLOAD)
    headers["X-AgencyBD-Signature"] = "0" * 64
    assert client.post("/api/webhooks/inbound", content=body, headers=headers).status_code == 401
    # stale (replayed) request with a valid signature
    old_body, old_headers = _signed(WEBHOOK_PAYLOAD, ts=int(time.time()) - 3600)
    assert client.post("/api/webhooks/inbound", content=old_body, headers=old_headers).status_code == 401
    # body tampered after signing
    body2, headers2 = _signed(WEBHOOK_PAYLOAD)
    assert client.post("/api/webhooks/inbound", content=body2 + b" ", headers=headers2).status_code == 401


# ---------------- Core behaviour with valid credentials ----------------

def test_geo_endpoints(client, growth_headers):
    res = client.get("/api/geo/countries", headers=growth_headers)
    assert res.status_code == 200
    assert "United States" in res.json()["countries"]

    res_states = client.get("/api/geo/states?country=United States", headers=growth_headers)
    assert "California" in res_states.json()["states_provinces"]

    res_cities = client.get("/api/geo/cities?country=United States&state=California", headers=growth_headers)
    assert "San Francisco" in res_cities.json()["cities"]


def test_market_intelligence_recommend_endpoint(client, growth_headers):
    res = client.post("/api/intelligence/recommend_markets", headers=growth_headers, json={
        "project_demand": "We build custom LLM agent swarms for FinTech and Healthcare",
        "ticket_size": "$50k-$150k"
    })
    assert res.status_code == 200
    data = res.json()
    assert "primary_target" in data and "operational_search_queries" in data
    assert len(data["top_recommended_geos"]) > 0


def test_native_endpoints_api(client, growth_headers):
    r1 = client.post("/api/native/verify_email", json={"email": "bu@resend.com"}, headers=growth_headers)
    assert r1.status_code == 200 and "confidence_score" in r1.json()

    r2 = client.post("/api/native/score_copy", headers=growth_headers, json={
        "subject": "quick question",
        "body": "Hi there.\n\nSaw your product.\n\nWorth a brief look?"
    })
    assert r2.status_code == 200 and r2.json()["overall_score"] >= 80

    r3 = client.post("/api/native/waterfall_enrich", headers=growth_headers, json={
        "first_name": "Alex", "last_name": "Bouaziz", "company_name": "Deel",
        "domain": "deel.com", "title": "CEO"
    })
    assert r3.status_code == 200 and "@deel.com" in r3.json()["resolved_email"]

    r4 = client.post("/api/native/parse_spintax", json={"template_text": "{Hi|Hey} there"}, headers=growth_headers)
    assert r4.json()["generated_variant"] in ["Hi there", "Hey there"]


def test_internal_errors_do_not_leak_details(client, growth_headers):
    res = client.post("/api/pipeline/run", json={"lead_id": 999999}, headers=growth_headers)
    assert res.status_code == 404
    assert "Traceback" not in res.text


def test_probe_presence_endpoint(client, growth_headers):
    res = client.post("/api/hunt/local/probe_presence", headers=growth_headers, json={
        "name": "Acme Motors",
        "city": "Dallas",
        "website": None
    })
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Acme Motors"
    assert data["classification"] == "no_website_in_osm"
    assert "pitch_strategy" in data


def test_pipeline_deals_crud_and_forecast(client, growth_headers):
    # 1. Create Deal
    res = client.post("/api/pipeline/deals/create", headers=growth_headers, json={
        "company_name": "Lone Star Dental",
        "domain": "lonestardental.org",
        "deal_value": 7500,
        "stage": "sourced",
        "notes": "Dead website detected on mobile"
    })
    assert res.status_code == 200
    deal = res.json()
    deal_id = deal["id"]
    assert deal["deal_stage"] == "sourced"

    # 2. Query Pipeline
    res_pipe = client.get("/api/pipeline/deals", headers=growth_headers)
    assert res_pipe.status_code == 200
    pipe = res_pipe.json()
    assert pipe["total_deals"] >= 1
    assert pipe["total_value"] >= 7500
    assert "sourced" in pipe["stages"]

    # 3. Advance Deal Stage
    res_stage = client.post("/api/pipeline/deals/stage", headers=growth_headers, json={
        "lead_id": deal_id,
        "new_stage": "meeting_booked"
    })
    assert res_stage.status_code == 200
    updated = res_stage.json()
    assert updated["deal_stage"] == "meeting_booked"


def test_sourcing_sec_edgar_venture_endpoint(client, growth_headers):
    res = client.get("/api/sourcing/venture/sec_edgar?limit=5", headers=growth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "leads" in data
    assert isinstance(data["leads"], list)


def test_sourcing_hiring_signals_endpoint(client, growth_headers):
    res = client.get("/api/sourcing/hiring/signals?query=Engineer&limit=5", headers=growth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "leads" in data
    assert isinstance(data["leads"], list)


def test_sourcing_xray_people_endpoint(client, growth_headers):
    res = client.post("/api/sourcing/xray_people", headers=growth_headers, json={
        "company_name": "Stripe",
        "titles": ["CTO", "CEO"],
        "location": "San Francisco, CA",
        "limit": 3
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "profiles" in data
    assert len(data["profiles"]) > 0
    first = data["profiles"][0]
    assert "xray_url" in first or "linkedin_url" in first


def test_swarm_math_score_endpoint(client, growth_headers):
    res = client.post("/api/swarm/math/score", headers=growth_headers, json={
        "source_channel": "sec_edgar_form_d",
        "title": "CTO",
        "lcp_seconds": 3.6,
        "detected_stack": ["Next.js", "WordPress"],
        "email_confidence": 92,
        "catch_all_decoded": True
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "probability" in data
    assert data["probability"]["p_close"] >= 0.70
    assert "deal_economics" in data
    assert data["deal_economics"]["expected_value_usd"] > 10000


def test_swarm_autopilot_run_endpoint(client, growth_headers, monkeypatch):
    from api import autopilot_engine
    # Mock source_sec_edgar_venture to return a fast fixture
    monkeypatch.setattr(
        autopilot_engine.sourcing,
        "source_sec_edgar_venture",
        lambda funding_stage, limit, org_id: [
            {
                "id": 999,
                "company_name": "Apex AI Labs",
                "domain": "apex-ai.internal",
                "source_channel": "sec_edgar_form_d"
            }
        ]
    )
    res = client.post("/api/swarm/autopilot/run", headers=growth_headers, json={
        "channel": "sec_edgar",
        "limit": 1
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "result" in data
    assert data["result"]["status"] == "completed"
    assert len(data["result"]["leads"]) == 1
    assert data["result"]["total_expected_pipeline_usd"] > 0


def test_brain_status_endpoint(client, growth_headers):
    res = client.get("/api/brain/status", headers=growth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "brain" in data
    assert "tier" in data["brain"]


def test_brain_plan_endpoint(client, growth_headers):
    res = client.post("/api/brain/plan", headers=growth_headers, json={
        "goal": "Acquire 5 Series A fintech companies with slow LCP"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "execution_plan" in data
    assert len(data["execution_plan"]) >= 4


def test_brain_chat_endpoint(client, growth_headers):
    res = client.post("/api/brain/chat", headers=growth_headers, json={
        "messages": [{"role": "user", "content": "Find 3 high intent accounts"}]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["intent"] == "SOURCING_DISPATCH"
    assert "reply" in data


def test_brain_triage_objection_endpoint(client, growth_headers):
    res = client.post("/api/brain/triage-objection", headers=growth_headers, json={
        "objection": "Your squad is too expensive for our seed budget",
        "prospect_name": "Sarah",
        "company": "FintechHQ"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["category"] == "BUDGET_PRICING"
    assert "draft_reply" in data


def test_brain_artifact_endpoint(client, growth_headers):
    res = client.post("/api/brain/artifact", headers=growth_headers, json={
        "lead": {"company_name": "Novu Labs", "domain": "novulabs.com", "contact_name": "Elena"},
        "tech_audit": {"detected_stack": ["React", "Next.js"], "lcp_seconds": 3.7},
        "deal_metrics": {"monthly_financial_loss_usd": 2800.0, "expected_value_usd": 50000.0}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "Novu Labs" in data["artifact_markdown"]
    assert "artifact_title" in data


def test_browser_render_endpoint(client, growth_headers, monkeypatch):
    from api import browser_service
    # Mock render_spa_dom to avoid external network calls during unit tests
    monkeypatch.setattr(
        browser_service,
        "render_spa_dom",
        lambda domain: {
            "status": "success",
            "domain": domain,
            "rendered_by": "mock_chrome",
            "title": "Mock Corp",
            "emails": ["founders@mockcorp.com"],
            "phones": ["+1-555-0100"],
            "detected_stack": ["Next.js", "Tailwind CSS"],
            "has_react": True
        }
    )
    res = client.post("/api/browser/render", headers=growth_headers, json={
        "domain": "mockcorp.com"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "Next.js" in data["detected_stack"]
    assert "founders@mockcorp.com" in data["emails"]


def test_browser_screenshot_endpoint(client, growth_headers, monkeypatch):
    from api import browser_service
    monkeypatch.setattr(
        browser_service,
        "capture_screenshot",
        lambda domain, viewport: {
            "status": "success",
            "domain": domain,
            "viewport": viewport,
            "data_uri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        }
    )
    res = client.post("/api/browser/screenshot", headers=growth_headers, json={
        "domain": "mockcorp.com",
        "viewport": "mobile"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "data_uri" in data


def test_differential_compare_endpoint(client, growth_headers):
    res = client.post("/api/differential/compare", headers=growth_headers, json={
        "target_domain": "novalabs.internal",
        "competitor_domain": "benchmarks.internal"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "target" in data
    assert "competitor" in data
    assert "differential" in data
    assert "competitive_pitch_hook" in data["differential"]


def test_evidence_endpoints(client, growth_headers):
    from api import evidence_ledger
    rec = evidence_ledger.record_evidence(
        target_domain="ledgercorp.com",
        operation="test_ledger_api",
        observations={"http_status": 200},
        derivations={"lcp": 2.1},
        inferences={"p_close": 0.88},
        unknowns=[{"facet": "phone", "reason_code": "NOT_PUBLIC"}]
    )

    # 1. Test get by ID
    res_get = client.get(f"/api/evidence/ledger/{rec.evidence_id}", headers=growth_headers)
    assert res_get.status_code == 200
    assert res_get.json()["evidence"]["target_domain"] == "ledgercorp.com"

    # 2. Test get unknowns
    res_unk = client.get("/api/evidence/unknowns/ledgercorp.com", headers=growth_headers)
    assert res_unk.status_code == 200
    assert len(res_unk.json()["unknowns"]) >= 1





