"""
Unit and Integration Tests for Enterprise Auth and RBAC Middleware.
"""

import pytest
from datetime import timedelta
import jwt
from fastapi import HTTPException
from security.auth import (
    SecurityService,
    get_current_principal,
    require_role,
    require_permission,
    Principal,
    ROLE_PERMISSIONS,
    scoped_org
)
from security import auth as auth_mod
from database.db import create_api_key_record, list_api_keys, revoke_api_key_record, init_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_api_key_generation_and_hashing():
    key = SecurityService.generate_api_key("agy_live")
    assert key.startswith("agy_live_")
    assert len(key) > 30

    hashed = SecurityService.hash_api_key(key)
    assert len(hashed) == 64
    assert hashed == SecurityService.hash_api_key(key)

def test_jwt_issuance_and_decoding():
    token = SecurityService.create_jwt_token(
        user_id="user_123",
        org_id="org_cyber",
        role="growth_lead"
    )
    decoded = SecurityService.decode_jwt_token(token)
    assert decoded["sub"] == "user_123"
    assert decoded["org_id"] == "org_cyber"
    assert decoded["role"] == "growth_lead"
    assert "pipeline:run" in decoded["permissions"]

def test_jwt_expiration():
    # Expired token (delta negative)
    token = SecurityService.create_jwt_token(
        user_id="user_old",
        expires_delta=timedelta(seconds=-10)
    )
    with pytest.raises(HTTPException) as exc_info:
        SecurityService.decode_jwt_token(token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail

def test_no_builtin_or_default_credentials():
    """The previously published keys must no longer authenticate."""
    for leaked in (
        "agy_live_super_admin_enterprise_master",
        "agy_live_growth_lead_default_access",
        "agy_live_auditor_compliance_readonly",
        "invalid_forged_key",
    ):
        with pytest.raises(HTTPException) as exc_info:
            get_current_principal(x_api_key=leaked, auth_creds=None)
        assert exc_info.value.status_code == 401

def test_missing_credentials_rejected():
    with pytest.raises(HTTPException) as exc_info:
        get_current_principal(x_api_key=None, auth_creds=None)
    assert exc_info.value.status_code == 401

def test_role_permissions_come_from_server_not_token_claims():
    from fastapi.security import HTTPAuthorizationCredentials
    import time
    forged = jwt.encode(
        {"sub": "mallory", "org_id": "org_default", "role": "auditor", "permissions": ["*"],
         "iss": "agencybd-enterprise", "aud": "agencybd-api",
         "iat": time.time(), "exp": time.time() + 600},
        auth_mod.JWT_SECRET_KEY, algorithm="HS256")
    principal = get_current_principal(
        x_api_key=None,
        auth_creds=HTTPAuthorizationCredentials(scheme="Bearer", credentials=forged))
    assert "*" not in principal.permissions
    assert principal.permissions == ROLE_PERMISSIONS["auditor"]

def test_jwt_with_unknown_role_rejected():
    from fastapi.security import HTTPAuthorizationCredentials
    import time
    bad = jwt.encode(
        {"sub": "x", "role": "root", "iss": "agencybd-enterprise", "aud": "agencybd-api",
         "iat": time.time(), "exp": time.time() + 600},
        auth_mod.JWT_SECRET_KEY, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        get_current_principal(x_api_key=None, auth_creds=HTTPAuthorizationCredentials(scheme="Bearer", credentials=bad))
    assert exc_info.value.status_code == 401

def test_jwt_signed_with_wrong_secret_or_alg_none_rejected():
    import time
    claims = {"sub": "x", "role": "super_admin", "iss": "agencybd-enterprise", "aud": "agencybd-api",
              "iat": time.time(), "exp": time.time() + 600}
    for token in (jwt.encode(claims, "some-other-secret-" + "q" * 30, algorithm="HS256"),
                  jwt.encode(claims, "", algorithm="none")):
        with pytest.raises(HTTPException) as exc_info:
            SecurityService.decode_jwt_token(token)
        assert exc_info.value.status_code == 401

def test_create_api_key_rejects_unknown_role():
    with pytest.raises(ValueError):
        create_api_key_record(name="bad", user_id="u", role="root")

def test_scoped_org_blocks_cross_tenant_for_non_admin():
    growth = Principal(user_id="u", org_id="org_a", role="growth_lead",
                       permissions=ROLE_PERMISSIONS["growth_lead"], auth_method="jwt")
    assert scoped_org(growth) == "org_a"
    assert scoped_org(growth, "org_a") == "org_a"
    with pytest.raises(HTTPException) as exc_info:
        scoped_org(growth, "org_b")
    assert exc_info.value.status_code == 403
    admin = Principal(user_id="a", org_id="org_default", role="super_admin",
                      permissions=["*"], auth_method="api_key")
    assert scoped_org(admin, "org_b") == "org_b"

def test_database_persisted_api_key_lifecycle():
    # 1. Create key
    raw_key = create_api_key_record(
        name="Automation Runner Key",
        user_id="bot_runner_99",
        role="growth_lead",
        org_id="org_alpha"
    )
    assert raw_key.startswith("agy_live_")

    # 2. Authenticate using newly generated key
    principal = get_current_principal(x_api_key=raw_key, auth_creds=None)
    assert principal.user_id == "bot_runner_99"
    assert principal.org_id == "org_alpha"
    assert principal.role == "growth_lead"

    # 3. List keys
    keys = list_api_keys(org_id="org_alpha")
    matching = [k for k in keys if k["name"] == "Automation Runner Key"]
    assert len(matching) > 0
    key_id = matching[0]["id"]

    # 4. Revoke key
    revoked = revoke_api_key_record(key_id, org_id="org_alpha")
    assert revoked is True

    # 5. Authenticate with revoked key must fail
    with pytest.raises(HTTPException) as exc_info:
        get_current_principal(x_api_key=raw_key, auth_creds=None)
    assert exc_info.value.status_code == 401

def test_rbac_role_enforcement():
    growth_principal = Principal(
        user_id="u1",
        org_id="org_default",
        role="growth_lead",
        permissions=ROLE_PERMISSIONS["growth_lead"],
        auth_method="jwt"
    )
    auditor_principal = Principal(
        user_id="u2",
        org_id="org_default",
        role="auditor",
        permissions=ROLE_PERMISSIONS["auditor"],
        auth_method="jwt"
    )

    # growth_lead allowed for growth_lead or super_admin
    checker = require_role(["growth_lead", "super_admin"])
    assert checker(growth_principal) == growth_principal

    # auditor blocked from growth actions
    with pytest.raises(HTTPException) as exc_info:
        checker(auditor_principal)
    assert exc_info.value.status_code == 403

def test_rbac_permission_enforcement():
    growth_principal = Principal(
        user_id="u1",
        org_id="org_default",
        role="growth_lead",
        permissions=ROLE_PERMISSIONS["growth_lead"],
        auth_method="jwt"
    )
    perm_checker = require_permission("outreach:dispatch")
    assert perm_checker(growth_principal) == growth_principal

    # Permission that growth_lead doesn't have
    restricted_checker = require_permission("admin:destroy_all")
    with pytest.raises(HTTPException) as exc_info:
        restricted_checker(growth_principal)
    assert exc_info.value.status_code == 403
