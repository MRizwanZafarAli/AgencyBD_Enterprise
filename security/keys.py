"""Purpose-bound keys derived from the master vault secret (HKDF-style, HMAC-SHA256)."""

import hashlib
import hmac

from config.env import get_secret


def derive_key(purpose: str) -> bytes:
    """A stable 32-byte key for ``purpose``. Different purposes never share a key."""
    master = get_secret("AGENCYBD_HMAC_VAULT_KEY", "VAULT_SECRET_KEY").encode()
    return hmac.new(master, f"agencybd:v1:{purpose}".encode(), hashlib.sha256).digest()
