"""
Unit and Integration Tests for Observability, Structured Logging, and Prometheus Metrics.
"""

import pytest
import json
import logging
from core.logger import JSONFormatter, get_enterprise_logger
from core.metrics import MetricsManager

def test_json_logging_format():
    logger = get_enterprise_logger("TestLogger")
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="TestLogger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Enterprise pipeline triggered",
        args=(),
        exc_info=None
    )
    record.trace_id = "trace_abc_123"
    record.org_id = "org_enterprise"
    record.event = "PIPELINE_START"

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Enterprise pipeline triggered"
    assert parsed["service"] == "AgencyBD_Enterprise"
    assert parsed["trace_id"] == "trace_abc_123"
    assert parsed["org_id"] == "org_enterprise"
    assert parsed["event"] == "PIPELINE_START"
    assert "timestamp" in parsed

def test_prometheus_metrics_export():
    # Record some events
    MetricsManager.record_lead_sourced(channel="google_maps", org_id="org_test")
    MetricsManager.record_audit(status="success", org_id="org_test")
    MetricsManager.record_dispatch(inbox="alex@mail.com", org_id="org_test")
    MetricsManager.record_bounce(inbox="alex@mail.com", org_id="org_test")
    MetricsManager.record_meeting_booked(org_id="org_test")
    MetricsManager.set_circuit_breaker(inbox="alex@mail.com", tripped=True)

    metrics_bytes = MetricsManager.export_prometheus_metrics()
    metrics_text = metrics_bytes.decode("utf-8")

    assert "agencybd_leads_discovered_total" in metrics_text
    assert 'channel="google_maps"' in metrics_text
    assert "agencybd_tech_audits_total" in metrics_text
    assert "agencybd_emails_dispatched_total" in metrics_text
    assert "agencybd_emails_bounced_total" in metrics_text
    assert "agencybd_meetings_booked_total" in metrics_text
    assert "agencybd_circuit_breaker_active" in metrics_text
