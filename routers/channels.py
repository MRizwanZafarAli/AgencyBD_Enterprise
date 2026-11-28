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
    return ch.list_platforms_with_specs(principal.org_id)


@router.get("/overview")
def overview(principal: Principal = Depends(READ)):
    return ch.overview(principal.org_id)


class PreferencesBody(BaseModel):
    hidden_platforms: List[str] = Field(default_factory=list)


@router.post("/preferences")
def save_preferences(body: PreferencesBody, principal: Principal = Depends(WRITE)):
    return {"hidden_platforms": _guard(ch.set_hidden_platforms, principal.org_id, body.hidden_platforms)}


class CustomChannelBody(BaseModel):
    label: str = Field(..., max_length=60)
    archetype: str = "custom"
    home_url: str = ""
    quick_links: List[Dict[str, str]] = Field(default_factory=list)
    sender_pattern: str = ""


@router.post("/custom")
def add_custom_channel(body: CustomChannelBody, principal: Principal = Depends(WRITE)):
    return _guard(ch.create_custom_channel, principal.org_id, body.label, body.archetype, body.home_url, body.quick_links, body.sender_pattern)


@router.delete("/custom/{slug}")
def remove_custom_channel(slug: str, principal: Principal = Depends(WRITE)):
    if not ch.delete_custom_channel(principal.org_id, slug):
        raise HTTPException(status_code=404, detail="Custom channel not found")
    return {"deleted": slug}


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


@router.post("/{platform}/records/{record_id}/promote")
def promote_record(platform: str, record_id: int, principal: Principal = Depends(WRITE)):
    """Promote a channel pipeline item into the main CRM leads table."""
    out = _guard(ch.promote_to_crm, principal.org_id, platform, record_id)
    if not out:
        raise HTTPException(status_code=404, detail="Record not found")
    return out


class CaptureBody(BaseModel):
    title: str = Field(..., max_length=180)
    url: Optional[str] = None
    client_name: Optional[str] = None
    budget: Optional[float] = 0
    currency_spent: Optional[float] = 0
    boosted: bool = False
    hook_template_id: Optional[str] = None
    client_payment_verified: bool = False
    client_hire_rate: Optional[int] = 0
    client_avg_hourly: Optional[float] = 0
    status: str = "applied"
    notes: Optional[str] = None


@router.post("/{platform}/capture")
def capture_sidepanel(platform: str, body: CaptureBody, principal: Principal = Depends(WRITE)):
    """1-click Side-Panel Auto-Capture into native channel table + Clients CRM."""
    return _guard(ch.capture_from_sidepanel, principal.org_id, platform, body.model_dump())


@router.post("/{platform}/bids")
def create_bid(platform: str, body: Dict[str, Any], principal: Principal = Depends(WRITE)):
    return _guard(ch.add_bid, principal.org_id, platform, body)


@router.patch("/{platform}/bids/{bid_id}")
def patch_bid(platform: str, bid_id: int, body: Dict[str, Any], principal: Principal = Depends(WRITE)):
    out = _guard(ch.update_bid, principal.org_id, platform, bid_id, body)
    if not out:
        raise HTTPException(status_code=404, detail="Bid not found")
    return out


@router.delete("/{platform}/bids/{bid_id}")
def remove_bid(platform: str, bid_id: int, principal: Principal = Depends(WRITE)):
    if not _guard(ch.delete_bid, principal.org_id, platform, bid_id):
        raise HTTPException(status_code=404, detail="Bid not found")
    return {"deleted": bid_id}


@router.post("/{platform}/gigs")
def create_gig(platform: str, body: Dict[str, Any], principal: Principal = Depends(WRITE)):
    return _guard(ch.add_gig, principal.org_id, platform, body)


@router.patch("/{platform}/gigs/{gig_id}")
def patch_gig(platform: str, gig_id: int, body: Dict[str, Any], principal: Principal = Depends(WRITE)):
    out = _guard(ch.update_gig, principal.org_id, platform, gig_id, body)
    if not out:
        raise HTTPException(status_code=404, detail="Gig not found")
    return out


@router.delete("/{platform}/gigs/{gig_id}")
def remove_gig(platform: str, gig_id: int, principal: Principal = Depends(WRITE)):
    if not _guard(ch.delete_gig, principal.org_id, platform, gig_id):
        raise HTTPException(status_code=404, detail="Gig not found")
    return {"deleted": gig_id}


@router.post("/{platform}/reviews")
def create_review(platform: str, body: Dict[str, Any], principal: Principal = Depends(WRITE)):
    return _guard(ch.invite_review, principal.org_id, platform, body)


@router.patch("/{platform}/reviews/{review_id}")
def patch_review(platform: str, review_id: int, body: Dict[str, Any], principal: Principal = Depends(WRITE)):
    out = _guard(ch.update_review, principal.org_id, platform, review_id, body)
    if not out:
        raise HTTPException(status_code=404, detail="Review not found")
    return out


@router.post("/{platform}/pacing")
def save_pacing(platform: str, body: Dict[str, Any], principal: Principal = Depends(WRITE)):
    return _guard(ch.upsert_pacing, principal.org_id, platform, body)


class FiverrCheckBody(BaseModel):
    text: str = Field(..., max_length=5000)


@router.post("/fiverr/compliance-check")
def fiverr_compliance_check(body: FiverrCheckBody, principal: Principal = Depends(READ)):
    from workflows.channel_shields import check_fiverr_compliance
    return check_fiverr_compliance(body.text)


class ClutchQualifyBody(BaseModel):
    service_fit: int = 20
    budget: float = 0
    min_project_size: float = 10000
    specificity: int = 20
    timeline_weeks: int = 4


@router.post("/clutch/qualify")
def clutch_qualify(body: ClutchQualifyBody, principal: Principal = Depends(READ)):
    from workflows.channel_shields import qualify_clutch_inquiry
    return qualify_clutch_inquiry(body.service_fit, body.budget, body.min_project_size, body.specificity, body.timeline_weeks)


@router.get("/upwork/mcp")
def upwork_mcp_info(principal: Principal = Depends(READ)):
    from workflows.channel_shields import get_upwork_mcp_spec
    return get_upwork_mcp_spec()
