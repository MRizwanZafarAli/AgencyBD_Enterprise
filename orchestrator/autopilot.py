"""
Discovery Run: the autonomous loop, built only from steps that produce evidence.

    source  ->  verify the company's website  ->  audit + brief  ->  priority score  ->  contact?  ->  draft for approval

At every step, if something real is missing the run opens a work item for a person and stops for that lead. It never
substitutes a guess: no invented contact, no assumed measurement, no estimated revenue. Drafts go through the same guard chain
as every other message (jurisdiction, suppression, verification, policy) and wait in the approval inbox.
"""

from typing import Any, Callable, Dict, List, Optional

from agents.outreach_drafter import draft_from_brief
from agents.sourcing_agent import SourcingAgent
from database.models import ContactRepository, LeadRepository
from intel.company_brief import CompanyBriefEngine
from intel.lead_priority import score_lead
from net.fetcher import SSRFSecurityError
from workflows.inbox import WorkItemRepository
from workflows.sequence import OutreachSequenceWorkflow, SequenceStep

CHANNELS = ("sec_edgar", "hiring", "local")


class DiscoveryRun:
    def __init__(self, sourcing: Optional[SourcingAgent] = None, workflow: Optional[OutreachSequenceWorkflow] = None):
        self.sourcing = sourcing or SourcingAgent()
        self.workflow = workflow or OutreachSequenceWorkflow()

    def run(self, org_id: str, channel: str = "hiring", query: str = "", location: str = "", limit: int = 5, user: str = "autopilot",
            progress: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        if channel not in CHANNELS:
            raise ValueError(f"channel must be one of {CHANNELS}")
        limit = max(1, min(int(limit), 20))
        log: List[Dict[str, str]] = []
        skipped: List[Dict[str, str]] = []
        errors: List[str] = []

        results: List[Dict[str, Any]] = []

        def note(step: str, message: str) -> None:
            log.append({"step": step, "message": message})
            if progress:
                progress({"log": log[-12:], "processed": len(results)})

        # 1. source (every source verifies the website before a lead exists)
        if channel == "sec_edgar":
            out = self.sourcing.source_sec_edgar_venture(limit=limit, org_id=org_id)
        elif channel == "hiring":
            out = self.sourcing.source_hn_hiring_signals(role_keyword=query or "Engineer", limit=limit, org_id=org_id)
        else:
            out = self._local(query, location, limit, org_id)
        leads, skipped, errors = out["leads"], out["skipped"], out.get("errors", [])
        note("source", f"{len(leads)} companies with a verified website; {len(skipped)} skipped")

        for lead in leads:
            note("lead", f"Checking {lead['company_name']} ({lead['domain']})")
            results.append(self._process(lead, org_id, user, note))
        return {"channel": channel, "sourced": len(leads), "skipped": skipped, "errors": errors,
                "drafts_pending_approval": sum(1 for r in results if r["outcome"] == "draft_pending_approval"),
                "work_items_opened": sum(1 for r in results if r.get("work_item")), "leads": results, "log": log}

    # ------------------------------------------------------------------ pieces

    def _local(self, category: str, city: str, limit: int, org_id: str) -> Dict[str, Any]:
        from intel import local_hunt
        found = local_hunt.hunt(category, city, limit=limit)
        leads, skipped = [], []
        for r in found["results"]:
            if not r.get("domain"):
                skipped.append({"name": r["name"], "reason": f"no website to audit ({r['classification'].replace('_', ' ')}); save it from Local Client Hunt to pitch a new site"})
                continue
            lead = LeadRepository.create_or_get_lead(
                company_name=r["name"], domain=r["domain"], phone=r.get("phone"), address=r.get("address"), rating=r.get("rating") or 0.0,
                reviews_count=r.get("reviews") or 0, source_channel="google_maps", source_query=f"{category} in {city}",
                notes=f"WEB PRESENCE: {r['classification']}", org_id=org_id)
            leads.append(lead)
        return {"leads": leads, "skipped": skipped, "errors": []}

    def prepare_lead(self, lead: Dict[str, Any], org_id: str, user: str, country_code: Optional[str] = None) -> Dict[str, Any]:
        """Runs the per-lead steps (audit, score, contact check, draft for approval) for one existing lead."""
        return self._process(lead, org_id, user, lambda *a: None, country_code)

    def _process(self, lead: Dict[str, Any], org_id: str, user: str, note, country_override: Optional[str] = None) -> Dict[str, Any]:
        lead_id, name, domain = lead["id"], lead["company_name"], lead["domain"]
        out: Dict[str, Any] = {"lead_id": lead_id, "company_name": name, "domain": domain, "outcome": "", "work_item": None}

        company_id = lead.get("company_id") or self._company_id(org_id, domain, name)
        try:
            brief = CompanyBriefEngine.generate_brief(company_id, org_id, refresh=True)
        except SSRFSecurityError:
            out["outcome"] = "skipped_unsafe_target"
            return out
        except Exception as exc:
            out["outcome"] = "audit_failed"
            out["reason"] = str(exc)[:160]
            out["work_item"] = WorkItemRepository.add(org_id, "review_lead", f"Audit failed for {name}", str(exc)[:300], "lead", lead_id, 30, f"audit_failed:{lead_id}")["id"]
            return out
        out["audit_status"] = brief.get("status")
        if brief.get("status") == "unreachable":
            note("audit", f"{name}: site unreachable from our servers (not proof it is down)")
        elif brief.get("status") == "blocked":
            note("audit", f"{name}: site refuses automated access, so its pages were not graded")

        score = score_lead(lead_id, org_id)
        out.update(priority=score["score"], band=score["band"], reasons=score["reasons"])
        note("score", f"{name}: priority {score['score']} ({score['band']})")

        contacts = [c for c in ContactRepository.get_contacts_by_lead(lead_id, org_id) if c["verification_status"] == "verified"]
        if not contacts:
            item = WorkItemRepository.add(org_id, "find_contact", f"Find a decision maker at {name}",
                                          f"{domain} audited; priority {score['score']} ({score['band']}). No verified contact on file. {self._contact_hint(domain)}",
                                          "lead", lead_id, min(95, 40 + score["score"] // 2), f"contact:{lead_id}")
            out.update(outcome="needs_contact", work_item=item["id"])
            return out

        contact = contacts[0]
        draft = draft_from_brief(brief, contact["first_name"], domain)
        if not draft:
            item = WorkItemRepository.add(org_id, "review_lead", f"Review {name}: nothing specific to say yet",
                                          "The audit produced no medium-or-higher measured finding to base an email on.", "lead", lead_id, 25, f"review:{lead_id}")
            out.update(outcome="nothing_to_say", work_item=item["id"])
            return out

        country = country_override or contact.get("country_code") or lead.get("country_code")
        res = self.workflow.execute_step(org_id=org_id, recipient_email=contact["email"], country_code=country, lead_id=lead_id,
                                         recipient_name=contact["first_name"], company_name=name, created_by=user,
                                         step=SequenceStep(step_number=1, delay_days=0, subject=draft["subject"], body=draft["body"]))
        out.update(outcome="draft_pending_approval" if res.status == "pending_approval" else res.status, reason=res.reason, draft_id=res.draft_id)
        if res.status == "blocked_by_policy":
            item = WorkItemRepository.add(org_id, "review_lead", f"Outreach to {name} was blocked",
                                          res.reason or "Blocked by policy", "lead", lead_id, 45, f"blocked:{lead_id}")
            out["work_item"] = item["id"]
        return out

    @staticmethod
    def _contact_hint(domain: str) -> str:
        """What the company's own pages publish, as a pointer for whoever picks up the task (never saved as a contact)."""
        from intel.contacts import find_contacts
        try:
            found = find_contacts(domain)["candidates"]
        except Exception:
            return ""
        people = [f"{c['name']} ({c['title']})" for c in found if c["kind"] == "person"][:3]
        generic = [c["email"] for c in found if c["kind"] != "person"][:2]
        if not people and not generic:
            return "The site publishes no people or emails."
        return "The site publishes: " + "; ".join(filter(None, [", ".join(people), ", ".join(generic)])) + ". Open the client to review."

    @staticmethod
    def _company_id(org_id: str, domain: str, name: str) -> int:
        from database.models import CompanyRepository
        return CompanyRepository.create_or_get(name=name, domain=domain, org_id=org_id)["id"]
