"""
Unit and Integration Tests for Distributed Task Queue & Dead-Letter Queue (DLQ).
"""

import pytest
from database.db import init_db
from tasks.task_queue import TaskQueueEngine

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_enqueue_and_complete_task():
    # 1. Enqueue task
    task_id = TaskQueueEngine.enqueue(
        task_name="crawl_site",
        payload={"domain": "example.com"},
        org_id="org_queue_test"
    )
    assert task_id.startswith("task_")

    # 2. Fetch task
    task = TaskQueueEngine.fetch_next_task(org_id="org_queue_test")
    assert task is not None
    assert task["id"] == task_id
    assert task["status"] == "running"
    assert task["payload"]["domain"] == "example.com"

    # 3. Mark completed
    TaskQueueEngine.mark_completed(task_id)

    # 4. Next fetch should be empty
    next_task = TaskQueueEngine.fetch_next_task(org_id="org_queue_test")
    assert next_task is None

def test_task_retry_and_dead_letter_queue():
    task_id = TaskQueueEngine.enqueue(
        task_name="unstable_api_call",
        payload={"endpoint": "https://flaky.api/leads"},
        org_id="org_dlq_test",
        max_retries=2
    )

    # Attempt 1: Fails -> pending
    status_1 = TaskQueueEngine.mark_failed(task_id, "503 Service Unavailable")
    assert status_1 == "pending"

    # Attempt 2: Fails -> exceeds max_retries=2 -> dead_letter
    status_2 = TaskQueueEngine.mark_failed(task_id, "Connection Timeout")
    assert status_2 == "dead_letter"

    # Verify task is in Dead Letter Queue
    dlq_tasks = TaskQueueEngine.list_dead_letters(org_id="org_dlq_test")
    assert len(dlq_tasks) >= 1
    target = [t for t in dlq_tasks if t["id"] == task_id][0]
    assert target["retries"] == 2
    assert "Connection Timeout" in target["error_message"]

    # Requeue from DLQ
    requeued = TaskQueueEngine.retry_dead_letter(task_id)
    assert requeued is True

    # Now it can be picked up again
    task = TaskQueueEngine.fetch_next_task(org_id="org_dlq_test")
    assert task["id"] == task_id
    assert task["retries"] == 0
