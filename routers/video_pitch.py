"""
Video Pitch & Teardown Storyboard Generator Router for AgencyBD Enterprise.
Generates grounded, evidence-backed video pitch storyboards for prospects
using measured Core Web Vitals, security header gaps, and proven agency portfolio proof.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config.settings import settings
from database.db import get_db
from engines.native_multimodal_generator import NativeMultimodalGenerator
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/reports/video-storyboard", tags=["Video Pitch Storyboard"])
RUN = require_permission("pipeline:run")
READ = require_permission("leads:read")


class StoryboardRequest(BaseModel):
    lead_id: int
    prospect_name: Optional[str] = "Founder / CTO"


@router.post("")
def generate_video_storyboard(
    req: StoryboardRequest,
    principal: Principal = Depends(RUN)
):
    """
    Generates an evidence-grounded 4-scene video pitch storyboard
    citing real measured findings from the prospect's tech audit.
    """
    org = principal.org_id

    with get_db() as db:
        lead = db.execute(
            "SELECT id, company_name, domain FROM leads WHERE id = ? AND org_id = ?",
            (req.lead_id, org)
        ).fetchone()

        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Pull measured audit findings
        audit = db.execute(
            "SELECT lcp_score, missing_headers_json FROM tech_audits WHERE lead_id = ? ORDER BY id DESC LIMIT 1",
            (req.lead_id,)
        ).fetchone()

    # Pull agency proof metric from configured profile
    proof = getattr(settings.agency, "case_study_metric", None) or None

    lcp_val = audit["lcp_score"] if audit and audit["lcp_score"] is not None else None
    missing_headers = None
    if audit and audit["missing_headers_json"]:
        import json
        try:
            missing_headers = json.loads(audit["missing_headers_json"])
        except Exception:
            missing_headers = None

    storyboard = NativeMultimodalGenerator.generate_video_pitch_storyboard(
        prospect_name=req.prospect_name or "Founder / CTO",
        company_name=lead["company_name"],
        domain=lead["domain"],
        lcp_score=lcp_val,
        missing_headers=missing_headers,
        proof_point=proof,
        sender_name=principal.user_id
    )

    return {
        "status": "success",
        "lead_id": req.lead_id,
        "company_name": lead["company_name"],
        "domain": lead["domain"],
        "storyboard": storyboard
    }
