"""The executive deck states only what the check measured: no default loading time, no invented conversion-loss percentage."""

from datetime import datetime, timezone

from reports.deck_generator import ExecutiveDeckGenerator


def render(findings):
    data = {"audit": {"domain": "acme.example", "overall_score": 61, "findings": findings}, "comparison": None, "generated_at": datetime(2026, 11, 2, tzinfo=timezone.utc), "domain": "acme.example", "competitor": None}
    return ExecutiveDeckGenerator().render_deck_html(data, "org_deck")


def finding(check, text, value, sev="high"):
    return {"check_id": check, "finding": text, "severity": sev, "evidence_value": value, "fix": "x", "estimated_impact": "i", "category": "performance"}


def test_without_a_measured_loading_time_no_speed_claim_is_made():
    html = render([finding("missing_hsts", "No HSTS.", "absent")])
    assert "Loading time was not measured in this check" in html and "Google rates" not in html and "about <strong" not in html
    assert "{speed_html}" not in html


def test_a_measured_loading_time_is_quoted_with_googles_published_thresholds_only():
    html = render([finding("slow_lcp", "Largest Contentful Paint is slow.", "3.4 s")])
    assert "about <strong" in html and "3.4s" in html and "above the good range" in html
    assert "Google rates up to 2.5s as good and over 4.0s as poor" in html


def test_no_invented_conversion_figures_or_unprovable_claims():
    html = render([finding("slow_lcp", "Largest Contentful Paint is slow.", "5.2 s")])
    for text in ("~7%", "Opportunity Drag", "Research across top web properties", "100% Verified", "Recurring API Tax", "abandon slow checkout"):
        assert text not in html
    assert "well above the good range" in html
