"""
Outbound Webhooks Router & Dispatch Engine for AgencyBD Enterprise.
Dispatches real-time HMAC-signed events to external CRMs (HubSpot, Salesforce, Zapier, Make, n8n)
when deals move to 'won', clients are created, or audits finish.
"""

import hashlib
import hmac
import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

from database.db import get_db
from net.fetcher import SafeFetcher
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])
READ = require_permission("leads:read")
MANAGE = require_permission("apikeys:manage")


class WebhookCreateRequest(BaseModel):
    url: str
    secret: Optional[str] = None
    events: Optional[List[str]] = ["deal.won", "client.created"]
    active: Optional[bool] = True


def _sign_payload(secret: str, payload_bytes: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def dispatch_webhook_event(org_id: str, event_name: str, payload: Dict[str, Any]):
    """Asynchronously dispatches an event to all subscribed webhooks for this organization."""
    def _run():
        with get_db() as db:
            rows = db.execute(
                "SELECT id, url, secret, events_json FROM outbound_webhooks WHERE org_id = ? AND active = 1",
                (org_id,)
            ).fetchall()
            
            for r in rows:
                subscribed = json.loads(r["events_json"]) if r["events_json"] else []
                if event_name not in subscribed and "*" not in subscribed:
                    continue

                full_body = {
                    "event": event_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "org_id": org_id,
                    "data": payload
                }
                body_bytes = json.dumps(full_body).encode("utf-8")
                sig = _sign_payload(r["secret"], body_bytes)

                headers = {
                    "Content-Type": "application/json",
                    "X-AgencyBD-Signature": sig,
                    "X-AgencyBD-Event": event_name,
                    "User-Agent": "AgencyBD-Webhook-Dispatcher/2.4"
                }

                status_code = None
                err_msg = None
                try:
                    res = SafeFetcher.safe_fetch(
                        r["url"],
                        method="POST",
                        json_body=full_body,
                        headers=headers,
                        timeout=8
                    )
                    status_code = res.status_code
                except Exception as e:
                    err_msg = str(e)[:250]
                    status_code = getattr(e, "status_code", 500)

                db.execute(
                    "UPDATE outbound_webhooks SET last_delivered_at = CURRENT_TIMESTAMP, last_status_code = ?, last_error = ? WHERE id = ?",
                    (status_code, err_msg, r["id"])
                )
                db.commit()

    threading.Thread(target=_run, daemon=True).start()


@router.get("")
def list_webhooks(principal: Principal = Depends(READ)) -> Dict[str, Any]:
    org = principal.org_id
    with get_db() as db:
        rows = db.execute(
            "SELECT id, url, secret, events_json, active, last_delivered_at, last_status_code, last_error, created_at "
            "FROM outbound_webhooks WHERE org_id = ? ORDER BY id DESC",
            (org,)
        ).fetchall()
        
        webhooks = []
        for r in rows:
            w = dict(r)
            w["events"] = json.loads(w["events_json"]) if w["events_json"] else []
            # Mask secret for display
            w["secret_masked"] = w["secret"][:6] + "..." + w["secret"][-4:] if len(w["secret"]) > 10 else "******"
            del w["secret"]
            webhooks.append(w)

    return {
        "webhooks": webhooks,
        "available_events": [
            {"id": "deal.won", "label": "Deal Marked as Won", "description": "Triggered when a client or deal transitions to Won status"},
            {"id": "client.created", "label": "Client Created", "description": "Triggered when a new prospect/client is enrolled into CRM"},
            {"id": "audit.completed", "label": "Audit Completed", "description": "Triggered when a Website Doctor or Site Clinic audit finishes"},
            {"id": "visitor.high_intent", "label": "High-Intent Visitor Detected", "description": "Triggered when a target company visits pricing or contact pages"}
        ]
    }


@router.post("")
def create_webhook(req: WebhookCreateRequest, principal: Principal = Depends(MANAGE)) -> Dict[str, Any]:
    org = principal.org_id
    if not req.url.startswith("http://") and not req.url.startswith("https://"):
        raise HTTPException(status_code=422, detail="Webhook URL must begin with http:// or https://")

    secret = req.secret or hashlib.sha256(f"{org}_{req.url}_{time.time()}".encode("utf-8")).hexdigest()[:32]
    events_json = json.dumps(req.events or ["deal.won", "client.created"])

    with get_db() as db:
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO outbound_webhooks (org_id, url, secret, events_json, active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (org, req.url, secret, events_json, 1 if req.active else 0)
        )
        wid = cursor.lastrowid
        db.commit()

    return {"status": "created", "id": wid, "url": req.url, "secret": secret}


@router.delete("/{webhook_id}")
def delete_webhook(webhook_id: int, principal: Principal = Depends(MANAGE)) -> Dict[str, Any]:
    org = principal.org_id
    with get_db() as db:
        res = db.execute("DELETE FROM outbound_webhooks WHERE id = ? AND org_id = ?", (webhook_id, org))
        db.commit()
        if res.rowcount == 0:
            raise HTTPException(status_code=404, detail="Webhook not found")

    return {"status": "deleted", "id": webhook_id}


@router.post("/{webhook_id}/test")
def test_webhook(webhook_id: int, principal: Principal = Depends(MANAGE)) -> Dict[str, Any]:
    org = principal.org_id
    with get_db() as db:
        row = db.execute("SELECT * FROM outbound_webhooks WHERE id = ? AND org_id = ?", (webhook_id, org)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        url = row["url"]
        secret = row["secret"]

    test_payload = {
        "event": "test.ping",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "org_id": org,
        "data": {
            "message": "Hello from AgencyBD Enterprise Webhook Dispatcher",
            "deal": {"company": "Acme Corp", "value_usd": 15000, "status": "won"}
        }
    }
    body_bytes = json.dumps(test_payload).encode("utf-8")
    sig = _sign_payload(secret, body_bytes)

    t0 = time.time()
    status_code = None
    err = None
    headers = {
        "Content-Type": "application/json",
        "X-AgencyBD-Signature": sig,
        "X-AgencyBD-Event": "test.ping",
        "User-Agent": "AgencyBD-Webhook-Dispatcher/2.4"
    }
    try:
        res = SafeFetcher.safe_fetch(
            url,
            method="POST",
            json_body=test_payload,
            headers=headers,
            timeout=5
        )
        status_code = res.status_code
    except Exception as e:
        status_code = getattr(e, "status_code", 500)
        err = str(e)[:200]

    ms = int((time.time() - t0) * 1000)

    with get_db() as db:
        db.execute(
            "UPDATE outbound_webhooks SET last_delivered_at = CURRENT_TIMESTAMP, last_status_code = ?, last_error = ? WHERE id = ?",
            (status_code, err, webhook_id)
        )
        db.commit()

    return {
        "status": "delivered" if (status_code and status_code < 400) else "error",
        "status_code": status_code,
        "latency_ms": ms,
        "error": err
    }
