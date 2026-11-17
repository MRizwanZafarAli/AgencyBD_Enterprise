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
ISO_COUNTRIES = frozenset("AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split())     # real ISO 3166-1 alpha-2 codes; anything else is treated as unknown


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
        if code not in ISO_COUNTRIES and code not in COUNTRY_POLICIES:
            return JurisdictionDecision(
                country_code=code, status="blocked", allowed=False, requires_lia=False,
                reason=f"'{code}' is not a recognised country code, so the recipient's jurisdiction is unknown.",
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
