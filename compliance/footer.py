"""
Compliance Footers & One-Click Unsubscribe Headers.
Every outbound email carries:
1. Sender identity and physical address (CAN-SPAM).
2. A signed unsubscribe link (RFC 2369) plus RFC 8058 one-click headers.
3. A legitimate-interest notice for UK/EU corporate outreach.

Unsubscribe tokens are HMAC-SHA256 over (org, email) with a key derived from the vault secret,
so a link cannot be forged or re-targeted at another address or tenant.
"""

import hmac
import hashlib
import os
from typing import Dict, Tuple
from urllib.parse import urlencode

from config.env import is_production
from security.keys import derive_key

_DEFAULT_DEV_ADDRESS = "100 Example Street, Suite 1, Austin, TX 78701 (set AGENCYBD_SENDER_ADDRESS)"


def _public_base_url() -> str:
    url = os.getenv("AGENCYBD_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if url:
        return url
    if is_production():
        raise RuntimeError("AGENCYBD_PUBLIC_BASE_URL must be set in production so unsubscribe links work.")
    return "http://localhost:8001"


def _sender_company() -> str:
    return os.getenv("AGENCYBD_SENDER_COMPANY", "ApexCore Digital Agency")


def _sender_address() -> str:
    addr = os.getenv("AGENCYBD_SENDER_ADDRESS", "").strip()
    if addr:
        return addr
    if is_production():
        raise RuntimeError("AGENCYBD_SENDER_ADDRESS (physical postal address) is required in production (CAN-SPAM).")
    return _DEFAULT_DEV_ADDRESS


class ComplianceFooterBuilder:
    @staticmethod
    def generate_unsubscribe_token(email: str, org_id: str) -> str:
        payload = f"{org_id}|{email.strip().lower()}".encode()
        return hmac.new(derive_key("unsubscribe"), payload, hashlib.sha256).hexdigest()

    @classmethod
    def verify_unsubscribe_token(cls, email: str, org_id: str, token: str) -> bool:
        if not token or not email or not org_id:
            return False
        return hmac.compare_digest(cls.generate_unsubscribe_token(email, org_id), token.strip().lower())

    @classmethod
    def build_unsubscribe_url(cls, recipient_email: str, org_id: str, base_url: str = "") -> str:
        query = urlencode({
            "email": recipient_email.strip().lower(),
            "org_id": org_id,
            "token": cls.generate_unsubscribe_token(recipient_email, org_id),
        })
        return f"{(base_url or _public_base_url()).rstrip('/')}/api/compliance/unsubscribe?{query}"

    @classmethod
    def build_footer(
        cls,
        recipient_email: str,
        org_id: str = "org_default",
        company_name: str = "",
        physical_address: str = "",
        base_url: str = "",
        include_lia: bool = False
    ) -> Tuple[str, str, Dict[str, str]]:
        """Returns (plain_text_footer, html_footer, headers_dict)."""
        company_name = company_name or _sender_company()
        physical_address = physical_address or _sender_address()
        unsub_url = cls.build_unsubscribe_url(recipient_email, org_id, base_url)

        headers = {
            "List-Unsubscribe": f"<{unsub_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }

        lia_text = ""
        lia_html = ""
        if include_lia:
            lia_text = "\nThis email was sent under GDPR / PECR Legitimate Interest grounds based on your public corporate role.\n"
            lia_html = '<p style="font-size: 11px; color: #718096; margin-top: 4px;">Sent under GDPR / PECR Legitimate Interest based on your public professional role.</p>'

        plain_footer = (
            f"\n\n---\n"
            f"{company_name} | {physical_address}\n"
            f"{lia_text}"
            f"If you'd prefer not to hear from us, unsubscribe here: {unsub_url}\n"
        )

        html_footer = f"""
        <br/><br/>
        <div style="border-top: 1px solid #e2e8f0; padding-top: 12px; margin-top: 24px; font-family: sans-serif; font-size: 12px; color: #718096; line-height: 1.4;">
            <p style="margin: 0;"><strong>{company_name}</strong> &bull; {physical_address}</p>
            {lia_html}
            <p style="margin: 4px 0 0 0;">
                <a href="{unsub_url}" style="color: #4a5568; text-decoration: underline;">Unsubscribe</a>
            </p>
        </div>
        """

        return plain_footer, html_footer, headers
