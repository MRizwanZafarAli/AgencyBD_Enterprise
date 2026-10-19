"""
Tests for TeardownDeckExporter (3-Page Executive Boardroom Deck).
"""

from unittest.mock import MagicMock, patch
from engines.teardown_deck_exporter import TeardownDeckExporter


def test_teardown_deck_exporter_data_generation(tmp_path):
    exporter = TeardownDeckExporter(storage_dir=str(tmp_path))
    mock_diff = {
        "target": {"domain": "apexlabs.internal", "detected_stack": ["Next.js"], "lcp_seconds": 4.1},
        "competitor": {"domain": "stripe.com", "detected_stack": ["React"], "lcp_seconds": 1.4},
        "differential": {"latency_gap_seconds": 2.7, "monthly_conversion_deficit_usd": 12000.0, "competitive_pitch_hook": "Hook"},
    }
    with patch.object(exporter.diff_engine, "compare_domains", return_value=mock_diff):
        data = exporter.generate_deck_data("apexlabs.internal", "stripe.com")

    assert data["target_domain"] == "apexlabs.internal"
    assert data["competitor_domain"] == "stripe.com"
    assert "target" in data
    assert "competitor" in data
    assert "differential" in data
    assert "win_probability" in data
    assert "deal_valuation" in data
    assert data["win_probability"]["p_close_percent"] > 0


def test_teardown_deck_exporter_html_rendering(tmp_path):
    exporter = TeardownDeckExporter(storage_dir=str(tmp_path))
    mock_diff = {
        "target": {"domain": "apexlabs.internal", "detected_stack": ["Next.js"], "lcp_seconds": 4.1},
        "competitor": {"domain": "stripe.com", "detected_stack": ["React"], "lcp_seconds": 1.4},
        "differential": {"latency_gap_seconds": 2.7, "monthly_conversion_deficit_usd": 12000.0, "competitive_pitch_hook": "Hook"},
    }
    with patch.object(exporter.diff_engine, "compare_domains", return_value=mock_diff):
        html = exporter.generate_html("apexlabs.internal", "stripe.com")


    # Assert 3-page structure and CSS styling
    assert "Executive Teardown Deck" in html
    assert "Page 1 of 3" in html
    assert "Page 2 of 3" in html
    assert "Page 3 of 3" in html
    assert "@page" in html
    assert "page-break-after: always" in html
    assert "Deficit = Sessions" in html
    assert "90-Day Modernization Roadmap" in html


def test_teardown_deck_exporter_file_export(tmp_path):
    exporter = TeardownDeckExporter(storage_dir=str(tmp_path))
    result = exporter.export_deck(
        target_domain="apexlabs.internal",
        competitor_domain="stripe.com",
        output_format="html"
    )

    assert result["status"] == "success"
    assert result["target_domain"] == "apexlabs.internal"
    assert result["html_path"] is not None
    assert (tmp_path / result["html_filename"]).exists()

    content = (tmp_path / result["html_filename"]).read_text(encoding="utf-8")
    assert "apexlabs.internal" in content
