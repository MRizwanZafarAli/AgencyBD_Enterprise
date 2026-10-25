"""
Enterprise Prometheus Metrics Exporter & Real-Time Telemetry.
Tracks high-cardinality operational KPIs across multi-agent sourcing, audits, dispatches, and conversions.
"""

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
from typing import Dict, Any

# Custom registry to avoid default Python process overhead in lightweight scrapes
registry = CollectorRegistry()

# 1. Pipeline Counters
LEADS_DISCOVERED = Counter(
    "agencybd_leads_discovered_total",
    "Total leads sourced across channels",
    ["channel", "org_id"],
    registry=registry
)

TECH_AUDITS_EXECUTED = Counter(
    "agencybd_tech_audits_total",
    "Total deep headless technical audits executed",
    ["status", "org_id"],
    registry=registry
)

EMAILS_DISPATCHED = Counter(
    "agencybd_emails_dispatched_total",
    "Outbound emails dispatched across secondary pools",
    ["inbox", "org_id"],
    registry=registry
)

EMAILS_BOUNCED = Counter(
    "agencybd_emails_bounced_total",
    "Undelivered or bounced emails",
    ["inbox", "org_id"],
    registry=registry
)

INBOUND_REPLIES = Counter(
    "agencybd_replies_total",
    "Inbound replies received and triaged",
    ["sentiment", "org_id"],
    registry=registry
)

MEETINGS_BOOKED = Counter(
    "agencybd_meetings_booked_total",
    "Qualified meetings confirmed on founder calendars",
    ["org_id"],
    registry=registry
)

WEBHOOK_EVENTS = Counter(
    "agencybd_webhook_events_total",
    "Inbound webhook ingress events",
    ["provider", "status"],
    registry=registry
)

# 2. Operational Gauges
CIRCUIT_BREAKER_ACTIVE = Gauge(
    "agencybd_circuit_breaker_active",
    "Status of deliverability circuit breaker (1=tripped, 0=healthy)",
    ["inbox"],
    registry=registry
)

ACTIVE_QUEUE_TASKS = Gauge(
    "agencybd_active_queue_tasks",
    "Current background tasks in execution queue",
    registry=registry
)

# 3. Latency Histograms
PIPELINE_LATENCY = Histogram(
    "agencybd_pipeline_latency_seconds",
    "Execution duration across swarm pipeline stages",
    ["stage"],
    registry=registry
)

# 2. Operations: request health, background jobs, safety switches
HTTP_REQUESTS = Counter("agencybd_http_requests_total", "HTTP requests by route template and status", ["method", "route", "status"], registry=registry)
HTTP_LATENCY = Histogram("agencybd_http_request_seconds", "HTTP request duration by route template", ["route"], registry=registry,
                         buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 15, 60))
DISCOVERY_RUNS = Counter("agencybd_discovery_runs_total", "Discovery runs by outcome", ["status"], registry=registry)
RESCAN_ALERTS = Counter("agencybd_rescan_alerts_total", "New vulnerability matches found by the nightly re-scan", ["kev"], registry=registry)
BACKGROUND_FAILURES = Counter("agencybd_background_failures_total", "Failures inside background jobs", ["job"], registry=registry)
SENDING_HALTED = Gauge("agencybd_sending_halted", "1 when the stop-sending switch is on for a tenant", ["org_id"], registry=registry)


class MetricsManager:
    @staticmethod
    def record_lead_sourced(channel: str = "google_maps", org_id: str = "org_default"):
        LEADS_DISCOVERED.labels(channel=channel, org_id=org_id).inc()

    @staticmethod
    def record_audit(status: str = "success", org_id: str = "org_default"):
        TECH_AUDITS_EXECUTED.labels(status=status, org_id=org_id).inc()

    @staticmethod
    def record_dispatch(inbox: str, org_id: str = "org_default"):
        EMAILS_DISPATCHED.labels(inbox=inbox, org_id=org_id).inc()

    @staticmethod
    def record_bounce(inbox: str, org_id: str = "org_default"):
        EMAILS_BOUNCED.labels(inbox=inbox, org_id=org_id).inc()

    @staticmethod
    def record_reply(sentiment: str = "positive", org_id: str = "org_default"):
        INBOUND_REPLIES.labels(sentiment=sentiment, org_id=org_id).inc()

    @staticmethod
    def record_meeting_booked(org_id: str = "org_default"):
        MEETINGS_BOOKED.labels(org_id=org_id).inc()

    @staticmethod
    def record_webhook(provider: str = "resend", status: str = "success"):
        WEBHOOK_EVENTS.labels(provider=provider, status=status).inc()

    @staticmethod
    def set_circuit_breaker(inbox: str, tripped: bool):
        CIRCUIT_BREAKER_ACTIVE.labels(inbox=inbox).set(1.0 if tripped else 0.0)

    @staticmethod
    def export_prometheus_metrics() -> bytes:
        """Returns raw prometheus scrape response bytes."""
        return generate_latest(registry)
