"""
Enterprise Autonomy Policy Router.
Manages tenant-specific autonomy policies (L0, L1, L2, L3)
and surfaces immutable policy decision audit logs.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from security.auth import Principal, require_permission
from policy.engine import PolicyEngine
from database.db import get_db

router = APIRouter(prefix="/api/policy", tags=["Autonomy Policy Engine"])

class SetPolicyRuleRequest(BaseModel):
    rule_name: str
    level: str  # L0 | L1 | L2 | L3 | NEVER
    config: Optional[Dict[str, Any]] = None

class EvaluatePolicyRequest(BaseModel):
    action_type: str
    context: Dict[str, Any]

@router.get("/rules")
def list_policy_rules(principal: Principal = Depends(require_permission("leads:read"))):
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM policies WHERE org_id = ?", (principal.org_id,))
        return [dict(r) for r in cursor.fetchall()]

@router.post("/rules")
def set_policy_rule(req: SetPolicyRuleRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    if req.level not in ("L0", "L1", "L2", "L3", "NEVER"):
        raise HTTPException(status_code=400, detail="Invalid autonomy level. Must be L0, L1, L2, L3, or NEVER.")
    PolicyEngine.set_tenant_policy(
        org_id=principal.org_id,
        rule_name=req.rule_name,
        level=req.level,
        config=req.config
    )
    return {"status": "success", "rule_name": req.rule_name, "level": req.level}

@router.post("/evaluate")
def evaluate_policy(req: EvaluatePolicyRequest, principal: Principal = Depends(require_permission("leads:read"))):
    decision = PolicyEngine.evaluate(
        org_id=principal.org_id,
        action_type=req.action_type,
        context=req.context
    )
    return decision.to_dict()

@router.get("/decisions")
def list_policy_decisions(limit: int = 50, principal: Principal = Depends(require_permission("leads:read"))):
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM policy_decisions
            WHERE org_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (principal.org_id, limit))
        return [dict(r) for r in cursor.fetchall()]
