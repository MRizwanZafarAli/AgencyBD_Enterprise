"""Enterprise Tenders API: Go/No-Go Scorecard, Compliance Matrix, Bid Studio, Translation, Health & Re-scoring."""

import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.db import get_db
from database.models import OpportunityRepository
from intel.tender_intel import (
    evaluate_bid_scorecard,
    extract_compliance_matrix,
    generate_bid_studio_artifact,
    translate_tender_title,
)
from radar.engine import rescore_tenders
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/tenders", tags=["Tenders"])
READ = require_permission("leads:read")
WRITE = require_permission("leads:write")


class BidActionBody(BaseModel):
    action: str = "executive_summary"


def _load_tender(org_id: str, opportunity_id: int) -> dict:
    opp = OpportunityRepository.get_opportunity(opportunity_id, org_id=org_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Tender not found")
    return opp


@router.post("/{opportunity_id}/scorecard")
def tender_scorecard(opportunity_id: int, principal: Principal = Depends(READ)):
    opp = _load_tender(principal.org_id, opportunity_id)
    return evaluate_bid_scorecard(opp, principal.org_id)


@router.post("/{opportunity_id}/compliance-matrix")
def tender_compliance_matrix(opportunity_id: int, principal: Principal = Depends(READ)):
    opp = _load_tender(principal.org_id, opportunity_id)
    return extract_compliance_matrix(opp)


@router.post("/{opportunity_id}/bid-actions")
def tender_bid_actions(opportunity_id: int, body: BidActionBody, principal: Principal = Depends(READ)):
    opp = _load_tender(principal.org_id, opportunity_id)
    return generate_bid_studio_artifact(opp, body.action)


@router.post("/{opportunity_id}/translate")
def tender_translate(opportunity_id: int, principal: Principal = Depends(READ)):
    opp = _load_tender(principal.org_id, opportunity_id)
    lang = (opp.get("metadata") or {}).get("language", "")
    return translate_tender_title(opp.get("title") or "", lang=lang)


@router.post("/rescore")
def tender_rescore_all(principal: Principal = Depends(WRITE)):
    updated = rescore_tenders(principal.org_id)
    return {"rescored": updated}


@router.get("/source-health")
def tender_source_health(principal: Principal = Depends(READ)):
    """Return live health status for TED, UK FTS, UK Contracts Finder, and SAM.gov (auth_required / rate_limited / ok)."""
    portals = [
        ("ted", "TED (EU)"),
        ("uk_fts", "UK Find a Tender"),
        ("uk_cf", "UK Contracts Finder"),
        ("sam_gov", "SAM.gov (US)"),
    ]
    latest: dict = {}
    with get_db() as db:
        for sid, _ in portals:
            row = db.execute(
                "SELECT status, stored, detail FROM connector_runs WHERE org_id = ? AND source = ? ORDER BY id DESC LIMIT 1",
                (principal.org_id, sid),
            ).fetchone()
            if row:
                latest[sid] = dict(row)

    out = []
    sam_key = (os.getenv("SAM_GOV_API_KEY") or "").strip()
    for sid, label in portals:
        r = latest.get(sid)
        if sid == "sam_gov" and (not sam_key or sam_key.startswith("your_")):
            out.append({"id": sid, "label": label, "status": "auth_required", "hits": 0, "detail": "Set SAM_GOV_API_KEY"})
            continue
        if not r:
            out.append({"id": sid, "label": label, "status": "ok", "hits": 0, "detail": "Ready"})
            continue
        err = (r.get("detail") or "").lower()
        raw_st = (r.get("status") or "ok").lower()
        if raw_st == "not_configured" or "auth_required" in err:
            st = "auth_required"
        elif "429" in err or "rate_limit" in err:
            st = "rate_limited"
        elif raw_st == "error":
            st = "error"
        else:
            st = "ok"
        out.append({"id": sid, "label": label, "status": st, "hits": int(r.get("stored") or 0), "detail": r.get("detail") or raw_st})
    return {"sources": out}
