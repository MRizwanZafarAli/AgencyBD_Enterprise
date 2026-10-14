"""
Startup guard tests: the app must not boot in production with missing, placeholder or leaked secrets.
Each case runs in a fresh interpreter because secrets are read at import time.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOOD = "g" * 48


def _boot(env_overrides: dict, module: str = "security.auth"):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AGENCYBD_")}
    env.update({"PYTHONPATH": str(ROOT), "DB_PATH": str(Path(os.environ["DB_PATH"]).parent / "boot.db")})
    env.update(env_overrides)
    # Point the loader at an empty directory so the developer's real .env cannot leak into the test
    env["AGENCYBD_SKIP_DOTENV"] = "1"
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60,
    )


def _prod(**kw):
    base = {"AGENCYBD_ENV": "production", "AGENCYBD_JWT_SECRET": GOOD,
            "AGENCYBD_WEBHOOK_SECRET": GOOD, "AGENCYBD_HMAC_VAULT_KEY": GOOD}
    base.update(kw)
    return base


def test_production_boots_with_strong_secrets():
    r = _boot(_prod(), "api")
    assert r.returncode == 0, r.stderr[-500:]


@pytest.mark.parametrize("var", ["AGENCYBD_JWT_SECRET", "AGENCYBD_WEBHOOK_SECRET", "AGENCYBD_HMAC_VAULT_KEY"])
def test_production_refuses_missing_secret(var):
    env = _prod()
    env.pop(var)
    r = _boot(env, "api")
    assert r.returncode != 0
    assert "SecretConfigError" in r.stderr


@pytest.mark.parametrize("bad", ["replace_me", "short", "super-secret-enterprise-jwt-key-change-in-prod-999",
                                 "agy_enterprise_webhook_secret_998811"])
def test_production_refuses_weak_or_leaked_secret(bad):
    r = _boot(_prod(AGENCYBD_JWT_SECRET=bad), "security.auth")
    assert r.returncode != 0 and "SecretConfigError" in r.stderr


def test_leaked_secret_refused_even_in_development():
    r = _boot({"AGENCYBD_ENV": "development",
               "AGENCYBD_JWT_SECRET": "super-secret-enterprise-jwt-key-prod-999"}, "security.auth")
    assert r.returncode != 0 and "SecretConfigError" in r.stderr


def test_development_falls_back_to_ephemeral_secret():
    r = _boot({"AGENCYBD_ENV": "development"}, "security.auth")
    assert r.returncode == 0, r.stderr[-500:]


def test_no_secret_literals_remain_in_source():
    leaked = [
        "super-secret-enterprise-jwt-key", "agy_enterprise_webhook_secret_998811",
        "apexcore_enterprise_secret_vault_seed", "agy_live_super_admin_enterprise_master",
        "agy_live_growth_lead_default_access", "agy_live_auditor_compliance_readonly",
    ]
    allowed = {"config/env.py", "tests/test_secrets.py", "tests/test_auth_rbac.py"}
    offenders = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if (not path.is_file() or rel in allowed or path.suffix not in {".py", ".yml", ".yaml", ".sh", ".conf", ".md", ".ts", ".tsx"}
                or any(part in {"node_modules", ".git", "dist", "__pycache__"} for part in path.parts)):
            continue
        text = path.read_text(errors="ignore")
        offenders += [f"{rel}: {needle}" for needle in leaked if needle in text]
    assert not offenders, offenders
