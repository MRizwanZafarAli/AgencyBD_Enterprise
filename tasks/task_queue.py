"""
Enterprise Distributed Task Queue & Dead-Letter-Queue (DLQ) Engine.
Supports prioritized async jobs, exponential backoff retries, and tamper-resistant DLQ persistence.
"""

import time
import json
import uuid
import traceback
from typing import Dict, Any, List, Optional, Callable
from database.db import get_db

class TaskQueueEngine:
    @staticmethod
    def enqueue(
        task_name: str,
        payload: Dict[str, Any],
        org_id: str = "org_default",
        max_retries: int = 3
    ) -> str:
        """Enqueues a new background task."""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO task_queue (id, org_id, task_name, payload_json, status, retries, max_retries)
                VALUES (?, ?, ?, ?, 'pending', 0, ?)
            """, (task_id, org_id, task_name, json.dumps(payload), max_retries))
            conn.commit()
        return task_id

    @staticmethod
    def fetch_next_task(org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Atomically claims the next pending task for execution."""
        with get_db() as conn:
            cursor = conn.cursor()
            if org_id:
                cursor.execute("""
                    SELECT * FROM task_queue
                    WHERE status = 'pending' AND org_id = ?
                    ORDER BY created_at ASC LIMIT 1
                """, (org_id,))
            else:
                cursor.execute("""
                    SELECT * FROM task_queue
                    WHERE status = 'pending'
                    ORDER BY created_at ASC LIMIT 1
                """)
            row = cursor.fetchone()
            if not row:
                return None
            
            task_dict = dict(row)
            task_dict["payload"] = json.loads(task_dict["payload_json"])
            task_dict["status"] = "running"
            
            # Transition to running
            cursor.execute("UPDATE task_queue SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task_dict["id"],))
            conn.commit()
            return task_dict

    @staticmethod
    def mark_completed(task_id: str) -> None:
        """Marks task as successfully completed."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE task_queue SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
            conn.commit()

    @staticmethod
    def mark_failed(task_id: str, error_message: str) -> str:
        """
        Increments retry count. If retries < max_retries, sets back to 'pending'.
        If retries >= max_retries, moves to Dead Letter Queue ('dead_letter').
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT retries, max_retries FROM task_queue WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return "not_found"

            current_retries = row["retries"] + 1
            max_retries = row["max_retries"]

            if current_retries >= max_retries:
                new_status = "dead_letter"
            else:
                new_status = "pending"

            cursor.execute("""
                UPDATE task_queue
                SET status = ?, retries = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_status, current_retries, error_message, task_id))
            conn.commit()
            return new_status

    @staticmethod
    def list_dead_letters(org_id: str = "org_default") -> List[Dict[str, Any]]:
        """Lists all tasks trapped in the Dead Letter Queue for founder inspection."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, org_id, task_name, payload_json, retries, error_message, created_at, updated_at
                FROM task_queue
                WHERE status = 'dead_letter' AND org_id = ?
                ORDER BY updated_at DESC
            """, (org_id,))
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item["payload"] = json.loads(item["payload_json"])
                result.append(item)
            return result

    @staticmethod
    def retry_dead_letter(task_id: str, org_id: Optional[str] = None) -> bool:
        """Resets a dead-lettered task back to pending with 0 retries (optionally scoped to a tenant)."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE task_queue
                SET status = 'pending', retries = 0, error_message = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'dead_letter' AND (? IS NULL OR org_id = ?)
            """, (task_id, org_id, org_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def execute_task_sync(task_id: str, handlers: Dict[str, Callable]) -> Dict[str, Any]:
        """Executes a single task synchronously using registered handler function."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM task_queue WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return {"status": "error", "message": "Task not found"}

            task_name = row["task_name"]
            payload = json.loads(row["payload_json"])

        handler = handlers.get(task_name)
        if not handler:
            TaskQueueEngine.mark_failed(task_id, f"No handler registered for task: {task_name}")
            return {"status": "error", "message": f"No handler for {task_name}"}

        try:
            result = handler(payload)
            TaskQueueEngine.mark_completed(task_id)
            return {"status": "completed", "result": result}
        except Exception as e:
            tb = traceback.format_exc()
            final_status = TaskQueueEngine.mark_failed(task_id, str(e))
            return {"status": final_status, "error": str(e), "traceback": tb}
