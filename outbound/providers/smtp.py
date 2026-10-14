"""
SMTP Send Provider (per-mailbox credentials).

Each message is sent through the credentials stored (encrypted) for the From mailbox, so rotation across mailboxes is
real. Without credentials the send fails with an honest diagnostic.
"""

import smtplib
import ssl
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Any, Dict, Optional


from net.fetcher import SafeFetcher
from outbound.providers.base import OutboundMessage, SendProvider, SendResult
from outbound.providers.registry import MailboxRegistry


def open_smtp(creds: Dict[str, Any], timeout: int = 15) -> smtplib.SMTP:
    """
    Connects to the tenant-configured relay without trusting DNS twice: resolve once, refuse non-public
    addresses, connect to that exact IP, and still verify the TLS certificate against the configured hostname.
    """
    ip = SafeFetcher.resolve_and_validate_hostname(creds["host"])
    server = smtplib.SMTP(timeout=timeout)
    server._host = creds["host"]  # smtplib uses this name for TLS server_hostname / certificate verification
    server.connect(ip, int(creds["port"]))
    return server


class SmtpProvider(SendProvider):
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, username: Optional[str] = None,
                 password: Optional[str] = None, use_tls: bool = True):
        # Optional explicit credentials (tests, one-off); normally resolved per mailbox in send().
        self._explicit = {"host": host, "port": port or 587, "username": username, "password": password, "use_tls": use_tls} \
            if host and username and password else None

    def _credentials_for(self, message: OutboundMessage) -> Optional[Dict[str, Any]]:
        if self._explicit:
            return self._explicit
        with __import__("database.db", fromlist=["get_db"]).get_db() as db:
            row = db.execute("SELECT id FROM mailboxes WHERE org_id = ? AND email = ?",
                             (message.org_id, message.from_email.lower())).fetchone()
        return MailboxRegistry.get_smtp_credentials(message.org_id, row["id"]) if row else None

    def health_check(self, org_id: Optional[str] = None, mailbox_id: Optional[int] = None) -> Dict[str, Any]:
        creds = self._explicit or (MailboxRegistry.get_smtp_credentials(org_id, mailbox_id) if org_id and mailbox_id else None)
        if not creds:
            return {"provider": "smtp", "status": "not_configured", "ready": False}
        try:
            with open_smtp(creds, timeout=8) as server:
                if creds["use_tls"]:
                    server.starttls(context=ssl.create_default_context())
                server.login(creds["username"], creds["password"])
            return {"provider": "smtp", "status": "connected", "ready": True, "host": creds["host"]}
        except Exception as exc:
            return {"provider": "smtp", "status": "error", "ready": False, "error": str(exc)[:200]}

    def send(self, message: OutboundMessage) -> SendResult:
        creds = self._credentials_for(message)
        if not creds:
            return SendResult(success=False, provider="smtp", status="not_configured",
                              error=f"No SMTP credentials stored for mailbox {message.from_email}.")
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"], msg["From"], msg["To"] = message.subject, message.from_email, message.to_email
            msg["Date"] = formatdate(localtime=False)
            msg["Message-ID"] = make_msgid(domain=message.from_email.split("@")[-1])
            if message.reply_to:
                msg["Reply-To"] = message.reply_to
            for key, value in message.headers.items():
                if "\n" in key or "\r" in key or "\n" in str(value) or "\r" in str(value):
                    raise ValueError("Header injection attempt blocked.")
                msg[key] = value
            msg.attach(MIMEText(message.body_text, "plain"))
            if message.body_html:
                msg.attach(MIMEText(message.body_html, "html"))

            with open_smtp(creds) as server:
                if creds["use_tls"]:
                    server.starttls(context=ssl.create_default_context())
                server.login(creds["username"], creds["password"])
                server.sendmail(message.from_email, [message.to_email], msg.as_string())
            return SendResult(success=True, provider="smtp", provider_message_id=msg["Message-ID"], status="sent",
                              diagnostics={"host": creds["host"], "to": message.to_email})
        except smtplib.SMTPRecipientsRefused as exc:
            return SendResult(success=False, provider="smtp", status="recipient_refused", error=f"Recipient refused: {str(exc)[:160]}")
        except Exception as exc:
            return SendResult(success=False, provider="smtp", status="failed", error=str(exc)[:200])
