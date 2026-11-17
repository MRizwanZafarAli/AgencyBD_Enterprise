"""
Unit & Integration Tests for Sovereign Universal Scraper & Browser Sidepanel API (`engines/universal_scraper.py`, `routers/browser_sidepanel.py`).
"""

import pytest
from fastapi.testclient import TestClient
from api import app
from database.db import init_db
from security.auth import SecurityService
from engines.universal_scraper import universal_scraper, UniversalScraperEngine

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def sdr_headers():
    token = SecurityService.create_jwt_token(user_id="sdr_test", role="sdr_rep", org_id="org_default")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def super_admin_headers():
    token = SecurityService.create_jwt_token(user_id="admin_test", role="super_admin", org_id="org_default")
    return {"Authorization": f"Bearer {token}"}

def test_html_sanitization_and_boilerplate_stripping():
    engine = UniversalScraperEngine()
    html_sample = """
    <html>
        <head><title>Acme Software</title><style>.hidden { display: none; }</style></head>
        <body>
            <nav><a href="/home">Home</a></nav>
            <div id="cookie-consent-banner">Accept all cookies</div>
            <main>
                <h1>Next-Gen Cloud Solutions</h1>
                <p>We build mission-critical enterprise platforms.</p>
                <ul><li>High Speed</li><li>Zero Downtime</li></ul>
            </main>
            <footer>Copyright 2026 Acme Inc</footer>
            <script>console.log("tracking pixel");</script>
        </body>
    </html>
    """
    soup = engine.sanitize_html(html_sample)
    assert soup.find("script") is None
    assert soup.find("style") is None
    assert soup.find("nav") is None
    assert soup.find("footer") is None
    assert "cookie" not in soup.get_text().lower()

    md = engine.html_to_markdown(soup)
    assert "# Next-Gen Cloud Solutions" in md
    assert "We build mission-critical enterprise platforms." in md
    assert "- High Speed" in md

def test_challenge_radar_detection():
    engine = UniversalScraperEngine()
    
    clean_html = "<html><body><h1>Welcome to Stripe</h1></body></html>"
    challenged, ctype = engine.detect_challenges(clean_html)
    assert challenged is False
    assert ctype is None

    cloudflare_html = "<html><head><title>Just a moment...</title></head><body><div class='cf-turnstile'>Verify you are human</div></body></html>"
    challenged, ctype = engine.detect_challenges(cloudflare_html)
    assert challenged is True
    assert ctype == "cloudflare_turnstile"

def test_bm25_keyword_filtering():
    engine = UniversalScraperEngine()
    md_sample = (
        "# Company Overview\n\nWe provide modern solutions.\n\n"
        "## Executive Leadership\n\nAlex Rivera is our Chief Technology Officer.\n\n"
        "## Cookie Notice\n\nWe use cookies for analytics."
    )
    filtered = engine.filter_relevance(md_sample, ["leadership", "technology"])
    assert "Executive Leadership" in filtered
    assert "Alex Rivera" in filtered

def test_api_browser_markdown_endpoint(client, sdr_headers, monkeypatch):
    from unittest.mock import patch
    from engines.universal_scraper import ScrapeResult

    mock_res = ScrapeResult(
        url="https://stripe.com",
        domain="stripe.com",
        title="Financial Infrastructure",
        fit_markdown="# Financial Infrastructure\n\nPayments for the internet.",
        raw_html_length=15000,
        markdown_length=500,
        compression_ratio=96.7,
        challenge_detected=False,
    )

    with patch.object(universal_scraper, "scrape_url", return_value=mock_res):
        resp = client.get("/api/v1/browser/markdown?target=stripe.com", headers=sdr_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["domain"] == "stripe.com"
        assert "# Financial Infrastructure" in data["fit_markdown"]
        assert "96.7%" in data["compression_ratio"]

def test_api_browser_navigate_and_resolve(client, sdr_headers, monkeypatch):
    from unittest.mock import patch

    with patch("engines.native_browser_service.NativeBrowserService.capture_screenshot", return_value={"status": "success", "data_uri": "data:image/png;base64,iVBORw0KGgoAAA"}):
        with patch("engines.native_browser_service.NativeBrowserService.render_spa_dom", return_value={"title": "Test Domain", "detected_stack": ["React"]}):
            resp = client.post(
                "/api/v1/browser/session/navigate",
                json={"target": "example.com", "session_id": "test_sess_1"},
                headers=sdr_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert data["navigation"]["title"] == "Test Domain"
            assert data["navigation"]["viewport_screenshot"] is not None

    # Test Challenge Resolution
    res_resp = client.post(
        "/api/v1/browser/session/resolve",
        json={"session_id": "test_sess_1"},
        headers=sdr_headers,
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["ok"] is True

def test_api_launch_headed_chrome_window(client, super_admin_headers, monkeypatch):
    from unittest.mock import patch
    with patch("engines.interactive_browser_session.InteractiveBrowserSession.launch_headed_window", return_value={"status": "launched", "url": "https://example.com"}):
        resp = client.post(
            "/api/v1/browser/session/launch-headed",
            json={"target": "https://example.com", "session_id": "test_sess_1"},
            headers=super_admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["result"]["status"] == "launched"
