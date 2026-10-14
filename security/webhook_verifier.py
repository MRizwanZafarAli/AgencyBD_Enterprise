"""
Enterprise Webhook Security & Signature Verifier.
HMAC-SHA256 signatures with anti-replay protection.

Wire format
  X-AgencyBD-Timestamp: <unix seconds>
  X-AgencyBD-Signature: [sha256=]hex(HMAC_SHA256(secret, f"{timestamp}.{raw_body}"))

The timestamp is part of the signed message, so it cannot be changed or stripped
without invalidating the signature.
"""

import hmac
import hashlib
import time
from typing import Optional

from config.env import get_secret

WEBHOOK_SECRET = get_secret("AGENCYBD_WEBHOOK_SECRET")


class WebhookSecurity:
    @staticmethod
    def _message(payload_bytes: bytes, timestamp: Optional[int]) -> bytes:
        if timestamp is None:
            return payload_bytes
        return f"{int(timestamp)}.".encode("utf-8") + payload_bytes

    @staticmethod
    def sign_payload(payload_bytes: bytes, secret: str = None, timestamp: Optional[int] = None) -> str:
        """Calculates the HMAC-SHA256 signature; binds ``timestamp`` into the message when given."""
        key = (secret or WEBHOOK_SECRET).encode("utf-8")
        return hmac.new(key, WebhookSecurity._message(payload_bytes, timestamp), hashlib.sha256).hexdigest()

    @staticmethod
    def verify_signature(
        payload_bytes: bytes,
        signature: str,
        secret: str = None,
        timestamp: Optional[int] = None,
        tolerance_seconds: int = 300
    ) -> bool:
        """
        Constant-time signature check. When ``timestamp`` is supplied it must be within
        ``tolerance_seconds`` of now and is verified as part of the signed message.
        """
        if not signature:
            return False

        if timestamp is not None:
            try:
                ts = int(timestamp)
            except (TypeError, ValueError):
                return False
            if abs(int(time.time()) - ts) > tolerance_seconds:
                return False

        expected_sig = WebhookSecurity.sign_payload(payload_bytes, secret, timestamp)
        clean_sig = signature.strip()
        if clean_sig.lower().startswith("sha256="):
            clean_sig = clean_sig[len("sha256="):]
        return hmac.compare_digest(clean_sig.lower(), expected_sig)


class WebhookSecrets:
    """Per-tenant webhook signing secrets, encrypted at rest."""

    @staticmethod
    def rotate(org_id: str) -> str:
        import secrets
        from database.db import get_db
        from security.crypto import encrypt_secret
        secret = secrets.token_urlsafe(32)
        with get_db() as db:
            db.execute("INSERT INTO webhook_secrets (org_id, secret_enc) VALUES (?, ?) ON CONFLICT(org_id) DO UPDATE SET "
                       "secret_enc = excluded.secret_enc, created_at = CURRENT_TIMESTAMP", (org_id, encrypt_secret(secret)))
            db.commit()
        return secret

    @staticmethod
    def get(org_id: str):
        from database.db import get_db
        from security.crypto import decrypt_secret
        with get_db() as db:
            row = db.execute("SELECT secret_enc FROM webhook_secrets WHERE org_id = ?", (org_id,)).fetchone()
        return decrypt_secret(row["secret_enc"]) if row else None
