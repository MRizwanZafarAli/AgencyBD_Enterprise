"""
Unit & Integration Tests for Swarm API Endpoints (`routers/swarm.py`).
"""

import pytest
from fastapi.testclient import TestClient
from api import app
from database.db import init_db
from security.auth import SecurityService

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def super_admin_headers():
    token = SecurityService.create_jwt_token(user_id="admin_test", role="super_admin", org_id="org_default")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def sdr_headers():
    token = SecurityService.create_jwt_token(user_id="sdr_test", role="sdr_rep", org_id="org_default")
    return {"Authorization": f"Bearer {token}"}

def test_get_swarm_telemetry(client, sdr_headers):
    resp = client.get("/api/v1/swarm/telemetry", headers=sdr_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "telemetry" in data
    assert data["telemetry"]["total_agents"] == 8

def test_toggle_swarm_autonomy_rbac(client, super_admin_headers, sdr_headers):
    # SDR should be forbidden from toggling autonomy
    resp_sdr = client.post("/api/v1/swarm/activate", json={"activate": True}, headers=sdr_headers)
    assert resp_sdr.status_code == 403

    # Super Admin should succeed
    resp_admin = client.post("/api/v1/swarm/activate", json={"activate": True}, headers=super_admin_headers)
    assert resp_admin.status_code == 200
    assert resp_admin.json()["swarm_active"] is True

def test_list_lifecycle_events(client, sdr_headers):
    resp = client.get("/api/v1/swarm/events?limit=10", headers=sdr_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data["events"], list)

def test_list_skills(client, sdr_headers):
    resp = client.get("/api/v1/swarm/skills", headers=sdr_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["total"] >= 5

def test_run_skill_endpoint(client, super_admin_headers):
    resp = client.post(
        "/api/v1/swarm/skills/run",
        json={
            "skill_name": "deliverability_gate",
            "params": {
                "recipient_email": "prospect@acme-corp.com",
                "subject": "Quick performance note",
                "body": "Hi there, wanted to share a speed optimization note.",
            },
        },
        headers=super_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["result"]["allowed"] is True
