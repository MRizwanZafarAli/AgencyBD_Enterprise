"""
Unit and Integration Tests for Multi-Tenant org_id Isolation.
"""

import pytest
from database.db import init_db
from database.models import (
    LeadRepository,
    AuditRepository,
    ContactRepository,
    OutreachRepository,
    BookingRepository
)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_multi_tenant_lead_isolation():
    # 1. Create lead in Tenant Alpha
    lead_alpha = LeadRepository.create_or_get_lead(
        company_name="Alpha Tech Corp",
        domain="alphacorp.io",
        org_id="org_alpha"
    )

    # 2. Create lead in Tenant Beta
    lead_beta = LeadRepository.create_or_get_lead(
        company_name="Beta Innovations Inc",
        domain="betainnovations.com",
        org_id="org_beta"
    )

    # 3. List leads for Tenant Alpha
    alpha_leads = LeadRepository.list_leads(org_id="org_alpha")
    alpha_domains = [l["domain"] for l in alpha_leads]
    assert "alphacorp.io" in alpha_domains
    assert "betainnovations.com" not in alpha_domains

    # 4. List leads for Tenant Beta
    beta_leads = LeadRepository.list_leads(org_id="org_beta")
    beta_domains = [l["domain"] for l in beta_leads]
    assert "betainnovations.com" in beta_domains
    assert "alphacorp.io" not in beta_domains

    # 5. Direct ID query with org_id enforcement
    assert LeadRepository.get_lead(lead_alpha["id"], org_id="org_alpha") is not None
    assert LeadRepository.get_lead(lead_alpha["id"], org_id="org_beta") is None

def test_multi_tenant_enrichment_and_booking_isolation():
    # Create leads for separate orgs
    lead_a = LeadRepository.create_or_get_lead("Org A Agency", "orga-agency.com", org_id="tenant_a")
    lead_b = LeadRepository.create_or_get_lead("Org B Agency", "orgb-agency.com", org_id="tenant_b")

    # Add decision makers
    dm_a = ContactRepository.add_decision_maker(
        lead_id=lead_a["id"],
        first_name="Alice",
        last_name="Smith",
        title="CTO",
        email="alice@orga-agency.com",
        org_id="tenant_a"
    )
    dm_b = ContactRepository.add_decision_maker(
        lead_id=lead_b["id"],
        first_name="Bob",
        last_name="Jones",
        title="CEO",
        email="bob@orgb-agency.com",
        org_id="tenant_b"
    )

    # Verify contacts isolated
    contacts_a = ContactRepository.get_contacts_by_lead(lead_a["id"], org_id="tenant_a")
    assert len(contacts_a) == 1
    assert contacts_a[0]["email"] == "alice@orga-agency.com"

    contacts_cross = ContactRepository.get_contacts_by_lead(lead_a["id"], org_id="tenant_b")
    assert len(contacts_cross) == 0

    # Book meeting
    booking_a = BookingRepository.create_booking(
        lead_id=lead_a["id"],
        decision_maker_id=dm_a["id"],
        booking_time="2026-10-15 14:00",
        cal_link="https://cal.com/apexcore/15min",
        founder_prep_brief="Full architectural audit prepared.",
        org_id="tenant_a"
    )

    # Check bookings listing
    bookings_tenant_a = BookingRepository.list_bookings(org_id="tenant_a")
    assert any(b["id"] == booking_a["id"] for b in bookings_tenant_a)

    bookings_tenant_b = BookingRepository.list_bookings(org_id="tenant_b")
    assert not any(b["id"] == booking_a["id"] for b in bookings_tenant_b)
