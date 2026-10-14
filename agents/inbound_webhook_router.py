"""
Inbound Webhook Router & Email Thread Stripper.
Normalizes inbound replies from multiple ESPs (Resend, SendGrid, Instantly, Smartlead, generic),
strips quote history, classifies sentiment, handles CAN-SPAM auto-suppression, and logs replies.
"""

import re
from typing import Dict, Any, Optional, Tuple
from agents.objection_agent import ObjectionAgent
from database.db import add_entity_to_suppression, get_db
from database.models import LeadRepository, ReplyRepository

class InboundWebhookRouter:
    def __init__(self):
        self.objection_agent = ObjectionAgent()

    @staticmethod
    def strip_email_quotes(raw_body: str) -> str:
        """
        Extracts clean prospect response by stripping quoted reply chains,
        outlook style headers, and email client signatures.
        """
        if not raw_body:
            return ""

        # Normalize line endings
        text = raw_body.replace("\r\n", "\n")

        # Patterns indicating start of quoted history
        quote_splitters = [
            r"-----Original Message-----",
            r"On\s+.*,\s+.*wrote:",
            r"From:\s+.*Sent:\s+.*",
            r"wrote:\s*$",
            r"--- Original Message ---",
            r"________________________________"
        ]

        for pattern in quote_splitters:
            split_res = re.split(pattern, text, flags=re.IGNORECASE)
            if len(split_res) > 1:
                text = split_res[0]

        # Strip lines starting with '>'
        lines = [line for line in text.split("\n") if not line.strip().startswith(">")]
        clean_text = "\n".join(lines).strip()

        # Remove trailing signature delimiters
        sig_split = re.split(r"^--\s*$", clean_text, flags=re.MULTILINE)
        if len(sig_split) > 1:
            clean_text = sig_split[0].strip()

        return clean_text

    def normalize_esp_payload(self, payload: Dict[str, Any], provider_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts normalized email fields regardless of ESP format:
        sender, recipient, subject, body, message_id, provider.
        """
        sender = ""
        recipient = ""
        subject = ""
        raw_body = ""
        message_id = payload.get("id") or payload.get("message_id") or ""
        provider = provider_hint or "generic"

        # 1. Resend Inbound Webhook
        if "data" in payload and isinstance(payload["data"], dict) and "from" in payload["data"]:
            provider = "resend"
            data = payload["data"]
            sender = data.get("from", "")
            to_val = data.get("to", [])
            recipient = to_val[0] if isinstance(to_val, list) and to_val else str(to_val)
            subject = data.get("subject", "")
            raw_body = data.get("text") or data.get("html") or ""

        # 2. SendGrid Inbound Parse
        elif "from" in payload and ("to" in payload or "envelope" in payload):
            provider = "sendgrid"
            sender = payload.get("from", "")
            recipient = payload.get("to", "")
            subject = payload.get("subject", "")
            raw_body = payload.get("text") or payload.get("html") or ""

        # 3. Smartlead / Instantly Webhook
        elif "reply_text" in payload or "lead_email" in payload:
            provider = "smartlead_instantly"
            sender = payload.get("lead_email") or payload.get("from", "")
            recipient = payload.get("campaign_email") or payload.get("to", "")
            subject = payload.get("subject", "Re: Discussion")
            raw_body = payload.get("reply_text") or payload.get("body", "")

        # 4. Standard / Generic Payload
        else:
            sender = payload.get("sender") or payload.get("from") or ""
            recipient = payload.get("recipient") or payload.get("to") or ""
            subject = payload.get("subject", "")
            raw_body = payload.get("body") or payload.get("text") or ""

        # Extract pure email from "Name <email@domain.com>"
        sender_match = re.search(r"[\w\.-]+@[\w\.-]+", sender)
        clean_sender = sender_match.group(0).lower() if sender_match else sender.lower()

        clean_body = self.strip_email_quotes(raw_body)

        return {
            "provider": provider,
            "sender_email": clean_sender,
            "recipient_email": recipient,
            "subject": subject,
            "raw_body": raw_body,
            "clean_body": clean_body,
            "message_id": message_id
        }

    def process_inbound_reply(self, payload: Dict[str, Any], org_id: str = "org_default") -> Dict[str, Any]:
        """
        Full inbound processing pipeline:
        1. Normalize payload & strip thread history.
        2. Resolve or associate with lead in database.
        3. Triage sentiment & objection category.
        4. If opt-out / negative: auto-suppress immediately.
        5. Log reply and generate rebuttal draft.
        """
        normalized = self.normalize_esp_payload(payload)
        sender_email = normalized["sender_email"]
        clean_body = normalized["clean_body"] or normalized["raw_body"]

        # Find matching lead by decision_maker email or company domain
        lead_id = None
        domain_part = sender_email.split("@")[-1] if "@" in sender_email else ""
        
        with get_db() as conn:
            cursor = conn.cursor()
            # Try finding decision maker
            cursor.execute("SELECT lead_id FROM decision_makers WHERE LOWER(email) = ? AND org_id = ?", (sender_email, org_id))
            row = cursor.fetchone()
            if row:
                lead_id = row["lead_id"]
            elif domain_part:
                # Try finding lead by domain
                cursor.execute("SELECT id FROM leads WHERE (domain = ? OR domain = ?) AND org_id = ?", (domain_part, f"www.{domain_part}", org_id))
                lead_row = cursor.fetchone()
                if lead_row:
                    lead_id = lead_row["id"]

        # Default fallback lead if no previous outbound trace exists
        if not lead_id:
            lead = LeadRepository.create_or_get_lead(
                company_name=domain_part.split(".")[0].capitalize() or "Inbound Company",
                domain=domain_part or "inbound-sender.com",
                source_channel="inbound_webhook",
                notes=f"Auto-created from inbound email: {sender_email}",
                org_id=org_id
            )
            lead_id = lead["id"]

        # Perform objection classification & draft generation
        sentiment, category, strategy = self.objection_agent.classify_reply(clean_body)
        rebuttal_result = self.objection_agent.draft_rebuttal(lead_id, clean_body)

        # Automated CAN-SPAM opt-out handling
        auto_suppressed = False
        if category == "not_interested" or sentiment == "negative":
            add_entity_to_suppression(
                email_or_domain=sender_email,
                entity_type="email",
                reason=f"inbound_opt_out: {clean_body[:80]}"
            )
            if domain_part:
                add_entity_to_suppression(
                    email_or_domain=domain_part,
                    entity_type="domain",
                    reason=f"inbound_opt_out_domain: {sender_email}"
                )
            auto_suppressed = True

        return {
            "status": "processed",
            "lead_id": lead_id,
            "sender_email": sender_email,
            "clean_body": clean_body,
            "sentiment": sentiment,
            "objection_category": category,
            "strategy": strategy,
            "auto_rebuttal": rebuttal_result.get("rebuttal_draft", ""),
            "auto_suppressed": auto_suppressed,
            "provider": normalized["provider"],
            "org_id": org_id
        }
