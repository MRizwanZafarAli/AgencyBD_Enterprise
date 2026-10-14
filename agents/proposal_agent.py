"""
Proposal Studio.

Drafts two *different* proposals for an opportunity, grounded in (1) the stored job post and
(2) the agency's own case studies, then mechanically verifies every figure and past-work claim
(see proposals/verifier.py). Only verified drafts reach the human Approval Inbox.

Real-mode requirements: a language model (ANTHROPIC_API_KEY) and at least one portfolio asset.
"""

import json
from typing import Any, Dict, List, Optional

from config.honesty import NotConfiguredError, PreconditionFailedError
from config.settings import settings
from database.models import OpportunityRepository, ProposalRepository
from llm.client import LLMGateway
from portfolio.library import PortfolioLibrary
from proposals.verifier import verify_proposal, VerificationReport

PROMPT_VERSION = "v3_grounded_verified"
VARIANT_FOCUS = {
    "A": "Technical depth: show you understand the architecture and risks; speak to an engineering lead.",
    "B": "Business outcome and speed: lead with the result and timeline; speak to a non-technical decision maker.",
}

SYSTEM = (
    "You write proposals for a software agency. You may state facts ONLY if they appear in the JOB POST or in a "
    "numbered CASE STUDY below. Never invent clients, projects, metrics, tools or timelines. If no case study fits, "
    "do not claim past work. Every sentence that describes something the agency did must be listed in `claims` with "
    "its source ('job' or 'asset:<id>') and must paraphrase text from that source. Copy figures exactly. "
    "No placeholders, no greeting like 'Hi there' without a name, 90-170 words, one clear low-friction next step."
)


def _build_prompt(title: str, description: str, client: Optional[str], assets: List[Dict[str, Any]], feedback: str = "") -> str:
    case_block = "\n\n".join(f"[CASE STUDY asset:{a['id']}] {a['title']} ({a.get('industry') or 'n/a'})\n{a['body']}" for a in assets) \
        or "(none relevant: do not claim any past work)"
    profile = f"Agency: {settings.agency.name}. Contact: {settings.agency.founder_name}. Booking link: {settings.agency.booking_link}"
    return (
        f"{profile}\n\nJOB POST\nTitle: {title}\nClient: {client or 'unknown'}\n{description}\n\n{case_block}\n\n"
        f"Write TWO proposals that differ in structure and emphasis.\n"
        f"Variant A: {VARIANT_FOCUS['A']}\nVariant B: {VARIANT_FOCUS['B']}\n\n"
        f"Return JSON: {{\"variant_a\": {{\"body\": str, \"claims\": [{{\"text\": str, \"source\": str}}]}}, "
        f"\"variant_b\": {{\"body\": str, \"claims\": [...]}}}}\n"
        + (f"\nYour previous attempt was rejected for these reasons; fix them:\n{feedback}\n" if feedback else "")
    )


def _similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


class ProposalAgent:
    @classmethod
    def draft_proposal(
        cls,
        opportunity_id: int,
        org_id: str = "org_default",
        title: Optional[str] = None,        # accepted for backwards compatibility; the stored opportunity wins
        description: Optional[str] = None,
        client_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        opp = OpportunityRepository.get_opportunity(opportunity_id, org_id)
        if not opp:
            raise LookupError("Opportunity not found")
        job_title = opp["title"]
        job_text = f"{opp['title']}\n{opp.get('description') or ''}"

        if not PortfolioLibrary.list_assets(org_id):
            raise PreconditionFailedError(
                "portfolio_empty",
                "Add at least one real case study to your portfolio first (POST /api/portfolio/assets). "
                "Proposals may only cite work you have actually done.")

        hits = PortfolioLibrary.search(org_id, job_text, k=3)
        assets = [a for a, _ in hits]
        asset_texts = {a["id"]: f"{a['title']} {a['body']} {json.dumps(a.get('metrics') or {})}" for a in assets}
        profile_text = f"{settings.agency.name} {settings.agency.founder_name} {settings.agency.booking_link}"

        feedback, attempts, drafts, reports, model_used = "", 0, {}, {}, None
        for attempts in (1, 2):
            out = LLMGateway.complete_json(
                _build_prompt(job_title, opp.get("description") or "", client_name, assets, feedback),
                system=SYSTEM, agent_name="ProposalStudio", org_id=org_id, temperature=0.4, max_tokens=1600)
            model_used = out["model"]
            data = out["data"]
            drafts, reports = {}, {}
            for key, label in (("variant_a", "A"), ("variant_b", "B")):
                v = data.get(key) or {}
                body = str(v.get("body", "")).strip()
                drafts[label] = {"body": body, "claims": v.get("claims") or []}
                reports[label] = verify_proposal(body, drafts[label]["claims"], job_text, asset_texts, profile_text)
            if _similarity(drafts["A"]["body"], drafts["B"]["body"]) > 0.8:
                for r in reports.values():
                    r.violations.append("Variants are nearly identical; they must differ in structure and emphasis.")
                    r.ok = False
            if all(r.ok for r in reports.values()):
                break
            feedback = "\n".join(f"- Variant {k}: {v}" for k, r in reports.items() for v in r.violations)

        proposal_ids, variants_out = {}, {}
        cited = [a["id"] for a in assets]
        for label in ("A", "B"):
            report: VerificationReport = reports[label]
            rec = ProposalRepository.create_proposal(
                opportunity_id=opportunity_id, body=drafts[label]["body"], variant=label, model=model_used,
                prompt_version=PROMPT_VERSION, org_id=org_id,
                status="draft" if report.ok else "needs_edit",
                verification=report.to_dict(), cited_asset_ids=cited,
                queue_for_approval=report.ok)
            proposal_ids[label] = rec["id"]
            variants_out[label] = {"proposal_id": rec["id"], "body": drafts[label]["body"], "focus": VARIANT_FOCUS[label].split(":")[0],
                                   "model": model_used, "verification": report.to_dict(), "queued_for_approval": report.ok}

        any_ok = any(r.ok for r in reports.values())
        return {
            "status": "pending_human_approval" if any_ok else "verification_failed",
            "opportunity_id": opportunity_id,
            "proposal_id": proposal_ids["A"],
            "proposal_ids": proposal_ids,
            "variant_a": variants_out["A"],
            "variant_b": variants_out["B"],
            "cited_assets": [{"id": a["id"], "title": a["title"], "relevance": round(s, 3)} for a, s in hits],
            "no_relevant_proof": not hits,
            "attempts": attempts,
        }
