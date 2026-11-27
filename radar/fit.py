"""
Transparent fit scoring for opportunities.

The score answers one question: "does this look like work our agency does, and is it safe to pursue?" It is built only
from (a) the opportunity text and (b) what the agency has told the system about itself (services catalog, portfolio
tech/services, configured keywords). Every point comes with a plain-language reason, and the risk flags are visible, so
a human can disagree with the machine. With no agency profile there is NO score (None), not a made-up one.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

from database.db import get_db
import json

WORD = re.compile(r"[a-z0-9][a-z0-9+#.\-]{1,}")
STOP = {
    "the", "and", "for", "with", "that", "this", "our", "you", "your", "are", "from", "have", "will", "can", "has", "was",
    "need", "looking", "work", "team", "build", "using", "use", "new", "help", "get", "all", "any", "not", "but", "more", "who",
    "within", "into", "about", "across", "between", "through", "during", "before", "after", "around", "under", "over", "such",
    "their", "there", "these", "those", "other", "which", "where", "while", "would", "should", "could", "being", "having",
    "making", "working", "every", "first", "great", "high", "well", "also", "able", "must", "only", "very", "just", "like",
    "make", "made", "many", "most", "much", "some", "time", "year", "years", "both", "each", "than", "then", "they", "them",
    "what", "when", "how", "why", "its", "per", "via", "etc",
}
# Words so common in every tech job post that matching them says nothing about fit
GENERIC = {
    "development", "developer", "developers", "engineer", "engineers", "engineering", "software", "web", "services", "service",
    "solutions", "senior", "junior", "full", "stack", "fullstack", "remote", "applications", "application", "design", "systems",
    "platform", "company", "projects", "project", "experience", "strong", "skills", "technology", "technologies", "digital",
    "business", "client", "clients", "custom", "modern", "audit", "technical", "analysis", "reporting", "fixes", "core",
    "role", "position", "opportunity", "seeking", "required", "preferred", "including", "based", "support", "ensure",
    "manage", "create", "deliver", "process", "quality", "product", "products", "feature", "features", "growth", "scale",
    "best", "good", "fast", "workflows", "workflow", "performance", "database", "databases", "tools", "tool",
}

RISK_PATTERNS = {
    "off_platform_contact": re.compile(r"\b(whatsapp|telegram|skype id|contact me (at|on)|pay(ment)? outside|outside (of )?(upwork|the platform))\b", re.I),
    "unpaid_or_equity_only": re.compile(r"\b(unpaid|equity only|no (budget|pay)|for exposure|free (trial|test) (task|project)|revenue share only|sweat equity)\b", re.I),
    "unrealistic_timeline": re.compile(r"\b(within (24|48) hours|by tomorrow|in (1|one|2|two) days?|overnight)\b", re.I),
    "scam_signals": re.compile(r"\b(guaranteed returns|crypto airdrop|investment opportunity|wire transfer|gift cards?|send (us )?your (id|passport))\b", re.I),
    "requires_local_presence": re.compile(r"\b(must (be )?(located|based|reside)|on-?site only|us citizens? only|security clearance)\b", re.I),
    "no_agencies_red_flag": re.compile(r"\b(no agencies|no staffing|direct hire only|w2 only|no c2c|no third[- ]party|no recruiters|corp-to-corp not)\b", re.I),
}
RISK_PENALTY = {"off_platform_contact": 0.3, "unpaid_or_equity_only": 0.4, "unrealistic_timeline": 0.15, "scam_signals": 0.6,
                "requires_local_presence": 0.2, "no_agencies_red_flag": 0.25, "vague_scope": 0.1, "below_budget_floor": 0.25}


@dataclass
class FitResult:
    score: Optional[float]
    reasons: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)


def _terms(text: str) -> Set[str]:
    return {w for w in WORD.findall((text or "").lower()) if w not in STOP and w not in GENERIC}


def agency_profile_terms(org_id: str) -> Set[str]:
    """Skills/service words the agency itself has declared (catalog, portfolio, env override). Empty = no profile."""
    terms: Set[str] = {t.strip().lower() for t in os.getenv("AGENCYBD_FIT_KEYWORDS", "").split(",") if t.strip()}
    with get_db() as db:
        for r in db.execute("SELECT name, offer FROM services WHERE org_id = ?", (org_id,)).fetchall():
            terms |= _terms(f"{r['name']} {r['offer']}")
        for r in db.execute("SELECT industry, services_json, tech_json FROM portfolio_assets WHERE org_id = ?", (org_id,)).fetchall():
            terms |= _terms(r["industry"] or "")
            terms |= {t.lower() for t in json.loads(r["services_json"] or "[]")} | {t.lower() for t in json.loads(r["tech_json"] or "[]")}
            terms |= _terms(" ".join(json.loads(r["services_json"] or "[]") + json.loads(r["tech_json"] or "[]")))
    return {t for t in terms if len(t) >= 3}


def score_opportunity(title: str, description: str, opp_type: str, budget_max: Optional[float], profile_terms: Set[str]) -> FitResult:
    text = f"{title}\n{description}"
    flags = [name for name, pat in RISK_PATTERNS.items() if pat.search(text)]
    if len(_terms(description)) < 12 and opp_type != "tender":
        flags.append("vague_scope")
    floor = float(os.getenv("AGENCYBD_MIN_PROJECT_BUDGET", "0") or 0)
    if floor and budget_max is not None and budget_max < floor:
        flags.append("below_budget_floor")

    if not profile_terms:
        return FitResult(None, ["No agency profile yet: add services and portfolio case studies to enable fit scoring."], flags)

    words = _terms(text)
    hits = sorted(words & profile_terms)
    reasons: List[str] = []
    score = min(0.7, 0.15 * len(hits))
    if hits:
        reasons.append("Matches your declared skills/services: " + ", ".join(hits[:8]))
    else:
        reasons.append("Nothing in the post matches your declared skills or services.")
    if budget_max is None:
        reasons.append("No budget stated.")
    elif opp_type == "hiring_signal":
        reasons.append(f"Salary range mentioned (up to {budget_max:,.0f}); that is employee pay, not a project budget.")
    else:
        score += 0.1
        reasons.append(f"Budget stated (up to {budget_max:,.0f}).")
    if opp_type == "tender":
        score += 0.1
        reasons.append("Public tender: formal process, usually larger contracts.")
    elif opp_type == "hiring_signal":
        reasons.append("A hiring post, not a project: the angle is pitching a team to cover the role.")
    for f in flags:
        score -= RISK_PENALTY.get(f, 0.1)
        reasons.append(f"Risk: {f.replace('_', ' ')}.")
    return FitResult(round(max(0.0, min(1.0, score)), 2), reasons, flags)


def feedback_profile(org_id: str) -> dict:
    """Loads persisted thumbs-up/down company and keyword weights for self-learning fit scoring."""
    down_companies: Set[str] = set()
    up_companies: Set[str] = set()
    down_terms: Set[str] = set()
    up_terms: Set[str] = set()
    try:
        with get_db() as db:
            rows = db.execute(
                """
                SELECT f.vote, o.title, o.company_name
                FROM opportunity_feedback f
                JOIN opportunities o ON o.id = f.opportunity_id
                WHERE f.org_id = ?
                """,
                (org_id,),
            ).fetchall()
        for r in rows:
            co = (r["company_name"] or "").strip().lower()
            terms = _terms(r["title"] or "")
            if r["vote"] == "down":
                if co:
                    down_companies.add(co)
                down_terms |= terms
            elif r["vote"] == "up":
                if co:
                    up_companies.add(co)
                up_terms |= terms
    except Exception:
        pass
    return {
        "down_companies": down_companies,
        "up_companies": up_companies,
        "down_terms": down_terms - up_terms,
        "up_terms": up_terms - down_terms,
    }


def apply_feedback_adjustment(fit: FitResult, title: str, company_name: Optional[str], fb: dict) -> FitResult:
    """Adjusts fit_score using persisted thumbs-up/down feedback on company & role terms."""
    if fit.score is None or not fb:
        return fit
    delta = 0.0
    notes: List[str] = []
    co = (company_name or "").strip().lower()
    if co and co in fb.get("down_companies", set()):
        delta -= 0.25
        notes.append(f"Down-ranked: you previously marked {company_name} as not a fit.")
    elif co and co in fb.get("up_companies", set()):
        delta += 0.10
        notes.append(f"Boosted: you previously liked {company_name}.")

    title_terms = _terms(title or "")
    neg_hits = sorted(title_terms & fb.get("down_terms", set()))
    pos_hits = sorted(title_terms & fb.get("up_terms", set()))
    if neg_hits:
        delta -= min(0.25, 0.08 * len(neg_hits))
        notes.append("Down-ranked from 👎 feedback on: " + ", ".join(neg_hits[:4]))
    if pos_hits:
        delta += min(0.15, 0.05 * len(pos_hits))
        notes.append("Boosted from 👍 feedback on: " + ", ".join(pos_hits[:4]))

    if delta == 0.0:
        return fit
    return FitResult(
        round(max(0.0, min(1.0, fit.score + delta)), 2),
        fit.reasons + notes,
        fit.risk_flags,
    )
