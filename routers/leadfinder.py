"""Lead Finder API: saved searches, what they found, and search links for LinkedIn-style people searches."""

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from leadfinder import engine, sources
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/leadfinder", tags=["Lead Finder"])
READ = require_permission("leads:read")
WRITE = require_permission("leads:write")


class SearchBody(BaseModel):
    name: str = Field(..., max_length=80)
    source: str
    params: Dict[str, Any] = {}
    notify: bool = True
    every_hours: int = 24


class SearchPatch(BaseModel):
    name: Optional[str] = Field(None, max_length=80)
    params: Optional[Dict[str, Any]] = None
    notify: Optional[bool] = None
    active: Optional[bool] = None
    every_hours: Optional[int] = None


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError:
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/sources")
def list_sources(principal: Principal = Depends(READ)):
    return {"sources": [{"id": k, "label": v["label"], "about": v["about"], "needs_key": v["needs"], "ready": not v["needs"] or bool((os.environ.get(v["needs"]) or "").strip())}
                        for k, v in sources.SOURCES.items()],
            "signals": [{"id": k, "label": v["label"]} for k, v in sources.SIGNALS.items()]}


@router.get("/searches")
def searches(principal: Principal = Depends(READ)):
    return {"searches": engine.list_searches(principal.org_id)}


@router.post("/searches")
def create(body: SearchBody, principal: Principal = Depends(WRITE)):
    return _guard(engine.create_search, principal.org_id, body.name, body.source, body.params, body.notify, body.every_hours)


@router.put("/searches/{search_id}")
def update(search_id: int, body: SearchPatch, principal: Principal = Depends(WRITE)):
    out = _guard(engine.update_search, principal.org_id, search_id, body.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(status_code=404, detail="Search not found")
    return out


@router.delete("/searches/{search_id}")
def delete(search_id: int, principal: Principal = Depends(WRITE)):
    if not engine.delete_search(principal.org_id, search_id):
        raise HTTPException(status_code=404, detail="Search not found")
    return {"deleted": search_id}


@router.post("/searches/{search_id}/run")
def run(search_id: int, principal: Principal = Depends(WRITE)):
    return _guard(engine.run_search, principal.org_id, search_id)


@router.get("/hits")
def hits(status: Optional[str] = None, search_id: Optional[int] = None, principal: Principal = Depends(READ)):
    if status not in (None, "new", "saved", "dismissed"):
        raise HTTPException(status_code=422, detail="status must be new, saved or dismissed")
    return {"hits": engine.list_hits(principal.org_id, status, search_id)}


class SaveBody(BaseModel):
    website: Optional[str] = Field(None, max_length=253)


@router.post("/hits/{hit_id}/save")
def save(hit_id: int, body: Optional[SaveBody] = None, principal: Principal = Depends(WRITE)):
    return _guard(engine.save_to_clients, principal.org_id, hit_id, body.website if body else None)


@router.post("/hits/{hit_id}/dismiss")
def dismiss(hit_id: int, principal: Principal = Depends(WRITE)):
    if not engine.dismiss(principal.org_id, hit_id):
        raise HTTPException(status_code=404, detail="Hit not found or already saved")
    return {"dismissed": hit_id}


@router.get("/places")
def places(principal: Principal = Depends(READ)):
    """Official places to look that publish no feed we may read. Links only; nothing is fetched."""
    return {"places": sources.LOOK_HERE}


@router.get("/xray")
def xray(role: str, industry: str = "", location: str = "", principal: Principal = Depends(READ)):
    return {"links": _guard(sources.xray_links, role, industry, location)}
