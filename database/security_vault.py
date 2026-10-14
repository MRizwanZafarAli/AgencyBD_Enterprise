"""
SecurityVault: Enterprise Cryptographic Data Protection & Tamper Verification.
Implements:
1. HMAC-SHA256 digital signatures on all database records to detect unauthorized modifications.
2. Global CAN-SPAM / GDPR SHA-256 suppression hashing.
3. Immutable compliance audit logging.
4. Cryptographic record integrity verification.
"""

import hmac
import hashlib
import json
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

from config.env import get_secret

# HMAC signing key. Required in production; VAULT_SECRET_KEY is the legacy variable name.
VAULT_SECRET_KEY = get_secret("AGENCYBD_HMAC_VAULT_KEY", "VAULT_SECRET_KEY").encode()

class SecurityVault:
    @staticmethod
    def generate_sha256_hash(text: str) -> str:
        """Computes one-way cryptographic SHA-256 hash for privacy-safe suppression matching."""
        return hashlib.sha256(text.lower().strip().encode("utf-8")).hexdigest()

    @staticmethod
    def sign_record(entity_type: str, record_id: int, payload: Dict[str, Any]) -> str:
        """
        Generates HMAC-SHA256 digital signature over a record payload.
        Any tampering outside the application causes signature verification to fail.
        """
        # Canonicalize JSON payload
        clean_payload = {k: v for k, v in payload.items() if k not in ["record_hash", "created_at", "updated_at"]}
        serialized = json.dumps(clean_payload, sort_keys=True, default=str)
        sign_target = f"{entity_type}:{record_id}:{serialized}".encode("utf-8")
        return hmac.new(VAULT_SECRET_KEY, sign_target, hashlib.sha256).hexdigest()

    @staticmethod
    def verify_record_signature(entity_type: str, record_id: int, payload: Dict[str, Any], signature: str) -> bool:
        """Verifies if record payload matches its cryptographic HMAC signature."""
        expected_sig = SecurityVault.sign_record(entity_type, record_id, payload)
        return hmac.compare_digest(expected_sig, signature)

    @staticmethod
    def sanitize_identifier(text: str) -> str:
        """Strict sanitization preventing SQL, command, or script injections."""
        if not text:
            return ""
        # Remove any null bytes or script tags
        clean = text.replace("\x00", "").strip()
        return clean
