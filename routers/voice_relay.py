"""
Autonomous Voice & Sales Conversation Intelligence Router.
Provides real-time discovery call transcript analytics, talk-to-listen assessment,
competitor battlecards, deal health scoring, and interactive sales objection reframing.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.db import get_db, log_audit_trail
from engines.native_sales_intelligence import NativeSalesIntelligence
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/voice", tags=["Sales Conversation Intelligence"])
READ = require_permission("leads:read")
RUN = require_permission("pipeline:run")
engine = NativeSalesIntelligence()


class CallAnalysisRequest(BaseModel):
    transcript: str
    lead_id: Optional[int] = None
    founder_speaker_label: Optional[str] = "Agency"
    prospect_speaker_label: Optional[str] = "Prospect"


class ObjectionRequest(BaseModel):
    objection_text: str


@router.post("/qualify")
def qualify_sales_call(
    req: CallAnalysisRequest,
    principal: Principal = Depends(RUN)
):
    """
    Analyzes a discovery call transcript, calculates talk-to-listen ratio,
    detects customer pain points, pulls competitor battlecards, and scores deal health.
    """
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript text cannot be empty")

    analysis = engine.analyze_transcript(
        transcript_text=req.transcript,
        founder_speaker_label=req.founder_speaker_label or "Agency"
    )

    if req.lead_id:
        org = principal.org_id
        with get_db() as db:
            lead = db.execute(
                "SELECT id, company_name FROM leads WHERE id = ? AND org_id = ?",
                (req.lead_id, org)
            ).fetchone()
            if lead:
                note_body = (
                    f"[Call Intel] Win Probability: {analysis['estimated_deal_win_probability_pct']}% "
                    f"({analysis['deal_health_verdict']}). "
                    f"Talk ratio: {analysis['founder_talk_percent']}% vs {analysis['prospect_talk_percent']}%. "
                    f"Pains: {', '.join(analysis['validated_customer_pain_points']) or 'None detected'}."
                )
                db.execute(
                    "INSERT INTO client_notes (org_id, lead_id, kind, body, created_by) VALUES (?, ?, 'note', ?, ?)",
                    (org, req.lead_id, note_body, principal.user_id)
                )
                db.commit()

                log_audit_trail(
                    lead_id=req.lead_id,
                    actor=principal.user_id,
                    action="voice_transcript_analyzed",
                    metadata={
                        "win_prob": analysis["estimated_deal_win_probability_pct"],
                        "verdict": analysis["deal_health_verdict"],
                        "competitors": analysis["detected_competitors"]
                    }
                )

    return {
        "status": "success",
        "analysis": analysis
    }


@router.post("/simulate-objection")
def simulate_sales_objection(
    req: ObjectionRequest,
    principal: Principal = Depends(READ)
):
    """
    Interactive Deal Desk Objection Simulator.
    Returns Challenger psychological reframe, verbal counter-script,
    grounded portfolio proof, and bridge question.
    """
    res = engine.simulate_objection(req.objection_text)
    return {
        "status": "success",
        "result": res
    }


@router.get("/battlecards")
def list_sales_battlecards(principal: Principal = Depends(READ)):
    """Returns all pre-packaged competitor and objection battlecards."""
    return {
        "battlecards": engine.list_battlecards()
    }
