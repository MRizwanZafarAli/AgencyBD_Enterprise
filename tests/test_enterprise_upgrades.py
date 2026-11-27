"""
Tests for Phase 1-5 Enterprise Upgrades:
1. Two-Way Master Inbox ingest & sequence auto-pause
2. Scheduled Autopilot, Round-Robin Assignment & Risk-Tiered Autonomy Gate
3. Social Intent Radar connector
4. Sales Navigator Companion lead capture & Account IQ
5. Interactive Proposals & Smart Links view/e-sign telemetry
"""

import pytest
from fastapi.testclient import TestClient

from api import app
from database.db import get_db, init_db
from database.models import LeadRepository
from orchestrator.schedule_runner import (
    assign_round_robin,
    create_schedule,
    evaluate_tier_a_auto_approve,
    list_schedules,
    toggle_schedule,
)
from security.auth import SecurityService


@pytest.fixture(autouse=True)
def _db_ready():
    init_db()


def _headers(role: str = "super_admin", org_id: str = "org_ent_test") -> dict:
    tok = SecurityService.create_jwt_token(user_id=f"test_{role}", role=role, org_id=org_id)
    return {"Authorization": f"Bearer {tok}"}


def test_master_inbox_ingest_and_sequence_auto_pause():
    client = TestClient(app)
    org = "org_ent_inbox"
    lead = LeadRepository.create_or_get_lead("Acme Inbox Co", "acmeinbox.example", org_id=org)

    with get_db() as conn:
        seq_id = conn.execute(
            "INSERT INTO sequences (org_id, name, steps_json) VALUES (?, ?, ?)",
            (org, "Seq1", '[{"subject":"hi","body":"hello","delay_days":0}]'),
        ).lastrowid
        conn.execute(
            """
            INSERT INTO sequence_enrollments (org_id, sequence_id, lead_id, recipient_email, country_code, next_run_at, status)
            VALUES (?, ?, ?, 'ceo@acmeinbox.example', 'US', CURRENT_TIMESTAMP, 'active')
            """,
            (org, seq_id, lead["id"]),
        )
        conn.commit()

    res = client.post(
        "/api/email/inbox/ingest",
        headers=_headers("growth_lead", org),
        json={
            "sender_email": "ceo@acmeinbox.example",
            "recipient_email": "outreach@agencybd.enterprise",
            "subject": "Re: Audit",
            "body": "Sounds interesting, can we talk Tuesday?",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ingested"
    assert body["lead_id"] == lead["id"]

    # Sequence must be auto-paused ('replied')
    with get_db() as conn:
        st = conn.execute(
            "SELECT status FROM sequence_enrollments WHERE org_id = ? AND recipient_email = 'ceo@acmeinbox.example'",
            (org,),
        ).fetchone()["status"]
        assert st == "replied"

    inbox_res = client.get("/api/email/inbox", headers=_headers("growth_lead", org))
    assert inbox_res.status_code == 200
    assert len(inbox_res.json()["messages"]) >= 1


def test_scheduled_autopilot_and_tier_a_gate():
    org = "org_ent_sched"
    s = create_schedule(org_id=org, name="Morning React Hunt", channel="hiring", query="react", cadence_hours=12)
    assert s["enabled"] == 1
    assert any(x["id"] == s["id"] for x in list_schedules(org))

    toggled = toggle_schedule(org, s["id"], False)
    assert toggled["enabled"] == 0

    lead = LeadRepository.create_or_get_lead("RR Co", "rrco.example", org_id=org)
    owner = assign_round_robin(org, lead["id"])
    assert owner in ("sdr_rep", "growth_lead")

    good = evaluate_tier_a_auto_approve(
        subject="Quick question about your site",
        body="Hi there, I noticed your site lacks a meta description and has slow LCP.",
        country_code="US",
        mx_verified=True,
        fit_score=0.85,
    )
    assert good["eligible"] is True

    bad = evaluate_tier_a_auto_approve(
        subject="Quick question",
        body="Hi there, checking in.",
        country_code="US",
        mx_verified=False,
        fit_score=0.60,
    )
    assert bad["eligible"] is False and len(bad["reasons"]) >= 2


def test_account_iq_proposals_and_smart_links():
    client = TestClient(app)
    org = "org_ent_prop"
    lead = LeadRepository.create_or_get_lead("SmartLink Co", "smartlink.example", org_id=org)

    iq = client.get(f"/api/clients/{lead['id']}/account-iq", headers=_headers("growth_lead", org))
    assert iq.status_code == 200
    assert iq.json()["company_name"] == "SmartLink Co"

    prop_res = client.post(
        "/api/proposals/create",
        headers=_headers("growth_lead", org),
        json={
            "lead_id": lead["id"],
            "title": "Modernization Scope",
            "summary": "Fix performance & security.",
            "scope_items": ["Fix TLS", "Improve LCP"],
            "price_amount": 4500,
        },
    )
    assert prop_res.status_code == 200
    token = prop_res.json()["proposal"]["token"]

    # Public view logs Smart Link telemetry
    view_res = client.get(f"/p/{token}")
    assert view_res.status_code == 200 and "Modernization Scope" in view_res.text

    # Public e-sign acceptance marks proposal accepted & lead won
    accept_res = client.post(f"/p/{token}/accept", data={"signed_by": "Jane CEO"})
    assert accept_res.status_code == 200 and "Proposal Accepted" in accept_res.text

    list_res = client.get(f"/api/proposals/lead/{lead['id']}", headers=_headers("growth_lead", org))
    assert list_res.status_code == 200
    assert list_res.json()["proposals"][0]["status"] == "accepted"
    assert list_res.json()["smart_link_views"][0]["view_count"] >= 1


def test_sales_nav_companion_capture():
    client = TestClient(app)
    org = "org_ent_sn"
    res = client.post(
        "/api/v1/browser/session/capture-leads",
        headers=_headers("growth_lead", org),
        json={
            "leads": [
                {
                    "company_name": "NavCapture Corp",
                    "domain": "navcapture.example",
                    "contact_name": "Sam Founder",
                    "contact_title": "CEO",
                    "linkedin_url": "https://www.linkedin.com/in/sam-founder",
                }
            ]
        },
    )
    assert res.status_code == 200
    assert res.json()["captured_count"] == 1


def test_email_hub_ai_writer_templates_crud_and_bulk_send():
    client = TestClient(app)
    org = "org_ent_email_ai"
    sdr_headers = _headers("sdr_rep", org)

    # 1. AI Writer offline structured fallback works without paid keys
    ai_res = client.post(
        "/api/email/ai-draft",
        headers=sdr_headers,
        json={
            "provider": "auto",
            "recipient_name": "Sarah Jenkins",
            "company_name": "Acme Health",
            "goal": "15-min performance teardown",
            "tone": "consultative",
        },
    )
    assert ai_res.status_code == 200
    assert "Sarah" in ai_res.json()["body"]
    assert ai_res.json()["provider_used"] == "structured_fallback"

    # 2. Custom Templates CRUD
    c_res = client.post(
        "/api/email/templates",
        headers=sdr_headers,
        json={"name": "Custom Pitch", "subject": "Hello {{company}}", "body": "Hi {{first_name}}, quick note."},
    )
    assert c_res.status_code == 200
    db_id = c_res.json()["db_id"]
    list_res = client.get("/api/email/templates", headers=sdr_headers)
    assert any(t["name"] == "Custom Pitch" for t in list_res.json())
    d_res = client.delete(f"/api/email/templates/{db_id}", headers=sdr_headers)
    assert d_res.status_code == 200

    # 3. Bulk send queues drafts with merge tags & spintax
    b_res = client.post(
        "/api/email/bulk-send",
        headers=sdr_headers,
        json={
            "recipients": [
                {"email": "a@example.com", "name": "Alice Smith", "company": "AlphaCo"},
                {"email": "bad-email", "name": "Bad", "company": "None"},
            ],
            "subject": "{Hi|Hello} {{company}}",
            "body": "Hey {{first_name}}, let's chat.",
            "as_draft": True,
        },
    )
    assert b_res.status_code == 200
    assert b_res.json()["processed"] == 1
    assert len(b_res.json()["skipped"]) == 1


def test_local_demo_site_guardrails_and_bulk_scrape_queue():
    client = TestClient(app)
    hdrs = _headers("growth_lead", "org_ent_local_qa")

    # 1. Demo site has noindex meta, X-Robots-Tag, sticky bar, and 14-day TTL
    d_res = client.post(
        "/api/hunt/local/demo_site",
        headers=hdrs,
        json={"name": "Yorkshire Smiles", "category": "Dentist", "city": "Leeds, UK", "phone": "+44 113 000 0000"},
    )
    assert d_res.status_code == 200
    assert d_res.json()["expires_in_days"] == 14
    view = client.get(d_res.json()["demo_url"])
    assert view.status_code == 200
    assert 'content="noindex, nofollow"' in view.text
    assert view.headers.get("x-robots-tag") == "noindex, nofollow"
    assert "Concept preview prepared for Yorkshire Smiles" in view.text

    # 2. Bulk scrape queue returns job_id immediately and exposes status endpoint
    b_res = client.post(
        "/api/v1/browser/bulk-scrape",
        headers=hdrs,
        json={"items": [{"id": "p1", "url": "https://example.invalid", "name": "Example"}]},
    )
    assert b_res.status_code == 200
    job_id = b_res.json()["job_id"]
    s_res = client.get(f"/api/v1/browser/bulk-scrape/{job_id}", headers=hdrs)
    assert s_res.status_code == 200 and s_res.json()["total"] == 1


def test_find_jobs_qa_checks_stopwords_feedback_and_red_flags():
    from database.models import OpportunityRepository
    from radar.fit import apply_feedback_adjustment, feedback_profile, score_opportunity

    org = "org_ent_jobs_qa"
    profile = {"react", "python", "playwright", "core", "within"}
    # Stop-words ('core', 'within') are filtered out; 'no agencies' triggers red flag
    fit = score_opportunity(
        "Senior React Engineer",
        "Work within core workflows. No agencies or third-party recruiters.",
        "hiring_signal",
        None,
        profile,
    )
    assert "no_agencies_red_flag" in fit.risk_flags
    assert all("within" not in r and "core" not in r for r in fit.reasons)

    # Persist thumbs-down feedback and confirm feedback_profile down-ranks future scans
    opp = OpportunityRepository.create_opportunity(
        opp_type="hiring_signal",
        source="remoteok",
        title="QA Automation Engineer",
        description="Playwright testing",
        external_id="qa_fb_1",
        fit_score=0.7,
        company_name="Upgrade",
        org_id=org,
    )
    client = TestClient(app)
    fb_res = client.post(
        f"/api/opportunities/{opp['id']}/feedback",
        headers=_headers("growth_lead", org),
        json={"vote": "down"},
    )
    assert fb_res.status_code == 200
    fb = feedback_profile(org)
    adjusted = apply_feedback_adjustment(fit, "QA Automation Engineer", "Upgrade", fb)
    assert adjusted.score is not None and adjusted.score < (fit.score or 1.0)


def test_social_intent_engine_classification_queries_and_reply_studio():
    from connectors.social_radar import classify_intent, extract_external_urls
    from intel.social_intel import build_offer_queries, draft_social_reply, resolve_author_identity
    from api import app

    # 1. Intent classification, boolean query, competitor complaint & trigger sentence
    buying = classify_intent(
        "Our Shopify store is slow. Looking for an agency to help redesign our checkout.",
        query='("shopify" OR "ecommerce") AND ("agency" OR "redesign")',
        reply_count=2,
        is_comment=True,
    )
    assert buying is not None
    assert buying["intent_type"] == "buying_request"
    assert "Looking for an agency" in buying["trigger_sentence"]
    assert buying["intent_score"] >= 60

    comp = classify_intent(
        "Honestly fed up with Wix, migrating off next week.",
        competitors=["Wix", "HubSpot"],
    )
    assert comp is not None
    assert comp["intent_type"] == "competitor_complaint"

    noise = classify_intent("[For Hire] Junior dev looking for a job, check my resume")
    assert noise is None

    # 2. External URL extraction ignores social platforms and keeps business domains
    urls = extract_external_urls("Check https://reddit.com/r/saas and our site https://acme-dental.io/book")
    assert urls == ["https://acme-dental.io/book"]

    # 3. Author identity extraction from post text (no external network required)
    ident = resolve_author_identity(
        platform="Reddit",
        author="saas_founder99",
        title="Need a Webflow agency",
        description="Building AcmeFlow at https://acmeflow.io — connect on https://linkedin.com/in/saasfounder99",
    )
    assert ident["website_domain"] == "acmeflow.io"
    assert ident["linkedin_url"] == "https://linkedin.com/in/saasfounder99"
    assert ident["company_name"] == "AcmeFlow"

    # 4. Offer-aware queries & reply studio endpoints
    client = TestClient(app)
    hdrs = _headers("growth_lead", "org_social_qa")
    oq = client.get("/api/leadfinder/social/offer-queries", headers=hdrs)
    assert oq.status_code == 200 and len(oq.json()["queries"]) >= 1

    rep = client.post(
        "/api/leadfinder/social/draft-reply",
        headers=hdrs,
        json={
            "platform": "Reddit",
            "community": "r/entrepreneur",
            "title": "Need Shopify speed help",
            "description": "Our store takes 6 seconds to load.",
            "intent_type": "pain_point",
            "trigger_sentence": "Our store takes 6 seconds to load.",
            "tone": "value_first",
        },
    )
    assert rep.status_code == 200
    body = rep.json()
    assert "draft" in body and len(body["draft"]) > 20
    assert "No direct links" in body["guardrail"]
    assert build_offer_queries("org_social_qa")
    assert draft_social_reply(
        platform="Hacker News",
        community="Ask HN",
        title="Need React audit",
        description="",
        intent_type="buying_request",
        trigger_sentence="Need React audit",
        tone="direct_dm",
    )["tone"] == "direct_dm"


def test_social_radar_qa_bluesky_auth_hn_html_and_dedup(monkeypatch):
    from connectors.social_radar import (
        SocialIntentRadarConnector,
        _canonical_url,
        _strip_html_entities,
        _title_author_hash,
    )

    # 1. Bluesky without credentials surfaces auth_required instead of 403
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    conn = SocialIntentRadarConnector()
    bsky_items, bsky_health = conn.fetch_bluesky(query="shopify")
    assert bsky_items == []
    assert bsky_health["status"] == "auth_required"

    # 2. HN HTML entity stripping before trigger_sentence + numericFilters passed to Algolia
    cleaned = _strip_html_entities("<p>We&#x27;re looking for an agency &amp; dev.</p>")
    assert "<p>" not in cleaned and "We're looking for an agency & dev." in cleaned

    captured_urls = []
    def fake_safe_get(url, timeout=8, headers=None):
        captured_urls.append(url)
        return 200, '{"hits": [{"objectID": "99", "comment_text": "<p>Looking for an agency &#x27;asap&#x27;.</p>", "story_title": "Ask HN: Agencies", "author": "alice", "created_at": "2026-11-27T08:00:00Z", "points": 3}]}', {}

    monkeypatch.setattr("connectors.social_radar.SafeFetcher.safe_get", fake_safe_get)
    hn_items, hn_health = conn.fetch_hn_comments(query="agency", time_window="24h")
    assert hn_health["status"] == "ok" and len(hn_items) == 1
    assert "<p>" not in hn_items[0].description
    assert "numericFilters=created_at_i>=" in captured_urls[0]

    # 3. Canonical URL & (title, author) deduplication
    assert _canonical_url("https://www.reddit.com/r/SaaS/comments/abc/title/?utm_source=ddg") == "reddit.com/r/saas/comments/abc/title"
    assert _title_author_hash("Need Shopify Dev!", "Bob_99") == _title_author_hash("need shopify dev", "bob99")


def test_tenders_enterprise_connectors_scorecard_and_bid_studio():
    from connectors.ted import parse_notices as parse_ted
    from connectors.uk_fts import parse_releases as parse_uk_fts
    from database.models import OpportunityRepository
    from api import app

    # 1. TED parses buyer_email, country, and notice_stage
    ted_items = parse_ted({
        "notices": [{
            "publication-number": "123456-2026",
            "notice-title": {"ita": "PROCEDURA APERTA - Servizi informatici"},
            "description-lot": {"ita": "Sviluppo piattaforma cloud"},
            "buyer-name": {"ita": "Comune di Milano"},
            "buyer-email": {"ita": "appalti@comune.milano.it"},
            "buyer-country": {"ita": "ITA"},
            "notice-type": {"ita": "cn-standard"},
            "classification-cpv": ["72200000"],
            "estimated-value-lot": [350000],
            "deadline-receipt-tender-date-lot": ["2026-12-20T12:00:00Z"],
        }]
    })
    assert len(ted_items) == 1
    assert ted_items[0].metadata["buyer_email"] == "appalti@comune.milano.it"
    assert ted_items[0].metadata["country"] == "ITA"
    assert ted_items[0].metadata["notice_stage"] == "rfp"

    # 2. UK FTS parses contactPoint email & award incumbent
    uk_items = parse_uk_fts({
        "releases": [{
            "id": "ocds-1",
            "ocid": "ocds-b5fd17-1",
            "tag": ["award"],
            "buyer": {"id": "b1", "name": "NHS Digital"},
            "parties": [{"id": "b1", "roles": ["buyer"], "contactPoint": {"email": "procure@nhs.uk", "telephone": "+44 20 7946 0000"}, "address": {"countryName": "United Kingdom"}}],
            "tender": {"title": "Cloud Portal", "description": "ISO 27001 required. 60% Technical 40% Price.", "classification": {"id": "72200000"}, "value": {"amount": 5000000, "currency": "GBP"}},
            "awards": [{"date": "2024-01-10", "suppliers": [{"name": "Tier1 Prime Ltd"}]}],
        }]
    })
    assert len(uk_items) == 1
    assert uk_items[0].metadata["buyer_email"] == "procure@nhs.uk"
    assert uk_items[0].metadata["incumbent"] == "Tier1 Prime Ltd"

    # 3. Tender Scorecard, Compliance Matrix, Bid Studio, Translate & Rescore APIs
    org = "org_tenders_qa"
    opp = OpportunityRepository.create_opportunity(
        opp_type="tender",
        source="uk_fts",
        title="PROCEDURA APERTA Digital Platform",
        description="ISO 27001 mandatory. 60% Technical 40% Price. Max 2000 words.",
        external_id="tnd_qa_1",
        budget_max=5_000_000,
        company_name="ECMWF",
        org_id=org,
    )
    client = TestClient(app)
    hdrs = _headers("growth_lead", org)

    sc = client.post(f"/api/tenders/{opp['id']}/scorecard", headers=hdrs)
    assert sc.status_code == 200
    sc_data = sc.json()
    assert sc_data["verdict"] in ("GO", "CONDITIONAL", "NO-GO")
    assert sc_data["mega_tender_teaming"]["is_mega"] is True

    cm = client.post(f"/api/tenders/{opp['id']}/compliance-matrix", headers=hdrs)
    assert cm.status_code == 200 and cm.json()["count"] >= 3

    ba = client.post(f"/api/tenders/{opp['id']}/bid-actions", headers=hdrs, json={"action": "clarification_qa"})
    assert ba.status_code == 200 and "Clarification" in ba.json()["title"]

    tr = client.post(f"/api/tenders/{opp['id']}/translate", headers=hdrs)
    assert tr.status_code == 200 and "Open Procedure" in tr.json()["translated"]

    rs = client.post("/api/tenders/rescore", headers=hdrs)
    assert rs.status_code == 200 and rs.json()["rescored"] >= 1


def test_tenders_qa_fx_utc_deadline_and_sam_health(monkeypatch):
    from intel.tender_intel import normalize_to_gbp, _days_until
    from api import app

    # 1. FX normalization to GBP
    assert normalize_to_gbp(2_100_000, "EUR") < 2_000_000  # 2.1M EUR * 0.85 = 1.785M GBP
    assert normalize_to_gbp(2_600_000, "USD") >= 2_000_000  # 2.6M USD * 0.79 = 2.054M GBP
    assert normalize_to_gbp(None, "GBP") == 0.0

    # 2. UTC deadline parsing (date-only treats end of UTC day)
    assert _days_until("2020-01-01") < 0
    assert _days_until(None) is None

    # 3. SAM.gov source-health surfaces auth_required when key is missing
    monkeypatch.delenv("SAM_GOV_API_KEY", raising=False)
    client = TestClient(app)
    res = client.get("/api/tenders/source-health", headers=_headers("growth_lead", "org_tenders_qa"))
    assert res.status_code == 200
    by_id = {s["id"]: s for s in res.json()["sources"]}
    assert by_id["sam_gov"]["status"] == "auth_required"


def test_watching_command_center_stacking_autoplay_and_bulk():
    from leadfinder import engine as lf_engine
    from api import app

    org = "org_watch_qa"
    client = TestClient(app)
    hdrs = _headers("growth_lead", org)

    # 1. Create a tender_cpv monitor with auto_play=True and verify it runs cleanly
    c_res = client.post(
        "/api/leadfinder/searches",
        headers=hdrs,
        json={
            "name": "NHS Tender Watch",
            "source": "tender_cpv",
            "params": {"q": "", "auto_play": True, "min_score_alert": 70, "alert_mode": "instant"},
            "notify": True,
            "every_hours": 6,
        },
    )
    assert c_res.status_code == 200
    s = c_res.json()
    assert s["auto_play"] is True
    assert s["alert_mode"] == "instant"

    # 2. Verify bulk-save and bulk-dismiss endpoints accept hit_ids cleanly
    bs = client.post("/api/leadfinder/hits/bulk-save", headers=hdrs, json={"hit_ids": []})
    bd = client.post("/api/leadfinder/hits/bulk-dismiss", headers=hdrs, json={"hit_ids": []})
    assert bs.status_code == 200 and bs.json()["saved"] == 0
    assert bd.status_code == 200 and bd.json()["dismissed"] == 0
    assert lf_engine._infer_domain("https://acme-dental.io/careers", {}) == "acme-dental.io"
    assert lf_engine._infer_domain("https://jobs.acme-dental.io/role", {}) == "acme-dental.io"
    assert lf_engine._normalize_company_name("Acme Dental Ltd.") == lf_engine._normalize_company_name("Acme Dental, Inc")
    assert lf_engine.MAX_AUTO_PLAY_PER_RUN == 10


def test_today_command_center_briefing_kpis_and_attribution():
    from api import app

    client = TestClient(app)
    res = client.get("/api/today/command-center?days=14", headers=_headers("super_admin", "org_default"))
    assert res.status_code == 200
    data = res.json()
    assert len(data["briefing_bullets"]) == 3
    assert "weighted_forecast" in data["kpis"]
    assert "delivered_pct" in data["kpis"]
    assert len(data["attribution_matrix"]) == 5
    assert len(data["velocity_series"]) == 14
    assert "replies_followups" in data["action_queue"]
    assert "bottlenecks" in data["action_queue"]


def test_clients_pipeline_inline_value_bulk_and_hygiene():
    from database.models import LeadRepository
    from api import app

    org = "org_clients_qa"
    l1 = LeadRepository.create_or_get_lead(company_name="Acme Dental", domain="acmedental.io", source_channel="map_osm", org_id=org)
    l2 = LeadRepository.create_or_get_lead(company_name="Does anyone know a dev?", domain="hn-test.local", source_channel="social_hacker_news", org_id=org)
    client = TestClient(app)
    hdrs = _headers("growth_lead", org)

    # 1. Inline value update
    v_res = client.post(f"/api/pipeline/deals/{l1['id']}/value", headers=hdrs, json={"deal_value": 12500})
    assert v_res.status_code == 200 and v_res.json()["deal_value"] == 12500

    # 2. Bulk stage change
    b_res = client.post("/api/pipeline/deals/bulk", headers=hdrs, json={"lead_ids": [l1["id"]], "action": "stage", "stage": "audited"})
    assert b_res.status_code == 200 and b_res.json()["updated"] == 1

    # 3. Hygiene scan detects .local / raw HN question junk
    h_res = client.get("/api/pipeline/deals/hygiene", headers=hdrs)
    assert h_res.status_code == 200
    assert any(j["id"] == l2["id"] for j in h_res.json()["junk"])

    # 4. Clean junk purges .local / raw HN question
    c_res = client.post("/api/pipeline/deals/clean_junk", headers=hdrs)
    assert c_res.status_code == 200 and c_res.json()["deleted_count"] >= 1


def test_clients_pipeline_qa_merge_rotting_reset_and_lost_reason():
    from database.db import get_db
    from database.models import LeadRepository
    from api import app

    org = "org_clients_qa_3checks"
    client = TestClient(app)
    hdrs = _headers("growth_lead", org)

    # Create two leads (using direct SQL for the duplicate so we can test merge re-parenting)
    keep = LeadRepository.create_or_get_lead(company_name="KeepCo", domain="keepco.io", source_channel="map_osm", org_id=org)
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO leads (org_id, company_name, domain, source_channel, status) VALUES (?, ?, ?, ?, ?)",
            (org, "KeepCo Dup", "www.keepco.io", "social_hacker_news", "sequence_active"),
        )
        dup_id = cur.lastrowid
        # Attach child records to dup_id across decision_makers, tech_audits, client_notes, outbound_drafts, work_items
        conn.execute(
            "INSERT INTO decision_makers (org_id, lead_id, first_name, last_name, title, email) VALUES (?, ?, 'Jane', 'Doe', 'CEO', 'jane@keepco.io')",
            (org, dup_id),
        )
        conn.execute(
            "INSERT INTO tech_audits (org_id, lead_id, load_time_ms, ttfb_ms, lcp_score, mobile_responsive) VALUES (?, ?, 1200, 300, 3.1, 1)",
            (org, dup_id),
        )
        conn.execute(
            "INSERT INTO client_notes (org_id, lead_id, kind, body) VALUES (?, ?, 'note', 'Met at conference')",
            (org, dup_id),
        )
        conn.execute(
            "INSERT INTO outbound_drafts (org_id, lead_id, recipient_email, country_code, subject, body, status) VALUES (?, ?, 'jane@keepco.io', 'US', 'Hi', 'Body', 'pending')",
            (org, dup_id),
        )
        conn.execute(
            "INSERT INTO work_items (org_id, kind, title, entity_type, entity_id, status) VALUES (?, 'task', 'Follow up', 'lead', ?, 'open')",
            (org, dup_id),
        )
        # Backdate keep's updated_at by 10 days in sequence_active so it is rotting
        conn.execute(
            "UPDATE leads SET status = 'sequence_active', updated_at = datetime('now', '-10 days') WHERE id = ?",
            (keep["id"],),
        )
        conn.commit()

    # Check 1: Merge re-parents all child records to keep["id"] before deleting dup_id
    m_res = client.post("/api/pipeline/deals/merge", headers=hdrs, json={"keep_id": keep["id"], "remove_id": dup_id})
    assert m_res.status_code == 200
    reparented = m_res.json()["reparented"]
    assert reparented.get("decision_makers") == 1
    assert reparented.get("tech_audits") == 1
    assert reparented.get("client_notes") == 1
    assert reparented.get("outbound_drafts") == 1
    assert reparented.get("work_items") == 1
    with get_db() as conn:
        assert conn.execute("SELECT id FROM leads WHERE id = ?", (dup_id,)).fetchone() is None
        assert conn.execute("SELECT COUNT(*) FROM client_notes WHERE lead_id = ? AND org_id = ?", (keep["id"], org)).fetchone()[0] == 1

    # Check 2: Backdate keep's updated_at by 10 days, verify rotting, then stage move resets days_idle to 0 and is_rotting to False
    with get_db() as conn:
        conn.execute(
            "UPDATE leads SET status = 'sequence_active', updated_at = datetime('now', '-10 days') WHERE id = ?",
            (keep["id"],),
        )
        conn.commit()
    p1 = client.get("/api/pipeline/deals", headers=hdrs).json()
    seq_leads = [x for x in p1["stages"]["sequence_active"]["leads"] if x["id"] == keep["id"]]
    assert len(seq_leads) == 1
    assert seq_leads[0]["days_idle"] >= 10
    assert seq_leads[0]["is_rotting"] is True

    s_res = client.post("/api/pipeline/deals/stage", headers=hdrs, json={"lead_id": keep["id"], "new_stage": "meeting_booked"})
    assert s_res.status_code == 200
    p2 = client.get("/api/pipeline/deals", headers=hdrs).json()
    mtg_leads = [x for x in p2["stages"]["meeting_booked"]["leads"] if x["id"] == keep["id"]]
    assert len(mtg_leads) == 1
    assert mtg_leads[0]["days_idle"] == 0
    assert mtg_leads[0]["is_rotting"] is False

    # Check 3: Lost-reason capture persists on lead and in pipeline response
    l_res = client.post(
        "/api/pipeline/deals/stage",
        headers=hdrs,
        json={"lead_id": keep["id"], "new_stage": "lost", "lost_reason": "No Budget"},
    )
    assert l_res.status_code == 200
    p3 = client.get("/api/pipeline/deals", headers=hdrs).json()
    lost_leads = [x for x in p3["stages"]["lost"]["leads"] if x["id"] == keep["id"]]
    assert len(lost_leads) == 1
    assert lost_leads[0]["lost_reason"] == "No Budget"


def test_channels_archetype_registry_capture_gigs_reviews_and_overview():
    from database.models import LeadRepository
    from api import app

    org = "org_channels_archetype_qa"
    client = TestClient(app)
    hdrs = _headers("growth_lead", org)

    # 1. Registry returns archetype + native currency per platform
    plat_res = client.get("/api/channels/platforms", headers=hdrs)
    assert plat_res.status_code == 200
    plats = {p["id"]: p for p in plat_res.json()["platforms"]}
    assert plats["upwork"]["archetype"] == "bidding_marketplace"
    assert plats["upwork"]["native_currency"]["name"] == "Connects"
    assert plats["freelancer"]["native_currency"]["name"] == "Bids"
    assert plats["peopleperhour"]["native_currency"]["name"] == "Proposal Credits"
    assert plats["guru"]["native_currency"]["name"] == "Quotes"
    assert plats["clutch"]["archetype"] == "review_directory"
    assert plats["fiverr"]["archetype"] == "inbound_storefront"

    # 2. Side-panel capture logs into channel_bids AND creates CRM lead
    cap = client.post(
        "/api/channels/upwork/capture",
        headers=hdrs,
        json={
            "title": "Next.js SaaS Redesign",
            "client_name": "NovaHealth",
            "url": "https://upwork.com/jobs/novahealth",
            "budget": 8500,
            "currency_spent": 16,
            "boosted": True,
            "hook_template_id": "Audit-L1",
            "client_payment_verified": True,
            "status": "replied",
        },
    )
    assert cap.status_code == 200
    assert cap.json()["bid"]["crm_lead_id"] == cap.json()["lead"]["id"]

    # 3. Fiverr gig SKU & storefront KPIs
    g_res = client.post(
        "/api/channels/fiverr/gigs",
        headers=hdrs,
        json={"title": "Next.js Audit", "impressions": 1000, "clicks": 50, "orders": 5, "revenue": 2500},
    )
    assert g_res.status_code == 200
    f_sum = client.get("/api/channels/fiverr/summary", headers=hdrs).json()
    assert [k["id"] for k in f_sum["kpis"]] == ["active_gigs", "ctr_pct", "cvr_pct", "avg_response_sla", "monthly_revenue"]
    assert f_sum["native"]["gigs"][0]["title"] == "Next.js Audit"

    # 4. Won CRM client surfaces in Clutch Review Engine
    won = LeadRepository.create_or_get_lead(company_name="WonClient Co", domain="wonclient.io", source_channel="linkedin", org_id=org)
    LeadRepository.update_deal_stage(won["id"], "won", org_id=org)
    c_sum = client.get("/api/channels/clutch/summary", headers=hdrs).json()
    assert any(w["id"] == won["id"] for w in c_sum["native"]["won_clients"])
    assert [k["id"] for k in c_sum["kpis"]] == ["verified_reviews", "avg_rating", "directory_rank", "inbound_inquiries", "utm_traffic"]

    # 5. Overview returns ROI matrix + alerts, and preferences hide/show channels
    ov = client.get("/api/channels/overview", headers=hdrs).json()
    assert len(ov["platforms"]) >= 9
    assert isinstance(ov["alerts"], list)
    pref = client.post("/api/channels/preferences", headers=hdrs, json={"hidden_platforms": ["guru"]})
    assert pref.status_code == 200 and "guru" in pref.json()["hidden_platforms"]
    ov2 = client.get("/api/channels/overview", headers=hdrs).json()
    assert not any(r["platform"] == "guru" for r in ov2["platforms"])

    # 6. QA Check 1: Idempotent 1-click capture (trailing slash / repeat URL deduplicates)
    cap2 = client.post(
        "/api/channels/upwork/capture",
        headers=hdrs,
        json={"title": "Next.js SaaS Redesign v2", "url": "https://upwork.com/jobs/novahealth/", "budget": 9500},
    )
    assert cap2.status_code == 200
    assert cap2.json()["deduplicated"] is True
    assert cap2.json()["bid"]["id"] == cap.json()["bid"]["id"]
    assert cap2.json()["bid"]["bid_amount"] == 9500

    # 7. QA Check 2: Zero-spend channel returns net_roi_pct=None (never Infinity/NaN)
    fiverr_row = next(r for r in ov2["platforms"] if r["platform"] == "fiverr")
    assert fiverr_row["spend_usd"] == 0
    assert fiverr_row["net_roi_pct"] is None

    # 8. QA Check 3: Custom channel slug collision guard + org_id preference isolation
    cc1 = client.post("/api/channels/custom", headers=hdrs, json={"label": "Upwork", "archetype": "custom"})
    cc2 = client.post("/api/channels/custom", headers=hdrs, json={"label": "All", "archetype": "custom"})
    assert cc1.status_code == 200 and cc1.json()["slug"] == "custom_upwork"
    assert cc2.status_code == 200 and cc2.json()["slug"] == "custom_all"

    other_hdrs = _headers("growth_lead", "org_channels_isolated_b")
    other_plats = client.get("/api/channels/platforms", headers=other_hdrs).json()
    assert "guru" not in other_plats["hidden_platforms"]
    assert not any(p["id"] == "custom_upwork" for p in other_plats["platforms"])


def test_email_hub_and_tools_enterprise_upgrades():
    from database.db import get_db
    from database.models import LeadRepository
    from api import app

    org = "org_email_tools_qa"
    client = TestClient(app)
    hdrs = _headers("super_admin", org)

    # 1. Unified Email Hub overview: sent_today <= metrics_7d.sent
    ov = client.get("/api/email/overview", headers=hdrs).json()
    assert ov["fleet"]["sent_today"] <= ov["metrics_7d"]["sent"]
    assert "has_real_mailbox" in ov

    # 2. Mailbox >3% bounce guard auto-pauses mailbox
    mb = client.post("/api/email/mailboxes", headers=hdrs, json={"email": "sender@acme.io", "display_name": "Acme Sender"}).json()
    with get_db() as conn:
        for i in range(6):
            conn.execute(
                "INSERT INTO outreach_events (org_id, mailbox_id, recipient_email, event_type) VALUES (?, ?, ?, 'sent')",
                (org, mb["id"], f"r{i}@example.com"),
            )
        conn.execute(
            "INSERT INTO outreach_events (org_id, mailbox_id, recipient_email, event_type) VALUES (?, ?, 'r0@example.com', 'bounced')",
            (org, mb["id"]),
        )
        conn.commit()
    boxes = client.get("/api/email/mailboxes", headers=hdrs).json()
    box = next(b for b in boxes if b["id"] == mb["id"])
    assert box["bounce_rate_7d"] > 3.0
    assert box["is_active"] == 0
    assert box["reputation_status"] == "paused"
    assert box["auto_paused_reason"]

    # 3. Master Inbox mark-interested advances deal to meeting_booked
    lead = LeadRepository.create_or_get_lead(company_name="InboxLead", domain="inboxlead.io", source_channel="email", org_id=org)
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO inbox_messages (org_id, lead_id, direction, sender_email, recipient_email, subject, body, category, sentiment, status) "
            "VALUES (?, ?, 'inbound', 'ceo@inboxlead.io', 'sender@acme.io', 'Re: Audit', 'Let us book a call', 'objection', 'positive', 'unread')",
            (org, lead["id"]),
        )
        msg_id = cur.lastrowid
        conn.commit()
    mi = client.post(f"/api/email/inbox/{msg_id}/mark-interested", headers=hdrs)
    assert mi.status_code == 200 and mi.json()["category"] == "interested"
    assert LeadRepository.get_lead(lead["id"], org)["status"] == "meeting_booked"

    # 4. Tools overview returns telemetry + recent_runs
    t_ov = client.get("/api/tools/overview", headers=hdrs)
    assert t_ov.status_code == 200
    assert t_ov.json()["telemetry"]["swarm_agents"] == 8
    assert isinstance(t_ov.json()["recent_runs"], list)
