"""Sign-in with a tier password, and password management. Passwords are never returned, logged or echoed in an error."""

import os
from datetime import timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from security import passwords
from security.auth import JWT_EXPIRATION_HOURS, ROLE_PERMISSIONS, Principal, SecurityService, get_current_principal

router = APIRouter(prefix="/api/auth", tags=["Sign-in"])


class LoginBody(BaseModel):
    role: str = Field(..., max_length=32)
    password: str = Field(..., max_length=passwords.MAX_LENGTH + 64)


class PasswordBody(BaseModel):
    role: str = Field(..., max_length=32)
    new_password: str = Field(..., max_length=passwords.MAX_LENGTH + 64)
    current_password: Optional[str] = Field(None, max_length=passwords.MAX_LENGTH + 64)


def _ip(request: Request) -> str:
    """The address used for the lockout. Behind nginx (AGENCYBD_TRUST_PROXY=1) it is the real visitor taken from X-Real-IP, which nginx sets
    itself; otherwise every visitor would share the proxy's address and one attacker could lock everybody out. Never trusted by default."""
    if os.getenv("AGENCYBD_TRUST_PROXY", "").lower() in ("1", "true", "on", "yes"):
        real = (request.headers.get("x-real-ip") or "").strip()
        if real:
            return real[:64]
    return request.client.host if request.client else "unknown"


@router.get("/tiers")
def tiers() -> Dict[str, Any]:
    """Which tiers can sign in on this installation (names only, no secrets). Used by the sign-in screen."""
    st = passwords.status()
    return {"tiers": [{"role": t["role"], "label": t["label"], "available": t["is_set"]} for t in st], "any_set": any(t["is_set"] for t in st),
            "min_length": passwords.MIN_LENGTH}


@router.post("/login")
def login(body: LoginBody, request: Request) -> Dict[str, Any]:
    ip = _ip(request)
    wait = passwords.retry_after(ip)
    if wait:
        raise HTTPException(status_code=429, detail=f"Too many wrong passwords. Try again in {max(1, wait // 60 + (1 if wait % 60 else 0))} minute(s).", headers={"Retry-After": str(wait)})
    if not any(t["is_set"] for t in passwords.status()):
        raise HTTPException(status_code=503, detail="No passwords are set yet. On the server, run: python scripts/set_passwords.py")
    ok = passwords.verify(body.role, body.password)
    passwords.record(ip, body.role, ok)
    if not ok:
        raise HTTPException(status_code=401, detail="That tier and password do not match.")
    org = passwords.org_id()
    token = SecurityService.create_jwt_token(user_id=body.role, org_id=org, role=body.role, expires_delta=timedelta(hours=JWT_EXPIRATION_HOURS))
    return {"token": token, "expires_in": JWT_EXPIRATION_HOURS * 3600,
            "me": {"user_id": body.role, "org_id": org, "role": body.role, "permissions": ROLE_PERMISSIONS[body.role], "auth_method": "jwt"}}


@router.get("/passwords")
def password_status(principal: Principal = Depends(get_current_principal)) -> Dict[str, Any]:
    """Which tiers have a password and when it last changed. Super admin sees all tiers; everyone else sees only their own."""
    rows = passwords.status(principal.org_id)
    if principal.role != "super_admin":
        rows = [r for r in rows if r["role"] == principal.role]
    return {"tiers": rows, "min_length": passwords.MIN_LENGTH, "can_set_all": principal.role == "super_admin"}


@router.post("/password")
def change_password(body: PasswordBody, request: Request, principal: Principal = Depends(get_current_principal)) -> Dict[str, Any]:
    """Super admin may set any tier's password. Anyone may change their own tier's password by giving the current one."""
    if body.role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=422, detail="Unknown tier.")
    own = body.role == principal.role
    wait = passwords.retry_after(_ip(request))
    if wait:
        raise HTTPException(status_code=429, detail="Too many wrong passwords. Try again later.", headers={"Retry-After": str(wait)})
    if principal.role != "super_admin" and not own:
        raise HTTPException(status_code=403, detail="You can only change your own tier's password.")
    if own and (not body.current_password or not passwords.verify(body.role, body.current_password, principal.org_id)):
        passwords.record(_ip(request), body.role, False)
        raise HTTPException(status_code=401, detail="The current password is not right.")
    try:
        passwords.set_password(body.role, body.new_password, by=principal.role, org=principal.org_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    out: Dict[str, Any] = {"status": "changed", "role": body.role, "note": "Everyone signed in to this tier must sign in again."}
    if own:                                                       # keep the person who just changed it signed in
        out["token"] = SecurityService.create_jwt_token(user_id=principal.user_id, org_id=principal.org_id, role=principal.role)
    return out
