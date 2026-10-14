"""
Mailbox Registry & Deliverability Load Balancer.

* Each mailbox has its own encrypted SMTP credentials (never returned by any API).
* The daily cap is enforced on a rolling 24h window of real 'sent' events, so it cannot get stuck or be reset by accident.
* New mailboxes follow an organic ramp-up (5 -> 10 -> 20 -> 30/day, then full cap) unless the operator marks the
  mailbox as already warmed.
* ESP matching uses the recipient domain's real MX records (Google Workspace -> Google mailbox, Microsoft -> Microsoft).
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.db import get_db
from net.dns_records import lookup_mx
from net.fetcher import SafeFetcher
from security.crypto import decrypt_secret, encrypt_secret

RAMP_SCHEDULE = [(3, 5), (7, 10), (14, 20), (21, 30)]  # (up to day N inclusive, sends per day)


def classify_esp(mx_hosts: Optional[List[str]]) -> str:
    """google | microsoft | other | unknown, from MX hostnames."""
    if mx_hosts is None:
        return "unknown"
    joined = " ".join(h.lower() for h in mx_hosts)
    if "google.com" in joined or "googlemail.com" in joined:
        return "google"
    if "protection.outlook.com" in joined or "outlook.com" in joined:
        return "microsoft"
    return "other" if mx_hosts else "unknown"


def ramp_cap(created_at: Optional[str], daily_cap: int, skip_warmup: bool, now: Optional[datetime] = None) -> int:
    """Effective sends/day: the organic ramp-up for young mailboxes, the configured cap otherwise."""
    if skip_warmup or not created_at:
        return daily_cap
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "")).replace(tzinfo=timezone.utc)
    except ValueError:
        return daily_cap
    age_days = max(0, ((now or datetime.now(timezone.utc)) - created).days) + 1
    for limit, cap in RAMP_SCHEDULE:
        if age_days <= limit:
            return min(cap, daily_cap)
    return daily_cap


def _public(row) -> Dict[str, Any]:
    d = dict(row)
    d.pop("password_enc", None)
    return d


class MailboxRegistry:
    @staticmethod
    def register_mailbox(
        org_id: str,
        email: str,
        display_name: str = "",
        provider_type: str = "smtp",
        daily_cap: int = 35,
        skip_warmup: bool = False,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        use_tls: bool = True,
    ) -> Dict[str, Any]:
        email = email.strip().lower()
        if "@" not in email:
            raise ValueError("Invalid mailbox address.")
        daily_cap = max(1, min(int(daily_cap), 200))
        if smtp_host:
            SafeFetcher.resolve_and_validate_hostname(smtp_host)  # refuses private/internal relays (SSRF)
        esp = classify_esp(lookup_mx(email.split("@", 1)[1]))
        with get_db() as db:
            db.execute("""
                INSERT INTO mailboxes (org_id, email, display_name, provider_type, daily_cap, sent_today, reputation_status, is_active, esp, skip_warmup)
                VALUES (?, ?, ?, ?, ?, 0, 'healthy', 1, ?, ?)
                ON CONFLICT(org_id, email) DO UPDATE SET
                    display_name = excluded.display_name, provider_type = excluded.provider_type,
                    daily_cap = excluded.daily_cap, is_active = 1, esp = excluded.esp, skip_warmup = excluded.skip_warmup
            """, (org_id, email, display_name, provider_type, daily_cap, esp, 1 if skip_warmup else 0))
            row = db.execute("SELECT * FROM mailboxes WHERE org_id = ? AND email = ?", (org_id, email)).fetchone()
            if smtp_host and smtp_username and smtp_password:
                db.execute("""
                    INSERT INTO mailbox_credentials (org_id, mailbox_id, smtp_host, smtp_port, smtp_username, password_enc, use_tls)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mailbox_id) DO UPDATE SET smtp_host = excluded.smtp_host, smtp_port = excluded.smtp_port,
                        smtp_username = excluded.smtp_username, password_enc = excluded.password_enc,
                        use_tls = excluded.use_tls, updated_at = CURRENT_TIMESTAMP
                """, (org_id, row["id"], smtp_host, smtp_port, smtp_username, encrypt_secret(smtp_password), 1 if use_tls else 0))
            db.commit()
            return MailboxRegistry._with_flags(db, org_id, dict(row))

    @staticmethod
    def _with_flags(db, org_id: str, mailbox: Dict[str, Any]) -> Dict[str, Any]:
        has = db.execute("SELECT 1 FROM mailbox_credentials WHERE mailbox_id = ? AND org_id = ?", (mailbox["id"], org_id)).fetchone()
        mailbox["has_credentials"] = bool(has)
        mailbox["effective_daily_cap"] = ramp_cap(mailbox.get("created_at"), mailbox["daily_cap"], bool(mailbox.get("skip_warmup")))
        mailbox["sent_last_24h"] = MailboxRegistry._sent_last_24h(db, org_id, mailbox["id"])
        return mailbox

    @staticmethod
    def _sent_last_24h(db, org_id: str, mailbox_id: int) -> int:
        return db.execute("""
            SELECT COUNT(*) FROM outreach_events
            WHERE org_id = ? AND mailbox_id = ? AND event_type = 'sent' AND created_at >= datetime('now', '-24 hours')
        """, (org_id, mailbox_id)).fetchone()[0]

    @staticmethod
    def list_mailboxes(org_id: str) -> List[Dict[str, Any]]:
        with get_db() as db:
            rows = db.execute("SELECT * FROM mailboxes WHERE org_id = ? ORDER BY created_at DESC", (org_id,)).fetchall()
            return [MailboxRegistry._with_flags(db, org_id, dict(r)) for r in rows]

    @staticmethod
    def get_mailbox(mailbox_id: int, org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            if org_id:
                row = db.execute("SELECT * FROM mailboxes WHERE id = ? AND org_id = ?", (mailbox_id, org_id)).fetchone()
            else:
                row = db.execute("SELECT * FROM mailboxes WHERE id = ?", (mailbox_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_smtp_credentials(org_id: str, mailbox_id: int) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            row = db.execute("SELECT * FROM mailbox_credentials WHERE mailbox_id = ? AND org_id = ?", (mailbox_id, org_id)).fetchone()
        if not row:
            return None
        return {"host": row["smtp_host"], "port": row["smtp_port"], "username": row["smtp_username"],
                "password": decrypt_secret(row["password_enc"]), "use_tls": bool(row["use_tls"])}

    @staticmethod
    def update_reputation(mailbox_id: int, status: str) -> None:
        with get_db() as db:
            db.execute("UPDATE mailboxes SET reputation_status = ? WHERE id = ?", (status, mailbox_id))
            db.commit()

    @staticmethod
    def record_send(org_id: str, mailbox_id: int, recipient_email: str, lead_id: Optional[int] = None,
                    message_id: Optional[str] = None) -> None:
        with get_db() as db:
            db.execute("UPDATE mailboxes SET sent_today = sent_today + 1 WHERE id = ?", (mailbox_id,))
            db.execute("""
                INSERT INTO outreach_events (org_id, mailbox_id, lead_id, recipient_email, event_type, message_id)
                VALUES (?, ?, ?, ?, 'sent', ?)
            """, (org_id, mailbox_id, lead_id, recipient_email, message_id))
            db.commit()

    @staticmethod
    def record_event(org_id: str, recipient_email: str, event_type: str, mailbox_id: Optional[int] = None,
                     lead_id: Optional[int] = None, message_id: Optional[str] = None,
                     payload: Optional[Dict[str, Any]] = None) -> None:
        with get_db() as db:
            db.execute("""
                INSERT INTO outreach_events (org_id, mailbox_id, lead_id, recipient_email, event_type, message_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (org_id, mailbox_id, lead_id, recipient_email.lower(), event_type, message_id, json.dumps(payload or {})))
            db.commit()

    @classmethod
    def select_best_mailbox(cls, org_id: str, recipient_domain: Optional[str] = None,
                            require_credentials: bool = False) -> Optional[Dict[str, Any]]:
        """
        Picks a mailbox that is active, not paused, under its effective cap for the last 24h, and (optionally)
        has SMTP credentials. Prefers an ESP match with the recipient's real MX, then the least-used mailbox.
        """
        with get_db() as db:
            rows = db.execute("""
                SELECT * FROM mailboxes WHERE org_id = ? AND is_active = 1 AND reputation_status != 'paused'
            """, (org_id,)).fetchall()
            available = []
            for r in rows:
                m = cls._with_flags(db, org_id, dict(r))
                if require_credentials and not m["has_credentials"]:
                    continue
                if m["sent_last_24h"] < m["effective_daily_cap"]:
                    available.append(m)
        if not available:
            return None
        available.sort(key=lambda m: m["sent_last_24h"] / max(m["effective_daily_cap"], 1))
        if recipient_domain:
            target = classify_esp(lookup_mx(recipient_domain))
            if target in ("google", "microsoft"):
                matched = [m for m in available if m.get("esp") == target]
                if matched:
                    return matched[0]
        return available[0]

    @staticmethod
    def reset_daily_caps(org_id: Optional[str] = None) -> int:
        """Resets the informational sent_today counter. Enforcement uses the rolling 24h event count, not this."""
        with get_db() as db:
            cur = db.execute("UPDATE mailboxes SET sent_today = 0 WHERE org_id = ?", (org_id,)) if org_id \
                else db.execute("UPDATE mailboxes SET sent_today = 0")
            db.commit()
            return cur.rowcount
