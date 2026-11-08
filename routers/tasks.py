"""
Enterprise Distributed Task Queue & Dead-Letter Queue (DLQ) Router.
Enables real-time visibility into asynchronous background jobs, automatic retries,
and manual DLQ inspection and replay.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.db import get_db
from security.auth import Principal, require_permission
from tasks.task_queue import TaskQueueEngine

router = APIRouter(prefix="/api/system/queue", tags=["Task Queue"])
MANAGE = require_permission("apikeys:manage")
READ = require_permission("leads:read")


class EnqueueRequest(BaseModel):
    task_name: str
    payload: Dict[str, Any]
    max_retries: Optional[int] = 3


@router.get("")
def get_queue_status(principal: Principal = Depends(READ)):
    """Returns queue telemetry, pending counts, and dead-letter tasks for this workspace."""
    org = principal.org_id
    with get_db() as db:
        counts = {}
        for status in ("pending", "running", "completed", "dead_letter"):
            row = db.execute(
                "SELECT COUNT(*) FROM task_queue WHERE org_id = ? AND status = ?",
                (org, status)
            ).fetchone()
            counts[status] = row[0] if row else 0

        recent_rows = db.execute(
            "SELECT id, task_name, status, retries, max_retries, error_message, created_at, updated_at "
            "FROM task_queue WHERE org_id = ? ORDER BY created_at DESC LIMIT 15",
            (org,)
        ).fetchall()
        recent = [dict(r) for r in recent_rows]

    dead_letters = TaskQueueEngine.list_dead_letters(org_id=org)
    return {
        "counts": counts,
        "recent_tasks": recent,
        "dead_letters": dead_letters[:10],
        "is_healthy": counts.get("dead_letter", 0) == 0
    }


@router.post("/enqueue")
def enqueue_task(req: EnqueueRequest, principal: Principal = Depends(MANAGE)):
    """Enqueues a new background task."""
    task_id = TaskQueueEngine.enqueue(
        task_name=req.task_name,
        payload=req.payload,
        org_id=principal.org_id,
        max_retries=req.max_retries or 3
    )
    return {"status": "enqueued", "task_id": task_id}


@router.post("/{task_id}/retry")
def retry_dead_letter_task(task_id: str, principal: Principal = Depends(MANAGE)):
    """Retries a dead-letter task by returning it to 'pending' with 0 retries."""
    ok = TaskQueueEngine.retry_dead_letter(task_id=task_id, org_id=principal.org_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Dead-letter task not found or unauthorized")
    return {"status": "retried", "task_id": task_id}


@router.post("/drain")
def drain_pending_tasks(limit: int = 5, principal: Principal = Depends(MANAGE)):
    """Processes up to `limit` pending tasks using registered workers."""
    org = principal.org_id
    handlers = {
        "ping": lambda payload: {"echo": payload.get("message", "ok")},
        "audit_notify": lambda payload: {"notified": payload.get("lead_id")},
    }

    processed = []
    for _ in range(min(limit, 20)):
        task = TaskQueueEngine.fetch_next_task(org_id=org)
        if not task:
            break
        task_id = task["id"]
        res = TaskQueueEngine.execute_task_sync(task_id, handlers)
        processed.append({"task_id": task_id, "result": res})

    return {"processed_count": len(processed), "results": processed}
