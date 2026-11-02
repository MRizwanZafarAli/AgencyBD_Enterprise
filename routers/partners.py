"""Referral partner tracker API."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from security.auth import Principal, require_permission
from workflows import partners as pt

router = APIRouter(prefix="/api/partners", tags=["Partners"])
READ = require_permission("leads:read")
WRITE = require_permission("leads:write")


class EventBody(BaseModel):
    kind: str
    body: Optional[str] = None


def _guard(fn, *a):
    try:
        return fn(*a)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("")
def list_partners(principal: Principal = Depends(READ)) -> Dict[str, Any]:
    return {**pt.list_partners(principal.org_id), "kinds": pt.KINDS, "stages": pt.STAGES}


@router.post("")
def create(data: Dict[str, Any], principal: Principal = Depends(WRITE)):
    return _guard(pt.create, principal.org_id, data)


@router.put("/{partner_id}")
def update(partner_id: int, data: Dict[str, Any], principal: Principal = Depends(WRITE)):
    out = _guard(pt.update, principal.org_id, partner_id, data)
    if not out:
        raise HTTPException(status_code=404, detail="Partner not found")
    return out


@router.delete("/{partner_id}")
def delete(partner_id: int, principal: Principal = Depends(WRITE)):
    if not pt.delete(principal.org_id, partner_id):
        raise HTTPException(status_code=404, detail="Partner not found")
    return {"deleted": partner_id}


@router.post("/{partner_id}/events")
def add_event(partner_id: int, body: EventBody, principal: Principal = Depends(WRITE)):
    out = _guard(pt.add_event, principal.org_id, partner_id, body.kind, body.body)
    if not out:
        raise HTTPException(status_code=404, detail="Partner not found")
    return out


@router.get("/{partner_id}/events")
def events(partner_id: int, principal: Principal = Depends(READ)):
    out = pt.events(principal.org_id, partner_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    return {"events": out}
