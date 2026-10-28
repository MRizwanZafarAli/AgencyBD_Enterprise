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
