"""QA sweep: every endpoint, as every kind of user.

For all endpoints in the API description it checks, as not signed in and as each tier:
  * nothing ever crashes (no 5xx), even with an empty or odd request
  * nothing is open without signing in, except a short, named list of public endpoints
  * the Super admin is never refused for lack of permission (it holds every permission)
  * a lower tier is never let in where a higher tier is refused (no privilege inversion)
The full result grid is written to $QA_MATRIX_OUT (JSON) when that variable is set, for the QA report.
"""

import json
import os
import re

import pytest

from api import app

TIERS = ["super_admin", "growth_lead", "sdr_rep", "auditor"]
ORDER = {"super_admin": 3, "growth_lead": 2, "sdr_rep": 1, "auditor": 1}          # sdr_rep and auditor are siblings, not ranked against each other
PUBLIC = {                                                                         # reachable without signing in, on purpose
    ("GET", "/healthz/live"), ("GET", "/healthz/ready"), ("GET", "/api/health"), ("GET", "/api/auth/tiers"), ("POST", "/api/auth/login"),
}
SIGNED_BY_SECRET = ("/api/webhooks/inbound", "/api/integrations/crm/hubspot", "/api/compliance/unsubscribe", "/api/connectors/upwork/callback")     # protected by a signature or a one-time token instead of a session
SKIP = ("/api/outbound/drafts/{draft_id}/send", "/api/dispatch/send", "/api/controls/outbound")        # would send real mail or flip the global stop switch
SLOW = ("/api/clients/{lead_id}/prepare", "/api/sourcing/hiring/signals", "/api/clients/{lead_id}/find_contacts", "/api/sourcing/venture/sec_edgar", "/api/radar/scan")
# network-bound: they wait on outside sites (13 to 24 seconds when the network is down). Here they only prove "sign in required" and "auditor refused";
# what they do is covered by their own tests. 0 below means "not called".
SAFE_PLATFORM, SAFE_TEXT = "fiverr", "x"


def _fill(path: str) -> str:
    def sub(m):
        name = m.group(1).split(":")[0]
        if name == "platform":
            return SAFE_PLATFORM
        if name in ("channel",):
            return "email"
        if name.endswith("id") or name.endswith("_id") or name in ("lead_id", "company_id"):
            return "1"
        if "domain" in name:
            return "example.com"
        return SAFE_TEXT
    return re.sub(r"\{([^}]+)\}", sub, path)


def _routes():
    out = []
    for path, ops in app.openapi()["paths"].items():
        if path == "/{full_path}" or "{full_path" in path:
            continue
        for method in ops:
            if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                out.append((method.upper(), path))
    return sorted(out)


ROUTES = [r for r in _routes() if r[1] not in SKIP]


@pytest.fixture(scope="module")
def grid(request):
    """status of every (method, path) for anonymous and each tier."""
    from fastapi.testclient import TestClient
    from security.auth import SecurityService
    client = TestClient(app, raise_server_exceptions=False)             # a crash must come back as a 500 we can count, not as a test error
    headers = {t: {"Authorization": f"Bearer {SecurityService.create_jwt_token(user_id=t, org_id='org_default', role=t)}"} for t in TIERS}
    result = {}
    for method, path in ROUTES:
        url = _fill(path)
        row = {}
        for who in ["anonymous"] + TIERS:
            if path in SLOW and who not in ("anonymous", "auditor"):
                row[who] = 0
                continue
            kw = {"headers": headers.get(who, {})}
            if method in ("POST", "PUT", "PATCH"):
                kw["json"] = {}
            try:
                resp = client.request(method, url, **kw)
                code = resp.status_code
                if code == 503:                                          # an honest "this is not set up" answer is not a crash
                    try:
                        code = 503 if resp.json().get("status") == "not_configured" else 599
                    except Exception:
                        code = 599
                row[who] = code
            except Exception as exc:                                    # pragma: no cover - reported below
                row[who] = f"EXC {type(exc).__name__}"
        result[f"{method} {path}"] = row
    out = os.getenv("QA_MATRIX_OUT")
    if out:
        with open(out, "w") as f:
            json.dump(result, f, indent=1, sort_keys=True)
    return result


def test_the_sweep_covers_the_whole_api():
    assert len(ROUTES) >= 200


def test_nothing_crashes_for_any_user(grid):
    bad = {k: v for k, v in grid.items() if any(isinstance(s, str) or (s >= 500 and s != 503) for s in v.values())}
    assert not bad, "endpoints that crash:\n" + "\n".join(f"  {k}: {v}" for k, v in bad.items())


def test_nothing_is_open_without_signing_in(grid):
    open_ = [k for k, v in grid.items() if v["anonymous"] not in (401, 403, 405, 503) and (k.split(" ")[0], k.split(" ")[1]) not in PUBLIC
             and not any(s in k for s in SIGNED_BY_SECRET)]
    assert not open_, "reachable without signing in:\n" + "\n".join(f"  {k}: {grid[k]['anonymous']}" for k in open_)


def test_the_super_admin_is_never_refused_for_permission(grid):
    refused = [k for k, v in grid.items() if v["super_admin"] == 403]
    assert not refused, "super admin got 403 on: " + ", ".join(refused)


def test_a_lower_tier_never_gets_in_where_a_higher_tier_is_refused(grid):
    inverted = []
    for k, v in grid.items():
        for low in TIERS:
            for high in TIERS:
                if ORDER[high] > ORDER[low] and v[high] == 403 and v[low] not in (401, 403):
                    inverted.append(f"{k}: {high}={v[high]} but {low}={v[low]}")
    assert not inverted, "privilege inversions:\n" + "\n".join(inverted)
