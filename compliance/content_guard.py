"""
Content guard for outreach about security findings.

A version match is not proof of a vulnerability, and frightening a stranger with it is both unfair and a deliverability and
legal risk. Messages must state what was observed, use hedged language ("potentially affected"), and never threaten or claim a
breach. This runs on every outbound message, whatever produced it.
"""

import re
from typing import Optional

FEAR = re.compile(r"\b(hack(?:ed|ers?|ing)?|breach(?:ed|es)?|compromis(?:ed|e)|ransom\w*|exploit(?:ed|able|s)?|attack(?:ed|ers?|s)?|"
                  r"malware|data leak\w*|stolen|your customers.? data is)\b", re.IGNORECASE)
CERTAINTY = re.compile(r"\b(?:you are|your (?:site|website|server)[^.]{0,30} is|is definitely|are definitely)\s+(?:currently\s+)?(?:vulnerable|insecure|unsafe|at risk)\b", re.IGNORECASE)
DEADLINE = re.compile(r"\b(?:fix|act|respond|reply)\s+(?:this|it)?\s*(?:within|before)\s+\d+\s*(?:hours?|days?)\b|\bbefore it'?s too late\b", re.IGNORECASE)


def check_outreach_text(subject: str, body: str) -> Optional[str]:
    """Returns the reason a message must not be sent, or None if it is acceptable."""
    text = f"{subject}\n{body}"
    if (m := FEAR.search(text)):
        return f"Outreach may not use alarming security language ('{m.group(0)}'). State what was observed and that it is potentially affected."
    if (m := CERTAINTY.search(text)):
        return "Outreach may not claim the recipient is definitely vulnerable; a version match only shows potential exposure."
    if DEADLINE.search(text):
        return "Outreach may not pressure the recipient with a deadline about a security issue."
    return None
