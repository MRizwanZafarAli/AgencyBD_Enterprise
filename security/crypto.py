"""Authenticated encryption for secrets stored in the database (mailbox passwords, webhook secrets, OAuth tokens).

Fernet (AES-128-CBC + HMAC-SHA256) with a key derived from the vault secret. Rotating AGENCYBD_HMAC_VAULT_KEY
makes stored ciphertexts unreadable, which is the intended failure mode: re-enter the credentials."""

import base64

from cryptography.fernet import Fernet, InvalidToken

from security.keys import derive_key


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(derive_key("stored-credentials")))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored credential cannot be decrypted (vault key changed or data corrupted). Re-enter it.") from exc
