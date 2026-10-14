"""
BookingAgent: Discovery Call Conversion, Briefing Generator & CRM Relay.
Prepares executive briefing packs for agency founders before calls and syncs booking records.
"""

from typing import Dict, Any, Optional
from database.models import LeadRepository, ContactRepository, AuditRepository, BookingRepository
from config.settings import settings
from config.honesty import NotConfiguredError, PreconditionFailedError

class BookingAgent:
    """
    Manages final call conversions and compiles a 1-page founder briefing pack
    so the agency partner can close deals effortlessly on discovery calls.
    """

    def book_meeting(self, lead_id: int, booking_time: str, cal_link: Optional[str] = None) -> Dict[str, Any]:
        lead = LeadRepository.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead ID {lead_id} does not exist.")

        audit = AuditRepository.get_audit_by_lead(lead_id)
        contacts = ContactRepository.get_contacts_by_lead(lead_id)
        contact = contacts[0] if contacts else None
        cal_url = cal_link or settings.agency.booking_link

        company = lead["company_name"]
        domain = lead["domain"]
        channel = lead["source_channel"]
        contact_name = f"{contact['first_name']} {contact['last_name']} ({contact['title']})" if contact else "Decision Maker"

        # Generate Founder Executive Brief
        brief = (
            f"=== DISCOVERY CALL PREP BRIEF: {company.upper()} ===\n"
            f"• Scheduled Time: {booking_time}\n"
            f"• Executive Contact: {contact_name} | Email: {contact['email'] if contact else 'N/A'}\n"
            f"• Domain: {domain} (Channel: {channel})\n"
            f"• Core Finding: {audit['calculated_pitch_angle'] if audit else 'No audit on file: ask discovery questions first'}\n"
            f"• Tech Stack: {', '.join(audit['tech_stack']) if (audit and audit.get('tech_stack')) else 'Standard Web'}\n"
            f"• Recommended Close Strategy:\n"
            f"   1. First 3 Mins: Congratulate on recent momentum, confirm their current product sprint priorities.\n"
            f"   2. Mins 4-10: Walk through the live audit breakdown ({str(audit['lcp_score']) + 's LCP' if audit else 'no audit on file; walk through their goals instead'}).\n"
            f"   3. Mins 11-20: Offer a targeted 2-week pilot sprint (Risk-free milestone deliverable).\n"
            f"   4. Mins 21-25: Close on technical scoping session for next Tuesday."
        )

        booking = BookingRepository.create_booking(
            lead_id=lead_id,
            decision_maker_id=contact["id"] if contact else None,
            booking_time=booking_time,
            cal_link=cal_url,
            founder_prep_brief=brief,
            org_id=lead.get("org_id") or "org_default"
        )

        return {
            "booking_id": booking["id"],
            "lead_id": lead_id,
            "status": "booked",
            "company_name": company,
            "booking_time": booking_time,
            "cal_link": cal_url,
            "founder_prep_brief": brief
        }
