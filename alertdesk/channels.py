"""Where alerts go. Every channel returns (ok, detail) and never raises; no secret is ever put in a detail, a log line or an API response.

Free and official first: Telegram (Bot API) and ntfy. WhatsApp uses Meta's own Cloud API, which has had a free allowance but changed its pricing in
October 2026, so it is optional and the message says so. A phone call uses Twilio, whose trial can only call a number you verified; it is off unless configured."""

import base64
import json
import os
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote
from xml.sax.saxutils import escape

from net.fetcher import SafeFetcher

Result = Tuple[bool, str]
E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _post(url: str, headers: Optional[Dict[str, str]] = None, json_body: Any = None, form: Optional[Dict[str, str]] = None, timeout: int = 20):
    return SafeFetcher.safe_fetch(url, timeout=timeout, headers=headers, method="POST", json_body=json_body, form_body=form, max_bytes=200_000)


def _get(url: str, timeout: int = 20):
    return SafeFetcher.safe_fetch(url, timeout=timeout, max_bytes=500_000)


# ------------------------------------------------------------------ Telegram (free, official)

def telegram_configured(cfg: Dict[str, Any]) -> bool:
    return bool(_env("TELEGRAM_BOT_TOKEN") and str(cfg.get("chat_id") or "").strip())


def send_telegram(cfg: Dict[str, Any], text: str, message_id: Optional[int] = None) -> Result:
    if not telegram_configured(cfg):
        return False, "Telegram is not set up (a bot token and your chat ID are needed)."
    body: Dict[str, Any] = {"chat_id": str(cfg["chat_id"]), "text": text[:3900], "disable_web_page_preview": True}
    if message_id:
        body["reply_markup"] = {"inline_keyboard": [[{"text": "I'm on it ✓", "callback_data": f"ack:{message_id}"}]]}
    try:
        r = _post(f"https://api.telegram.org/bot{_env('TELEGRAM_BOT_TOKEN')}/sendMessage", json_body=body)
    except Exception as exc:
        return False, f"Could not reach Telegram: {type(exc).__name__}"
    if r.status_code == 200:
        return True, "Sent to Telegram."
    if r.status_code in (400, 403):
        return False, "Telegram refused it. Send your bot any message first, and check the chat ID."
    if r.status_code == 401:
        return False, "Telegram rejected the bot token."
    return False, f"Telegram answered HTTP {r.status_code}."


def telegram_updates(offset: int) -> Tuple[list, int]:
    """Replies and button taps since `offset`. Returns (updates, next_offset). Empty on any problem."""
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        return [], offset
    try:
        r = _get(f"https://api.telegram.org/bot{token}/getUpdates?offset={int(offset)}&timeout=0&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D")
        data = json.loads(r.text) if r.status_code == 200 else {}
    except Exception:
        return [], offset
    updates = data.get("result", []) if isinstance(data, dict) else []
    return updates, (max(u["update_id"] for u in updates) + 1 if updates else offset)


def telegram_answer_callback(callback_id: str, text: str = "Noted") -> None:
    token = _env("TELEGRAM_BOT_TOKEN")
    if token and callback_id:
        try:
            _post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json_body={"callback_query_id": callback_id, "text": text})
        except Exception:
            pass


# ------------------------------------------------------------------ ntfy (free, no account)

def ntfy_configured(cfg: Dict[str, Any]) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{8,64}", str(cfg.get("topic") or "")))


def send_ntfy(cfg: Dict[str, Any], text: str, title: str = "AgencyBD", urgent: bool = False) -> Result:
    if not ntfy_configured(cfg):
        return False, "ntfy is not set up (a hard-to-guess topic name of 8+ letters or digits is needed)."
    server = str(cfg.get("server") or "https://ntfy.sh").rstrip("/")
    headers = {"Title": title[:80], "Priority": "5" if urgent else "4", "Tags": "incoming_envelope", "Content-Type": "text/plain; charset=utf-8"}
    try:
        r = SafeFetcher.safe_fetch(f"{server}/{quote(str(cfg['topic']))}", timeout=20, method="POST", max_bytes=100_000, headers=headers,
                                   form_body=text[:3900].encode("utf-8"))                       # type: ignore[arg-type]  (requests accepts a raw body here)
    except Exception as exc:
        return False, f"Could not reach ntfy: {type(exc).__name__}"
    return (True, "Sent to ntfy.") if r.status_code == 200 else (False, f"ntfy answered HTTP {r.status_code}.")


# ------------------------------------------------------------------ WhatsApp (Meta Cloud API, official)

def whatsapp_configured(cfg: Dict[str, Any]) -> bool:
    return bool(_env("WHATSAPP_CLOUD_TOKEN") and _env("WHATSAPP_PHONE_NUMBER_ID") and E164.match(str(cfg.get("to") or "")))


def send_whatsapp(cfg: Dict[str, Any], text: str) -> Result:
    if not whatsapp_configured(cfg):
        return False, "WhatsApp is not set up (a Cloud API token, a phone number ID and your number in +923001234567 form are needed)."
    try:
        r = _post(f"https://graph.facebook.com/v21.0/{_env('WHATSAPP_PHONE_NUMBER_ID')}/messages", headers={"Authorization": f"Bearer {_env('WHATSAPP_CLOUD_TOKEN')}"},
                  json_body={"messaging_product": "whatsapp", "to": str(cfg["to"]).lstrip("+"), "type": "text", "text": {"preview_url": False, "body": text[:3900]}})
    except Exception as exc:
        return False, f"Could not reach WhatsApp: {type(exc).__name__}"
    if r.status_code == 200:
        return True, "Sent to WhatsApp."
    if r.status_code in (401, 403):
        return False, "WhatsApp rejected the token."
    try:
        code = (json.loads(r.text).get("error") or {}).get("code")
    except Exception:
        code = None
    if code == 131047:
        return False, "WhatsApp only allows free-form messages within 24 hours of you writing to the business number. Send it a message, then try again."
    return False, f"WhatsApp answered HTTP {r.status_code}" + (f" (error {code})." if code else ".")


# ------------------------------------------------------------------ phone call (Twilio)

def call_configured(cfg: Dict[str, Any]) -> bool:
    return bool(_env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN") and E164.match(_env("TWILIO_FROM_NUMBER")) and E164.match(str(cfg.get("to") or "")))


def place_call(cfg: Dict[str, Any], speech: str) -> Result:
    """Rings you and reads `speech` aloud. On a Twilio trial the number must be one you verified there, and a trial call opens with Twilio's own notice."""
    if not call_configured(cfg):
        return False, "Phone calls are not set up (Twilio account SID, auth token, a Twilio number, and your number in +923001234567 form)."
    sid = _env("TWILIO_ACCOUNT_SID")
    auth = base64.b64encode(f"{sid}:{_env('TWILIO_AUTH_TOKEN')}".encode()).decode()
    twiml = f'<Response><Say voice="Polly.Joanna" language="en-US">{escape(speech[:600])}</Say><Pause length="1"/><Say voice="Polly.Joanna">I will repeat. {escape(speech[:300])}</Say></Response>'
    try:
        r = _post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json", headers={"Authorization": f"Basic {auth}"},
                  form={"To": str(cfg["to"]), "From": _env("TWILIO_FROM_NUMBER"), "Twiml": twiml})
    except Exception as exc:
        return False, f"Could not reach Twilio: {type(exc).__name__}"
    if r.status_code in (200, 201):
        return True, "Calling you now."
    try:
        msg = (json.loads(r.text) or {}).get("message", "")
    except Exception:
        msg = ""
    msg = re.sub(r"(AC[0-9a-f]{20,}|[0-9a-f]{32})", "…", msg)[:160]
    return False, f"Twilio refused the call (HTTP {r.status_code}). {msg}".strip()


def configured_channels(channels: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
    return {"telegram": telegram_configured(channels.get("telegram", {})), "ntfy": ntfy_configured(channels.get("ntfy", {})),
            "whatsapp": whatsapp_configured(channels.get("whatsapp", {})), "call": call_configured(channels.get("call", {}))}
