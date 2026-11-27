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
