"""Settings > Integrations: manage API keys of related products (super-admin only; values are never returned)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import integrations
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])
MANAGE = require_permission("apikeys:manage")        # held only by the super-admin wildcard


class KeyBody(BaseModel):
    value: str


@router.get("")
def list_integrations(principal: Principal = Depends(MANAGE)):
    return {"integrations": integrations.list_status(),
            "note": "Keys are encrypted at rest, shared by every workspace on this installation, and never shown again after saving."}


@router.put("/{name}")
def save_integration(name: str, body: KeyBody, principal: Principal = Depends(MANAGE)):
    try:
        return integrations.set_key(name, body.value, principal.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{name}")
def remove_integration(name: str, principal: Principal = Depends(MANAGE)):
    try:
        return {"removed": integrations.clear_key(name)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{name}/test")
def test_integration(name: str, principal: Principal = Depends(MANAGE)):
    try:
        return integrations.test_key(name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
