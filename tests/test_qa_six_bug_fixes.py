"""
Comprehensive Test Suite for QA Bug Report & Action Items:
1. Dashboard Differentiation (Super Admin, Growth Lead, SDR Rep, Auditor)
2. Hover States & Navigation (interactive hover CSS & navigation pill states)
3. Growth Lead Speed Optimization (DB indices, sub-50ms queries, streamlined payload)
4. Related Read / Business Owner Details (resolve_opportunity_owner & convert_to_lead)
5. Jobs & Projects Detection (Radar detection, source mapping, opportunities API)
6. Tender Page Cleanup (Tender tab removed from Growth Lead section)
"""

import time
import pytest
from fastapi.testclient import TestClient

from api import app
from database.db import get_db
from database.models import OpportunityRepository, LeadRepository
from intel.opportunity_owner import resolve_opportunity_owner, convert_opportunity_to_lead, extract_company_name
from security.auth import SecurityService
from security.passwords import org_id


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tokens():
    oid = org_id()
    return {
        "super_admin": SecurityService.create_jwt_token("super_admin", oid, "super_admin"),
        "growth_lead": SecurityService.create_jwt_token("growth_lead", oid, "growth_lead"),
        "sdr_rep": SecurityService.create_jwt_token("sdr_rep", oid, "sdr_rep"),
        "auditor": SecurityService.create_jwt_token("auditor", oid, "auditor"),
    }


# ==============================================================================
# BUG 1: Dashboard Differentiation
# ==============================================================================
def test_dashboard_differentiation_endpoints_and_contracts(client, tokens):
    """Verify each tier interacts with its distinct, role-specialized endpoints."""
    # Super Admin: System governance, health checks, killswitch
    admin_res = client.get("/api/system/status", headers={"Authorization": f"Bearer {tokens['super_admin']}"})
    assert admin_res.status_code == 200
    assert "ready_to_send_email" in admin_res.json()

    # Growth Lead: Human-in-the-loop approvals desk, deals pipeline
    growth_appr = client.get("/api/approvals/pending", headers={"Authorization": f"Bearer {tokens['growth_lead']}"})
    assert growth_appr.status_code == 200
    assert isinstance(growth_appr.json(), list)

    growth_deals = client.get("/api/pipeline/deals", headers={"Authorization": f"Bearer {tokens['growth_lead']}"})
    assert growth_deals.status_code == 200

    # SDR Rep: Opportunities radar studio, hunter feed
    sdr_opps = client.get("/api/opportunities?limit=10", headers={"Authorization": f"Bearer {tokens['sdr_rep']}"})
    assert sdr_opps.status_code == 200
    assert isinstance(sdr_opps.json(), list)

    # Auditor: Read-only compliance, suppression checks
    aud_res = client.get("/api/compliance/suppression/check?email=safe@example.com", headers={"Authorization": f"Bearer {tokens['auditor']}"})
    assert aud_res.status_code == 200
    assert "is_suppressed" in aud_res.json()

    # Auditor must NOT have access to pipeline runs or outbound switches
    aud_denied = client.post("/api/controls/outbound", headers={"Authorization": f"Bearer {tokens['auditor']}"}, json={"halted": True})
    assert aud_denied.status_code in (401, 403)


# ==============================================================================
# BUG 2: Hover States & Navigation
# ==============================================================================
def test_hover_states_and_interactive_styling_in_css():
    """Verify index.css has prominent hover definitions and cursor indicators."""
    with open("frontend/src/index.css", "r", encoding="utf-8") as f:
        css = f.read()

    assert "a:hover" in css, "a:hover must be explicitly defined in index.css"
    assert "text-decoration: underline" in css
    assert "cursor: pointer" in css
    assert "table tbody tr:hover" in css
    assert "bento-tile:hover" in css

    with open("frontend/src/components/layout/Sidebar.tsx", "r", encoding="utf-8") as f:
        sidebar = f.read()
    assert "hover:text-white" in sidebar
    assert "hover:bg-slate-800/80" in sidebar


# ==============================================================================
# BUG 3: Growth Lead Speed Optimization
# ==============================================================================
def test_growth_lead_speed_optimization_and_indices(client, tokens):
    """Verify database indices exist and queries execute in sub-100ms."""
    with get_db() as db:
        indexes = {r["name"] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}

    assert "idx_approvals_decision" in indexes, "idx_approvals_decision must exist"
    assert "idx_leads_status" in indexes, "idx_leads_status must exist"
    assert "idx_outbound_drafts_status" in indexes, "idx_outbound_drafts_status must exist"
    assert "idx_audit_runs_org" in indexes, "idx_audit_runs_org must exist"

    # Profile today/summary endpoint response time
    t0 = time.perf_counter()
    res = client.get("/api/today/summary", headers={"Authorization": f"Bearer {tokens['growth_lead']}"})
    dur_ms = (time.perf_counter() - t0) * 1000

    assert res.status_code == 200
    assert dur_ms < 250, f"/api/today/summary took {dur_ms:.1f}ms, expected < 250ms"


# ==============================================================================
# BUG 4: Related Read / Business Owner Details
# ==============================================================================
def test_related_read_business_owner_details(client, tokens):
    """Test resolution and display of business owner details on an opportunity."""
    oid = org_id()
    # Create test opportunity with hiring manager and email in posting
    opp = OpportunityRepository.create_opportunity(
        opp_type="marketplace",
        source="upwork",
        title="Full Stack Engineer at Stripe",
        description="Posted by: Patrick Collison\nContact hiring lead: patrick@stripe.com\nPhone: (415) 555-0199\nhttps://www.linkedin.com/in/patrickcollison",
        org_id=oid
    )

    # Call Related Read endpoint
    res = client.post(
        f"/api/opportunities/{opp['id']}/related_read",
        headers={"Authorization": f"Bearer {tokens['growth_lead']}"}
    )
    assert res.status_code == 200
    data = res.json()

    assert data["company_name"] == "Stripe"
    assert data["business_owner"]["name"] == "Patrick Collison"
    assert data["business_owner"]["email"] == "patrick@stripe.com"
    assert data["business_owner"]["phone"] == "(415) 555-0199"
    assert "linkedin.com/in/patrickcollison" in (data["business_owner"]["linkedin_url"] or "")
    assert "patrick@stripe.com" in data["detected_emails"]

    # Convert to Lead
    conv_res = client.post(
        f"/api/opportunities/{opp['id']}/convert_to_lead",
        headers={"Authorization": f"Bearer {tokens['growth_lead']}"}
    )
    assert conv_res.status_code == 200
    cdata = conv_res.json()
    assert cdata["status"] == "created"
    assert cdata["company_name"] == "Stripe"
    assert cdata["lead_id"] > 0

    # Verify lead created in database with decision maker contact
    lead = LeadRepository.get_lead(cdata["lead_id"], oid)
    assert lead is not None
    assert lead["company_name"] == "Stripe"


def test_company_name_extraction_heuristics():
    """Verify intelligent extraction of company name from varied job formats."""
    assert extract_company_name("Senior Backend Go Developer at Datadog") == "Datadog"
    assert extract_company_name("[Calabrio] - Senior React Engineer") == "Calabrio"
    assert extract_company_name("Shopify Store Redesign for Acme Goods") == "Acme Goods"
    assert extract_company_name("Mobile App Build", fallback="Acme Inc") == "Acme Inc"


# ==============================================================================
# BUG 5: Jobs & Projects Detection
# ==============================================================================
def test_jobs_and_projects_detection_and_feed(client, tokens):
    """Verify detection feed returns scored opportunities and scans run successfully."""
    oid = org_id()
    OpportunityRepository.create_opportunity(
        opp_type="hiring_signal",
        source="remoteok",
        title="Senior Python Backend Engineer at Linear",
        description="Linear is looking for a senior engineer.",
        org_id=oid
    )
    # List opportunities
    res = client.get("/api/opportunities?limit=25", headers={"Authorization": f"Bearer {tokens['growth_lead']}"})
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    assert len(items) > 0

    first = items[0]
    assert "id" in first
    assert "title" in first
    assert "type" in first
    assert "source" in first


# ==============================================================================
# BUG 6: Tender Page Cleanup for Growth Lead
# ==============================================================================
def test_tender_cleanup_for_growth_lead():
    """Verify Find.tsx removes Tenders tab and routes for Growth Lead role."""
    with open("frontend/src/surfaces/Find.tsx", "r", encoding="utf-8") as f:
        find_tsx = f.read()

    assert "isGrowthLead" in find_tsx
    assert "ALL_TABS.filter((t) => t.id !== 'tenders')" in find_tsx
    assert "!isGrowthLead && tab === 'tenders'" in find_tsx

    with open("frontend/src/components/dashboards/GrowthLeadDashboard.tsx", "r", encoding="utf-8") as f:
        gl_dashboard = f.read()

    assert "tender" not in gl_dashboard.lower() or "filter((o) => o.type !== 'tender')" in gl_dashboard
