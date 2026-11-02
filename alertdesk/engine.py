"""Settings, schedule, ingestion and the escalation ladder.

A client message is a row. Each step of your escalation plan (for example Telegram now, WhatsApp after 5 minutes, a phone call after 15) is tried once
it is due, inside your working window, until you acknowledge the message. Everything is stored in the database, so a restart loses nothing, and a
step that came due while the app was off sends only the most recent one instead of a burst.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from alertdesk import channels
from alertdesk.parsers import PLATFORM_DOMAINS, PLATFORM_LABEL
from database.db import get_db

logger = logging.getLogger("AgencyBD.alertdesk")
FMT = "%Y-%m-%d %H:%M:%S"
CHANNELS = ("telegram", "ntfy", "whatsapp", "call")
MAX_STEPS = 10
MAX_TRIES = 3
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "timezone": "Asia/Karachi",
    "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "start": "00:00", "end": "23:59", "off_hours": "hold"},
    "quiet_hours": {"enabled": False, "start": "23:00", "end": "07:00"},
    "steps": [{"after_minutes": 0, "channel": "telegram"}, {"after_minutes": 5, "channel": "whatsapp"}, {"after_minutes": 15, "channel": "call"}],
    "channels": {"telegram": {"chat_id": ""}, "ntfy": {"topic": "", "server": "https://ntfy.sh"}, "whatsapp": {"to": ""}, "call": {"to": ""}},
    "watch": {"platforms": list(PLATFORM_DOMAINS), "extra_senders": [], "poll_seconds": 60},
    "ai_summary": False,
    "paused_until": None,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(FMT)


def _parse(s: str) -> datetime:
    return datetime.strptime(s, FMT).replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ settings

def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _tz(cfg: Dict[str, Any]) -> ZoneInfo:
    try:
        return ZoneInfo(cfg.get("timezone") or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def validate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Raises ValueError with a sentence a person can act on. Returns the normalised settings."""
    cfg = _merge(DEFAULTS, data or {})
    cfg["enabled"] = bool(cfg["enabled"])
    try:
        ZoneInfo(cfg["timezone"])
    except Exception:
        raise ValueError("Time zone must be a name such as Asia/Karachi or Europe/London.")
    s = cfg["schedule"]
    days = s.get("days")
    if not isinstance(days, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in days) or (cfg["enabled"] and not days):
        raise ValueError("Pick at least one working day (0 is Monday, 6 is Sunday).")
    s["days"] = sorted(set(days))
    for label, block in (("working hours", s), ("quiet hours", cfg["quiet_hours"])):
        if not HHMM.match(str(block.get("start", ""))) or not HHMM.match(str(block.get("end", ""))):
            raise ValueError(f"Times for {label} must look like 09:00.")
    if s.get("off_hours") not in ("hold", "first_only"):
        raise ValueError("Outside working hours either hold alerts until you are back, or send only the first alert.")
    cfg["quiet_hours"]["enabled"] = bool(cfg["quiet_hours"].get("enabled"))

    steps = cfg["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError(f"The escalation plan needs between 1 and {MAX_STEPS} steps.")
    clean = []
    for st in steps:
        try:
            after = int(st.get("after_minutes"))
        except (TypeError, ValueError, AttributeError):
            raise ValueError("Each step needs a number of minutes.")
        if not 0 <= after <= 1440:
            raise ValueError("A step can start between 0 minutes and 24 hours after the message.")
        if st.get("channel") not in CHANNELS:
            raise ValueError(f"A step's channel must be one of: {', '.join(CHANNELS)}.")
        clean.append({"after_minutes": after, "channel": st["channel"]})
    cfg["steps"] = sorted(clean, key=lambda x: x["after_minutes"])

    ch = cfg["channels"]
    chat = str(ch["telegram"].get("chat_id") or "").strip()
    if chat and not re.fullmatch(r"-?\d{3,20}", chat):
        raise ValueError("The Telegram chat ID is a number (it can start with a minus sign).")
    ch["telegram"]["chat_id"] = chat
    topic = str(ch["ntfy"].get("topic") or "").strip()
    if topic and not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", topic):
        raise ValueError("The ntfy topic must be 8 to 64 letters, digits, dashes or underscores. Make it hard to guess: anyone who knows it can read it.")
    ch["ntfy"]["topic"] = topic
    server = str(ch["ntfy"].get("server") or "https://ntfy.sh").strip().rstrip("/")
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d+)?", server):
        raise ValueError("The ntfy server must be an https address such as https://ntfy.sh.")
    ch["ntfy"]["server"] = server
    for name in ("whatsapp", "call"):
        num = re.sub(r"[\s()-]", "", str(ch[name].get("to") or ""))
        if num and not re.fullmatch(r"\+\d{8,15}", num):
            raise ValueError("Phone numbers use the international form, for example +923001234567.")
        ch[name]["to"] = num

    w = cfg["watch"]
    plats = w.get("platforms")
    if not isinstance(plats, list) or not set(plats) <= set(PLATFORM_DOMAINS):
        raise ValueError("Watch only platforms from the list.")
    extra = [str(x).strip().lower() for x in (w.get("extra_senders") or []) if str(x).strip()]
    if len(extra) > 10 or not all(re.fullmatch(r"[a-z0-9._+-]+@[a-z0-9.-]+\.[a-z]{2,}|[a-z0-9.-]+\.[a-z]{2,}", x) for x in extra):
        raise ValueError("Extra senders are up to 10 email addresses or domains.")
    w["extra_senders"] = extra
    w["poll_seconds"] = max(30, min(600, int(w.get("poll_seconds") or 60)))
    cfg["ai_summary"] = bool(cfg["ai_summary"])
    pu = cfg.get("paused_until")
    if pu:
        try:
            _parse(pu)
        except ValueError:
            raise ValueError("paused_until must be a UTC time like 2026-11-01 09:00:00.")
    return cfg


def get_settings(org_id: str) -> Dict[str, Any]:
    with get_db() as db:
        row = db.execute("SELECT data_json FROM alert_settings WHERE org_id = ?", (org_id,)).fetchone()
    return _merge(DEFAULTS, json.loads(row["data_json"])) if row else json.loads(json.dumps(DEFAULTS))


def save_settings(org_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    cfg = validate(data)
    with get_db() as db:
        db.execute("INSERT INTO alert_settings (org_id, data_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(org_id) DO UPDATE SET data_json = excluded.data_json, updated_at = CURRENT_TIMESTAMP",
                   (org_id, json.dumps(cfg)))
        db.commit()
    return cfg


def pause(org_id: str, minutes: Optional[int], now: Optional[datetime] = None) -> Dict[str, Any]:
    cfg = get_settings(org_id)
    cfg["paused_until"] = _fmt((now or utcnow()) + timedelta(minutes=minutes)) if minutes else None
    return save_settings(org_id, cfg)


# ------------------------------------------------------------------ schedule

def is_active(dt: datetime, cfg: Dict[str, Any]) -> bool:
    local = dt.astimezone(_tz(cfg))
    s = cfg["schedule"]
    if local.weekday() not in s["days"]:
        return False
    t, a, b = local.hour * 60 + local.minute, _minutes(s["start"]), _minutes(s["end"])
    return a <= t <= b if a <= b else (t >= a or t <= b)


def next_active(dt: datetime, cfg: Dict[str, Any]) -> datetime:
    """`dt` if you are working then, otherwise the first minute you are. Falls back to `dt` if the schedule never opens."""
    cur = dt
    for _ in range(8 * 24 * 60):
        if is_active(cur, cfg):
            return cur
        cur += timedelta(minutes=1)
    return dt


def in_quiet(dt: datetime, cfg: Dict[str, Any]) -> bool:
    q = cfg["quiet_hours"]
    if not q["enabled"]:
        return False
    local = dt.astimezone(_tz(cfg))
    t, a, b = local.hour * 60 + local.minute, _minutes(q["start"]), _minutes(q["end"])
    return a <= t < b if a <= b else (t >= a or t < b)


def after_quiet(dt: datetime, cfg: Dict[str, Any]) -> datetime:
    cur = dt
    for _ in range(24 * 60):
        if not in_quiet(cur, cfg):
            return cur
        cur += timedelta(minutes=1)
    return dt


def step_time(received: datetime, idx: int, step: Dict[str, Any], cfg: Dict[str, Any]) -> datetime:
    """When this step is due: after the message, but never outside your working hours, and never a phone call in quiet hours."""
    first_only = cfg["schedule"]["off_hours"] == "first_only"
    was_off = not is_active(received, cfg)
    base = received if not was_off else next_active(received, cfg)
    if was_off and first_only and idx == 0:
        return received
    when = base + timedelta(minutes=step["after_minutes"])
    if not is_active(when, cfg):
        when = next_active(when, cfg)
    if step["channel"] == "call" and in_quiet(when, cfg):
        when = after_quiet(when, cfg)
    return when


# ------------------------------------------------------------------ messages

def _row(r) -> Dict[str, Any]:
    return dict(r)


def ingest(org_id: str, platform: str, sender: str, preview: str, *, subject: str = "", url: Optional[str] = None, source_ref: Optional[str] = None,
           received_at: Optional[datetime] = None, kind: str = "message", origin: str = "email") -> Optional[Dict[str, Any]]:
    """Stores a client message. None if this exact email was already stored."""
    when = _fmt(received_at or utcnow())
    ref = source_ref or f"manual:{when}:{sender}:{(preview or '')[:40]}"
    with get_db() as db:
        try:
            cur = db.execute("INSERT INTO client_messages (org_id, platform, kind, sender, subject, preview, url, origin, source_ref, received_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (org_id, platform, kind, (sender or "")[:120], (subject or "")[:200], (preview or "")[:2000], url, origin, ref, when))
        except Exception:                                   # UNIQUE (org_id, source_ref)
            return None
        db.commit()
        return _row(db.execute("SELECT * FROM client_messages WHERE id = ?", (cur.lastrowid,)).fetchone())


def list_messages(org_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with get_db() as db:
        q, params = "SELECT * FROM client_messages WHERE org_id = ?", [org_id]
        if status:
            q, params = q + " AND status = ?", params + [status]
        rows = [_row(r) for r in db.execute(q + " ORDER BY id DESC LIMIT ?", params + [limit]).fetchall()]
        for r in rows:
            r["attempts"] = [dict(a) for a in db.execute("SELECT step_index, channel, status, detail, at FROM alert_attempts WHERE message_id = ? ORDER BY step_index", (r["id"],)).fetchall()]
    return rows


def set_status(org_id: str, message_id: int, status: str, via: str) -> bool:
    with get_db() as db:
        n = db.execute("UPDATE client_messages SET status = ?, acknowledged_at = ?, acknowledged_via = ? WHERE id = ? AND org_id = ? AND status = 'new'",
                       (status, _fmt(utcnow()), via, message_id, org_id)).rowcount
        db.commit()
    return n > 0


def ack_all(org_id: str, via: str) -> int:
    with get_db() as db:
        n = db.execute("UPDATE client_messages SET status = 'acknowledged', acknowledged_at = ?, acknowledged_via = ? WHERE org_id = ? AND status = 'new'", (_fmt(utcnow()), via, org_id)).rowcount
        db.commit()
    return n


def get_state(org_id: str, key: str, default: Optional[str] = None) -> Optional[str]:
    with get_db() as db:
        row = db.execute("SELECT value FROM alert_state WHERE org_id = ? AND key = ?", (org_id, key)).fetchone()
    return row["value"] if row else default


def set_state(org_id: str, key: str, value: Optional[str]) -> None:
    with get_db() as db:
        db.execute("INSERT INTO alert_state (org_id, key, value) VALUES (?, ?, ?) ON CONFLICT(org_id, key) DO UPDATE SET value = excluded.value", (org_id, key, value))
        db.commit()


# ------------------------------------------------------------------ wording

def _age(msg: Dict[str, Any], now: datetime) -> int:
    return max(0, int((now - _parse(msg["received_at"])).total_seconds() // 60))


def alert_text(msg: Dict[str, Any], idx: int, now: datetime) -> str:
    label = PLATFORM_LABEL.get(msg["platform"], msg["platform"])
    head = (f"New message on {label} from {msg['sender']}" if idx == 0 else f"Reminder: {msg['sender']} on {label} wrote {_age(msg, now)} min ago and is still waiting")
    body = (msg.get("preview") or msg.get("subject") or "(no text in the notification)").strip()
    tail = f"\n\nOpen: {msg['url']}" if msg.get("url") else ""
    return f"{head}\n\n{body}{tail}\n\nTap \"I'm on it\" (Telegram) or acknowledge it in AgencyBD to stop reminders."


def speech_text(msg: Dict[str, Any], cfg: Dict[str, Any], now: datetime) -> str:
    from config.settings import settings
    label = PLATFORM_LABEL.get(msg["platform"], msg["platform"])
    gist = (msg.get("preview") or msg.get("subject") or "").strip()
    if cfg.get("ai_summary") and gist:
        gist = _summarise(gist) or gist
    return f"Hello {settings.agency.founder_name.split()[0]}. {msg['sender']} messaged you on {label} {_age(msg, now)} minutes ago. {gist[:220]}. Please reply to them."


def _summarise(text: str) -> Optional[str]:
    """One short spoken sentence from the model, only if you configured one and switched this on. Falls back to the plain text on any problem."""
    try:
        from llm.client import LLMGateway
        if not LLMGateway.has_provider():
            return None
        out = LLMGateway.complete(f"Summarise this client message in one short spoken sentence (max 25 words). Do not add anything that is not in it.\n\n{text[:1500]}",
                                  system="You write one plain spoken sentence for a phone call.", max_tokens=80)
        t = (out.get("text") if isinstance(out, dict) else str(out or "")).strip()
        return t[:220] or None
    except Exception:
        return None


# ------------------------------------------------------------------ the ladder

def _attempts(db, message_id: int) -> Dict[int, Dict[str, Any]]:
    return {r["step_index"]: dict(r) for r in db.execute("SELECT * FROM alert_attempts WHERE message_id = ?", (message_id,)).fetchall()}


def run_steps(org_id: str, cfg: Dict[str, Any], now: datetime) -> List[Dict[str, Any]]:
    """Sends whatever is due for every unacknowledged message. Returns what it did."""
    done: List[Dict[str, Any]] = []
    paused = cfg.get("paused_until") and now < _parse(cfg["paused_until"])
    if paused:
        return done
    for msg in list_messages(org_id, "new", limit=100):
        with get_db() as db:
            tried = _attempts(db, msg["id"])
        received = _parse(msg["received_at"])
        due = []
        for idx, step in enumerate(cfg["steps"]):
            when = step_time(received, idx, step, cfg)
            prior = tried.get(idx)
            if now < when:
                continue
            if prior and (prior["status"] in ("sent", "skipped") or prior["tries"] >= MAX_TRIES or (now - _parse(prior["at"])).total_seconds() < 60):
                continue
            due.append((when, idx, step, prior))
        if not due:
            continue
        due.sort(key=lambda x: x[0])
        for _, idx, step, prior in due[:-1]:                           # several came due at once (the app was off): only the latest is sent
            if not prior:
                _record(org_id, msg["id"], idx, step["channel"], "skipped", "Superseded by a later step that was due at the same time.", 1, now)
        _, idx, step, prior = due[-1]
        done.append(_do_step(org_id, cfg, msg, idx, step, prior, now))
    return done


def _do_step(org_id: str, cfg: Dict[str, Any], msg: Dict[str, Any], idx: int, step: Dict[str, Any], prior: Optional[Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    ch, conf = step["channel"], cfg["channels"]
    text = alert_text(msg, idx, now)
    if ch == "telegram":
        ok, detail = channels.send_telegram(conf["telegram"], text, msg["id"])
    elif ch == "ntfy":
        ok, detail = channels.send_ntfy(conf["ntfy"], text, title=f"New message from {msg['sender']}", urgent=idx > 0)
    elif ch == "whatsapp":
        ok, detail = channels.send_whatsapp(conf["whatsapp"], text)
    else:
        ok, detail = channels.place_call(conf["call"], speech_text(msg, cfg, now))
    not_set_up = (not ok) and "not set up" in detail
    status = "sent" if ok else ("skipped" if not_set_up else "failed")
    tries = (prior["tries"] + 1) if prior else 1
    _record(org_id, msg["id"], idx, ch, status, detail, tries, now)
    return {"message_id": msg["id"], "step": idx, "channel": ch, "status": status, "detail": detail}


def _record(org_id: str, message_id: int, idx: int, channel: str, status: str, detail: str, tries: int, now: datetime) -> None:
    with get_db() as db:
        db.execute("INSERT INTO alert_attempts (org_id, message_id, step_index, channel, status, detail, tries, at) VALUES (?,?,?,?,?,?,?,?) "
                   "ON CONFLICT(message_id, step_index) DO UPDATE SET status = excluded.status, detail = excluded.detail, tries = excluded.tries, at = excluded.at",
                   (org_id, message_id, idx, channel, status, (detail or "")[:300], tries, _fmt(now)))
        db.commit()


def poll_acks(org_id: str, cfg: Dict[str, Any]) -> int:
    """A Telegram button tap acknowledges that message; any other reply to your bot acknowledges everything waiting. Needs no public address."""
    if not channels.telegram_configured(cfg["channels"]["telegram"]):
        return 0
    chat = str(cfg["channels"]["telegram"]["chat_id"])
    updates, nxt = channels.telegram_updates(int(get_state(org_id, "telegram_offset", "0") or 0))
    acked = 0
    for u in updates:
        cb = u.get("callback_query")
        if cb and str((cb.get("message") or {}).get("chat", {}).get("id")) == chat:
            m = re.fullmatch(r"ack:(\d+)", cb.get("data") or "")
            if m and set_status(org_id, int(m.group(1)), "acknowledged", "telegram"):
                acked += 1
            channels.telegram_answer_callback(cb.get("id", ""), "Noted, no more reminders for that one.")
        msg = u.get("message")
        if msg and str(msg.get("chat", {}).get("id")) == chat and msg.get("text"):
            acked += ack_all(org_id, "telegram reply")
    if nxt:
        set_state(org_id, "telegram_offset", str(nxt))
    return acked


def cycle(org_id: str, now: Optional[datetime] = None, *, mail: bool = True) -> Dict[str, Any]:
    """One pass: read new notification emails, take acknowledgements, send what is due."""
    now = now or utcnow()
    cfg = get_settings(org_id)
    out: Dict[str, Any] = {"enabled": cfg["enabled"], "ingested": 0, "acked": 0, "steps": [], "mail_error": None}
    if not cfg["enabled"]:
        return out
    if mail:
        from alertdesk import mailwatch
        last = get_state(org_id, "last_mail_poll")
        if not last or (now - _parse(last)).total_seconds() >= cfg["watch"]["poll_seconds"]:
            n, err = mailwatch.poll(org_id, cfg, now)
            out["ingested"], out["mail_error"] = n, err
            set_state(org_id, "last_mail_poll", _fmt(now))
            set_state(org_id, "last_mail_error", err)
    out["acked"] = poll_acks(org_id, cfg)
    out["steps"] = run_steps(org_id, cfg, now)
    set_state(org_id, "last_cycle_at", _fmt(now))
    return out


def status(org_id: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or utcnow()
    cfg = get_settings(org_id)
    with get_db() as db:
        waiting = db.execute("SELECT COUNT(*) FROM client_messages WHERE org_id = ? AND status = 'new'", (org_id,)).fetchone()[0]
    paused = bool(cfg.get("paused_until") and now < _parse(cfg["paused_until"]))
    return {"enabled": cfg["enabled"], "paused": paused, "paused_until": cfg.get("paused_until") if paused else None, "working_now": is_active(now, cfg), "waiting": waiting,
            "last_cycle_at": get_state(org_id, "last_cycle_at"), "last_mail_poll": get_state(org_id, "last_mail_poll"), "last_mail_error": get_state(org_id, "last_mail_error") or None,
            "channels_ready": channels.configured_channels(cfg["channels"]), "mailbox_ready": _mailbox_ready()}


def _mailbox_ready() -> bool:
    import os
    return all((os.environ.get(k) or "").strip() for k in ("ALERT_IMAP_HOST", "ALERT_IMAP_USER", "ALERT_IMAP_PASSWORD"))


def tell(org_id: str, text: str, title: str = "AgencyBD", now: Optional[datetime] = None) -> Tuple[bool, str]:
    """One calm, non-urgent message on the free channels (ntfy first, then Telegram). Held back in quiet hours; never a phone call."""
    cfg = get_settings(org_id)
    if in_quiet(now or utcnow(), cfg):
        return False, "quiet hours"
    conf = cfg["channels"]
    ok, detail = False, "No free alert channel is set up."
    if channels.ntfy_configured(conf["ntfy"]):
        ok, detail = channels.send_ntfy(conf["ntfy"], text, title=title)
    if not ok and channels.telegram_configured(conf["telegram"]):
        ok, detail = channels.send_telegram(conf["telegram"], text)
    return ok, detail
