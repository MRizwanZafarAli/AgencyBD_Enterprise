"""
LLM reasoning that sits BESIDE the deterministic scores, never replaces them, and is grounded:

  analyze_fit        "should we chase this job?" The model must support each point with an exact quote from the job post.
                     Quotes that do not appear in the post are dropped, so a point it cannot back up never reaches the UI.
  summarize_brief    A plain-English summary of a company brief. Each sentence must cite evidence ids that exist in the brief;
                     sentences without valid citations are dropped.
"""

import re
from typing import Any, Dict, List

from config.honesty import PreconditionFailedError
from config.settings import settings
from database.models import OpportunityRepository
from llm.client import LLMGateway
from portfolio.library import PortfolioLibrary


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w$€£%.,/ -]", " ", (text or "").lower())).strip()


def verify_quotes(points: List[Dict[str, Any]], source_text: str) -> List[Dict[str, Any]]:
    haystack = _norm(source_text)
    kept = []
    for p in points or []:
        quote = _norm(str(p.get("quote", "")))
        if len(quote) >= 8 and quote in haystack and str(p.get("point", "")).strip():
            kept.append({"point": str(p["point"]).strip(), "quote": str(p["quote"]).strip()})
    return kept


FIT_SYSTEM = (
    "You advise a software agency on whether to pursue a job post. Use ONLY the job post and the agency facts given. "
    "Every item in `reasons` and `risks` needs a `quote`: an exact, contiguous excerpt (8+ characters) copied from the job post "
    "that supports it. If the post does not support a point, leave the point out. Do not guess budgets, company size or intent."
)


def analyze_fit(opportunity_id: int, org_id: str) -> Dict[str, Any]:
    opp = OpportunityRepository.get_opportunity(opportunity_id, org_id)
    if not opp:
        raise LookupError("Opportunity not found")
    assets = PortfolioLibrary.list_assets(org_id)
    services = ", ".join(settings.agency.core_services) or "(not set)"
    cases = "\n".join(f"- {a['title']} ({a.get('industry') or 'n/a'})" for a in assets[:12]) or "(no case studies on file)"
    post = f"{opp['title']}\n{opp.get('description') or ''}"
    prompt = (
        f"AGENCY: {settings.agency.name}. Services: {services}.\nPORTFOLIO:\n{cases}\n\nJOB POST (source: {opp.get('source')})\n{post[:6000]}\n\n"
        'Return JSON: {"verdict": "pursue"|"maybe"|"skip", "summary": str (<=40 words), '
        '"reasons": [{"point": str, "quote": str}], "risks": [{"point": str, "quote": str}], '
        '"questions_to_ask": [str] (<=4, to clarify scope or budget)}')
    out = LLMGateway.complete_json(prompt, system=FIT_SYSTEM, agent_name="FitAnalyst", org_id=org_id, max_tokens=900)
    data = out["data"]
    verdict = data.get("verdict") if data.get("verdict") in ("pursue", "maybe", "skip") else "maybe"
    reasons, risks = verify_quotes(data.get("reasons"), post), verify_quotes(data.get("risks"), post)
    dropped = (len(data.get("reasons") or []) + len(data.get("risks") or [])) - (len(reasons) + len(risks))
    return {"opportunity_id": opportunity_id, "verdict": verdict, "summary": str(data.get("summary", ""))[:400],
            "reasons": reasons, "risks": risks, "questions_to_ask": [str(q) for q in (data.get("questions_to_ask") or [])][:4],
            "unsupported_points_dropped": dropped, "deterministic_fit_score": opp.get("fit_score"), "model": out.get("model"),
            "note": "Points are shown only when backed by a quote from the job post. The deterministic score is the ranking authority."}


SUMMARY_SYSTEM = (
    "Summarise a company brief for a salesperson. Use ONLY the evidence items given. Write at most 5 short sentences. "
    "Every sentence must list the ids of the evidence items that support it. Never add facts that are not in the evidence."
)


def summarize_brief(brief: Dict[str, Any], org_id: str) -> Dict[str, Any]:
    evidence = brief.get("evidence") or []
    if not evidence:
        raise PreconditionFailedError("no_evidence", "This brief has no stored evidence yet. Refresh the brief first.")
    lines = "\n".join(f"[{e['id']}] {e['claim']} = {str(e.get('value'))[:160]}" for e in evidence[:40])
    prompt = (f"COMPANY: {brief.get('company', {}).get('name') if isinstance(brief.get('company'), dict) else brief.get('company_name', '')}\n"
              f"EVIDENCE:\n{lines}\n\nReturn JSON: {{\"sentences\": [{{\"text\": str, \"evidence_ids\": [int]}}], "
              f"\"best_pitch\": {{\"text\": str, \"evidence_ids\": [int]}}}}")
    out = LLMGateway.complete_json(prompt, system=SUMMARY_SYSTEM, agent_name="BriefSummarizer", org_id=org_id, max_tokens=700)
    valid = {e["id"] for e in evidence}

    def keep(item: Any):
        ids = [i for i in (item or {}).get("evidence_ids", []) if i in valid]
        return {"text": str(item["text"]).strip(), "evidence_ids": ids} if ids and str(item.get("text", "")).strip() else None

    sentences = [s for s in (keep(x) for x in out["data"].get("sentences") or []) if s]
    pitch = keep(out["data"].get("best_pitch"))
    return {"sentences": sentences, "best_pitch": pitch, "model": out.get("model"),
            "dropped": len(out["data"].get("sentences") or []) - len(sentences),
            "note": "Sentences without valid evidence citations were removed."}
