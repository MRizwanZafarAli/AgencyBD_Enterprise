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


class ScheduleCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    channel: str = Field(..., pattern="^(hiring|local|sec_edgar|social|radar_scan)$")
    query: str = ""
    location: str = ""
    limit_per_run: int = Field(5, ge=1, le=25)
    cadence_hours: int = Field(24, ge=1, le=168)
    assign_mode: str = Field("round_robin", pattern="^(round_robin|unassigned)$")
    auto_send_tier_a: bool = False


@router.get("/schedules")
def get_autopilot_schedules(principal: Principal = Depends(require_permission("leads:read"))):
    from orchestrator.schedule_runner import list_schedules
    return {"ok": True, "schedules": list_schedules(principal.org_id)}


@router.post("/schedules")
def add_autopilot_schedule(
    req: ScheduleCreateRequest,
    principal: Principal = Depends(require_permission("pipeline:run")),
):
    from orchestrator.schedule_runner import create_schedule
    try:
        sched = create_schedule(
            org_id=principal.org_id,
            name=req.name,
            channel=req.channel,
            query=req.query,
            location=req.location,
            limit_per_run=req.limit_per_run,
            cadence_hours=req.cadence_hours,
            assign_mode=req.assign_mode,
            auto_send_tier_a=req.auto_send_tier_a,
        )
        return {"ok": True, "schedule": sched}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/schedules/{schedule_id}/toggle")
def toggle_autopilot_schedule(
    schedule_id: int,
    enabled: bool = Query(...),
    principal: Principal = Depends(require_permission("pipeline:run")),
):
    from orchestrator.schedule_runner import toggle_schedule
    try:
        return {"ok": True, "schedule": toggle_schedule(principal.org_id, schedule_id, enabled)}
    except LookupError:
        raise HTTPException(status_code=404, detail="Schedule not found")


@router.post("/schedules/run-due")
def trigger_due_autopilot_schedules(
    principal: Principal = Depends(require_permission("pipeline:run")),
):
    from orchestrator.schedule_runner import run_due_schedules
    return {"ok": True, "triggered": run_due_schedules(principal.org_id)}
