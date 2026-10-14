"""
Reply Agent Router.
Handles inbound email triage, objection classification,
auto-suppression of opt-outs, and queuing responses into the Human Approval Inbox.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from security.auth import Principal, require_permission
from agents.reply_agent import ReplyAgent

router = APIRouter(prefix="/api/replies", tags=["Reply Agent"])

class ReplyTriageRequest(BaseModel):
    raw_body: str
    sender_email: str
    lead_id: Optional[int] = None
    company_name: Optional[str] = ""

@router.post("/inbound")
def triage_inbound_reply(req: ReplyTriageRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    agent = ReplyAgent()
    return agent.handle_inbound_reply(
        raw_body=req.raw_body,
        sender_email=req.sender_email,
        org_id=principal.org_id,
        lead_id=req.lead_id,
        company_name=req.company_name or ""
    )
