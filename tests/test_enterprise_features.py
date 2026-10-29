"""
Tests for new Enterprise BD features:
1. Executive Presentation Deck Generator
2. Live Visitor Intent Radar & IP Deanonymization
3. Outbound Webhooks & CRM Integration Engine
4. Daily Executive BD Morning Briefing
"""

import json
import pytest
from database.db import get_db


def test_executive_deck_export(client, make_key):
    h = make_key(role="super_admin")
    res = client.post("/api/reports/deck", headers=h, json={"domain": "example.com", "output_format": "html"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert data["domain"] == "example.com"
    assert "deck_" in data["html_filename"]
    assert data["view_url"].startswith("/api/reports/view/deck_")

    # Verify viewing the generated deck
    view_res = client.get(data["view_url"], headers=h)
    assert view_res.status_code == 200
    assert "Executive Diagnostic" in view_res.text
    assert "example.com" in view_res.text


def test_visitor_intent_tracking_and_conversion(client, make_key):
    h = make_key(role="growth_lead")

    # 1. Track a visitor
    track_res = client.post(
        "/api/analytics/visitor-track",
        headers=h,
        json={"ip_address": "199.16.156.38", "page_url": "/pricing"}
    )
    assert track_res.status_code == 200
    event_id = track_res.json()["id"]
    assert track_res.json()["intent_score"] >= 80

    # 2. List visitors
    list_res = client.get("/api/analytics/visitor-intent", headers=h)
    assert list_res.status_code == 200
    events = list_res.json()["events"]
    assert any(e["id"] == event_id for e in events)

    # 3. Convert visitor to client
    conv_res = client.post(f"/api/analytics/visitor-intent/{event_id}/convert", headers=h)
    assert conv_res.status_code == 200
    lead_id = conv_res.json()["lead_id"]
    assert lead_id > 0

    # 4. Converting again returns already_converted
    conv_again = client.post(f"/api/analytics/visitor-intent/{event_id}/convert", headers=h)
    assert conv_again.json()["status"] == "already_converted"


def test_webhooks_crud_and_dispatch(client, admin_headers):
    # 1. Create webhook
    create_res = client.post(
        "/api/webhooks",
        headers=admin_headers,
        json={"url": "http://127.0.0.1:9999/webhook", "events": ["deal.won", "client.created"]}
    )
    assert create_res.status_code == 200
    wid = create_res.json()["id"]

    # 2. List webhooks
    list_res = client.get("/api/webhooks", headers=admin_headers)
    assert list_res.status_code == 200
    whs = list_res.json()["webhooks"]
    assert any(w["id"] == wid for w in whs)

    # 3. Test webhook ping
    test_res = client.post(f"/api/webhooks/{wid}/test", headers=admin_headers)
    assert test_res.status_code == 200
    assert "latency_ms" in test_res.json()

    # 4. Delete webhook
    del_res = client.delete(f"/api/webhooks/{wid}", headers=admin_headers)
    assert del_res.status_code == 200


def test_today_executive_briefing(client, make_key):
    h = make_key(role="growth_lead")
    res = client.get("/api/today/briefing", headers=h)
    assert res.status_code == 200
    data = res.json()
    assert "headline" in data
    assert "markdown" in data
    assert "focus_items" in data
    assert "pipeline_value_str" in data


def test_database_engine_info_endpoint(client, make_key):
    h = make_key(role="growth_lead")
    res = client.get("/api/system/database", headers=h)
    assert res.status_code == 200
    data = res.json()
    assert "backend" in data
    assert "status" in data
    assert data["backend"] in ("sqlite", "postgresql")


def test_task_queue_and_dlq_endpoints(client, admin_headers):
    # 1. Enqueue task
    enq_res = client.post(
        "/api/system/queue/enqueue",
        headers=admin_headers,
        json={"task_name": "ping", "payload": {"message": "hello queue"}, "max_retries": 2}
    )
    assert enq_res.status_code == 200
    task_id = enq_res.json()["task_id"]

    # 2. Inspect queue
    q_res = client.get("/api/system/queue", headers=admin_headers)
    assert q_res.status_code == 200
    assert "counts" in q_res.json()
    assert "recent_tasks" in q_res.json()

    # 3. Drain task
    drain_res = client.post("/api/system/queue/drain?limit=5", headers=admin_headers)
    assert drain_res.status_code == 200
    assert drain_res.json()["processed_count"] >= 1


def test_crm_sync_inbound_endpoints(client, admin_headers):
    # Ensure a test lead exists
    with get_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO leads (org_id, company_name, domain, source_channel, status) "
            "VALUES ('org_default', 'Test CRM Corp', 'testcrmcorp.com', 'outreach', 'sourced')"
        )
        db.commit()

    # Inbound CRM update
    sync_res = client.post(
        "/api/integrations/crm/sync",
        headers=admin_headers,
        json={
            "domain": "testcrmcorp.com",
            "deal_stage": "opportunity",
            "deal_value": 25000.0,
            "note": "Spoke to VP of Eng, moving to proposal"
        }
    )
    assert sync_res.status_code == 200
    assert sync_res.json()["deal_stage"] == "proposal_sent"
    assert sync_res.json()["deal_value"] == 25000.0

    # Inbound HubSpot webhook
    hs_res = client.post(
        "/api/integrations/crm/hubspot",
        json=[{"objectId": 1, "propertyName": "lifecyclestage", "propertyValue": "customer"}]
    )
    assert hs_res.status_code == 200

    # Export all
    exp_res = client.get("/api/integrations/crm/export-all", headers=admin_headers)
    assert exp_res.status_code == 200
    assert "leads" in exp_res.json()


def test_video_pitch_storyboard_endpoint(client, make_key):
    h = make_key(role="growth_lead")
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO leads (org_id, company_name, domain, source_channel) "
            "VALUES ('org_default', 'Storyboard Test Inc', 'storyboardtest.com', 'demo')"
        )
        lead_id = cursor.lastrowid
        db.commit()

    res = client.post(
        "/api/reports/video-storyboard",
        headers=h,
        json={"lead_id": lead_id, "prospect_name": "Sarah Connor"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "storyboard" in data
    assert "storyboard_scenes" in data["storyboard"]
    assert len(data["storyboard"]["storyboard_scenes"]) >= 2


def test_voice_sales_intelligence_endpoints(client, make_key):
    h = make_key(role="growth_lead")

    # 1. Transcript Qualification
    sample_transcript = (
        "Agency: Hi Mark, thanks for meeting. Can you tell me what latency challenges you're facing?\n"
        "Prospect: Our loading times are really slow, LCP is lagging and our AWS bill is high. "
        "We considered Toptal but their open hourly billing is expensive."
    )
    res_qual = client.post(
        "/api/voice/qualify",
        headers=h,
        json={"transcript": sample_transcript}
    )
    assert res_qual.status_code == 200
    analysis = res_qual.json()["analysis"]
    assert "toptal" in analysis["detected_competitors"]
    assert "site_performance_latency" in analysis["validated_customer_pain_points"]
    assert "founder_talk_percent" in analysis

    # 2. Objection Simulator
    res_obj = client.post(
        "/api/voice/simulate-objection",
        headers=h,
        json={"objection_text": "Your price is way too expensive for our budget"}
    )
    assert res_obj.status_code == 200
    result = res_obj.json()["result"]
    assert result["matched"] is True
    assert "reframe" in result
    assert "verbal_counter_script" in result

    # 3. Battlecards list
    res_cards = client.get("/api/voice/battlecards", headers=h)
    assert res_cards.status_code == 200
    assert len(res_cards.json()["battlecards"]) >= 2

