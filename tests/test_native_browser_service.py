import pytest
from engines.native_browser_service import NativeBrowserService
from net.fetcher import SSRFSecurityError


def test_native_browser_service_initialization(tmp_path):
    service = NativeBrowserService(storage_dir=str(tmp_path))
    assert service.storage_dir.exists()
    # It should identify installed Chrome or return False gracefully
    available = service.is_browser_available()
    assert isinstance(available, bool)


def test_native_browser_ssrf_protection(tmp_path):
    service = NativeBrowserService(storage_dir=str(tmp_path))
    
    # 1. Loopback addresses should be blocked
    with pytest.raises(SSRFSecurityError):
        service._validate_ssrf_for_url("http://127.0.0.1:8000/internal")

    # 2. Private LAN should be blocked
    with pytest.raises(SSRFSecurityError):
        service._validate_ssrf_for_url("http://192.168.1.1/admin")

    # 3. AWS/Cloud metadata IP should be blocked
    with pytest.raises(SSRFSecurityError):
        service._validate_ssrf_for_url("http://169.254.169.254/latest/meta-data")

    # 4. File and gopher schemes should be blocked
    with pytest.raises(SSRFSecurityError):
        service._validate_ssrf_for_url("file:///etc/passwd")


def test_native_browser_dom_intelligence_extraction(tmp_path):
    service = NativeBrowserService(storage_dir=str(tmp_path))
    sample_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Apex Next-Gen AI Platform</title>
        <meta name="description" content="Empowering modern engineering squads with Next.js and AI">
      </head>
      <body>
        <div id="__next">
          <h1>Apex AI Labs</h1>
          <h2>Autonomous Swarm Architecture</h2>
          <p>Contact leadership: <a href="mailto:contact@apexlabs.com">Email Us</a></p>
          <p>Or write to: alex [at] apexlabs [dot] com</p>
          <p>Call our office: +1 (415) 555-0199</p>
          <a href="https://www.linkedin.com/company/apex-ai-labs">LinkedIn</a>
          <form><input type="text"><button type="submit">Submit</button></form>
        </div>
      </body>
    </html>
    """
    data = service._extract_dom_intelligence(sample_html, "apexlabs.com", "test_runner")
    assert data["status"] == "success"
    assert data["title"] == "Apex Next-Gen AI Platform"
    assert "Next.js" in data["detected_stack"]
    assert "contact@apexlabs.com" in data["emails"]
    assert "alex@apexlabs.com" in data["emails"]
    assert "+1 (415) 555-0199" in data["phones"] or "(415) 555-0199" in data["phones"]
    assert any("apex-ai-labs" in url for url in data["linkedin_urls"])
    assert data["has_contact_form"] is True


def test_native_browser_screenshot_fallback_or_run(tmp_path, monkeypatch):
    service = NativeBrowserService(storage_dir=str(tmp_path))
    # If Chrome is not available, returns unavailable status cleanly
    service.chrome_binary = None
    res = service.capture_screenshot("example.com")
    assert res["status"] == "unavailable"
    assert res["file_path"] is None
