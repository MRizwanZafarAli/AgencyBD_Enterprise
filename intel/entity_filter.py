"""
Is this legal entity an operating company a web/engineering agency could sell to?

SEC Form D filers are mostly investment vehicles (funds, SPVs, partnerships). They have no product website and no
engineering team, so they are dropped instead of being given a guessed domain. The check is a heuristic on the NAME only,
so it returns a reason, and "operating_company" means "not recognised as a vehicle", not "verified operating company".
"""

import re
from typing import Tuple

VEHICLE_TOKENS = re.compile(
    r"\b(l\.?\s?p\.?|l\.?l\.?l\.?p\.?|fund|funds|partners|partnership|partnerships|capital|trust|series|spv|investors?|"
    r"investment|investments|opportunit(?:y|ies)|equity|realty|properties|acquisition|feeder|master|co-?invest|"
    r"syndicate|holdings? (?:i|ii|iii|iv|v|vi)|ventures? (?:i|ii|iii|iv|v|vi)|a series of|segregated)\b", re.IGNORECASE)
ROMAN_SUFFIX = re.compile(r"\b(?:i{1,3}|iv|v|vi{0,3}|ix|x)\s*[,.]?\s*$", re.IGNORECASE)
NOISE_SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|corporation|company|co|plc|gmbh|sa)\b\.?", re.IGNORECASE)


def clean_company_name(raw: str) -> str:
    """Strips legal suffixes and stray punctuation: 'Xona Space Systems ., Inc.' -> 'Xona Space Systems'."""
    name = re.sub(r"https?://\S+", "", raw or "")
    name = re.sub(r"\([^)]*\)", "", name)                  # "(Remote US)", "(Series B)", "(YC W21)" describe the posting, not the company
    name = NOISE_SUFFIX.sub("", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip(" .,;:-|–—")


def classify_entity(raw_name: str) -> Tuple[str, str]:
    """Returns (kind, reason); kind is 'operating_company' or 'fund_or_vehicle'."""
    name = (raw_name or "").strip()
    if len(clean_company_name(name)) < 3:
        return "fund_or_vehicle", "name too short to identify a company"
    match = VEHICLE_TOKENS.search(name)
    if match:
        return "fund_or_vehicle", f"name contains '{match.group(0).strip()}', which marks an investment vehicle"
    if ROMAN_SUFFIX.search(clean_company_name(name)) and len(clean_company_name(name).split()) >= 2:
        return "fund_or_vehicle", "numbered entity (e.g. 'Name II'), typical of a fund series"
    return "operating_company", "name does not look like an investment vehicle"
