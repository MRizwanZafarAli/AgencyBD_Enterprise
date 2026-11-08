"""
Authentication, authorization and tenant scoping for AgencyBD_Enterprise.

Credentials
  * A person signs in with the secret password of their tier (see ``security/passwords.py``) and receives a short-lived
    ``Authorization: Bearer <jwt>`` token, an HS256 token signed with AGENCYBD_JWT_SECRET.
  * API keys no longer exist: an ``X-API-Key`` header is ignored.

There are no built-in or default credentials. Set the first passwords with ``python scripts/set_passwords.py``.
A token stops working when its tier's password is changed after the token was issued.

Authorization is role based. Permissions always come from the server-side
ROLE_PERMISSIONS table for the credential's role, never from token claims.
The tenant (``org_id``) is taken from the credential. Only a super_admin may act on
another tenant.
"""

import hmac
import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from config.env import get_secret

logger = logging.getLogger("AgencyBD.auth")

JWT_SECRET_KEY = get_secret("AGENCYBD_JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "agencybd-enterprise"
JWT_AUDIENCE = "agencybd-api"
JWT_EXPIRATION_HOURS = 12
PBKDF2_ITERATIONS = 600_000

DEFAULT_ORG_ID = "org_default"

# Role -> permission mapping. "*" is the super-admin wildcard.
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "super_admin": ["*"],
    "growth_lead": [
        "pipeline:run",
        "pipeline:write",
        "outreach:dispatch",
        "outreach:draft",
        "audit:read",
        "leads:read",
        "leads:write",
        "leads:create",
        "metrics:read",
        "webhooks:manage",
        "crm:sync",
        "hitl:approve",
        "approvals:read",
        "approvals:write",
        "replies:triage",
        "booking:create",
        "tasks:manage",
        "portfolio:manage",
        "outbound:manage"
    ],
    "sdr_rep": [
        "pipeline:run",
        "leads:read",
        "leads:write",
        "leads:create",
        "audit:read",
        "replies:triage",
        "booking:create",
        "outreach:draft",
        "approvals:read"
    ],
    "auditor": [
        "leads:read",
        "audit:read",
        "metrics:read",
        "audit_trail:read",
        "approvals:read"
    ]
}
# Permissions held only by the "*" wildcard: "apikeys:manage" (create, list and revoke API keys).


class Principal(BaseModel):
    user_id: str
    org_id: str
    role: str
    permissions: List[str]
    auth_method: str  # always "jwt": a session issued after a password sign-in


class SecurityService:
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """PBKDF2-HMAC-SHA256 password hashing."""
        if not salt:
            salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            PBKDF2_ITERATIONS
        ).hex()
        return pwd_hash, salt

    @staticmethod
    def verify_password(password: str, stored_hash: str, salt: str) -> bool:
        """Constant-time verification of password against stored PBKDF2 hash."""
        computed_hash, _ = SecurityService.hash_password(password, salt)
        return hmac.compare_digest(computed_hash, stored_hash)

    @staticmethod
    def create_jwt_token(
        user_id: str,
        org_id: str = DEFAULT_ORG_ID,
        role: str = "growth_lead",
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Issues a signed JWT. Unknown roles are refused."""
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"Unknown role: {role}")
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta if expires_delta is not None else timedelta(hours=JWT_EXPIRATION_HOURS))
        payload = {
            "sub": user_id,
            "org_id": org_id,
            "role": role,
            "permissions": ROLE_PERMISSIONS[role],  # informational; the server re-derives them
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": now.timestamp(),
            "exp": expire.timestamp()
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_jwt_token(token: str) -> Dict[str, Any]:
        """Validates signature, expiry, issuer and audience."""
        try:
            return jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]}
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="JWT token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid JWT token")


security_bearer = HTTPBearer(auto_error=False)

_AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def _session_is_current(org_id: str, role: str, issued_at: float) -> bool:
    """False when this tier's password was changed after the token was issued (so old sessions end at once)."""
    from security import passwords
    try:
        changed = passwords.updated_at(role, org_id)
    except Exception:
        logger.exception("session check failed")
        raise HTTPException(status_code=503, detail="Authentication backend unavailable")
    return changed is None or issued_at >= changed


def get_current_principal(
    auth_creds: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Principal:
    """Resolves the caller from a Bearer session token; otherwise 401. An X-API-Key header is not a credential."""
    if auth_creds and auth_creds.credentials:
        payload = SecurityService.decode_jwt_token(auth_creds.credentials)
        role = payload.get("role")
        if role not in ROLE_PERMISSIONS:
            raise HTTPException(status_code=401, detail="Invalid JWT token", headers=_AUTH_HEADERS)
        org = payload.get("org_id") or DEFAULT_ORG_ID
        if not _session_is_current(org, role, float(payload["iat"])):
            raise HTTPException(status_code=401, detail="This session ended because the password was changed. Sign in again.", headers=_AUTH_HEADERS)
        return Principal(
            user_id=str(payload["sub"]),
            org_id=org,
            role=role,
            permissions=ROLE_PERMISSIONS[role],
            auth_method="jwt"
        )

    raise HTTPException(
        status_code=401,
        detail="Sign in required. Send 'Authorization: Bearer <token>' from POST /api/auth/login.",
        headers=_AUTH_HEADERS
    )


def require_role(allowed_roles: List[str]):
    """FastAPI dependency enforcing role membership (super_admin always passes)."""
    def role_checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role == "super_admin":
            return principal
        if principal.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access forbidden: requires one of {allowed_roles}, your role is '{principal.role}'"
            )
        return principal
    return role_checker


def require_permission(permission: str):
    """FastAPI dependency enforcing a single permission."""
    def perm_checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if "*" in principal.permissions or permission in principal.permissions:
            return principal
        raise HTTPException(
            status_code=403,
            detail=f"Access forbidden: missing permission '{permission}'"
        )
    return perm_checker


def scoped_org(principal: Principal, requested_org: Optional[str] = None) -> str:
    """
    Returns the tenant a request may operate on. Defaults to the caller's own org.
    Asking for a different org is allowed only for super_admin.
    """
    if not requested_org or requested_org == principal.org_id:
        return principal.org_id
    if principal.role == "super_admin":
        return requested_org
    raise HTTPException(status_code=403, detail="Access forbidden: cross-tenant access denied")
