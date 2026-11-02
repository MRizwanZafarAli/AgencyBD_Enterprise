"""Reads platform notification emails from YOUR mailbox, read-only.

Safety: IMAP over TLS on port 993 with an app password; the mailbox is opened read-only and messages are fetched with BODY.PEEK, so nothing is marked
read, moved or deleted. Only mail from watched platforms is looked at, and the first run looks back at most 24 hours so it never floods you."""

import email
import email.policy
import imaplib
import os
import re
import socket
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from alertdesk import engine
from alertdesk.parsers import PLATFORM_DOMAINS, Parsed, parse_email
from net.fetcher import SafeFetcher

MAX_PER_POLL = 40
FETCH_BYTES = 80_000
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def default_connect() -> imaplib.IMAP4:
    host, user, password = (os.environ.get(k, "").strip() for k in ("ALERT_IMAP_HOST", "ALERT_IMAP_USER", "ALERT_IMAP_PASSWORD"))
    if not (host and user and password):
        raise RuntimeError("The alert mailbox is not set up.")
    SafeFetcher.resolve_and_validate_hostname(host)                    # an IMAP host is a network address like any other: no internal targets
    box = imaplib.IMAP4_SSL(host, 993, timeout=20)
    box.login(user, password)
    return box


def _text_and_html(msg: email.message.Message) -> Tuple[str, str]:
    text, html = "", ""
    for part in msg.walk():
        ctype = part.get_content_type()
        if part.get_content_disposition() == "attachment" or ctype not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_content()
        except Exception:
            payload = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        if ctype == "text/plain" and not text:
            text = payload
        elif ctype == "text/html" and not html:
            html = payload
    return text, html


def _when(msg: email.message.Message, fallback: datetime) -> datetime:
    try:
        d = parsedate_to_datetime(msg.get("Date"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    except Exception:
        return fallback


def _fetch(box, uid: int) -> Optional[email.message.Message]:
    typ, data = box.uid("FETCH", str(uid), f"(BODY.PEEK[]<0.{FETCH_BYTES}>)")
    if typ != "OK" or not data or not isinstance(data[0], tuple):
        return None
    return email.message_from_bytes(data[0][1], policy=email.policy.default)


def _uids(box, last_uid: Optional[int], now: datetime) -> List[int]:
    if last_uid is None:
        since = now - timedelta(days=1)
        typ, data = box.uid("SEARCH", None, f'(SINCE "{since.day:02d}-{MONTHS[since.month - 1]}-{since.year}")')
    else:
        typ, data = box.uid("SEARCH", None, f"(UID {last_uid + 1}:*)")
    if typ != "OK" or not data or not data[0]:
        return []
    ids = [int(x) for x in data[0].split()]
    return sorted(u for u in ids if last_uid is None or u > last_uid)


def poll(org_id: str, cfg: Dict[str, Any], now: datetime, connect: Callable[[], Any] = default_connect) -> Tuple[int, Optional[str]]:
    """Returns (messages stored, error text or None). Never raises: a mailbox problem is shown in Settings, it does not stop the desk."""
    watch = cfg["watch"]
    allowed = set(watch["platforms"])
    try:
        box = connect()
    except Exception as exc:
        return 0, _explain(exc)
    stored = 0
    try:
        box.select("INBOX", readonly=True)
        last = engine.get_state(org_id, "imap_last_uid")
        last_uid = int(last) if last else None
        newest = last_uid or 0
        for uid in _uids(box, last_uid, now)[-MAX_PER_POLL:]:
            newest = max(newest, uid)
            msg = _fetch(box, uid)
            if msg is None:
                continue
            text, html = _text_and_html(msg)
            parsed = parse_email(str(msg.get("From", "")), str(msg.get("Subject", "")), text, html, watch["extra_senders"])
            when = _when(msg, now)
            if not parsed or not parsed.alert or (parsed.platform != "other" and parsed.platform not in allowed):
                continue
            if last_uid is None and now - when > timedelta(days=1):    # first run: only the last day
                continue
            ref = str(msg.get("Message-ID") or f"uid:{uid}")
            if engine.ingest(org_id, parsed.platform, parsed.sender, parsed.preview, subject=parsed.subject, url=parsed.url, source_ref=ref, received_at=when, kind=parsed.kind):
                stored += 1
        engine.set_state(org_id, "imap_last_uid", str(newest) if newest else None)
        return stored, None
    except Exception as exc:
        return stored, _explain(exc)
    finally:
        try:
            box.logout()
        except Exception:
            pass


def preview(connect: Callable[[], Any] = default_connect, extra_senders: Optional[List[str]] = None, limit: int = 15) -> Dict[str, Any]:
    """What the watcher would do with your latest platform emails, without storing anything. This is how you check it matches how Fiverr and Upwork really write."""
    try:
        box = connect()
    except Exception as exc:
        return {"ok": False, "error": _explain(exc), "emails": []}
    rows: List[Dict[str, Any]] = []
    try:
        box.select("INBOX", readonly=True)
        typ, data = box.uid("SEARCH", None, "ALL")
        ids = sorted(int(x) for x in (data[0].split() if typ == "OK" and data and data[0] else []))
        for uid in reversed(ids[-250:]):
            msg = _fetch(box, uid)
            if msg is None:
                continue
            text, html = _text_and_html(msg)
            p: Optional[Parsed] = parse_email(str(msg.get("From", "")), str(msg.get("Subject", "")), text, html, extra_senders)
            if not p:
                continue
            rows.append({"from": str(msg.get("From", ""))[:80], "subject": p.subject[:120], "platform": p.platform, "kind": p.kind, "would_alert": p.alert, "sender": p.sender, "preview": p.preview[:140]})
            if len(rows) >= limit:
                break
        return {"ok": True, "error": None, "emails": rows}
    except Exception as exc:
        return {"ok": False, "error": _explain(exc), "emails": rows}
    finally:
        try:
            box.logout()
        except Exception:
            pass


def _explain(exc: Exception) -> str:
    text = str(exc)
    low = text.lower()
    if "authentication" in low or "invalid credentials" in low or "login" in low or "auth" in low:
        return "The mailbox refused the login. Use an app password (not your normal one), and make sure IMAP is switched on in the mail settings."
    if isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in low:
        return "The mailbox did not answer in time."
    if "not set up" in low:
        return "The alert mailbox is not set up yet (server, address and app password)."
    return "Could not read the mailbox: " + re.sub(r"\S+@\S+", "…", text)[:120]
