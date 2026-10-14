"""
ObjectionAgent: Autonomous Inbound Reply Classifier & Rebuttal Generator.
Triages incoming responses, classifies sentiment and objection vectors, and drafts high-impact rebuttals.
"""

import re
from typing import Dict, Any, Tuple
from database.models import LeadRepository, ReplyRepository
from config.settings import settings

class ObjectionAgent:
    """
    Intelligent objection handling agent that converts prospect resistance into booked meetings.
    """

    def classify_reply(self, reply_text: str) -> Tuple[str, str, str]:
        """
        Classifies incoming reply text.
        Returns: (sentiment, objection_category, rebuttal_strategy)
        """
        text_lower = reply_text.lower()

        # 1. Unsubscribe / Negative
        if any(w in text_lower for w in ["unsubscribe", "remove me", "stop emailing", "do not contact", "take me off"]):
            return (
                "negative",
                "not_interested",
                "Immediate polite acknowledgment & permanent suppression list update."
            )

        # 2. Positive / Interested
        if any(w in text_lower for w in ["yes", "interested", "interesting", "sure", "schedule", "meet", "sounds good", "demo", "calendar", "send it over", "send the pdf", "free next week", "let's chat", "let's talk", "call"]):
            return (
                "positive",
                "interested",
                "Provide immediate value, send the audit/teardown asset, and present 2 specific timeslots."
            )

        # 3. In-House Team Objection
        if any(w in text_lower for w in ["in-house", "internal team", "have developers", "our own team", "have engineers", "internal dev"]):
            return (
                "neutral",
                "in_house_team",
                "Acknowledge their internal team's focus on core product, and pitch specialized augmentation for non-core backlog or performance fire-drills."
            )

        # 4. Budget / Cost Objection
        if any(w in text_lower for w in ["budget", "expensive", "no funds", "can't afford", "cost", "money"]):
            return (
                "neutral",
                "no_budget",
                "De-risk commercial model: highlight milestone-based billing, zero upfront lock-in, and measurable ROI via conversion lift."
            )

        # 5. Send Info / Generic Inquiry
        return (
            "neutral",
            "send_info",
            "Deliver 3-point bullet summary of agency capability + case study proof metric + direct Cal.com link."
        )

    def draft_rebuttal(self, lead_id: int, reply_text: str) -> Dict[str, Any]:
        lead = LeadRepository.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead ID {lead_id} does not exist.")

        company = lead["company_name"]
        sentiment, category, strategy = self.classify_reply(reply_text)

        if category == "not_interested":
            draft = f"Understood completely—I've removed you from our list right away. Wishing {company} all the best."
        elif category == "interested":
            draft = (
                f"Great to hear! Here is the direct link to the 2-page performance breakdown: [View Audit Report]\n\n"
                f"Would Thursday at 2:00 PM EST or Friday at 11:00 AM EST work for a brief 15-minute walkthrough? Alternatively, grab whatever slot fits your schedule here: {settings.agency.booking_link}"
            )
        elif category == "in_house_team":
            draft = (
                f"Completely respect that—most of the founders we work with also have great internal squads.\n\n"
                f"We usually don't replace in-house teams; rather, we plug in as a specialized strike force for heavy architectural refactoring or backlog sprints so your core devs can stay 100% focused on product features.\n\n"
                f"Open to keeping in touch for when bandwidth gets tight, or would a brief 10-minute intro be worth a quick look?"
            )
        elif category == "no_budget":
            draft = (
                f"Totally understandable given current market conditions.\n\n"
                f"We structure all our sprints on flexible, milestone-based deliverables with zero long-term retainer lock-in. For instance, our speed and modernization sprints typically pay for themselves within 60 days via recovered conversion rates.\n\n"
                f"Happy to share our transparent pricing sheet so you have it on file for when the next cycle opens up?"
            )
        else: # send_info
            draft = (
                f"Happy to provide more context about {settings.agency.name}.\n"
                + (f"• {settings.agency.case_study_metric}\n" if settings.agency.case_study_metric else "")
                + ("• " + ", ".join(settings.agency.core_services) + "\n" if settings.agency.core_services else "")
                + ("\nBook a brief discussion here whenever convenient: " + settings.agency.booking_link if settings.agency.booking_link else "")
            )

        logged_reply = ReplyRepository.log_reply(
            lead_id=lead_id,
            reply_text=reply_text,
            sentiment=sentiment,
            objection_category=category,
            auto_rebuttal_draft=draft,
            org_id=lead.get("org_id") or "org_default"
        )

        return {
            "lead_id": lead_id,
            "reply_id": logged_reply["id"],
            "sentiment": sentiment,
            "objection_category": category,
            "rebuttal_strategy": strategy,
            "auto_rebuttal_draft": draft
        }
