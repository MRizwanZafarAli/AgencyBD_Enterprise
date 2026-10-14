"""
SwarmEngine: Central Multi-Agent Orchestrator for AgencyBD_Enterprise.
Coordinates all 8 micro-agents through a robust state machine with persistent DB tracking.
"""

from typing import Dict, Any, List, Optional
from database.db import init_db, get_db
from database.models import (
    LeadRepository, AuditRepository, ContactRepository,
    OutreachRepository, ReplyRepository, BookingRepository
)
from agents.sourcing_agent import SourcingAgent
from agents.tech_audit_agent import TechAuditAgent
from agents.enrichment_agent import EnrichmentAgent
from agents.dossier_agent import DossierAgent
from agents.copywriter_agent import CopywriterAgent
from agents.dispatch_agent import DispatchAgent
from agents.objection_agent import ObjectionAgent
from agents.booking_agent import BookingAgent
from agents.linkedin_agent import LinkedInAgent
from agents.site_crawler_agent import SiteCrawlerAgent
from agents.future_gtm_agent import FutureGTMAgent
from agents.deliverability_sentinel import DeliverabilitySentinelAgent
from agents.spintax_copywriter import SpintaxCopywriterAgent
from agents.waterfall_enrichment import WaterfallEnrichmentAgent
from agents.crm_relay_agent import CRMRelayAgent
from agents.hitl_approval_gate import HITLApprovalGateAgent
from database.security_vault import SecurityVault
from config.honesty import NotConfiguredError, PreconditionFailedError

class SwarmEngine:
    """
    Enterprise Orchestration Controller managing the entire autonomous BD pipeline.
    """

    def __init__(self):
        init_db()
        self.sourcing_agent = SourcingAgent()
        self.audit_agent = TechAuditAgent()
        self.enrichment_agent = EnrichmentAgent()
        self.dossier_agent = DossierAgent()
        self.copywriter_agent = CopywriterAgent()
        self.dispatch_agent = DispatchAgent()
        self.objection_agent = ObjectionAgent()
        self.booking_agent = BookingAgent()
        self.linkedin_agent = LinkedInAgent()
        self.site_crawler_agent = SiteCrawlerAgent()
        self.future_gtm_agent = FutureGTMAgent()
        self.sentinel_agent = DeliverabilitySentinelAgent()
        self.spintax_agent = SpintaxCopywriterAgent()
        self.waterfall_agent = WaterfallEnrichmentAgent()
        self.crm_agent = CRMRelayAgent()
        self.hitl_agent = HITLApprovalGateAgent()
        self.vault = SecurityVault()

    # --- Step 1: Sourcing ---
    def source_leads(self, channel: str = "google_maps", query: str = "luxury home renovation", location: str = "Austin, TX", limit: int = 10, org_id: str = "org_default") -> List[Dict[str, Any]]:
        if channel == "google_maps":
            return self.sourcing_agent.source_google_maps(query=query, location=location, limit=limit, org_id=org_id)
        elif channel == "hiring_intent":
            return self.sourcing_agent.source_hiring_signals(role_keyword=query, limit=limit, org_id=org_id)
        elif channel == "venture_database":
            return self.sourcing_agent.source_venture_directory(funding_stage=query, limit=limit, org_id=org_id)
        elif channel == "linkedin_company_search":
            return self.linkedin_agent.search_companies(keyword=query, location=location, limit=limit, org_id=org_id)
        else:
            raise ValueError(f"Unknown sourcing channel: {channel}")

    # --- LinkedIn People Search & Sequences ---
    def source_linkedin_people(self, company_name: str, titles: Optional[List[str]] = None, location: str = "United States", limit: int = 5) -> List[Dict[str, Any]]:
        return self.linkedin_agent.search_people(company_name=company_name, titles=titles, location=location, limit=limit)

    def generate_linkedin_outreach(self, first_name: str, company_name: str, trigger_hook: str) -> Dict[str, str]:
        return self.linkedin_agent.generate_linkedin_sequence(first_name=first_name, company_name=company_name, trigger_hook=trigger_hook)

    # --- Live Website Contact Crawler ---
    def crawl_website_for_contacts(self, domain: str) -> Dict[str, Any]:
        return self.site_crawler_agent.crawl_domain(domain=domain)

    # --- Next-Gen & Future GTM Paradigms (RB2B, Retell AI, Tavus) ---
    def deanonymize_visitor(self, ip_address: str = "198.51.100.42", visited_path: str = "/pricing", org_id: str = "org_default") -> Dict[str, Any]:
        return self.future_gtm_agent.deanonymize_website_visitor(ip_address=ip_address, visited_path=visited_path, org_id=org_id)

    def generate_voice_call_pathway(self, lead_id: int) -> Dict[str, Any]:
        return self.future_gtm_agent.generate_voice_call_pathway(lead_id=lead_id)

    def generate_video_pitch_spec(self, lead_id: int) -> Dict[str, Any]:
        return self.future_gtm_agent.generate_video_pitch_spec(lead_id=lead_id)

    # --- Enterprise Hardening: Deliverability Sentinel & Circuit Breaker ---
    def audit_deliverability_fleet(self) -> List[Dict[str, Any]]:
        return self.sentinel_agent.run_fleet_health_audit()

    def test_circuit_breaker(self, inbox: str, sent: int, bounced: int) -> Dict[str, Any]:
        return self.sentinel_agent.evaluate_circuit_breaker(inbox, sent, bounced)

    # --- Enterprise Hardening: Semantic Spintax Copywriting ---
    def generate_spintax_copy(self, lead_id: int) -> Dict[str, Any]:
        lead = LeadRepository.get_lead(lead_id)
        audit = AuditRepository.get_audit_by_lead(lead_id)
        contacts = ContactRepository.get_contacts_by_lead(lead_id)
        first_name = contacts[0]["first_name"] if contacts else "Founder"
        if not audit:
            raise PreconditionFailedError("audit_required", "Run a Website Doctor audit first: outreach may only cite measured facts.")
        lcp = audit["lcp_score"]
        stack = audit["tech_stack"][0] if audit.get("tech_stack") else "your current stack"
        return self.spintax_agent.generate_unique_sequence(
            first_name=first_name,
            company=lead["company_name"],
            domain=lead["domain"],
            lcp=lcp,
            stack=stack
        )

    # --- Enterprise Hardening: Multi-Vendor Waterfall Enrichment ---
    def run_waterfall_enrichment(self, lead_id: int, title: str = "Chief Technology Officer") -> Dict[str, Any]:
        lead = LeadRepository.get_lead(lead_id)
        return self.waterfall_agent.execute_waterfall(
            lead_id=lead_id,
            company_name=lead["company_name"],
            domain=lead["domain"],
            executive_title=title
        )

    # --- Enterprise Hardening: CRM & Webhook Relay ---
    def sync_crm(self, lead_id: int, stage: str = "meeting_scheduled", amount: float = 25000.0) -> Dict[str, Any]:
        lead = LeadRepository.get_lead(lead_id)
        return self.crm_agent.sync_to_hubspot(lead_id, lead["company_name"], lead["domain"], stage, amount)

    def send_slack_notification(self, title: str, details: Dict[str, Any]) -> Dict[str, Any]:
        return self.crm_agent.dispatch_slack_alert("#agency-pipeline-deals", "PIPELINE_DEAL", title, details)

    # --- Enterprise Hardening: Tiered Human-in-the-Loop Governance ---
    def route_governance_tier(self, lead_id: int, deal_val: float = 25000.0) -> Dict[str, Any]:
        return self.hitl_agent.route_for_approval_or_autopilot(lead_id, deal_val)

    def approve_held_lead(self, lead_id: int) -> Dict[str, Any]:
        return self.hitl_agent.approve_lead_dispatch(lead_id)

    # --- Step 2: Tech Audit ---
    def audit_lead(self, lead_id: int) -> Dict[str, Any]:
        return self.audit_agent.audit_lead(lead_id)

    # --- Step 3: Enrichment ---
    def enrich_lead(self, lead_id: int) -> Dict[str, Any]:
        return self.enrichment_agent.enrich_lead(lead_id)

    # --- Step 4: Executive Dossier ---
    def generate_dossier(self, lead_id: int) -> Dict[str, Any]:
        return self.dossier_agent.generate_dossier(lead_id)

    # --- Step 5: Copywriting ---
    def generate_copywriting(self, lead_id: int) -> Dict[str, Any]:
        return self.copywriter_agent.generate_sequence(lead_id)

    # --- Step 6: Dispatch ---
    def dispatch_lead(self, lead_id: int) -> Dict[str, Any]:
        return self.dispatch_agent.dispatch_lead(lead_id)

    # --- Step 7: Inbound Objection Triage ---
    def triage_reply(self, lead_id: int, reply_text: str) -> Dict[str, Any]:
        return self.objection_agent.draft_rebuttal(lead_id, reply_text)

    # --- Step 8: Meeting Booking ---
    def book_meeting(self, lead_id: int, booking_time: str, cal_link: Optional[str] = None) -> Dict[str, Any]:
        return self.booking_agent.book_meeting(lead_id, booking_time, cal_link)

    # --- Full Automated Pipeline for a Single Lead ---
    def run_autonomous_pipeline(self, lead_id: int) -> Dict[str, Any]:
        """
        Runs Audit -> Enrich -> Copywrite -> Dispatch sequentially for a lead.
        """
        audit = self.audit_lead(lead_id)
        contact = self.enrich_lead(lead_id)
        dossier = self.generate_dossier(lead_id)
        outreach = self.generate_copywriting(lead_id)
        dispatch = self.dispatch_lead(lead_id)

        return {
            "lead_id": lead_id,
            "pipeline_status": "dispatched" if dispatch.get("status") == "sent" else "ready_for_review",
            "audit": audit,
            "decision_maker": contact,
            "dossier": dossier,
            "outreach": outreach,
            "dispatch": dispatch
        }

    # --- System Metrics ---
    def get_pipeline_metrics(self, org_id: str = "org_default") -> Dict[str, Any]:
        """Pipeline KPIs for a single tenant."""
        def count(cursor, sql: str) -> int:
            cursor.execute(sql, (org_id,))
            return cursor.fetchone()[0]

        with get_db() as conn:
            cursor = conn.cursor()
            total_leads = count(cursor, "SELECT COUNT(*) FROM leads WHERE org_id = ?")

            cursor.execute("SELECT status, COUNT(*) FROM leads WHERE org_id = ? GROUP BY status", (org_id,))
            status_counts = dict(cursor.fetchall())

            total_audited = count(cursor, "SELECT COUNT(*) FROM tech_audits WHERE org_id = ?")
            total_verified_emails = count(cursor, "SELECT COUNT(*) FROM decision_makers WHERE verification_status = 'valid' AND org_id = ?")
            total_sent = count(cursor, "SELECT COUNT(*) FROM outreach_sequences WHERE status = 'sent' AND org_id = ?")
            total_replies = count(cursor, "SELECT COUNT(*) FROM inbound_replies WHERE org_id = ?")
            total_booked = count(cursor, "SELECT COUNT(*) FROM meeting_bookings WHERE org_id = ?")

            reply_rate = round((total_replies / total_sent * 100), 1) if total_sent > 0 else 0.0
            booking_rate = round((total_booked / total_sent * 100), 1) if total_sent > 0 else 0.0

            # Pipeline value (assumes an average agency deal size of $25,000)
            pipeline_value = total_booked * 25000 + (status_counts.get("replied", 0) * 12500)

            return {
                "total_leads": total_leads,
                "status_breakdown": status_counts,
                "total_audited": total_audited,
                "total_verified_emails": total_verified_emails,
                "total_sent": total_sent,
                "total_replies": total_replies,
                "total_booked": total_booked,
                "reply_rate_percent": reply_rate,
                "booking_rate_percent": booking_rate,
                "estimated_pipeline_value_usd": pipeline_value
            }
