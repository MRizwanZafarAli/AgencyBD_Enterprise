"""Alert Desk API: settings, detected client messages, tests. Secrets (mailbox password, bot tokens) live in Settings > Integrations and are never returned."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from alertdesk import channels, engine, mailwatch
from alertdesk.parsers import PLATFORM_LABEL
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/alerts", tags=["Alert Desk"])
READ = require_permission("leads:read")
WRITE = require_permission("leads:write")
MANAGE = require_permission("apikeys:manage")                     # destinations and secrets for the whole installation: super-admin only


class MessageBody(BaseModel):
    platform: str = "other"
    sender: str = Field(..., min_length=1, max_length=120)
    text: str = Field(..., min_length=1, max_length=2000)
    url: Optional[str] = Field(None, max_length=500)


class PauseBody(BaseModel):
    minutes: Optional[int] = Field(None, ge=1, le=10080)           # null resumes


def _guard(fn, *a):
    try:
        return fn(*a)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/settings")
def get_settings(principal: Principal = Depends(READ)) -> Dict[str, Any]:
    return {"settings": engine.get_settings(principal.org_id), "status": engine.status(principal.org_id), "can_edit": principal.role == "super_admin",
            "platforms": {k: PLATFORM_LABEL[k] for k in PLATFORM_LABEL if k != "other"}, "channels": list(engine.CHANNELS)}


@router.put("/settings")
def put_settings(body: Dict[str, Any], principal: Principal = Depends(MANAGE)):
    return {"settings": _guard(engine.save_settings, principal.org_id, body), "status": engine.status(principal.org_id)}


@router.post("/pause")
def pause(body: PauseBody, principal: Principal = Depends(MANAGE)):
    return {"settings": engine.pause(principal.org_id, body.minutes), "status": engine.status(principal.org_id)}


@router.get("/messages")
def messages(status: Optional[str] = None, principal: Principal = Depends(READ)):
    if status not in (None, "new", "acknowledged", "dismissed"):
        raise HTTPException(status_code=422, detail="status must be new, acknowledged or dismissed")
    return {"messages": engine.list_messages(principal.org_id, status), "status": engine.status(principal.org_id)}


@router.post("/messages")
def add_message(body: MessageBody, principal: Principal = Depends(WRITE)):
    """For a platform that does not email you, or to try the whole ladder. It is escalated exactly like a detected message."""
    if body.platform not in PLATFORM_LABEL:
        raise HTTPException(status_code=422, detail="Unknown platform.")
    if body.url and not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="The link must start with http:// or https://")
    return engine.ingest(principal.org_id, body.platform, body.sender, body.text, url=body.url, origin="manual")


@router.get("/messages/{message_id}/replies")
def reply_drafts(message_id: int, principal: Principal = Depends(READ)):
    from alertdesk import reply
    try:
        return reply.drafts(principal.org_id, message_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Message not found")


@router.post("/messages/{message_id}/ack")
def ack(message_id: int, principal: Principal = Depends(WRITE)):
    if not engine.set_status(principal.org_id, message_id, "acknowledged", f"app ({principal.user_id})"):
        raise HTTPException(status_code=404, detail="No waiting message with that id.")
    return {"acknowledged": message_id}


@router.post("/messages/{message_id}/dismiss")
def dismiss(message_id: int, principal: Principal = Depends(WRITE)):
    if not engine.set_status(principal.org_id, message_id, "dismissed", f"app ({principal.user_id})"):
        raise HTTPException(status_code=404, detail="No waiting message with that id.")
    return {"dismissed": message_id}


@router.post("/test/{channel}")
def test_channel(channel: str, principal: Principal = Depends(MANAGE)):
    """Sends one real test through the channel. A phone test places a real call, which can use trial minutes or cost money."""
    if channel not in engine.CHANNELS:
        raise HTTPException(status_code=404, detail="Unknown channel.")
    conf = engine.get_settings(principal.org_id)["channels"]
    text = "Test from AgencyBD: your alerts reach you here."
    if channel == "telegram":
        ok, detail = channels.send_telegram(conf["telegram"], text)
    elif channel == "ntfy":
        ok, detail = channels.send_ntfy(conf["ntfy"], text, title="AgencyBD test")
    elif channel == "whatsapp":
        ok, detail = channels.send_whatsapp(conf["whatsapp"], text)
    else:
        ok, detail = channels.place_call(conf["call"], "This is a test call from AgencyBD. Your phone alerts are working.")
    return {"ok": ok, "detail": detail}


@router.post("/mail/test")
def mail_test(principal: Principal = Depends(MANAGE)):
    """Shows how your latest platform emails would be read, without storing or changing anything."""
    cfg = engine.get_settings(principal.org_id)
    return mailwatch.preview(extra_senders=cfg["watch"]["extra_senders"])


class ProviderConfigBody(BaseModel):
    provider: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    schedule: Optional[Dict[str, Any]] = None


class WakeupTestBody(BaseModel):
    provider: str = "telegram"


class IngestMarketplaceBody(BaseModel):
    from_email: str
    subject: str
    body: str = ""
    external_msg_id: Optional[str] = None
    platform_override: Optional[str] = None


@router.get("/providers")
def get_alert_providers(principal: Principal = Depends(READ)):
    from workflows import alert_dispatcher as ad
    return {
        "providers": ad.get_provider_settings(principal.org_id, mask_secrets=True),
        "schedule": ad.get_escalation_schedule(principal.org_id),
        "can_edit": principal.role == "super_admin",
    }


@router.post("/providers")
def save_alert_providers(body: ProviderConfigBody, principal: Principal = Depends(MANAGE)):
    from workflows import alert_dispatcher as ad
    out: Dict[str, Any] = {}
    if body.provider:
        out["provider"] = _guard(
            ad.save_provider_settings,
            principal.org_id,
            body.provider,
            bool(body.enabled),
            body.config or {},
        )
    if body.schedule is not None:
        out["schedule"] = _guard(ad.save_escalation_schedule, principal.org_id, body.schedule)
    out["providers"] = ad.get_provider_settings(principal.org_id, mask_secrets=True)
    return out


@router.post("/wakeup-test")
def wakeup_test(body: WakeupTestBody, principal: Principal = Depends(MANAGE)):
    from workflows import alert_dispatcher as ad
    return _guard(ad.send_test_alert, principal.org_id, body.provider)


@router.get("/events")
def list_marketplace_events(status: Optional[str] = None, principal: Principal = Depends(READ)):
    import json
    from database.db import get_db
    with get_db() as db:
        if status:
            rows = db.execute(
                "SELECT * FROM marketplace_events WHERE org_id = ? AND status = ? ORDER BY id DESC LIMIT 50",
                (principal.org_id, status),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM marketplace_events WHERE org_id = ? ORDER BY id DESC LIMIT 50",
                (principal.org_id,),
            ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["compliance_warnings"] = json.loads(d.get("compliance_warnings") or "[]")
        except Exception:
            d["compliance_warnings"] = []
        out.append(d)
    return {"events": out}


@router.post("/events/ingest")
def ingest_marketplace_event(body: IngestMarketplaceBody, principal: Principal = Depends(WRITE)):
    import uuid
    from workflows.marketplace_ingestor import ingest_marketplace_email
    ext_id = body.external_msg_id or f"manual-{uuid.uuid4().hex}"
    res = ingest_marketplace_email(
        principal.org_id,
        body.from_email,
        body.subject,
        body.body,
        ext_id,
        platform_override=body.platform_override,
    )
    if not res:
        raise HTTPException(status_code=422, detail="Sender did not match any built-in or custom channel rule.")
    return res


@router.post("/events/{event_id}/ack")
def ack_marketplace_event(event_id: int, principal: Principal = Depends(WRITE)):
    from workflows.alert_dispatcher import ack_event
    ev = ack_event(principal.org_id, event_id, f"app ({principal.user_id})")
    if not ev:
        raise HTTPException(status_code=404, detail="Marketplace event not found.")
    return {"ok": True, "event": ev}


@router.post("/events/tick")
def tick_marketplace_escalations(principal: Principal = Depends(WRITE)):
    from workflows.alert_dispatcher import tick_escalations
    return tick_escalations(principal.org_id)


@router.post("/webhooks/telegram")
def telegram_ack_webhook(payload: Dict[str, Any]):
    """Receives Telegram inline keyboard callback ('ack:{id}') to stop Minute 2 wake-up calls."""
    from database.db import get_db
    from workflows.alert_dispatcher import ack_event
    cb = payload.get("callback_query") or {}
    data = str(cb.get("data") or "")
    if data.startswith("ack:"):
        try:
            ev_id = int(data.split(":", 1)[1])
            with get_db() as db:
                row = db.execute("SELECT org_id FROM marketplace_events WHERE id = ?", (ev_id,)).fetchone()
            if row:
                ack_event(row["org_id"], ev_id, "telegram")
                return {"ok": True, "acknowledged": ev_id}
        except Exception:
            pass
    return {"ok": True}


@router.post("/webhooks/twilio")
def twilio_ack_webhook(payload: Dict[str, Any]):
    """Receives Twilio WhatsApp reply ('ACK {id}') to stop wake-up calls."""
    from database.db import get_db
    from workflows.alert_dispatcher import ack_event
    body = str(payload.get("Body") or "").strip().upper()
    if body.startswith("ACK"):
        parts = body.split()
        if len(parts) >= 2 and parts[1].isdigit():
            ev_id = int(parts[1])
            with get_db() as db:
                row = db.execute("SELECT org_id FROM marketplace_events WHERE id = ?", (ev_id,)).fetchone()
            if row:
                ack_event(row["org_id"], ev_id, "twilio_whatsapp")
                return {"ok": True, "acknowledged": ev_id}
    return {"ok": True}
