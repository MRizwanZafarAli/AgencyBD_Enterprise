"""
Agent Swarm & Lifecycle Hooks API Router for AgencyBD Enterprise.
Provides endpoints for swarm telemetry, hook inspection, skill execution, and autonomy toggling.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.hooks import event_bus
from core.skills import skill_registry, SkillExecutionError
from agents.swarm import swarm_controller
from security.auth import Principal, get_current_principal, require_role, require_permission

router = APIRouter(prefix="/api/v1/swarm", tags=["Agent Swarm"])


class SwarmActivateRequest(BaseModel):
    activate: bool = Field(..., description="Whether to activate or deactivate the autonomous swarm")


class SkillRunRequest(BaseModel):
    skill_name: str = Field(..., description="Registered skill name, e.g. 'domain_whois_dns'")
    params: Dict[str, Any] = Field(default_factory=dict, description="Skill input parameters")


@router.get("/telemetry")
def get_swarm_telemetry(
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Returns real-time telemetry and state for all 8 autonomous agents in the swarm."""
    telemetry = swarm_controller.get_telemetry()
    telemetry["org_id"] = principal.org_id
    return {
        "ok": True,
        "telemetry": telemetry,
    }


@router.post("/activate")
def toggle_swarm_autonomy(
    req: SwarmActivateRequest,
    principal: Principal = Depends(require_role(["super_admin", "growth_lead"])),
) -> Dict[str, Any]:
    """Activates or pauses autonomous agent swarm execution."""
    if req.activate:
        swarm_controller.activate_swarm()
        msg = "Autonomous Agent Swarm activated."
    else:
        # Note: listeners remain in memory but swarm can be flagged inactive
        swarm_controller._is_active = False
        msg = "Autonomous Agent Swarm deactivated."

    return {
        "ok": True,
        "swarm_active": swarm_controller.is_active(),
        "message": msg,
    }


@router.get("/events")
def list_lifecycle_events(
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Returns recent lifecycle events recorded in the persistent audit trail."""
    events = event_bus.get_recent_events(org_id=principal.org_id, limit=limit)
    return {
        "ok": True,
        "count": len(events),
        "events": events,
    }


@router.get("/skills")
def list_available_skills(
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Lists all modular BD skills registered in the system."""
    skills = skill_registry.list_skills()
    return {
        "ok": True,
        "total": len(skills),
        "skills": skills,
    }


@router.post("/skills/run")
def execute_skill_endpoint(
    req: SkillRunRequest,
    principal: Principal = Depends(require_permission("lead:write")),
) -> Dict[str, Any]:
    """Manually or programmatically executes a modular BD skill."""
    skill = skill_registry.get(req.skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{req.skill_name}' not found")

    try:
        output = skill.run(req.params, org_id=principal.org_id, agent_name="API_Caller")
        return {
            "ok": True,
            "skill": req.skill_name,
            "result": output.model_dump(),
        }
    except ValueError as val_err:
        raise HTTPException(status_code=422, detail=f"Validation error: {val_err}")
    except SkillExecutionError as exec_err:
        raise HTTPException(status_code=500, detail=str(exec_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Skill execution failed: {exc}")
