"""Notes, follow-up tasks and the timeline for a client."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from security.auth import Principal, require_permission
from workflows import client_notes as cn

router = APIRouter(tags=["Client notes"])
READ = require_permission("leads:read")
WRITE = require_permission("leads:write")


class NoteBody(BaseModel):
    kind: str = "note"
    body: str
    due_date: Optional[str] = None


def _guard(fn, *a):
    try:
        return fn(*a)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/api/clients/{lead_id}/notes")
def list_notes(lead_id: int, principal: Principal = Depends(READ)) -> Dict[str, Any]:
    items = cn.list_for(principal.org_id, lead_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"items": items, "timeline": cn.timeline(principal.org_id, lead_id)}


@router.post("/api/clients/{lead_id}/notes")
def add_note(lead_id: int, body: NoteBody, principal: Principal = Depends(WRITE)):
    out = _guard(cn.add, principal.org_id, lead_id, body.kind, body.body, body.due_date, principal.user_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return out


@router.patch("/api/clients/{lead_id}/notes/{note_id}")
def patch_note(lead_id: int, note_id: int, data: Dict[str, Any], principal: Principal = Depends(WRITE)):
    out = _guard(cn.update, principal.org_id, lead_id, note_id, data)
    if out is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return out


@router.delete("/api/clients/{lead_id}/notes/{note_id}")
def delete_note(lead_id: int, note_id: int, principal: Principal = Depends(WRITE)):
    if not cn.delete(principal.org_id, lead_id, note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"deleted": note_id}


@router.get("/api/followups")
def followups(principal: Principal = Depends(READ)):
    return cn.followups(principal.org_id)


@router.get("/api/chase")
def chase(principal: Principal = Depends(READ)) -> Dict[str, Any]:
    """Clients in a live stage that went quiet with no follow-up planned, closest to a decision first."""
    from workflows import chase as ch
    return {"items": ch.to_chase(principal.org_id), "quiet_after_days": ch.QUIET_AFTER_DAYS}
