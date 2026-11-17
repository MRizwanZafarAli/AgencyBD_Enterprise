"""
Unit & Integration Tests for EventBus & Lifecycle Hooks (`core/hooks.py`).
"""

import time
import pytest
from core.hooks import (
    EventBus,
    hook,
    HOOK_LEAD_SOURCED,
    HOOK_AUDIT_COMPLETED,
    HOOK_SEND_APPROVED,
)
from database.db import init_db, get_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_event_bus_registration_and_sync_emission():
    bus = EventBus()
    received = []

    def handle_lead(payload):
        received.append(payload["domain"])
        return "handled"

    bus.register(HOOK_LEAD_SOURCED, handle_lead, priority=50)
    assert len(bus.list_handlers()[HOOK_LEAD_SOURCED]) == 1

    results = bus.emit(HOOK_LEAD_SOURCED, {"domain": "acme.com", "company": "Acme Inc"}, sync=True)
    assert received == ["acme.com"]
    assert results == ["handled"]

def test_event_bus_priority_ordering():
    bus = EventBus()
    order = []

    def second_handler(payload):
        order.append(2)

    def first_handler(payload):
        order.append(1)

    def third_handler(payload):
        order.append(3)

    bus.register("test_priority", third_handler, priority=90)
    bus.register("test_priority", first_handler, priority=10)
    bus.register("test_priority", second_handler, priority=50)

    bus.emit("test_priority", {}, sync=True)
    assert order == [1, 2, 3]

def test_event_bus_error_isolation():
    bus = EventBus()
    passed = []

    def failing_handler(payload):
        raise ValueError("Simulated handler crash")

    def safe_handler(payload):
        passed.append(True)

    bus.register("test_err", failing_handler, priority=10)
    bus.register("test_err", safe_handler, priority=20)

    # Should not raise exception
    bus.emit("test_err", {}, sync=True)
    assert passed == [True]

def test_event_bus_async_handler():
    import asyncio
    bus = EventBus()
    captured = []

    async def async_handler(payload):
        captured.append(payload["status"])
        return "async_done"

    bus.register(HOOK_AUDIT_COMPLETED, async_handler)
    bus.emit(HOOK_AUDIT_COMPLETED, {"status": "audit_ok"}, sync=False)

    # Allow thread/event loop to complete
    for _ in range(10):
        if captured:
            break
        time.sleep(0.05)
    assert captured == ["audit_ok"]

def test_lead_repository_triggers_lifecycle_event():
    import uuid
    from database.models import LeadRepository

    captured_events = []
    def on_lead(payload):
        captured_events.append(payload)

    from core.hooks import event_bus, HOOK_LEAD_SOURCED
    event_bus.register(HOOK_LEAD_SOURCED, on_lead)

    unique_domain = f"test-{uuid.uuid4().hex[:8]}.com"
    lead = LeadRepository.create_or_get_lead(
        company_name="Auto Hook Test Co",
        domain=unique_domain,
        org_id="org_default",
    )
    assert lead is not None
    assert lead["domain"] == unique_domain
    assert any(e.get("domain") == unique_domain for e in captured_events)

    # Verify event logged to lifecycle_events table
    events = []
    for _ in range(10):
        events = event_bus.get_recent_events(limit=10)
        if any(ev["event_name"] == HOOK_LEAD_SOURCED for ev in events):
            break
        time.sleep(0.05)
    assert any(ev["event_name"] == HOOK_LEAD_SOURCED for ev in events)



