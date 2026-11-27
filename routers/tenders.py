"""Enterprise Tenders API: Go/No-Go Scorecard, Compliance Matrix, Bid Studio, Translation & Re-scoring."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
