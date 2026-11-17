"""
Event-Driven Lifecycle Hooks & Bus Architecture for AgencyBD Enterprise.
Provides asynchronous, decoupled publish/subscribe event infrastructure for autonomous BD agents.
Supports 12 canonical lifecycle events, priority ordering, error isolation, and audit trail logging.
"""

import asyncio
import inspect
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.logger import get_enterprise_logger
from database.db import get_db

logger = get_enterprise_logger("EventBus")

# 12 Canonical Enterprise Lifecycle Hooks
HOOK_LEAD_SOURCED = "on_lead_sourced"
HOOK_AUDIT_COMPLETED = "on_audit_completed"
HOOK_CONTACT_VERIFIED = "on_contact_verified"
HOOK_INTENT_SPIKE = "on_intent_spike"
HOOK_DRAFT_CREATED = "on_draft_created"
HOOK_SEND_APPROVED = "on_send_approved"
HOOK_EMAIL_SENT = "on_email_sent"
HOOK_REPLY_RECEIVED = "on_reply_received"
HOOK_OBJECTION_CLASSIFIED = "on_objection_classified"
HOOK_KILLSWITCH_ENGAGED = "on_killswitch_engaged"
HOOK_QUOTA_WARNING = "on_quota_warning"
HOOK_CHURN_RISK_FLAGGED = "on_churn_risk_flagged"

ALL_CANONICAL_HOOKS: Set[str] = {
    HOOK_LEAD_SOURCED,
    HOOK_AUDIT_COMPLETED,
    HOOK_CONTACT_VERIFIED,
    HOOK_INTENT_SPIKE,
    HOOK_DRAFT_CREATED,
    HOOK_SEND_APPROVED,
    HOOK_EMAIL_SENT,
    HOOK_REPLY_RECEIVED,
    HOOK_OBJECTION_CLASSIFIED,
    HOOK_KILLSWITCH_ENGAGED,
    HOOK_QUOTA_WARNING,
    HOOK_CHURN_RISK_FLAGGED,
}


class HookRegistration:
    def __init__(self, callback: Callable, priority: int = 100, name: Optional[str] = None):
        self.callback = callback
        self.priority = priority  # Lower number = higher priority
        self.name = name or getattr(callback, "__name__", str(callback))
        self.is_async = inspect.iscoroutinefunction(callback)

    def __repr__(self) -> str:
        return f"<HookRegistration {self.name} priority={self.priority} async={self.is_async}>"


class EventBus:
    """
    Central Asynchronous & Synchronous Event Bus.
    Thread-safe, resilient, and non-blocking with persistent SQLite audit records.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._handlers: Dict[str, List[HookRegistration]] = {}
        self._middlewares: List[Callable] = []

    def register(self, event_name: str, callback: Callable, priority: int = 100, name: Optional[str] = None):
        """Registers a listener for a specific event."""
        with self._lock:
            if event_name not in self._handlers:
                self._handlers[event_name] = []
            reg = HookRegistration(callback, priority=priority, name=name)
            self._handlers[event_name].append(reg)
            # Sort handlers by priority ascending (10 runs before 100)
            self._handlers[event_name].sort(key=lambda r: r.priority)
            logger.info(f"Registered hook [{event_name}] -> {reg.name} (priority {priority})")

    def unregister(self, event_name: str, callback: Callable):
        """Unregisters a listener."""
        with self._lock:
            if event_name in self._handlers:
                self._handlers[event_name] = [
                    h for h in self._handlers[event_name] if h.callback != callback
                ]

    def clear(self, event_name: Optional[str] = None):
        """Clears registered handlers for testing."""
        with self._lock:
            if event_name:
                self._handlers.pop(event_name, None)
            else:
                self._handlers.clear()

    def list_handlers(self) -> Dict[str, List[str]]:
        """Returns currently active event handlers."""
        with self._lock:
            return {
                ev: [h.name for h in handlers]
                for ev, handlers in self._handlers.items()
            }

    def emit(
        self,
        event_name: str,
        payload: Dict[str, Any],
        source_agent: Optional[str] = None,
        org_id: str = "org_default",
        sync: bool = False,
    ) -> List[Any]:
        """
        Emits an event to all registered listeners.
        If sync=False (default), synchronous handlers execute immediately and
        async coroutines are scheduled on the running event loop or dispatched safely.
        If sync=True, waits for all handlers to complete and returns their return values.
        """
        start_time = time.time()
        handlers: List[HookRegistration] = []
        with self._lock:
            handlers = list(self._handlers.get(event_name, []))

        results: List[Any] = []
        errors: List[str] = []

        # Run registered middlewares
        for mw in self._middlewares:
            try:
                mw(event_name, payload, source_agent, org_id)
            except Exception as e:
                logger.warning(f"Middleware failed on {event_name}: {e}")

        for h in handlers:
            h_start = time.time()
            try:
                if h.is_async:
                    try:
                        loop = asyncio.get_running_loop()
                        if sync:
                            # Run synchronously within already running event loop via concurrent future
                            # or run_until_complete if we can, or asyncio.run if isolated
                            res = asyncio.run_coroutine_threadsafe(
                                h.callback(payload), loop
                            ).result(timeout=15.0)
                            results.append(res)
                        else:
                            loop.create_task(self._safe_async_call(h, payload))
                    except RuntimeError:
                        # No running loop in this thread
                        if sync:
                            res = asyncio.run(h.callback(payload))
                            results.append(res)
                        else:
                            # Run in background thread
                            threading.Thread(
                                target=lambda: asyncio.run(self._safe_async_call(h, payload)),
                                daemon=True,
                            ).start()
                else:
                    res = h.callback(payload)
                    results.append(res)
            except Exception as exc:
                err_msg = f"Handler {h.name} failed on {event_name}: {exc}"
                logger.error(err_msg, exc_info=True)
                errors.append(err_msg)

        duration_ms = (time.time() - start_time) * 1000.0
        status = "failed" if (errors and len(errors) == len(handlers)) else "processed"
        if not handlers:
            status = "emitted"

        # Asynchronously or safely persist to DB audit trail
        self._record_lifecycle_event(
            event_name=event_name,
            payload=payload,
            source_agent=source_agent,
            org_id=org_id,
            status=status,
            handlers_count=len(handlers),
            duration_ms=duration_ms,
            error_message="; ".join(errors) if errors else None,
        )

        return results

    async def _safe_async_call(self, h: HookRegistration, payload: Dict[str, Any]):
        try:
            await h.callback(payload)
        except Exception as exc:
            logger.error(f"Async handler {h.name} failed: {exc}", exc_info=True)

    def _record_lifecycle_event(
        self,
        event_name: str,
        payload: Dict[str, Any],
        source_agent: Optional[str],
        org_id: str,
        status: str,
        handlers_count: int,
        duration_ms: float,
        error_message: Optional[str],
    ):
        def _persist():
            try:
                # Sanitize payload for JSON storage
                safe_payload = {}
                for k, v in payload.items():
                    if isinstance(v, (str, int, float, bool, list, dict)) or v is None:
                        safe_payload[k] = v
                    else:
                        safe_payload[k] = str(v)
                payload_json = json.dumps(safe_payload, default=str)

                with get_db() as conn:
                    conn.execute(
                        """
                        INSERT INTO lifecycle_events (
                            org_id, event_name, payload_json, source_agent,
                            status, handlers_count, duration_ms, error_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            org_id,
                            event_name,
                            payload_json,
                            source_agent,
                            status,
                            handlers_count,
                            duration_ms,
                            error_message,
                        ),
                    )
                    conn.commit()
            except Exception as e:
                logger.warning(f"Could not persist lifecycle event to DB: {e}")

        threading.Thread(target=_persist, daemon=True).start()

    def get_recent_events(self, org_id: str = "org_default", limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent lifecycle events from the persistent audit trail."""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, event_name, payload_json, source_agent, status,
                           handlers_count, duration_ms, error_message, created_at
                    FROM lifecycle_events
                    WHERE org_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (org_id, limit),
                )
                rows = cursor.fetchall()
                out = []
                for r in rows:
                    out.append(
                        {
                            "id": r[0],
                            "event_name": r[1],
                            "payload": json.loads(r[2]) if r[2] else {},
                            "source_agent": r[3],
                            "status": r[4],
                            "handlers_count": r[5],
                            "duration_ms": r[6],
                            "error_message": r[7],
                            "created_at": r[8],
                        }
                    )
                return out
        except Exception as e:
            logger.error(f"Error querying lifecycle_events: {e}")
            return []


# Global Singleton Event Bus Instance
event_bus = EventBus()


def hook(event_name: str, priority: int = 100):
    """
    Decorator to register a function as a lifecycle hook listener.
    Usage:
        @hook(HOOK_LEAD_SOURCED, priority=10)
        def on_new_lead(payload):
            ...
    """

    def decorator(fn: Callable):
        event_bus.register(event_name, fn, priority=priority)
        return fn

    return decorator
