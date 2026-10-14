"""
Outbound Email Verification Gate (fail-closed).

An address may receive cold email only if it is positively 'verified'. Order of checks:
  1. syntax, system/trap prefixes, disposable domains (local, free)
  2. real MX lookup (no MX = invalid; DNS unreachable = unverified)
  3. cached vendor verdict (30 days) to avoid paying twice
  4. a real vendor call (ZeroBounce or MillionVerifier)
Vendor errors, timeouts, 'unknown', 'catch-all' and 'risky' all mean NOT verified. With no vendor configured the
gate refuses everything.
"""

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests


from database.db import get_db
from net.dns_records import lookup_mx
import os

from security.keys import derive_key

CACHE_DAYS = 30

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "10minutemail.com", "throwawaymail.com", "yopmail.com",
    "trashmail.com", "fakeinbox.com", "sharklasers.com", "getairmail.com", "dispostable.com", "maildrop.cc",
    "temp-mail.org", "burnermail.io", "guerrillamail.net",
}
SPAM_TRAP_PREFIXES = {"abuse", "postmaster", "spam", "spamtrap", "fbl", "compliance", "mailer-daemon", "noreply", "no-reply",
                      "donotreply", "do-not-reply", "root", "hostmaster", "webmaster"}
SYNTAX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+")


@dataclass
class VerificationResult:
    email: str
    status: str  # verified | invalid | risky | unverified | disposable | spamtrap
    is_deliverable: bool
    provider: str
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {"email": self.email, "status": self.status, "is_deliverable": self.is_deliverable,
                "provider": self.provider, "confidence": self.confidence, "reason": self.reason}


class VerifierVendor:
    name = "vendor"

    def check(self, email: str) -> Tuple[str, str]:
        """Returns (status, detail) where status is verified | invalid | risky | unknown. Raises on transport errors."""
        raise NotImplementedError


class ZeroBounceVendor(VerifierVendor):
    name = "zerobounce"
    URL = "https://api.zerobounce.net/v2/validate"  # fixed vendor host

    def __init__(self, api_key: str):
        self.api_key = api_key

    def check(self, email: str) -> Tuple[str, str]:
        resp = requests.get(self.URL, params={"api_key": self.api_key, "email": email, "ip_address": ""}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"zerobounce: {str(data['error'])[:100]}")
        status = str(data.get("status", "")).lower()
        detail = f"{status}/{data.get('sub_status', '')}"
        if status == "valid":
            return "verified", detail
        if status in ("invalid", "spamtrap", "abuse", "do_not_mail"):
            return "invalid", detail
        if status == "catch-all":
            return "risky", detail
        return "unknown", detail


class MillionVerifierVendor(VerifierVendor):
    name = "millionverifier"
    URL = "https://api.millionverifier.com/api/v3/"  # fixed vendor host

    def __init__(self, api_key: str):
        self.api_key = api_key

    def check(self, email: str) -> Tuple[str, str]:
        resp = requests.get(self.URL, params={"api": self.api_key, "email": email, "timeout": 20}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"millionverifier: {str(data['error'])[:100]}")
        result = str(data.get("result", "")).lower()
        if result == "ok":
            return "verified", result
        if result in ("invalid", "disposable"):
            return "invalid", result
        if result == "catch_all":
            return "risky", result
        return "unknown", result


def configured_vendor() -> Optional[VerifierVendor]:
    zb, mv = os.getenv("ZEROBOUNCE_API_KEY", ""), os.getenv("MILLIONVERIFIER_API_KEY", "")
    if zb and not zb.startswith("your_"):
        return ZeroBounceVendor(zb)
    if mv and not mv.startswith("your_"):
        return MillionVerifierVendor(mv)
    return None


def _hash(email: str) -> str:
    return hmac.new(derive_key("verification-cache"), email.encode(), hashlib.sha256).hexdigest()


class EmailVerificationGate:
    def __init__(self, vendor: Optional[VerifierVendor] = None, verifier_api_key: Optional[str] = None):
        self._vendor = vendor

    @staticmethod
    def is_valid_syntax(email: str) -> bool:
        return bool(SYNTAX.fullmatch(email))

    @staticmethod
    def _cache_get(email: str) -> Optional[Tuple[str, str, str]]:
        with get_db() as db:
            row = db.execute(
                "SELECT status, provider, detail FROM email_verifications WHERE email_hash = ? "
                "AND checked_at >= datetime('now', ?)", (_hash(email), f"-{CACHE_DAYS} days")).fetchone()
        return (row["status"], row["provider"], row["detail"] or "") if row else None

    @staticmethod
    def _cache_put(email: str, status: str, provider: str, detail: str) -> None:
        with get_db() as db:
            db.execute("INSERT OR REPLACE INTO email_verifications (email_hash, status, provider, detail, checked_at) "
                       "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", (_hash(email), status, provider, detail))
            db.commit()

    def verify(self, email: str) -> VerificationResult:
        clean = (email or "").strip().lower()

        def result(status, deliverable, provider, confidence, reason):
            return VerificationResult(clean, status, deliverable, provider, confidence, reason)

        if not self.is_valid_syntax(clean):
            return result("invalid", False, "syntax_guard", 0.0, "Invalid email syntax.")
        local, domain = clean.split("@", 1)
        if local in SPAM_TRAP_PREFIXES:
            return result("spamtrap", False, "honeypot_guard", 0.0, "System or trap-style mailbox name.")
        if domain in DISPOSABLE_DOMAINS:
            return result("disposable", False, "disposable_guard", 0.0, "Disposable email provider.")

        mx = lookup_mx(domain)
        if mx is None:
            return result("unverified", False, "dns_guard", 0.0, "DNS could not be queried; cannot verify.")
        if not mx:
            return result("invalid", False, "dns_guard", 0.0, f"{domain} has no MX records and cannot receive email.")

        cached = self._cache_get(clean)
        if cached:
            status, provider, detail = cached
            return result(status, status == "verified", f"{provider}(cached)", 0.95 if status == "verified" else 0.0, detail or status)

        vendor = self._vendor or configured_vendor()
        if vendor:
            try:
                status, detail = vendor.check(clean)
            except Exception as exc:
                return result("unverified", False, vendor.name, 0.0, f"Verifier unavailable ({str(exc)[:80]}); failing closed.")
            if status != "unknown":
                self._cache_put(clean, status, vendor.name, detail)
            ok = status == "verified"
            return result(status if status != "unknown" else "unverified", ok, vendor.name, 0.98 if ok else 0.0, detail)

        return result("unverified", False, "fail_closed_gate", 0.0,
                      "No email verifier configured (set ZEROBOUNCE_API_KEY or MILLIONVERIFIER_API_KEY); failing closed.")

    def allows_send(self, email: str) -> bool:
        r = self.verify(email)
        return r.status == "verified" and r.is_deliverable
