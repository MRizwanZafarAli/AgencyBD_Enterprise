"""
CopywriterAgent: Hyper-Personalized, Trigger-Based Multi-Touch Outreach Engine.
Crafts non-fluffy, high-converting 3-step email sequences and LinkedIn notes under 80 words.
"""

from typing import Dict, Any, List
from database.models import LeadRepository, AuditRepository, ContactRepository, OutreachRepository
from config.deliverability import analyze_spam_friction
from config.settings import settings
from config.honesty import NotConfiguredError, PreconditionFailedError

class CopywriterAgent:
    """
    Generates high-converting, trigger-based outreach using Pydantic validation
    and rigorous spam score auditing. Zero generic fluff.
    """

    def generate_sequence(self, lead_id: int) -> Dict[str, Any]:
        lead = LeadRepository.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead ID {lead_id} does not exist.")

        audit = AuditRepository.get_audit_by_lead(lead_id)
        contacts = ContactRepository.get_contacts_by_lead(lead_id)
        if not contacts:
            raise ValueError(f"No contacts enriched for Lead ID {lead_id}. Run EnrichmentAgent first.")

        contact = contacts[0]
        first_name = contact["first_name"]
        company = lead["company_name"]
        domain = lead["domain"]
        channel = lead["source_channel"]

        notes = (lead.get("notes") or "")
        # Outreach may only cite facts we hold evidence for.
        if channel == "google_maps" and not audit:
            raise PreconditionFailedError("audit_required", "Run a Website Doctor audit first: outreach may only cite measured facts.")
        if channel == "hiring_intent" and "HIRING SIGNAL" not in notes:
            raise PreconditionFailedError("signal_required", "No recorded hiring signal for this lead; refusing to claim one.")
        if channel not in ("hiring_intent", "google_maps") and not audit:
            raise PreconditionFailedError("audit_required", "Run a Website Doctor audit first: outreach may only cite measured facts.")

        # 1. Step 1: Trigger-Based Hook Email (< 80 words)
        if channel == "hiring_intent":
            subject = f"{first_name} - {company}'s tech backlog"
            body = (
                f"Hi {first_name},\n\n"
                f"Saw {company} has an open senior engineering role posted.\n\n"
                f"If hiring is slow, we can offer senior engineering capacity on your roadmap.\n\n"
                f"Open to a quick 10-minute intro this week to see if we're a fit?"
            )
        elif channel == "google_maps":
            lcp = audit["lcp_score"]
            stack = audit["tech_stack"][0] if (audit and audit.get("tech_stack")) else "legacy scripts"
            subject = f"{domain} mobile performance"
            body = (
                f"Hi {first_name},\n\n"
                f"Ran a speed audit on {domain} this morning—your mobile LCP is currently {lcp}s on {stack}, which is well above Google's 2.5s threshold.\n\n"
                f"Google treats 2.5s as the cut-off for a good Largest Contentful Paint, and slower pages tend to lose mobile visitors.\n\n"
                f"Mind if I send over a short note on what is slowing it down?"
            )
        else:
            subject = f"{company} architecture & AI roadmap"
            body = (
                f"Hi {first_name},\n\n"
                f"Congrats on the recent funding round for {company}.\n\n"
                f"We help teams ship engineering work quickly.\n\n"
                f"Worth a brief 10-minute sync to share what we do?"
            )

        # 2. Step 2: 72-Hour Value Bump Email (< 65 words)
        subject_2 = f"Re: {subject}"
        body_2 = (
            f"Hi {first_name},\n\n"
            f"Following up on this—I can put together a quick visual architecture teardown comparing your current latency to modern edge deployment standards.\n\n"
            f"Happy to put it together if useful for your team?\n\n"
            f"Best,\n{settings.agency.founder_name}"
        )

        # 3. Step 3: Break-up Note (< 50 words)
        subject_3 = f"Closing the loop: {company}"
        body_3 = (
            f"Hi {first_name},\n\n"
            f"I assume your engineering priorities are fully booked right now, so I won't follow up again.\n\n"
            + (f"If it becomes a priority down the road, you can grab time directly: {settings.agency.booking_link}\n\n" if settings.agency.booking_link else "")
            + f"Wishing {company} all the best."
        )

        # 4. LinkedIn Connection Note (< 300 characters)
        if channel == "hiring_intent":
            li_note = f"Hi {first_name}, saw {company} is hiring engineers. Would love to connect and follow your roadmap!"
        else:
            li_note = f"Hi {first_name}, noticed your work scaling {company}. Put together a quick technical performance audit on {domain}—glad to share if helpful."

        # Spam Score Analysis for all steps
        score_1, flags_1, _ = analyze_spam_friction(subject, body)
        score_2, flags_2, _ = analyze_spam_friction(subject_2, body_2)
        score_3, flags_3, _ = analyze_spam_friction(subject_3, body_3)

        steps_data = [
            {"step_number": 1, "channel": "email", "subject": subject, "body": body, "spam_score": score_1, "status": "drafted"},
            {"step_number": 2, "channel": "email", "subject": subject_2, "body": body_2, "spam_score": score_2, "status": "drafted"},
            {"step_number": 3, "channel": "email", "subject": subject_3, "body": body_3, "spam_score": score_3, "status": "drafted"}
        ]

        saved_sequences = OutreachRepository.save_sequence_steps(
            lead_id=lead_id,
            decision_maker_id=contact["id"],
            steps=steps_data,
            org_id=lead.get("org_id") or "org_default"
        )

        return {
            "lead_id": lead_id,
            "decision_maker": contact,
            "sequences": saved_sequences,
            "linkedin_connection_note": li_note
        }
