"""Endpoints for the interactive browser viewer (no fake click/type), plus permission and scoping checks."""

from unittest.mock import patch


def _nav(client, headers, session_id="s1"):
    with patch("engines.native_browser_service.NativeBrowserService.render_spa_dom", return_value={"title": "Example", "detected_stack": [], "emails": [], "phones": []}), \
         patch("engines.native_browser_service.NativeBrowserService.capture_screenshot", return_value={"status": "success", "data_uri": "data:image/png;base64,x", "file_path": "/tmp/x.png"}), \
         patch("engines.native_browser_service.NativeBrowserService._validate_ssrf_for_url", return_value="https://example.com"):
        return client.post("/api/browser/interactive/navigate", headers=headers, json={"target": "example.com", "session_id": session_id})


def test_interactive_navigate_is_a_viewer_not_a_driver(client, make_key):
    res = _nav(client, make_key("growth_lead"))
    assert res.status_code == 200 and res.json()["mode"] == "viewer" and res.json()["title"] == "Example"
    assert client.post("/api/browser/interactive/action", headers=make_key("super_admin"), json={"action_type": "click", "params": {}}).status_code in (404, 405)


def test_interactive_session_id_cannot_escape_the_sessions_folder(client, make_key):
    res = _nav(client, make_key("growth_lead"), session_id="../../etc")
    assert res.status_code == 422


def test_browser_endpoints_need_pipeline_permission(client, make_key):
    for path, body in (("/api/browser/render", {"domain": "example.com"}), ("/api/browser/screenshot", {"domain": "example.com"}),
                       ("/api/browser/interactive/navigate", {"target": "example.com"})):
        assert client.post(path, headers=make_key("auditor"), json=body).status_code == 403


def test_headed_window_refuses_non_http_targets(client, make_key):
    res = client.post("/api/browser/interactive/headed-window", headers=make_key("growth_lead"), json={"url": "--renderer-cmd-prefix=x"})
    assert res.status_code == 200 and res.json()["status"] == "error"


def test_removed_fabricating_or_dangerous_endpoints_are_gone(client, make_key):
    h = make_key("super_admin")
    for path in ("/api/swarm/autopilot/run", "/api/swarm/math/score", "/api/swarm/pods/run", "/api/brain/plan", "/api/brain/chat",
                 "/api/brain/artifact", "/api/teardown/deck/export", "/api/differential/compare", "/api/system/updater/apply",
                 "/api/intelligence/recommend_markets"):
        assert client.post(path, headers=h, json={}).status_code in (404, 405), path
