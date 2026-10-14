"""
DossierAgent: Executive Intelligence & Pain-Point Synthesizer.
Fuses firmographic data, hiring signals, and technical audit findings into a 1-page tactical dossier.
"""

from typing import Dict, Any, Optional
from database.models import LeadRepository, AuditRepository, ContactRepository
from config.settings import settings
from config.honesty import NotConfiguredError, PreconditionFailedError

class DossierAgent:
    """
    Synthesizes multi-source intelligence to give the agency founder and AI copywriters
    a sharp tactical view of why this prospect must buy now.
    """

    @staticmethod
    def _evidence_only_dossier(lead, audit, contact) -> Dict[str, Any]:
        """Facts we hold, and an explicit 'unknown' for everything we have not measured."""
        findings = []
        if audit:
            findings.append(f"Measured load time {audit['load_time_ms']} ms, TTFB {audit['ttfb_ms']} ms.")
            if audit.get("missing_headers"):
                findings.append("Missing security headers: " + ", ".join(audit["missing_headers"]))
        return {
            "lead_id": lead["id"],
            "company_name": lead["company_name"],
            "domain": lead["domain"],
            "decision_maker": f"{contact['first_name']} {contact['last_name']} ({contact['title']})" if contact else "Unknown (no contact on file)",
            "estimated_revenue": "Unknown (not measured)",
            "estimated_team_size": "Unknown (not measured)",
            "primary_vulnerability": " ".join(findings) if findings else "No audit on file. Run the Website Doctor first.",
            "agency_solution_match": "Decide after reviewing audit findings",
            "calculated_pitch_angle": audit["calculated_pitch_angle"] if audit else "No audit on file",
            "loom_video_concept": None,
            "booking_cta": settings.agency.booking_link,
            "evidence": {"audit_on_file": bool(audit), "contact_on_file": bool(contact)},
        }

    def generate_dossier(self, lead_id: int) -> Dict[str, Any]:
        lead = LeadRepository.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead ID {lead_id} does not exist.")

        audit = AuditRepository.get_audit_by_lead(lead_id)
        contacts = ContactRepository.get_contacts_by_lead(lead_id)
        contact = contacts[0] if contacts else None

        company_name = lead["company_name"]
        domain = lead["domain"]
        channel = lead["source_channel"]
        
        return self._evidence_only_dossier(lead, audit, contact)
