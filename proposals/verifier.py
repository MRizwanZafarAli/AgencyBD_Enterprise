"""
Claim verifier for generated proposals.

A proposal may only assert facts that exist in (a) the client's job post, (b) the agency case studies
that were retrieved for this job, or (c) the agency's own profile. The verifier enforces that
mechanically, so a fluent model cannot slip an invented metric or fake past project to a client.

Hard failures (draft is rejected):
  * a number >10, any percentage or money amount that appears in no source
  * a sentence describing past work that is not backed by a cited claim
  * a claim citing an unknown source, or whose text is not supported by that source
  * unfilled placeholders, empty or oversized drafts
Warnings (shown to the reviewer, not blocking): capitalised names that appear in no source.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Any

NUMBER_RE = re.compile(r"[$€£]?\d[\d,]*(?:\.\d+)?%?")
WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#.\-]{2,}")
PAST_WORK_RE = re.compile(
    r"\b(we|our team|our engineers|our agency)\b[^.!?\n]*\b(built|delivered|reduced|improved|migrated|launched|helped|"
    r"increased|cut|saved|scaled|shipped|rebuilt|cutover|deployed|grew)\b|"
    r"\b(case study|our client|for a client|a client of ours|previously|in the past)\b|"
    r"\b(recently|last year|last quarter)\b[^.!?\n]*\bwe\b",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(r"\[[^\]]{0,40}\]|\{\{.*?\}\}|\bTODO\b|\bTBD\b|lorem ipsum", re.IGNORECASE)
PROPER_PHRASE_RE = re.compile(r"\b(?:[A-Z][a-zA-Z0-9]+(?:\s+|$)){2,}")
STOP = {"the", "and", "for", "with", "that", "this", "our", "you", "your", "are", "from", "have", "will", "can", "has", "was",
        "were", "their", "into", "about", "more", "than", "how", "what", "when", "which", "would", "could", "should"}


def _norm_number(token: str) -> str:
    return token.replace(",", "").lstrip("$€£").rstrip("%").rstrip(".")


def numbers_in(text: str) -> set:
    return {_norm_number(t) for t in NUMBER_RE.findall(text) if _norm_number(t)}


def _is_claim_number(token: str) -> bool:
    """Small bare integers (timeline words like '2 weeks') are not factual claims; the rest are."""
    if token.endswith("%") or token[0] in "$€£":
        return True
    value = _norm_number(token)
    try:
        return float(value) > 10 or "." in value
    except ValueError:
        return False


def _tokens(text: str) -> set:
    return {w for w in WORD_RE.findall(text.lower()) if w not in STOP}


@dataclass
class VerificationReport:
    ok: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    numbers_checked: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "violations": self.violations, "warnings": self.warnings, "numbers_checked": self.numbers_checked}


def verify_proposal(
    body: str,
    claims: List[Dict[str, str]],
    job_text: str,
    assets: Dict[int, str],
    profile_text: str = "",
    min_words: int = 30,
    max_words: int = 260,
) -> VerificationReport:
    violations: List[str] = []
    warnings: List[str] = []
    body = (body or "").strip()

    words = len(body.split())
    if words < min_words:
        violations.append(f"Draft is too short ({words} words).")
    if words > max_words:
        violations.append(f"Draft is too long ({words} words; limit {max_words}).")
    if PLACEHOLDER_RE.search(body):
        violations.append("Draft contains an unfilled placeholder.")

    sources: Dict[str, str] = {"job": job_text}
    for aid, text in assets.items():
        sources[f"asset:{aid}"] = text
    allowed_text = " ".join([job_text, profile_text, *assets.values()])
    allowed_numbers = numbers_in(allowed_text)

    # 1. numbers
    checked = 0
    for token in NUMBER_RE.findall(body):
        if not _is_claim_number(token):
            continue
        checked += 1
        if _norm_number(token) not in allowed_numbers:
            violations.append(f"Unsupported figure '{token}': not present in the job post or any cited case study.")

    # 2. claims must cite a real source and be supported by it
    covered_tokens: List[set] = []
    for claim in claims or []:
        text, src = str(claim.get("text", "")), str(claim.get("source", ""))
        if src not in sources:
            violations.append(f"Claim cites unknown source '{src}'.")
            continue
        claim_tokens, src_tokens = _tokens(text), _tokens(sources[src])
        if claim_tokens and len(claim_tokens & src_tokens) / len(claim_tokens) < 0.6:
            violations.append(f"Claim not supported by {src}: \"{text[:80]}\"")
            continue
        if not numbers_in(text) <= numbers_in(sources[src]):
            violations.append(f"Claim contains a figure not found in {src}: \"{text[:80]}\"")
            continue
        covered_tokens.append(claim_tokens)

    # 3. every past-work sentence must be covered by a verified claim
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", body):
        if sentence.strip() and PAST_WORK_RE.search(sentence):
            stoks = _tokens(sentence)
            if not stoks or not any(c and len(stoks & c) / len(stoks) >= 0.5 for c in covered_tokens):
                violations.append(f"Unbacked statement about past work: \"{sentence.strip()[:90]}\"")

    # 4. unknown proper names (advisory)
    lowered = allowed_text.lower()
    for m in PROPER_PHRASE_RE.finditer(body):
        phrase = m.group(0).strip()
        if phrase.lower() not in lowered and len(phrase.split()) >= 2:
            warnings.append(f"Name not found in sources: '{phrase}'")

    return VerificationReport(ok=not violations, violations=violations, warnings=warnings[:8], numbers_checked=checked)
