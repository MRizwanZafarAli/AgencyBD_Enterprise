"""Per-tenant OAuth tokens (encrypted at rest) and signed `state` values for the browser redirect flow."""

import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from database.db import get_db
from security.crypto import decrypt_secret, encrypt_secret
from security.keys import derive_key

STATE_TTL_SECONDS = 600


def sign_state(org_id: str, provider: str) -> str:
    payload = urlsafe_b64encode(json.dumps({"o": org_id, "p": provider, "t": int(time.time())}).encode()).decode()
    sig = hmac.new(derive_key("oauth-state"), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_state(state: str, provider: str) -> Optional[str]:
    """Returns the org_id the state was issued for, or None if forged/expired/for another provider."""
    try:
        payload, sig = state.rsplit(".", 1)
        expected = hmac.new(derive_key("oauth-state"), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(urlsafe_b64decode(payload.encode()))
        if data["p"] != provider or time.time() - data["t"] > STATE_TTL_SECONDS:
            return None
        return data["o"]
    except Exception:
        return None


class TokenStore:
    @staticmethod
    def save(org_id: str, provider: str, access: str, refresh: Optional[str], expires_in: Optional[int], scope: str = "") -> None:
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in or 3600))).strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as db:
            db.execute("""
                INSERT INTO oauth_tokens (org_id, provider, access_enc, refresh_enc, expires_at, scope) VALUES (?,?,?,?,?,?)
                ON CONFLICT(org_id, provider) DO UPDATE SET access_enc = excluded.access_enc,
                    refresh_enc = COALESCE(excluded.refresh_enc, oauth_tokens.refresh_enc), expires_at = excluded.expires_at,
                    scope = excluded.scope, updated_at = CURRENT_TIMESTAMP
            """, (org_id, provider, encrypt_secret(access), encrypt_secret(refresh) if refresh else None, expires_at, scope))
            db.commit()

    @staticmethod
    def load(org_id: str, provider: str) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            row = db.execute("SELECT * FROM oauth_tokens WHERE org_id = ? AND provider = ?", (org_id, provider)).fetchone()
        if not row:
            return None
        return {"access": decrypt_secret(row["access_enc"]), "refresh": decrypt_secret(row["refresh_enc"]) if row["refresh_enc"] else None,
                "expires_at": datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc), "scope": row["scope"]}

    @staticmethod
    def delete(org_id: str, provider: str) -> bool:
        with get_db() as db:
            cur = db.execute("DELETE FROM oauth_tokens WHERE org_id = ? AND provider = ?", (org_id, provider))
            db.commit()
            return cur.rowcount > 0
