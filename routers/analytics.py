"""
Analytics & Learning Loop Router.
Surfaces strategic weekly performance reports, deliverability health,
variant conversion A/B tracking, and automated playbooks recommendations.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends
from security.auth import Principal, require_permission
from analytics.learning_loop import LearningLoopEngine

router = APIRouter(prefix="/api/analytics", tags=["Learning Loop & Strategy"])

@router.get("/learning_report")
def get_learning_report(principal: Principal = Depends(require_permission("leads:read"))):
    return LearningLoopEngine.generate_learning_report(org_id=principal.org_id)
