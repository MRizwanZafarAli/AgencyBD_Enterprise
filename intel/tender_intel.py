"""
Enterprise Procurement & Tender Intelligence:
- Go / No-Go Bid Scorecard (Scope Fit, Eligibility, Timeline Feasibility, SME Accessibility)
- Mega-Tender Subcontractor / Teaming Detection (> £2M/€2M/$2M)
- Pre-Market PIN Early Access & Award Renewal / Incumbent Tracking
- 1-Click Compliance & Requirements Matrix
- Bid Studio Artifacts (Executive Summary & Bid Outline, Formal Clarification Q&A)
- Lightweight EU Procurement Title Translator
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

from radar.fit import agency_profile_terms, score_opportunity

CERT_PATTERNS = [
    ("ISO 27001", re.compile(r"\biso\s*27001\b", re.I)),
    ("Cyber Essentials", re.compile(r"\bcyber\s*essentials\b", re.I)),
    ("SOC 2", re.compile(r"\bsoc\s*2\b", re.I)),
    ("GDPR / UK GDPR", re.compile(r"\bgdpr\b", re.I)),
    ("WCAG 2.1 AA", re.compile(r"\bwcag\b|accessibility", re.I)),
    ("SAM.gov Registration", re.compile(r"\bsam\.gov\b|uei\b|cage\b", re.I)),
    ("Security Clearance", re.compile(r"\bsecurity clearance\b|bpss\b|sc cleared\b", re.I)),
]

WEIGHT_RE = re.compile(r"(\d{1,3})\s*%\s*(technical|quality|price|commercial|social value|cost)", re.I)
WORD_LIMIT_RE = re.compile(r"(\d{3,5})\s*(words?|pages?)\s*(limit|max|maximum)?", re.I)

EU_GLOSSARY = {
    "procedura aperta": "Open Procedure",
    "procedura ristretta": "Restricted Procedure",
    "affidamento": "Contract Award",
    "servizi di sviluppo": "Development Services",
    "servizi informatici": "IT Services",
    "servizi": "Services",
    "manutenzione": "Maintenance",
    "piattaforma": "Platform",
    "sistema informativo": "Information System",
    "appalto": "Public Contract",
    "avviso di preinformazione": "Prior Information Notice (PIN)",
    "avis de marché": "Contract Notice",
    "services informatiques": "IT Services",
    "développement": "Development",
    "offene verfahren": "Open Procedure",
    "it-dienstleistungen": "IT Services",
    "softwareentwicklung": "Software Development",
    "licitación": "Public Tender",
    "servicios informáticos": "IT Services",
}


def _days_until(iso_str: Optional[str]) -> Optional[int]:
    if not iso_str:
        return None
    try:
        clean = iso_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean[:19] if len(clean) >= 19 and "T" in clean else clean[:10])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int((dt - datetime.now(timezone.utc)).total_seconds() // 86400)
    except Exception:
        return None


def translate_tender_title(title: str, lang: str = "") -> Dict[str, str]:
    """Translate common EU procurement terms into readable English."""
    out = title or ""
    for src, dst in EU_GLOSSARY.items():
        out = re.sub(re.escape(src), dst, out, flags=re.I)
    changed = out.lower() != (title or "").lower()
    return {
        "original": title,
        "translated": out,
        "language": lang or "auto",
        "was_translated": "true" if changed else "false",
    }


def evaluate_bid_scorecard(opp: Dict[str, Any], org_id: str) -> Dict[str, Any]:
    """Evaluate a tender against agency profile and return a 4-point Go / No-Go Bid Scorecard."""
    title = opp.get("title") or ""
    desc = opp.get("description") or ""
    meta = opp.get("metadata") or {}
    budget = opp.get("budget_max")
    currency = opp.get("currency") or "GBP"
    deadline = opp.get("deadline")
    stage = (meta.get("notice_stage") or "rfp").lower()

    profile = agency_profile_terms(org_id)
    fit = score_opportunity(title, desc, "tender", budget, profile)
    fit_pct = round((fit.score or 0.5) * 100)
    days_left = _days_until(deadline)

    # 1. Scope Fit
    scope_status = "pass" if fit_pct >= 60 else ("warn" if fit_pct >= 35 else "fail")
    scope_note = (
        f"{fit_pct}% match against declared agency capabilities"
        + (f" ({', '.join(fit.reasons[:2])})" if fit.reasons else "")
    )

    # 2. Eligibility & Mandatory Barriers
    found_certs = [name for name, pat in CERT_PATTERNS if pat.search(f"{title} {desc}")]
    if "Security Clearance" in found_certs or "SAM.gov Registration" in found_certs:
        elig_status = "warn"
        elig_note = f"Requires {', '.join(found_certs)} — verify entity eligibility before drafting."
    elif found_certs:
        elig_status = "warn"
        elig_note = f"Mentions compliance standards: {', '.join(found_certs)}."
    else:
        elig_status = "pass"
        elig_note = "No restrictive clearance or turnover barriers detected in notice summary."

    # 3. Timeline Feasibility
    if stage == "pin":
        time_status = "pass"
        time_note = "Pre-Market PIN — early engagement window before formal RFP deadline."
    elif days_left is None:
        time_status = "warn"
        time_note = "Rolling / unspecified deadline — confirm submission cut-off on portal."
    elif days_left < 0:
        time_status = "fail"
        time_note = f"Submission window closed {abs(days_left)}d ago."
    elif days_left < 7:
        time_status = "warn"
        time_note = f"Tight turnaround: only {days_left}d left to submit compliant bid."
    else:
        time_status = "pass"
        time_note = f"{days_left} days remaining — sufficient time for bid writing & QA."

    # 4. SME Accessibility & Mega-Tender Teaming
    lots_count = int(meta.get("lots_count") or 1)
    is_mega = bool(budget and float(budget) >= 2_000_000)
    if is_mega and lots_count <= 1:
        sme_status = "warn"
        sme_note = f"Mega-tender ({currency} {int(budget):,}, 1 lot) — pitch as Specialist Subcontractor / Teaming Partner to Tier-1 primes."
    elif is_mega:
        sme_status = "pass"
        sme_note = f"Multi-lot framework ({lots_count} lots) — target a specialist lot or Tier-1 teaming role."
    else:
        sme_status = "pass"
        sme_note = "SME-accessible contract scope & structure."

    checks = [
        {"name": "Scope Fit", "status": scope_status, "detail": scope_note},
        {"name": "Eligibility & Barriers", "status": elig_status, "detail": elig_note},
        {"name": "Timeline Feasibility", "status": time_status, "detail": time_note},
        {"name": "SME Accessibility", "status": sme_status, "detail": sme_note},
    ]

    fails = sum(1 for c in checks if c["status"] == "fail")
    warns = sum(1 for c in checks if c["status"] == "warn")
    if fails > 0:
        verdict = "NO-GO"
    elif warns >= 2 or is_mega:
        verdict = "CONDITIONAL"
    else:
        verdict = "GO"

    return {
        "verdict": verdict,
        "score": fit_pct,
        "days_left": days_left,
        "checks": checks,
        "mega_tender_teaming": {
            "is_mega": is_mega,
            "budget": budget,
            "currency": currency,
            "strategy": "Pitch as Specialist Subcontractor / Teaming Partner to Tier-1 primes" if is_mega else "",
        },
        "pin_early_access": {
            "is_pin": stage == "pin",
            "tip": "Pre-Market Engagement (PIN) — contact the Contracting Authority now to help shape the RFP spec." if stage == "pin" else "",
        },
        "renewal_tracker": {
            "is_award": stage == "award",
            "incumbent": meta.get("incumbent") or "",
            "award_date": meta.get("award_date") or "",
            "tip": "Contract Award Notice — track incumbent & set a re-tender reminder 6 months before expiry." if stage == "award" else "",
        },
    }


def extract_compliance_matrix(opp: Dict[str, Any]) -> Dict[str, Any]:
    """Extract mandatory requirements, evaluation weights, and submission rules into a checklist."""
    title = opp.get("title") or ""
    desc = opp.get("description") or ""
    combined = f"{title}\n{desc}"
    meta = opp.get("metadata") or {}

    items: List[Dict[str, Any]] = [
        {
            "id": "req_portal",
            "category": "Submission",
            "requirement": f"Register and submit via official portal ({opp.get('url') or 'Portal link'}) before deadline.",
            "mandatory": True,
            "weight": "Gate",
        }
    ]

    for name, pat in CERT_PATTERNS:
        if pat.search(combined):
            items.append({
                "id": f"cert_{name.lower().replace(' ', '_')}",
                "category": "Certification",
                "requirement": f"Evidence of {name} compliance or equivalent attestation.",
                "mandatory": True,
                "weight": "Pass/Fail",
            })

    weights = WEIGHT_RE.findall(combined)
    if weights:
        for pct, dim in weights[:4]:
            items.append({
                "id": f"eval_{dim.lower()}",
                "category": "Evaluation Weight",
                "requirement": f"{dim.title()} response scored at {pct}% weighting.",
                "mandatory": True,
                "weight": f"{pct}%",
            })
    else:
        items.append({
            "id": "eval_default",
            "category": "Evaluation Weight",
            "requirement": "Confirm Technical vs. Commercial (Price) split in full tender pack (typically 60% Quality / 40% Price).",
            "mandatory": False,
            "weight": "TBD",
        })

    limits = WORD_LIMIT_RE.findall(combined)
    for num, unit, _ in limits[:3]:
        items.append({
            "id": f"limit_{num}_{unit}",
            "category": "Formatting",
            "requirement": f"Strict response limit: {num} {unit}.",
            "mandatory": True,
            "weight": "Compliance",
        })

    cpvs = meta.get("cpv_codes") or opp.get("skills_required") or []
    if cpvs:
        items.append({
            "id": "cpv_scope",
            "category": "Scope Alignment",
            "requirement": f"Demonstrate 2–3 relevant case studies under {', '.join(str(c) for c in cpvs[:3])}.",
            "mandatory": True,
            "weight": "Scored",
        })

    return {"items": items, "count": len(items)}


def generate_bid_studio_artifact(opp: Dict[str, Any], action: str) -> Dict[str, str]:
    """Generate procurement-specific bid documents (Executive Summary / Bid Outline or Formal Q&A)."""
    title = opp.get("title") or "Public Sector Tender"
    buyer = opp.get("company_name") or "Contracting Authority"
    meta = opp.get("metadata") or {}
    cpvs = ", ".join(str(c) for c in (meta.get("cpv_codes") or opp.get("skills_required") or [])[:3]) or "IT & Digital Services"
    deadline = (opp.get("deadline") or "TBD")[:10]

    if action == "clarification_qa":
        content = (
            f"Subject: Clarification Question — {title}\n"
            f"To: Procurement Team, {buyer}\n\n"
            f"1. Scope & Incumbent Handover: Could the Authority confirm whether there is an incumbent supplier for {cpvs}, "
            f"and whether a structured knowledge-transfer / discovery phase is expected in Month 1?\n"
            f"2. SME & Consortium Participation: Could the Authority confirm whether specialist subcontractors or consortium bids "
            f"are permitted to satisfy specific technical lots without full prime-level turnover thresholds?\n"
            f"3. Evaluation Weighting: Please confirm the sub-weighting for Technical Architecture, Delivery Methodology, and Social Value.\n\n"
            f"(Submit via official portal prior to the Q&A cut-off before {deadline}.)"
        )
        return {"action": action, "title": "Formal Clarification Questions (Q&A)", "content": content}

    content = (
        f"# Executive Summary & Bid Outline\n"
        f"**Tender:** {title}\n"
        f"**Contracting Authority:** {buyer}\n"
        f"**Deadline:** {deadline} | **Classification:** {cpvs}\n\n"
        f"## 1. Executive Summary\n"
        f"Our team brings proven public-sector delivery experience across {cpvs}, combining rapid agile execution with strict "
        f"accessibility (WCAG 2.1 AA), security, and transparent milestone governance for {buyer}.\n\n"
        f"## 2. Technical Approach & Mobilisation (Weeks 1–4)\n"
        f"- Discovery & stakeholder alignment with {buyer} product owners\n"
        f"- Architecture & security compliance sign-off\n"
        f"- Iterative fortnightly sprint demos with measurable KPIs\n\n"
        f"## 3. Risk Mitigation & Social Value\n"
        f"- Zero-downtime cutover plan, automated QA/CI, and full documentation handover\n"
        f"- Measurable local skills, accessibility, and sustainability commitments"
    )
    return {"action": "executive_summary", "title": "Executive Summary & Bid Outline", "content": content}
