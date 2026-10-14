"""
Enterprise Reply Agent & Objection Resolver.
Classifies inbound prospect responses into:
- interested
- objection (pricing, timing, authority, competitor, already_solved)
- out_of_office
- wrong_person
- unsubscribe
- hostile

Actions:
1. Auto-suppresses unsubscribes across the global vault instantly.
2. For interested/objections: drafts grounded contextual response using agency playbook.
3. Queues draft into Human Approval Inbox unless tenant policy authorizes autonomous dispatch.
4. Records outreach event to trigger sequence stop-on-reply.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import json

from config.settings import settings
from agents.objection_agent import ObjectionAgent
from agents.inbound_webhook_router import InboundWebhookRouter
from compliance.suppression import KeyedSuppressionVault
from outbound.providers.registry import MailboxRegistry
from database.db import get_db
from database.models import ApprovalRepository


@dataclass
class ReplyClassification:
    category: str  # interested | objection | out_of_office | wrong_person | unsubscribe | hostile | generic
    sentiment: str  # positive | negative | neutral
    confidence: float
    objection_type: Optional[str] = None
    requires_approval: bool = True
    draft_response: Optional[str] = None
    auto_suppressed: bool = False

class ReplyAgent:
    def __init__(self):
        self.objection_agent = ObjectionAgent()

    def classify_text(self, clean_text: str) -> ReplyClassification:
        lower = clean_text.lower()

        # 1. Immediate Unsubscribe / Hostile Opt-Out Detection
        unsub_phrases = [
            "unsubscribe", "remove me", "take me off", "stop emailing",
            "not interested", "dont email", "don't email", "leave me alone",
            "lose my email", "cease and desist", "spam"
        ]
        if any(phrase in lower for phrase in unsub_phrases):
            is_hostile = any(w in lower for w in ["spam", "cease", "f***"])
            return ReplyClassification(
                category="hostile" if is_hostile else "unsubscribe",
                sentiment="negative",
                confidence=0.98,
                requires_approval=False,
                auto_suppressed=True
            )

        # 2. Out of Office / Automated Responder
        ooo_phrases = ["out of the office", "out of office", "on leave", "automatic reply", "away from my desk"]
        if any(phrase in lower for phrase in ooo_phrases):
            return ReplyClassification(
                category="out_of_office",
                sentiment="neutral",
                confidence=0.95,
                requires_approval=False
            )

        # 3. Wrong Person / Referral
        referral_phrases = ["not the right person", "speak with", "reach out to", "handled by", "talk to"]
        if any(phrase in lower for phrase in referral_phrases):
            return ReplyClassification(
                category="wrong_person",
                sentiment="neutral",
                confidence=0.88,
                requires_approval=True
            )

        # 4. Objection Analysis via ObjectionAgent
        sentiment, category, strategy = self.objection_agent.classify_reply(clean_text)

        if category in ("no_budget", "in_house_team"):
            if category == "no_budget":
                rebuttal = (
                    "Totally understandable given current market conditions.\n\n"
                    "We structure all our sprints on flexible, milestone-based deliverables with zero long-term lock-in. "
                    "Happy to share our transparent pricing sheet so you have it on file for when the next cycle opens up?"
                )
            else:
                rebuttal = (
                    "Completely respect that—most of the founders we work with also have great internal squads.\n\n"
                    "We usually plug in as a specialized strike force for heavy architectural refactoring so your core devs can stay focused on product features.\n\n"
                    "Would a brief 10-minute intro be worth a quick look?"
                )
            return ReplyClassification(
                category="objection",
                sentiment=sentiment,
                confidence=0.85,
                objection_type=category,
                requires_approval=True,
                draft_response=rebuttal
            )

        # 5. Interested / Meeting Request
        if category == "interested" or any(w in lower for w in ["send more info", "pricing", "send deck", "lets chat", "let's chat", "hop on a call", "sounds interesting", "calendar"]):
            draft = (
                "Hi there, thanks for getting back to me!\n\n"
                + (f"Feel free to pick a time that suits you here: {settings.agency.booking_link}\n\n" if settings.agency.booking_link else "Let me know a couple of times that suit you for a short call.\n\n")
                + f"Best,\n{settings.agency.founder_name}, {settings.agency.name}"
            )
            return ReplyClassification(
                category="interested",
                sentiment="positive",
                confidence=0.92,
                requires_approval=True,
                draft_response=draft
            )

        return ReplyClassification(
            category="generic",
            sentiment="neutral",
            confidence=0.6,
            requires_approval=True,
            draft_response="Thank you for reaching out. Let me review and follow up with you shortly."
        )


    def handle_inbound_reply(
        self,
        raw_body: str,
        sender_email: str,
        org_id: str = "org_default",
        lead_id: Optional[int] = None,
        company_name: str = ""
    ) -> Dict[str, Any]:
        clean_text = InboundWebhookRouter.strip_email_quotes(raw_body)
        classification = self.classify_text(clean_text)

        # 1. Unsubscribe handling
        if classification.auto_suppressed:
            KeyedSuppressionVault.suppress(
                entity=sender_email,
                entity_type="email",
                reason=f"inbound_reply_{classification.category}",
                source="reply_agent",
                org_id=org_id
            )
            MailboxRegistry.record_event(
                org_id=org_id,
                recipient_email=sender_email,
                event_type="unsubscribed",
                lead_id=lead_id,
                payload={"raw_text": clean_text[:200]}
            )
            return {
                "action": "auto_suppressed",
                "classification": classification.category,
                "sender_email": sender_email,
                "status": "suppressed"
            }

        # 2. Record Reply event (stops subsequent sequence steps)
        MailboxRegistry.record_event(
            org_id=org_id,
            recipient_email=sender_email,
            event_type="replied",
            lead_id=lead_id,
            payload={
                "category": classification.category,
                "sentiment": classification.sentiment,
                "preview": clean_text[:200]
            }
        )

        # 3. Queue into Human Approval Inbox if draft was produced
        approval_id = None
        if classification.draft_response and classification.requires_approval:
            approval_id = ApprovalRepository.create_approval_request(
                org_id=org_id,
                subject_type="reply_draft",
                subject_id=lead_id or 0,
                requested_by="ReplyAgent",
                reason=f"Inbound reply classified as {classification.category}. Proposed response drafted."
            )

        return {
            "action": "reply_drafted_for_approval" if approval_id else "processed",
            "classification": classification.category,
            "sentiment": classification.sentiment,
            "draft_response": classification.draft_response,
            "approval_id": approval_id,
            "sender_email": sender_email
        }
