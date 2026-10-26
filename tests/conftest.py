"""
Pytest configuration and test isolation fixtures for AgencyBD_Enterprise.

Environment is pinned BEFORE any application module is imported so that:
  * tests never touch the real database (a throwaway SQLite file is used)
  * secrets are deterministic test values (never the production ones)
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="agencybd_tests_"))
os.environ["AGENCYBD_ENV"] = "test"
os.environ["DB_PATH"] = str(_TMP / "test.db")
os.environ["AGENCYBD_JWT_SECRET"] = "test-jwt-secret-" + "x" * 40
os.environ["AGENCYBD_WEBHOOK_SECRET"] = "test-webhook-secret-" + "y" * 40
os.environ["AGENCYBD_HMAC_VAULT_KEY"] = "test-vault-key-" + "z" * 40
os.environ["AGENCYBD_WEBHOOK_ORG_ID"] = "org_default"

import os
os.environ.setdefault("AGENCYBD_SKIP_DOTENV", "1")   # tests never read the developer's real .env

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from database.db import get_db, init_db, create_api_key_record  # noqa: E402

TABLES_TO_CLEAR = [
    "meeting_bookings", "inbound_replies", "outreach_sequences", "decision_makers",
    "tech_audits", "leads", "suppression_vault", "audit_trail", "api_keys",
    "financial_ledger", "ab_test_cohorts", "task_queue", "portfolio_assets", "proposals", "approvals", "opportunities", "policies", "policy_decisions", "agent_runs", "mailboxes", "outreach_events",
    "work_items", "lead_scores", "channel_records", "client_notes", "agency_profile", "integration_keys", "vuln_cache", "job_runs", "org_controls", "discovery_runs", "mailbox_credentials", "email_verifications", "outbound_drafts", "sequences", "sequence_enrollments", "webhook_secrets",
    "audit_runs", "audit_findings", "evidence", "companies", "people", "signals", "services", "tech_audits",
]


def pytest_configure(config):
    config.addinivalue_line("markers", "network: needs real network/DNS access")


@pytest.fixture(autouse=True)
def offline_dns(monkeypatch, request):
    """Tests never touch real DNS (deterministic and offline). Mark a test @pytest.mark.network to opt out."""
    if request.node.get_closest_marker("network"):
        return
    import dns.resolver

    def unreachable(self, *args, **kwargs):
        raise dns.resolver.NoNameservers("DNS disabled in tests")
    monkeypatch.setattr(dns.resolver.Resolver, "resolve", unreachable)


@pytest.fixture
def web(monkeypatch):
    """Fake internet (see tests/webfake.py)."""
    from webfake import install_fake_web
    return install_fake_web(monkeypatch)


@pytest.fixture(autouse=True)
def clean_test_database():
    """Ensures each test has an isolated, clean database state."""
    init_db()
    with get_db() as conn:
        for table in TABLES_TO_CLEAR:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()


@pytest.fixture
def make_key():
    """Factory: make_key(role, org_id) -> request headers carrying a fresh API key."""
    def _make(role: str = "growth_lead", org_id: str = "org_default", user_id: str = "test_user"):
        raw = create_api_key_record(name=f"test-{role}", user_id=user_id, role=role, org_id=org_id)
        return {"X-API-Key": raw}
    return _make


@pytest.fixture
def client():
    from api import app
    return TestClient(app)


@pytest.fixture
def admin_headers(make_key):
    return make_key("super_admin")


@pytest.fixture
def growth_headers(make_key):
    return make_key("growth_lead")
