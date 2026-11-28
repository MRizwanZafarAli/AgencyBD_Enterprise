"""Dual Alert & Wake-Up Escalation Engine (Twilio WhatsApp/Voice, Meta WhatsApp Cloud, Telegram)."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as xml_escape

from database.db import get_db
from net.fetcher import SafeFetcher

PROVIDERS = ("twilio", "meta_whatsapp", "telegram")


def _mask_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in (cfg or {}).items():
        if any(s in k.lower() for s in ("token", "secret", "auth")) and isinstance(v, str) and v:
            out[k] = f"•••••{v[-4:]}" if len(v) > 4 else "•••••"
        else:
            out[k] = v
    return out


def get_provider_settings(org_id: str, mask_secrets: bool = True) -> Dict[str, Any]:
    with get_db() as db:
        rows = db.execute(
            "SELECT provider, enabled, config_json FROM alert_provider_settings WHERE org_id = ?",
            (org_id,),
        ).fetchall()
    res: Dict[str, Any] = {p: {"enabled": False, "config": {}} for p in PROVIDERS}
    for r in rows:
        try:
            cfg = json.loads(r["config_json"] or "{}")
        except Exception:
            cfg = {}
        res[r["provider"]] = {
            "enabled": bool(r["enabled"]),
            "config": _mask_config(cfg) if mask_secrets else cfg,
        }
    return res


def save_provider_settings(org_id: str, provider: str, enabled: bool, config: Dict[str, Any]) -> Dict[str, Any]:
    if provider not in PROVIDERS:
        raise ValueError(f"provider must be one of {PROVIDERS}")
    with get_db() as db:
        existing = db.execute(
            "SELECT config_json FROM alert_provider_settings WHERE org_id = ? AND provider = ?",
            (org_id, provider),
        ).fetchone()
        prev_cfg = json.loads(existing["config_json"] or "{}") if existing else {}
        merged = {**prev_cfg}
        for k, v in (config or {}).items():
            # Preserve existing secret if UI sent masked value back
            if isinstance(v, str) and (v.startswith("•") or "..." in v) and k in prev_cfg:
                continue
            merged[k] = v
        db.execute(
            """INSERT INTO alert_provider_settings (org_id, provider, enabled, config_json, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(org_id, provider) DO UPDATE SET
                 enabled = excluded.enabled,
                 config_json = excluded.config_json,
                 updated_at = CURRENT_TIMESTAMP""",
            (org_id, provider, 1 if enabled else 0, json.dumps(merged)),
        )
        db.commit()
    return get_provider_settings(org_id, mask_secrets=True)[provider]


def get_escalation_schedule(org_id: str) -> Dict[str, Any]:
    with get_db() as db:
        row = db.execute("SELECT * FROM escalation_schedules WHERE org_id = ?", (org_id,)).fetchone()
    if not row:
        return {
            "org_id": org_id,
            "mode": "solo",
            "primary_rep_name": "",
            "primary_whatsapp": "",
            "primary_phone": "",
            "primary_telegram_chat_id": "",
            "backup_rep_name": "",
            "backup_whatsapp": "",
            "backup_phone": "",
            "voice_call_delay_sec": 120,
            "backup_escalate_sec": 300,
            "quiet_hours_override": True,
        }
    d = dict(row)
    d["quiet_hours_override"] = bool(d.get("quiet_hours_override"))
    return d


def save_escalation_schedule(org_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    mode = data.get("mode") or "solo"
    if mode not in ("solo", "agency_shifts"):
        raise ValueError("mode must be 'solo' or 'agency_shifts'")
    with get_db() as db:
        db.execute(
            """INSERT INTO escalation_schedules (
                 org_id, mode, primary_rep_name, primary_whatsapp, primary_phone, primary_telegram_chat_id,
                 backup_rep_name, backup_whatsapp, backup_phone, voice_call_delay_sec, backup_escalate_sec, quiet_hours_override, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(org_id) DO UPDATE SET
                 mode = excluded.mode,
                 primary_rep_name = excluded.primary_rep_name,
                 primary_whatsapp = excluded.primary_whatsapp,
                 primary_phone = excluded.primary_phone,
                 primary_telegram_chat_id = excluded.primary_telegram_chat_id,
                 backup_rep_name = excluded.backup_rep_name,
                 backup_whatsapp = excluded.backup_whatsapp,
                 backup_phone = excluded.backup_phone,
                 voice_call_delay_sec = excluded.voice_call_delay_sec,
                 backup_escalate_sec = excluded.backup_escalate_sec,
                 quiet_hours_override = excluded.quiet_hours_override,
                 updated_at = CURRENT_TIMESTAMP""",
            (
                org_id,
                mode,
                (data.get("primary_rep_name") or "").strip(),
                (data.get("primary_whatsapp") or "").strip(),
                (data.get("primary_phone") or "").strip(),
                (data.get("primary_telegram_chat_id") or "").strip(),
                (data.get("backup_rep_name") or "").strip(),
                (data.get("backup_whatsapp") or "").strip(),
                (data.get("backup_phone") or "").strip(),
                max(30, int(data.get("voice_call_delay_sec") or 120)),
                max(60, int(data.get("backup_escalate_sec") or 300)),
                1 if data.get("quiet_hours_override", True) else 0,
            ),
        )
        db.commit()
    return get_escalation_schedule(org_id)


def _send_telegram(cfg: Dict[str, Any], chat_id: str, text: str, event_id: Optional[int] = None) -> Dict[str, Any]:
    token = (cfg.get("bot_token") or "").strip()
    target = (chat_id or cfg.get("chat_id") or "").strip()
    if not token or not target:
        return {"ok": False, "detail": "Telegram bot_token and chat_id required"}
    payload: Dict[str, Any] = {"chat_id": target, "text": text}
    if event_id is not None:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "✅ I'm on it (Stop Call)", "callback_data": f"ack:{event_id}"}]]
        }
    res = SafeFetcher.safe_post(f"https://api.telegram.org/bot{token}/sendMessage", json_body=payload, timeout=8)
    return {"ok": res.status_code == 200, "status_code": res.status_code}


def _send_meta_whatsapp(cfg: Dict[str, Any], to_number: str, text: str) -> Dict[str, Any]:
    token = (cfg.get("access_token") or "").strip()
    phone_id = (cfg.get("phone_number_id") or "").strip()
    target = (to_number or "").strip().lstrip("+")
    if not token or not phone_id or not target:
        return {"ok": False, "detail": "Meta phone_number_id, access_token, and recipient phone required"}
    res = SafeFetcher.safe_post(
        f"https://graph.facebook.com/v21.0/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json_body={"messaging_product": "whatsapp", "to": target, "type": "text", "text": {"body": text}},
        timeout=8,
    )
    return {"ok": 200 <= res.status_code < 300, "status_code": res.status_code}


def _send_twilio_whatsapp(cfg: Dict[str, Any], to_whatsapp: str, text: str) -> Dict[str, Any]:
    sid = (cfg.get("account_sid") or "").strip()
    tok = (cfg.get("auth_token") or "").strip()
    frm = (cfg.get("whatsapp_from") or "").strip()
    if not sid or not tok or not frm or not to_whatsapp:
        return {"ok": False, "detail": "Twilio account_sid, auth_token, whatsapp_from, and target required"}
    to_val = to_whatsapp if to_whatsapp.startswith("whatsapp:") else f"whatsapp:{to_whatsapp}"
    frm_val = frm if frm.startswith("whatsapp:") else f"whatsapp:{frm}"
    res = SafeFetcher.safe_post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        auth=(sid, tok),
        form_body={"From": frm_val, "To": to_val, "Body": text},
        timeout=8,
    )
    return {"ok": 200 <= res.status_code < 300, "status_code": res.status_code}


def _send_twilio_voice(cfg: Dict[str, Any], to_phone: str, speech: str) -> Dict[str, Any]:
    sid = (cfg.get("account_sid") or "").strip()
    tok = (cfg.get("auth_token") or "").strip()
    frm = (cfg.get("voice_from") or "").strip()
    if not sid or not tok or not frm or not to_phone:
        return {"ok": False, "detail": "Twilio account_sid, auth_token, voice_from, and target phone required"}
    twiml = f"<Response><Say voice='alice'>{xml_escape(speech)}</Say></Response>"
    res = SafeFetcher.safe_post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
        auth=(sid, tok),
        form_body={"From": frm, "To": to_phone, "Twiml": twiml},
        timeout=8,
    )
    return {"ok": 200 <= res.status_code < 300, "status_code": res.status_code, "twiml": twiml}


def trigger_initial_alert(event_id: int, org_id: str) -> Dict[str, Any]:
    """Second 0: fires WhatsApp + Telegram alert with buyer snippet, AI reply, and deep link."""
    with get_db() as db:
        ev = db.execute("SELECT * FROM marketplace_events WHERE id = ? AND org_id = ?", (event_id, org_id)).fetchone()
    if not ev:
        return {"ok": False, "detail": "Event not found"}
    ev_d = dict(ev)
    providers = get_provider_settings(org_id, mask_secrets=False)
    sched = get_escalation_schedule(org_id)

    msg = (
        f"🔥 [{ev_d['platform'].upper()}] New message from {ev_d['buyer_name']}\n"
        f"\"{ev_d['snippet'][:180]}\"\n\n"
        f"💡 AI Reply:\n{ev_d['ai_draft_reply']}\n\n"
        f"🔗 Open: {ev_d['deep_link']}\n"
        f"Reply ACK {event_id} to stop wake-up call."
    )
    results: Dict[str, Any] = {}
    if providers["telegram"]["enabled"]:
        results["telegram"] = _send_telegram(providers["telegram"]["config"], sched.get("primary_telegram_chat_id", ""), msg, event_id=event_id)
    if providers["meta_whatsapp"]["enabled"] and sched.get("primary_whatsapp"):
        results["meta_whatsapp"] = _send_meta_whatsapp(providers["meta_whatsapp"]["config"], sched["primary_whatsapp"], msg)
    if providers["twilio"]["enabled"] and sched.get("primary_whatsapp"):
        results["twilio_whatsapp"] = _send_twilio_whatsapp(providers["twilio"]["config"], sched["primary_whatsapp"], msg)
    return {"ok": True, "dispatched": results}


def tick_escalations(org_id: Optional[str] = None) -> Dict[str, Any]:
    """Escalation ticker: Stage 0->1 (Minute 2 voice call), Stage 1->2 (Minute 5 agency backup)."""
    now = datetime.now(timezone.utc)
    with get_db() as db:
        q = "SELECT * FROM marketplace_events WHERE status = 'pending'"
        params: List[Any] = []
        if org_id:
            q += " AND org_id = ?"
            params.append(org_id)
        rows = [dict(r) for r in db.execute(q, params).fetchall()]

    voice_calls = 0
    backup_escalations = 0
    for ev in rows:
        oid = ev["org_id"]
        sched = get_escalation_schedule(oid)
        providers = get_provider_settings(oid, mask_secrets=False)
        try:
            created = datetime.fromisoformat(str(ev["created_at"]).replace(" ", "T").replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_sec = (now - created).total_seconds()
        except Exception:
            age_sec = 0

        if ev["escalation_stage"] == 0 and age_sec >= sched["voice_call_delay_sec"]:
            # Atomic lock BEFORE firing voice call so overlapping tickers cannot double-call
            with get_db() as db:
                cur = db.execute(
                    "UPDATE marketplace_events SET escalation_stage = 1 WHERE id = ? AND status = 'pending' AND escalation_stage = 0",
                    (ev["id"],),
                )
                db.commit()
            if cur.rowcount == 1:
                if providers["twilio"]["enabled"] and sched.get("primary_phone"):
                    speech = f"Urgent {ev['platform']} inquiry from {ev['buyer_name']}. Check WhatsApp or Telegram now for your pre-written reply."
                    _send_twilio_voice(providers["twilio"]["config"], sched["primary_phone"], speech)
                voice_calls += 1

        elif ev["escalation_stage"] == 1 and sched["mode"] == "agency_shifts" and age_sec >= sched["backup_escalate_sec"]:
            # Atomic lock BEFORE firing backup escalation
            with get_db() as db:
                cur = db.execute(
                    "UPDATE marketplace_events SET escalation_stage = 2, status = 'escalated' WHERE id = ? AND status = 'pending' AND escalation_stage = 1",
                    (ev["id"],),
                )
                db.commit()
            if cur.rowcount == 1:
                backup_msg = f"🚨 ESCALATED ({ev['platform'].upper()}): {ev['buyer_name']} waiting >{sched['backup_escalate_sec']}s!\n{ev['snippet'][:140]}\n{ev['deep_link']}"
                if providers["twilio"]["enabled"]:
                    if sched.get("backup_whatsapp"):
                        _send_twilio_whatsapp(providers["twilio"]["config"], sched["backup_whatsapp"], backup_msg)
                    if sched.get("backup_phone"):
                        _send_twilio_voice(providers["twilio"]["config"], sched["backup_phone"], f"Escalated {ev['platform']} inquiry from {ev['buyer_name']}. Primary rep did not respond.")
                if providers["meta_whatsapp"]["enabled"] and sched.get("backup_whatsapp"):
                    _send_meta_whatsapp(providers["meta_whatsapp"]["config"], sched["backup_whatsapp"], backup_msg)
                backup_escalations += 1

    return {"checked": len(rows), "voice_calls": voice_calls, "backup_escalations": backup_escalations}


def ack_event(org_id: str, event_id: int, ack_by: str) -> Optional[Dict[str, Any]]:
    with get_db() as db:
        cur = db.execute(
            "UPDATE marketplace_events SET status = 'acknowledged', acknowledged_by = ?, acknowledged_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND org_id = ?",
            (ack_by, event_id, org_id),
        )
        db.commit()
        if not cur.rowcount:
            return None
        return dict(db.execute("SELECT * FROM marketplace_events WHERE id = ?", (event_id,)).fetchone())


def send_test_alert(org_id: str, provider: str) -> Dict[str, Any]:
    providers = get_provider_settings(org_id, mask_secrets=False)
    sched = get_escalation_schedule(org_id)
    text = "Test from AgencyBD Wake-Up Engine: your urgent marketplace alerts reach you here."
    if provider == "telegram":
        return _send_telegram(providers["telegram"]["config"], sched.get("primary_telegram_chat_id", ""), text)
    if provider == "meta_whatsapp":
        return _send_meta_whatsapp(providers["meta_whatsapp"]["config"], sched.get("primary_whatsapp", ""), text)
    if provider == "twilio_whatsapp":
        return _send_twilio_whatsapp(providers["twilio"]["config"], sched.get("primary_whatsapp", ""), text)
    if provider == "twilio_voice":
        return _send_twilio_voice(providers["twilio"]["config"], sched.get("primary_phone", ""), text)
    raise ValueError("provider must be telegram, meta_whatsapp, twilio_whatsapp, or twilio_voice")
