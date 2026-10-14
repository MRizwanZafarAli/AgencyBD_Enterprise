"""
Authentication, authorization and tenant scoping for AgencyBD_Enterprise.

Credentials
  * ``X-API-Key`` : opaque key; only its SHA-256 is stored (see ``api_keys`` table).
  * ``Authorization: Bearer <jwt>`` : HS256 token signed with AGENCYBD_JWT_SECRET.

There are no built-in or default credentials. Mint the first super-admin key with
``python scripts/create_admin_key.py``.

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
from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from config.env import get_secret

logger = logging.getLogger("AgencyBD.auth")

JWT_SECRET_KEY = get_secret("AGENCYBD_JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "agencybd-enterprise"
JWT_AUDIENCE = "agencybd-api"
JWT_EXPIRATION_HOURS = 24
PBKDF2_ITERATIONS = 600_000

DEFAULT_ORG_ID = "org_default"
API_KEY_PREFIX = "agy_live"

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
    auth_method: str  # "api_key" or "jwt"


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
    def generate_api_key(prefix: str = API_KEY_PREFIX) -> str:
        """Generates a 192-bit cryptographically secure API key."""
        return f"{prefix}_{secrets.token_hex(24)}"

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """One-way SHA-256 hash for storage. Keys are high-entropy, so a fast hash is appropriate."""
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

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


def _principal_from_api_key(raw_key: str) -> Principal:
    from database.db import get_db

    key_hash = SecurityService.hash_api_key(raw_key.strip())
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT user_id, org_id, role, revoked FROM api_keys WHERE key_hash = ?",
                (key_hash,)
            ).fetchone()
    except Exception:
        logger.exception("API key lookup failed")
        raise HTTPException(status_code=503, detail="Authentication backend unavailable")

    if not row or row["revoked"] or row["role"] not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=401, detail="Invalid or revoked API Key", headers=_AUTH_HEADERS)

    return Principal(
        user_id=row["user_id"],
        org_id=row["org_id"],
        role=row["role"],
        permissions=ROLE_PERMISSIONS[row["role"]],
        auth_method="api_key"
    )


def get_current_principal(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    auth_creds: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Principal:
    """Resolves the caller from X-API-Key or a Bearer JWT; otherwise 401."""
    if x_api_key:
        return _principal_from_api_key(x_api_key)

    if auth_creds and auth_creds.credentials:
        payload = SecurityService.decode_jwt_token(auth_creds.credentials)
        role = payload.get("role")
        if role not in ROLE_PERMISSIONS:
            raise HTTPException(status_code=401, detail="Invalid JWT token", headers=_AUTH_HEADERS)
        return Principal(
            user_id=str(payload["sub"]),
            org_id=payload.get("org_id") or DEFAULT_ORG_ID,
            role=role,
            permissions=ROLE_PERMISSIONS[role],
            auth_method="jwt"
        )

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide 'X-API-Key' header or 'Authorization: Bearer <token>'.",
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
