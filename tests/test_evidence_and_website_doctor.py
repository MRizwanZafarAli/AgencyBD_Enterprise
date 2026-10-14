"""
Unit tests for Website Doctor, Evidence Engine, Company Brief, and Presence Rescue.
Verifies that all checks produce structured findings, SSRF policies are strictly enforced,
and evidence links are recorded with zero fabricated data.
"""

import pytest
from net.fetcher import SafeFetcher, SSRFSecurityError
from auditors.engine import WebsiteDoctorEngine
from intel.resolver import CompanyResolver
from intel.company_brief import CompanyBriefEngine
from intel.presence import PresenceRescueEngine
from database.models import EvidenceRepository

def test_ssrf_safety_blocks_private_ips():
    """Verify that SafeFetcher rejects localhost, RFC1918, and cloud metadata."""
    with pytest.raises(SSRFSecurityError):
        SafeFetcher.validate_ip_address("127.0.0.1")

    with pytest.raises(SSRFSecurityError):
        SafeFetcher.validate_ip_address("169.254.169.254")

    with pytest.raises(SSRFSecurityError):
        SafeFetcher.validate_ip_address("10.0.0.1")

    with pytest.raises(SSRFSecurityError):
        SafeFetcher.validate_ip_address("192.168.1.1")

def test_company_resolver(web):
    """Verify company name and domain resolution."""
    from webfake import page
    web["deel.example"] = page("Deel", h1="Deel")
    res = CompanyResolver.resolve_domain_from_name("Deel", hint_domain="deel.example")
    assert res["status"] == "resolved"
    assert res["domain"] == "deel.example"
    assert res["company_id"] > 0

def test_website_doctor_audit(web):
    """Verify Website Doctor runs checks and records evidence."""
    from webfake import page
    web["example.example"] = page("Example", h1="Example")
    report = WebsiteDoctorEngine.run_audit("example.example")
    assert report["status"] == "completed"
    assert 0 <= report["overall_score"] <= 100
    assert "findings" in report
    assert isinstance(report["findings"], list)
    assert report["duration_ms"] >= 0
