"""
Sovereign Two-Way IMAP Master Inbox Sync & Auto-Reply Triage Engine.
Polls configured IMAP mailboxes, matches replies to outbound sequences/leads,
auto-pauses active sequences on reply, classifies intent via ReplyAgent,
auto-suppresses opt-outs, and stores unified thread messages in `inbox_messages`.
"""

import email
import imaplib
import logging
from email.header import decode_header
from email.utils import parseaddr
from typing import Any, Dict, List, Optional

from agents.reply_agent import ReplyAgent
from core.hooks import event_bus
from database.db import get_db
from net.validate import is_valid_hostname

logger = logging.getLogger("AgencyBD.imap_sync")

HOOK_INBOUND_REPLY = "on_inbound_reply"


def _decode_header_str(raw_val: Optional[str]) -> str:
    if not raw_val:
        return ""
    parts = decode_header(raw_val)
    decoded = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(chunk))
    return "".join(decoded).strip()


def _extract_plain_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp.lower():
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or "utf-8", errors="replace").strip()
    return ""


class NativeImapSyncEngine:
    """Two-way Master Inbox synchronization over IMAP/TLS."""

    def __init__(self) -> None:
        self.reply_agent = ReplyAgent()

    def ingest_inbound_message(
        self,
        *,
        org_id: str,
        sender_email: str,
        recipient_email: str,
        subject: str,
        body: str,
        mailbox_id: Optional[int] = None,
        message_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalizes, triages, stops active sequences, and persists an inbound reply."""
        clean_sender = parseaddr(sender_email)[1].strip().lower() or sender_email.strip().lower()
        clean_recipient = parseaddr(recipient_email)[1].strip().lower() or recipient_email.strip().lower()

        lead_id: Optional[int] = None
        company_name = ""
        with get_db() as conn:
            # Deduplicate by Message-ID if already synced
            if message_id:
                existing = conn.execute(
                    "SELECT id FROM inbox_messages WHERE org_id = ? AND message_id = ?",
                    (org_id, message_id),
                ).fetchone()
                if existing:
                    return {"status": "duplicate", "id": existing["id"]}

            # Match lead by contact email or previous outbound events
            row = conn.execute(
                """
                SELECT dm.lead_id, l.company_name
                FROM decision_makers dm
                JOIN leads l ON l.id = dm.lead_id
                WHERE LOWER(dm.email) = ? AND l.org_id = ?
                LIMIT 1
                """,
                (clean_sender, org_id),
            ).fetchone()
            if row:
                lead_id = row["lead_id"]
                company_name = row["company_name"] or ""
            else:
                enr = conn.execute(
                    "SELECT lead_id FROM sequence_enrollments WHERE LOWER(recipient_email) = ? AND org_id = ? AND lead_id IS NOT NULL ORDER BY id DESC LIMIT 1",
                    (clean_sender, org_id),
                ).fetchone()
                if enr:
                    lead_id = enr["lead_id"]
                else:
                    try:
                        ev = conn.execute(
                            "SELECT lead_id FROM outreach_events WHERE LOWER(recipient_email) = ? ORDER BY id DESC LIMIT 1",
                            (clean_sender,),
                        ).fetchone()
                        if ev:
                            lead_id = ev["lead_id"]
                    except Exception:
                        pass

            # Auto-pause any active sequence enrollments for this recipient
            conn.execute(
                """
                UPDATE sequence_enrollments
                SET status = 'replied'
                WHERE org_id = ? AND LOWER(recipient_email) = ? AND status IN ('active', 'awaiting_approval')
                """,
                (org_id, clean_sender),
            )
            conn.commit()

        triage = self.reply_agent.handle_inbound_reply(
            raw_body=body,
            sender_email=clean_sender,
            org_id=org_id,
            lead_id=lead_id,
            company_name=company_name,
        )

        # Global Suppression Guard: immediately suppress on unsubscribe reply
        cat_lower = str(triage.get("category") or "").lower()
        body_lower = (body or "").lower()
        if cat_lower == "unsubscribe" or any(p in body_lower for p in ("unsubscribe", "opt out", "opt-out", "remove me from")):
            from compliance.suppression import KeyedSuppressionVault
            KeyedSuppressionVault.suppress(
                clean_sender,
                entity_type="email",
                reason="inbound_unsubscribe",
                source="master_inbox",
                org_id=org_id,
            )
            with get_db() as conn:
                conn.execute(
                    "UPDATE sequence_enrollments SET status = 'stopped', stop_reason = 'unsubscribed' "
                    "WHERE org_id = ? AND LOWER(recipient_email) = ?",
                    (org_id, clean_sender),
                )
                conn.commit()

        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO inbox_messages
                (org_id, mailbox_id, lead_id, direction, sender_email, recipient_email, subject, body,
                 category, sentiment, auto_reply_draft, message_id, in_reply_to, status)
                VALUES (?, ?, ?, 'inbound', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')
                """,
                (
                    org_id,
                    mailbox_id,
                    lead_id,
                    clean_sender,
                    clean_recipient,
                    subject,
                    body,
                    triage.get("category", "generic"),
                    triage.get("sentiment", "neutral"),
                    triage.get("draft_response") or "",
                    message_id,
                    in_reply_to,
                ),
            )
            msg_row_id = cur.lastrowid
            conn.commit()

        try:
            event_bus.emit(
                HOOK_INBOUND_REPLY,
                {
                    "org_id": org_id,
                    "inbox_message_id": msg_row_id,
                    "lead_id": lead_id,
                    "sender_email": clean_sender,
                    "category": triage.get("category"),
                    "sentiment": triage.get("sentiment"),
                },
            )
        except Exception:
            pass

        return {
            "status": "ingested",
            "id": msg_row_id,
            "lead_id": lead_id,
            "triage": triage,
        }

    def sync_imap_mailbox(
        self,
        *,
        org_id: str,
        imap_host: str,
        imap_port: int,
        username: str,
        password: str,
        mailbox_email: str,
        mailbox_id: Optional[int] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Connects over IMAP4_SSL, reads recent UNSEEN emails, and ingests them."""
        if not is_valid_hostname(imap_host):
            raise ValueError(f"Invalid IMAP hostname: {imap_host}")

        ingested: List[Dict[str, Any]] = []
        client = imaplib.IMAP4_SSL(imap_host, int(imap_port), timeout=12)
        try:
            client.login(username, password)
            client.select("INBOX")
            typ, data = client.search(None, "UNSEEN")
            if typ != "OK" or not data or not data[0]:
                return {"ok": True, "synced_count": 0, "messages": []}

            uids = data[0].split()[-limit:]
            for uid in uids:
                f_typ, msg_data = client.fetch(uid, "(RFC822)")
                if f_typ != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw_bytes = msg_data[0][1]
                if not isinstance(raw_bytes, (bytes, bytearray)):
                    continue
                msg = email.message_from_bytes(raw_bytes)
                res = self.ingest_inbound_message(
                    org_id=org_id,
                    mailbox_id=mailbox_id,
                    sender_email=_decode_header_str(msg.get("From")),
                    recipient_email=mailbox_email,
                    subject=_decode_header_str(msg.get("Subject")) or "(no subject)",
                    body=_extract_plain_body(msg) or "(empty body)",
                    message_id=(msg.get("Message-ID") or "").strip() or None,
                    in_reply_to=(msg.get("In-Reply-To") or "").strip() or None,
                )
                ingested.append(res)
        finally:
            try:
                client.logout()
            except Exception:
                pass

        return {"ok": True, "synced_count": len(ingested), "messages": ingested}


imap_sync_engine = NativeImapSyncEngine()
