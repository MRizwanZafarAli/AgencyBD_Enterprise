"""Sequences: multi-day cadences, enrollments and manual scheduler runs."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from security.auth import Principal, require_permission
from workflows.scheduler import SequenceScheduler

router = APIRouter(prefix="/api/sequences", tags=["Sequences"])


class StepModel(BaseModel):
    subject: str
    body: str
    delay_days: int = Field(3, ge=0, le=60)


class CreateSequenceRequest(BaseModel):
    name: str
    steps: List[StepModel]


class EnrollRequest(BaseModel):
    recipient_email: str
    country_code: str = Field(..., min_length=2, max_length=3)
    lead_id: Optional[int] = None
    recipient_name: str = ""
    company_name: str = ""
    deal_value: Optional[float] = Field(None, ge=0)


@router.post("")
def create_sequence(req: CreateSequenceRequest, principal: Principal = Depends(require_permission("outreach:draft"))):
    return SequenceScheduler.create_sequence(principal.org_id, req.name, [s.model_dump() for s in req.steps])


@router.get("")
def list_sequences(principal: Principal = Depends(require_permission("leads:read"))):
    return SequenceScheduler.list_sequences(principal.org_id)


@router.post("/{sequence_id}/enroll")
def enroll(sequence_id: int, req: EnrollRequest, principal: Principal = Depends(require_permission("outreach:dispatch"))):
    try:
        return SequenceScheduler.enroll(principal.org_id, sequence_id, req.recipient_email, req.country_code, req.lead_id,
                                        req.recipient_name, req.company_name, req.deal_value)
    except LookupError:
        raise HTTPException(status_code=404, detail="Sequence not found")


@router.get("/enrollments")
def list_enrollments(status: Optional[str] = None, principal: Principal = Depends(require_permission("leads:read"))):
    return SequenceScheduler.list_enrollments(principal.org_id, status=status)


@router.post("/enrollments/{enrollment_id}/stop")
def stop_enrollment(enrollment_id: int, principal: Principal = Depends(require_permission("outreach:dispatch"))):
    if not SequenceScheduler.stop(principal.org_id, enrollment_id):
        raise HTTPException(status_code=404, detail="No active enrollment with that id")
    return {"stopped": enrollment_id}


@router.post("/run_due")
def run_due(principal: Principal = Depends(require_permission("tasks:manage"))):
    """Processes this tenant's due enrollments now (the background scheduler does this automatically when enabled)."""
    results = [r for r in SequenceScheduler.run_due() if SequenceScheduler.get_enrollment(principal.org_id, r["enrollment_id"])]
    return {"processed": len(results), "results": results}
