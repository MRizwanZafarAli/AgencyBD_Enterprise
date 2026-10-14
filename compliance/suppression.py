"""
Keyed Cryptographic Suppression Vault.
Ensures instant, cross-tenant opt-out suppression for both emails and root domains.
Uses SHA-256 with an HMAC salt to maintain data privacy while allowing O(1) checks.
"""

import hmac
import hashlib
from typing import Dict, Any, Optional
from database.db import get_db

from security.keys import derive_key

# Rows written before the key was moved into the secret store used this public salt. They are still
# honoured when checking (never when writing) so no existing opt-out is lost. Remove once migrated.
_LEGACY_SALT = b"agencybd_enterprise_vault_salt_2026"

class KeyedSuppressionVault:
    @staticmethod
    def hash_entity(entity: str) -> str:
        clean = entity.strip().lower()
        return hmac.new(derive_key("suppression"), clean.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _legacy_hash(entity: str) -> str:
        return hmac.new(_LEGACY_SALT, entity.strip().lower().encode(), hashlib.sha256).hexdigest()

    @classmethod
    def is_suppressed(cls, email: str, org_id: Optional[str] = None) -> bool:
        """
        Checks if the email or its root domain is suppressed in the global vault.
        """
        clean_email = email.strip().lower()
        email_hash = cls.hash_entity(clean_email)
        
        domain = clean_email.split("@")[-1] if "@" in clean_email else clean_email
        domain_hash = cls.hash_entity(domain)

        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("""
                SELECT 1 FROM suppression_vault
                WHERE entity_hash IN (?, ?, ?, ?)
                LIMIT 1
            """, (email_hash, domain_hash, cls._legacy_hash(clean_email), cls._legacy_hash(domain)))
            return cursor.fetchone() is not None

    @classmethod
    def suppress(
        cls,
        entity: str,
        entity_type: str = "email",  # email | domain
        reason: str = "user_unsubscribe",
        source: str = "inbound_reply",
        org_id: str = "org_default"
    ) -> bool:
        """Adds an entity to the suppression vault with an HMAC-keyed hash."""
        clean_entity = entity.strip().lower()
        entity_hash = cls.hash_entity(clean_entity)

        with get_db() as db:
            cursor = db.cursor()
            try:
                cursor.execute("""
                    INSERT INTO suppression_vault (entity_hash, entity_type, reason, source, org_id)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(entity_hash) DO NOTHING
                """, (entity_hash, entity_type, reason, source, org_id))
                db.commit()
                return True
            except Exception:
                return False
