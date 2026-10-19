"""
Tests for InteractiveBrowserSession (Human Touch & Autonomous Takeover).
"""

from unittest.mock import MagicMock, patch
import pytest
from engines.interactive_browser_session import InteractiveBrowserSession
from net.fetcher import SSRFSecurityError


def test_interactive_browser_session_init(tmp_path):
    session = InteractiveBrowserSession(session_id="test_sess_01", storage_dir=str(tmp_path))
    assert session.session_id == "test_sess_01"
    assert session.storage_dir.exists()
    assert session.current_url is None


def test_interactive_browser_ssrf_blocked(tmp_path):
    session = InteractiveBrowserSession(session_id="test_sess_02", storage_dir=str(tmp_path))
    with pytest.raises(SSRFSecurityError):
        session.navigate("http://127.0.0.1:8000/internal")


def test_interactive_browser_navigate_and_actions(tmp_path):
    session = InteractiveBrowserSession(session_id="test_sess_03", storage_dir=str(tmp_path))

    # Mock DOM rendering and screenshot capture
    mock_dom = {
        "status": "success",
        "domain": "example.com",
        "title": "Example Domain",
        "detected_stack": ["Next.js", "React"],
        "emails": ["founders@example.com"],
        "phones": ["+1 555-0100"],
    }
    mock_shot = {
        "status": "success",
        "file_path": str(tmp_path / "shot.png"),
        "data_uri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    }

    with patch.object(session.browser_service, "render_spa_dom", return_value=mock_dom), \
         patch.object(session.browser_service, "capture_screenshot", return_value=mock_shot), \
         patch.object(session.browser_service, "_validate_ssrf_for_url", return_value="https://example.com"):
        res = session.navigate("example.com")
        assert res["status"] == "success"
        assert res["session_id"] == "test_sess_03"
        assert res["title"] == "Example Domain"
        assert res["mode"] == "HUMAN_TOUCH_READY"
        assert "founders@example.com" in res["emails"]

        # Test dispatching human touch action
        click_res = session.dispatch_human_touch_action("click", {"x": 120, "y": 340})
        assert click_res["status"] == "success"
        assert click_res["action_executed"] == "click"
        assert click_res["params"]["x"] == 120

        # Type action
        type_res = session.dispatch_human_touch_action("type", {"text": "hello@agency.com"})
        assert type_res["status"] == "success"
        assert type_res["action_executed"] == "type"


def test_interactive_browser_headed_window_launch(tmp_path):
    session = InteractiveBrowserSession(session_id="test_sess_04", storage_dir=str(tmp_path))
    session.current_url = "https://example.com"

    with patch("subprocess.Popen") as mock_popen:
        session.browser_service.chrome_binary = "/mock/path/to/chrome"
        res = session.launch_headed_window()
        assert res["status"] == "launched"
        assert "example.com" in res["url"]
        mock_popen.assert_called_once()
