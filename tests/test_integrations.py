"""Settings > Integrations: keys are managed by the super-admin, encrypted, masked, applied immediately and restorable."""

import os

import pytest

from config import integrations
from database.db import get_db
from net.fetcher import FetchResult, SafeFetcher

SECRET = "sk-test-ABCDEFGHIJKLMNOP1234"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for p in integrations.PROVIDERS:
        monkeypatch.delenv(p.name, raising=False)
    integrations._original.clear()
    yield
    for p in integrations.PROVIDERS:
        os.environ.pop(p.name, None)
    integrations._original.clear()


def test_only_the_super_admin_can_manage_keys(client, make_key):
    for role in ("growth_lead", "sdr_rep", "auditor"):
        h = make_key(role)
        assert client.get("/api/integrations", headers=h).status_code == 403
        assert client.put("/api/integrations/ANTHROPIC_API_KEY", headers=h, json={"value": SECRET}).status_code == 403
    assert client.get("/api/integrations").status_code == 401
    assert client.get("/api/integrations", headers=make_key("super_admin")).status_code == 200


def test_saving_a_key_applies_it_immediately_and_never_returns_it(client, make_key):
    from llm.client import LLMGateway
    h = make_key("super_admin")
    assert LLMGateway.has_provider() is False
    res = client.put("/api/integrations/ANTHROPIC_API_KEY", headers=h, json={"value": SECRET})
    assert res.status_code == 200 and res.json()["display"] == "••••1234" and res.json()["source"] == "settings"
    assert LLMGateway.has_provider() is True                                    # takes effect without a restart
    listing = client.get("/api/integrations", headers=h)
    assert SECRET not in listing.text and "ABCDEFGHIJ" not in listing.text
    row = next(i for i in listing.json()["integrations"] if i["name"] == "ANTHROPIC_API_KEY")
    assert row["set"] and row["updated_at"]


def test_keys_are_encrypted_at_rest():
    integrations.set_key("PAGESPEED_API_KEY", SECRET, "admin")
    with get_db() as db:
        stored = db.execute("SELECT value_enc FROM integration_keys WHERE name = 'PAGESPEED_API_KEY'").fetchone()[0]
    assert SECRET not in stored and stored.startswith("gAAAA")                  # Fernet token


def test_removing_a_ui_key_restores_the_env_value_or_unsets(monkeypatch):
    monkeypatch.setenv("NVD_API_KEY", "from-dotenv-value-1234")
    integrations.set_key("NVD_API_KEY", SECRET, "admin")
    assert os.environ["NVD_API_KEY"] == SECRET                                 # Settings overrides .env
    assert integrations.clear_key("NVD_API_KEY") is True
    assert os.environ["NVD_API_KEY"] == "from-dotenv-value-1234"               # .env value is back
    integrations.set_key("GITHUB_TOKEN", SECRET, "admin")
    integrations.clear_key("GITHUB_TOKEN")
    assert "GITHUB_TOKEN" not in os.environ


def test_saved_keys_are_reapplied_after_a_restart():
    integrations.set_key("BRAVE_SEARCH_API_KEY", SECRET, "admin")
    os.environ.pop("BRAVE_SEARCH_API_KEY")                                     # simulate a fresh process
    integrations._original.clear()
    assert integrations.apply_all() >= 1 and os.environ["BRAVE_SEARCH_API_KEY"] == SECRET


@pytest.mark.parametrize("name,value", [("ANTHROPIC_API_KEY", "has a space"), ("ANTHROPIC_API_KEY", "line\nbreak"), ("ANTHROPIC_API_KEY", ""), ("ANTHROPIC_API_KEY", "x" * 600),
                                        ("SLACK_WEBHOOK_URL", "https://evil.example/hook"), ("OLLAMA_HOST", "ftp://x"), ("NOT_A_THING", "abc")])
def test_bad_values_and_unknown_names_are_rejected(client, make_key, name, value):
    assert client.put(f"/api/integrations/{name}", headers=make_key("super_admin"), json={"value": value}).status_code == 422
    assert name not in os.environ or name == "NOT_A_THING"


def test_connection_test_reports_ok_rejected_and_unreachable(client, make_key, monkeypatch):
    h = make_key("super_admin")
    integrations.set_key("GOOGLE_PLACES_API_KEY", SECRET, "admin")
    seen = {}

    def fake(cls, url, timeout=10, max_bytes=0, headers=None, method="GET", json_body=None, form_body=None):
        seen["url"], seen["headers"] = url, headers
        return FetchResult(status_code=seen["code"], text="{}", headers={}, final_url=url, elapsed_ms=1)
    monkeypatch.setattr(SafeFetcher, "safe_fetch", classmethod(fake))
    seen["code"] = 200
    assert client.post("/api/integrations/GOOGLE_PLACES_API_KEY/test", headers=h).json() == {"ok": True, "message": "The key works."}
    assert seen["url"].startswith("https://places.googleapis.com/") and seen["headers"]["X-Goog-Api-Key"] == SECRET
    seen["code"] = 403
    assert client.post("/api/integrations/GOOGLE_PLACES_API_KEY/test", headers=h).json()["ok"] is False
    seen["code"] = 503
    assert client.post("/api/integrations/GOOGLE_PLACES_API_KEY/test", headers=h).json()["ok"] is None
    monkeypatch.setattr(SafeFetcher, "safe_fetch", classmethod(lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))))
    assert client.post("/api/integrations/GOOGLE_PLACES_API_KEY/test", headers=h).json()["ok"] is None
    assert client.post("/api/integrations/SLACK_WEBHOOK_URL/test", headers=h).json()["ok"] is False            # nothing set
    integrations.set_key("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x", "admin")
    assert client.post("/api/integrations/SLACK_WEBHOOK_URL/test", headers=h).json()["ok"] is None           # never posts a test message


def test_every_provider_key_is_read_from_the_environment_at_call_time():
    """The mechanism only works if no module caches these at import time; guard against regressions."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    names = [p.name for p in integrations.PROVIDERS]
    used = set()
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).parts
        if rel[0] in ("tests", "frontend", "node_modules") or rel[:2] == ("config", "integrations.py"):
            continue
        text = path.read_text(errors="ignore")
        used |= {n for n in names if re.search(rf"os\.(getenv|environ\.get|environ)\(?\[?[\"']{n}[\"']", text)}
        for n in names:
            assert not re.search(rf"^[A-Z_]+ = os\.getenv\([\"']{n}", text, re.M), f"{path} reads {n} at import time"
    assert {"ANTHROPIC_API_KEY", "GOOGLE_PLACES_API_KEY", "PAGESPEED_API_KEY", "ZEROBOUNCE_API_KEY"} <= used
