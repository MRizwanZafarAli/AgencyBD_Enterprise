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
