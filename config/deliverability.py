"""
Email Deliverability Engine & Spam Guard Configuration.
Contains high-risk trigger dictionaries, domain rotation pools, and hygiene scoring.
"""

import re
from typing import Dict, List, Tuple

# Comprehensive list of high-risk spam triggers categorized by psychological/financial vectors
SPAM_TRIGGER_WORDS: set[str] = {
    # Financial & Hyperbolic Claims
    "100% free", "free cash", "make money fast", "risk free", "guaranteed income",
    "double your income", "earn $", "hidden assets", "millionaire", "billionaire",
    "no cost", "pennies a day", "pure profit", "unsecured credit", "work from home",
    "financial freedom", "unlimited earnings", "cash prize", "lowest price",
    
    # High-pressure Urgency
    "act now", "apply now", "call now", "urgent", "don't hesitate",
    "instant access", "limited time offer", "once in a lifetime", "exclusive deal",
    "take action today", "expires today", "final notice", "immediate response",
    
    # Deceptive & Manipulative
    "not spam", "this isn't a scam", "as seen on tv", "no catch", "no gimmicks",
    "no obligation", "no experience necessary", "dear friend", "congratulations",
    "winner", "you have been selected", "satisfaction guaranteed", "miracle",
    
    # Sensitive Marketing / Phishing patterns
    "click here", "click below", "order now", "buy now", "special promotion",
    "credit check", "refinance", "debt elimination", "passwords", "social security"
}

SECONDARY_SENDING_DOMAINS = [
    {"domain": "reach-apexcore.io", "inbox": "alex@reach-apexcore.io", "daily_limit": 35, "sent_today": 12, "warmup_days": 45, "spf_valid": True, "dkim_valid": True, "dmarc_valid": True},
    {"domain": "get-apexcore.com", "inbox": "alex@get-apexcore.com", "daily_limit": 35, "sent_today": 18, "warmup_days": 60, "spf_valid": True, "dkim_valid": True, "dmarc_valid": True},
    {"domain": "apexcore-labs.dev", "inbox": "team@apexcore-labs.dev", "daily_limit": 30, "sent_today": 8, "warmup_days": 35, "spf_valid": True, "dkim_valid": True, "dmarc_valid": True},
    {"domain": "apexcore-growth.net", "inbox": "outreach@apexcore-growth.net", "daily_limit": 35, "sent_today": 4, "warmup_days": 30, "spf_valid": True, "dkim_valid": True, "dmarc_valid": True},
]

def analyze_spam_friction(subject: str, body: str) -> Tuple[float, List[str], str]:
    """
    Evaluates cold email text against spam heuristics.
    Returns: (spam_score: float, flagged_tokens: List[str], rating: str)
    Score < 1.0 = Pristine / Low Risk
    Score 1.0 - 2.5 = Moderate Risk
    Score > 2.5 = High Risk (Block send)
    """
    combined_text = f"{subject.lower()} {body.lower()}"
    flagged = []
    
    # Check for direct spam trigger words
    for trigger in SPAM_TRIGGER_WORDS:
        if trigger in combined_text:
            flagged.append(trigger)
            
    # Check for excessive uppercase letters
    caps_count = sum(1 for c in subject if c.isupper())
    caps_ratio = caps_count / max(len(subject), 1)
    if caps_ratio > 0.4 and len(subject) > 8:
        flagged.append("EXCESSIVE_CAPS_IN_SUBJECT")
        
    # Check for excessive exclamation marks
    exclamation_count = combined_text.count("!")
    if exclamation_count > 2:
        flagged.append(f"EXCESSIVE_EXCLAMATIONS ({exclamation_count})")
        
    # Check for raw link overload
    link_count = len(re.findall(r"https?://", combined_text))
    if link_count > 2:
        flagged.append(f"LINK_OVERLOAD ({link_count} links)")

    # Score calculation
    base_score = len(flagged) * 0.85
    if "EXCESSIVE_CAPS_IN_SUBJECT" in flagged:
        base_score += 1.2
    if link_count > 2:
        base_score += 1.0
        
    final_score = round(base_score, 2)
    
    if final_score < 1.0:
        rating = "PRISTINE (High Deliverability)"
    elif final_score <= 2.5:
        rating = "MODERATE (Requires Minor Edits)"
    else:
        rating = "CRITICAL (Spam Filter Risk)"
        
    return final_score, flagged, rating
