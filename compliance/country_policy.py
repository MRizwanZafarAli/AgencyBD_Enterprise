"""
Country Compliance Policy Engine.
Enforces jurisdiction rules (CAN-SPAM, GDPR, PECR, CASL):
- US: Allowed (requires clear identity, physical address, opt-out)
- UK / EU: Needs Legitimate Interest Assessment (LIA) and role relevance
- DE / PL / AT: Blocked by default (strict opt-in requirements)
- CA: Blocked by default under CASL without prior documented consent
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class JurisdictionDecision:
    country_code: str
    status: str  # allowed | needs_lia | blocked
    allowed: bool
    requires_lia: bool
    reason: str
    required_disclosures: list[str]

# ISO 3166-1 alpha-2 mappings
COUNTRY_POLICIES = {
    "US": {
        "status": "allowed",
        "requires_lia": False,
        "reason": "US CAN-SPAM compliant with valid postal address and instant opt-out.",
        "disclosures": ["postal_address", "opt_out_link"]
    },
    "GB": {
        "status": "needs_lia",
        "requires_lia": True,
        "reason": "UK GDPR & PECR corporate subscriber rule applies; requires documented LIA and role relevance.",
        "disclosures": ["postal_address", "opt_out_link", "legal_basis_lia", "source_origin"]
    },
    "UK": {
        "status": "needs_lia",
        "requires_lia": True,
        "reason": "UK GDPR & PECR corporate subscriber rule applies; requires documented LIA.",
        "disclosures": ["postal_address", "opt_out_link", "legal_basis_lia", "source_origin"]
    },
    "FR": {
        "status": "needs_lia",
        "requires_lia": True,
        "reason": "EU GDPR B2B exception applies; requires role relevance and documented legitimate interest.",
        "disclosures": ["postal_address", "opt_out_link", "legal_basis_lia", "source_origin"]
    },
    "NL": {
        "status": "needs_lia",
        "requires_lia": True,
        "reason": "EU GDPR B2B exception applies with documented legitimate interest.",
        "disclosures": ["postal_address", "opt_out_link", "legal_basis_lia"]
    },
    "DE": {
        "status": "blocked",
        "requires_lia": False,
        "reason": "Germany UWG § 7 strictly prohibits cold B2B email without prior explicit consent (double opt-in).",
        "disclosures": []
    },
    "PL": {
        "status": "blocked",
        "requires_lia": False,
        "reason": "Poland Electronic Services Act requires explicit prior consent for marketing communications.",
        "disclosures": []
    },
    "AT": {
        "status": "blocked",
        "requires_lia": False,
        "reason": "Austria TKG 2021 § 174 requires prior consent for electronic marketing dispatches.",
        "disclosures": []
    },
    "CA": {
        "status": "blocked",
        "requires_lia": False,
        "reason": "Canada Anti-Spam Legislation (CASL) enforces private right of action; default blocked without express consent.",
        "disclosures": []
    }
}

class CountryComplianceEngine:
    @classmethod
    def evaluate(cls, country_code: Optional[str] = None) -> JurisdictionDecision:
        code = (country_code or "").upper().strip()
        if not code:
            # Fail closed: a missing country must never be silently treated as the permissive US regime.
            return JurisdictionDecision(
                country_code="??", status="blocked", allowed=False, requires_lia=False,
                reason="Recipient country is unknown; cold outreach requires a known jurisdiction.",
                required_disclosures=[])
        policy = COUNTRY_POLICIES.get(code)
        
        if not policy:
            # Default international policy: require LIA as safety floor
            return JurisdictionDecision(
                country_code=code,
                status="needs_lia",
                allowed=True,
                requires_lia=True,
                reason=f"Jurisdiction {code} requires documented legitimate interest assessment and role relevance.",
                required_disclosures=["postal_address", "opt_out_link", "source_origin"]
            )

        is_allowed = policy["status"] in ("allowed", "needs_lia")
        return JurisdictionDecision(
            country_code=code,
            status=policy["status"],
            allowed=is_allowed,
            requires_lia=policy["requires_lia"],
            reason=policy["reason"],
            required_disclosures=policy["disclosures"]
        )
