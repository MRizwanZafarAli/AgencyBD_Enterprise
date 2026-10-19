"""
Integration tests for new Enterprise REST endpoints:
  - /api/browser/interactive/navigate
  - /api/browser/interactive/action
  - /api/browser/interactive/headed-window
  - /api/swarm/pods/run
  - /api/teardown/deck/export
  - /api/teardown/deck/view/{filename}
"""

from unittest.mock import MagicMock, patch
import pytest


def test_interactive_browser_navigate_endpoint(client, make_key):
    headers = make_key("super_admin")
    mock_dom = {
        "status": "success",
        "domain": "apexlabs.io",
        "title": "Apex Labs",
        "detected_stack": ["Next.js"],
        "emails": [],
        "phones": [],
    }
    mock_shot = {
        "status": "success",
        "data_uri": "data:image/png;base64,fake",
        "file_path": "/tmp/fake.png",
    }

    with patch("engines.native_browser_service.NativeBrowserService.render_spa_dom", return_value=mock_dom), \
         patch("engines.native_browser_service.NativeBrowserService.capture_screenshot", return_value=mock_shot), \
         patch("engines.native_browser_service.NativeBrowserService._validate_ssrf_for_url", return_value="https://apexlabs.io"):
        res = client.post(
            "/api/browser/interactive/navigate",
            headers=headers,
            json={"target": "apexlabs.io", "session_id": "test_api_session"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["title"] == "Apex Labs"
        assert data["mode"] == "HUMAN_TOUCH_READY"


def test_interactive_browser_action_endpoint(client, make_key):
    headers = make_key("super_admin")
    with patch("engines.native_browser_service.NativeBrowserService.render_spa_dom", return_value={"title": "Updated"}), \
         patch("engines.native_browser_service.NativeBrowserService.capture_screenshot", return_value={"status": "success", "data_uri": "data:image/png;base64,updated"}):
        res = client.post(
            "/api/browser/interactive/action",
            headers=headers,
            json={
                "action_type": "click",
                "params": {"x": 200, "y": 450},
                "session_id": "test_api_session"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["action_executed"] == "click"


def test_interactive_browser_headed_window_endpoint(client, make_key):
    headers = make_key("super_admin")
    with patch("subprocess.Popen"):
        res = client.post(
            "/api/browser/interactive/headed-window",
            headers=headers,
            json={"url": "https://example.com", "session_id": "test_api_session"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["launched", "unavailable"]


def test_swarm_pods_run_endpoint(client, make_key):
    headers = make_key("super_admin")
    with patch("engines.native_browser_service.NativeBrowserService.render_spa_dom", return_value={"title": "Apex", "detected_stack": ["Next.js"], "emails": []}), \
         patch("agents.sourcing_agent.SourcingAgent.source_sec_edgar_venture", return_value=[{"company": "Apex", "domain": "apex.io"}]):
        res = client.post(
            "/api/swarm/pods/run",
            headers=headers,
            json={
                "domain": "apex.io",
                "competitor": "stripe.com",
                "pod_type": "all"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["active_pods"] == 5
        assert "sourcing" in data
        assert "deal_strategy" in data


def test_teardown_deck_export_and_view_endpoint(client, make_key, tmp_path):
    headers = make_key("super_admin")
    from api import teardown_deck_exporter
    teardown_deck_exporter.storage_dir = tmp_path

    res = client.post(
        "/api/teardown/deck/export",
        headers=headers,
        json={
            "target_domain": "apexlabs.internal",
            "competitor_domain": "stripe.com",
            "output_format": "html"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    html_name = data["html_filename"]

    # Now view the exported HTML
    view_res = client.get(f"/api/teardown/deck/view/{html_name}", headers=headers)
    assert view_res.status_code == 200
    assert "Executive Teardown Deck" in view_res.text
