"""Channels control centre (LinkedIn, Fiverr, Upwork, Freelancer, ...). Your own tracker; nothing here touches those sites."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from security.auth import Principal, require_permission
from workflows import channels as ch

router = APIRouter(prefix="/api/channels", tags=["Channels"])
READ = require_permission("leads:read")
WRITE = require_permission("leads:write")


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class RecordBody(BaseModel):
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)


class PatchBody(BaseModel):
    data: Dict[str, Any]


class SearchLinksBody(BaseModel):
    company: str
    titles: Optional[List[str]] = None
    location: Optional[str] = None


class ParseBody(BaseModel):
    text: str = Field(..., max_length=400)


@router.post("/parse")
def parse_quick_log(body: ParseBody, principal: Principal = Depends(READ)):
    """Turns one plain sentence into a draft application. Nothing is saved until the person confirms."""
    from workflows.quicklog import parse
    return parse(body.text)


@router.get("/parse_date")
def parse_date(text: str = "", principal: Principal = Depends(READ)):
    from workflows.quicklog import parse_date_phrase
    found = parse_date_phrase(text[:300])
    return {"date": found[0] if found else None, "matched": found[1] if found else None}


@router.get("/platforms")
def platforms(principal: Principal = Depends(READ)):
    return {"platforms": [{"id": k, **{x: v[x] for x in ("label", "kind", "home", "terms", "rules", "profile", "limits", "templates", "pages", "features")}, "has_search": bool(v["search"])} for k, v in ch.PLATFORMS.items()],
            "statuses": ch.STATUSES, "activity_kinds": ch.ACTIVITY_KINDS}


@router.get("/overview")
def overview(principal: Principal = Depends(READ)):
    return {"platforms": ch.overview(principal.org_id)}


@router.post("/linkedin/search_links")
def linkedin_links(body: SearchLinksBody, principal: Principal = Depends(READ)):
    """Links to open in your own browser. The server fetches nothing from LinkedIn."""
    return {"links": _guard(ch.linkedin_search_links, body.company, body.titles or [], body.location)}


@router.get("/{platform}/summary")
def platform_summary(platform: str, principal: Principal = Depends(READ)):
    return _guard(ch.summary, principal.org_id, platform)


@router.get("/{platform}/search_url")
def platform_search_url(platform: str, q: str, principal: Principal = Depends(READ)):
    from urllib.parse import quote
    if platform not in ch.PLATFORMS:
        raise HTTPException(status_code=404, detail="Unknown platform")
    template = ch.PLATFORMS[platform]["search"]
    if not template:
        raise HTTPException(status_code=422, detail=f"{ch.PLATFORMS[platform]['label']} has no search address; save its links by hand instead.")
    return {"url": template.format(q=quote(q[:100]))}


@router.get("/{platform}/records")
def list_records(platform: str, type: Optional[str] = None, principal: Principal = Depends(READ)):
    return {"records": _guard(ch.list_records, principal.org_id, platform, type)}


@router.post("/{platform}/records")
def add_record(platform: str, body: RecordBody, principal: Principal = Depends(WRITE)):
    return _guard(ch.add_record, principal.org_id, platform, body.type, body.data)


@router.patch("/{platform}/records/{record_id}")
def patch_record(platform: str, record_id: int, body: PatchBody, principal: Principal = Depends(WRITE)):
    out = _guard(ch.update_record, principal.org_id, platform, record_id, body.data)
    if not out:
        raise HTTPException(status_code=404, detail="Record not found")
    return out


@router.delete("/{platform}/records/{record_id}")
def remove_record(platform: str, record_id: int, principal: Principal = Depends(WRITE)):
    if not _guard(ch.delete_record, principal.org_id, platform, record_id):
        raise HTTPException(status_code=404, detail="Record not found")
    return {"deleted": record_id}
