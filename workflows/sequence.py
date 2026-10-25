"""
Outbound send workflow.

Every message passes the same ordered guards, whether it comes from the API, a sequence or the scheduler:

  1. jurisdiction   (unknown country = blocked)
  2. suppression    (email or domain, global)
  3. stop-on-reply  (replied / bounced / complaint / unsubscribed)
  4. verification   (fail-closed gate; only 'verified' passes)
  5. policy engine  (autonomy level: first touches default to human approval)

If the policy requires approval the message is stored as an ``outbound_drafts`` row and an approval is opened.
Only ``send_approved_draft`` sends it, and it sends the *stored* content (not whatever the caller supplies now), after
re-running guards 1-5, so an address that was suppressed or bounced after approval is still not mailed.
"""

import json
import threading
from workflows import controls
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from compliance.content_guard import check_outreach_text
from compliance.country_policy import CountryComplianceEngine
from compliance.footer import ComplianceFooterBuilder
from compliance.suppression import KeyedSuppressionVault
from database.db import get_db
from database.models import ApprovalRepository
from outbound.providers.base import OutboundMessage, SendProvider, SendResult
from outbound.providers.registry import MailboxRegistry
from outbound.providers.smtp import SmtpProvider
from outbound.verify import EmailVerificationGate
from policy.engine import PolicyEngine



@dataclass
class SequenceStep:
    step_number: int
    delay_days: int
    subject: str
    body: str
    channel: str = "email"


@dataclass
class SequenceExecutionResult:
    # sent | pending_approval | stopped_on_reply | suppressed | unverified | no_mailbox | blocked_by_policy | failed
    status: str
    step_number: int
    recipient_email: str
    mailbox_used: Optional[str] = None
    message_id: Optional[str] = None
    reason: Optional[str] = None
    draft_id: Optional[int] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class OutreachSequenceWorkflow:
    def __init__(self, provider: Optional[SendProvider] = None, verification_gate: Optional[EmailVerificationGate] = None):
        self._tl = threading.local()      # per-thread message state: one workflow instance may serve several threads
        self.provider = provider or SmtpProvider()
        self.verifier = verification_gate or EmailVerificationGate()

    # ------------------------------------------------------------------ guards

    @staticmethod
    def stop_reason(org_id: str, email: str) -> Optional[str]:
        """Why a sequence must not contact this person any more, or None."""
        email = email.lower()
        with get_db() as db:
            row = db.execute("""
                SELECT event_type FROM outreach_events
                WHERE org_id = ? AND recipient_email = ? AND event_type IN ('replied', 'unsubscribed', 'bounced', 'complaint')
                ORDER BY id DESC LIMIT 1
            """, (org_id, email)).fetchone()
            if row:
                return f"prospect {row['event_type']}"
            row = db.execute("""
                SELECT 1 FROM inbound_replies r JOIN decision_makers d ON d.lead_id = r.lead_id
                WHERE d.org_id = ? AND LOWER(d.email) = ? LIMIT 1
            """, (org_id, email)).fetchone()
            if row:
                return "prospect replied"
        return None

    @staticmethod
    def has_prospect_replied_or_opted_out(org_id: str, email: str) -> bool:
        return OutreachSequenceWorkflow.stop_reason(org_id, email) is not None

    def _guards(self, org_id: str, email: str, country_code: Optional[str], step_number: int,
                deal_value: Optional[float]) -> Optional[SequenceExecutionResult]:
        """Runs guards 1-5. Returns a terminal result, or None. Sets this thread's decision for the caller."""
        def stop(status: str, reason: str) -> SequenceExecutionResult:
            return SequenceExecutionResult(status=status, step_number=step_number, recipient_email=email, reason=reason)

        if controls.is_halted(org_id):
            return stop("halted", "Outbound is halted by the kill switch.")
        jurisdiction = CountryComplianceEngine.evaluate(country_code)
        if not jurisdiction.allowed:
            return stop("blocked_by_policy", jurisdiction.reason)
        self._tl.jurisdiction = jurisdiction
        if KeyedSuppressionVault.is_suppressed(email, org_id):
            return stop("suppressed", "Recipient is in the suppression vault.")
        reason = self.stop_reason(org_id, email)
        if reason:
            return stop("stopped_on_reply", f"Stopped: {reason}.")
        verification = self.verifier.verify(email)
        if verification.status != "verified" or not verification.is_deliverable:
            return stop("unverified", f"Email not verified ({verification.status}): {verification.reason}")
        ctx = {"email_verification_status": "verified", "recipient_email": email, "country_code": jurisdiction.country_code}
        if deal_value is not None:
            ctx["deal_value"] = deal_value
        decision = PolicyEngine.evaluate(org_id, "outbound_first_touch" if step_number == 1 else "outbound_followup", ctx)
        self._tl.decision = decision
        if not decision.allowed:
            return stop("blocked_by_policy", decision.reason)
        return None

    # ------------------------------------------------------------------ drafts

    @staticmethod
    def _create_draft(org_id: str, email: str, step: SequenceStep, country_code: str, lead_id, name, company,
                      deal_value, enrollment_id, rule: str, created_by: str) -> int:
        with get_db() as db:
            cur = db.execute("""
                INSERT INTO outbound_drafts (org_id, lead_id, enrollment_id, recipient_email, recipient_name, company_name,
                    country_code, step_number, subject, body, deal_value, status, policy_rule, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_approval', ?, ?)
            """, (org_id, lead_id, enrollment_id, email, name, company, country_code.upper(), step.step_number, step.subject,
                  step.body, deal_value, rule, created_by))
            db.commit()
            return cur.lastrowid

    @staticmethod
    def get_draft(org_id: str, draft_id: int) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            row = db.execute("SELECT * FROM outbound_drafts WHERE id = ? AND org_id = ?", (draft_id, org_id)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_drafts(org_id: str, status: Optional[str] = None, limit: int = 100):
        with get_db() as db:
            q, params = "SELECT * FROM outbound_drafts WHERE org_id = ?", [org_id]
            if status:
                q += " AND status = ?"
                params.append(status)
            rows = db.execute(q + " ORDER BY id DESC LIMIT ?", (*params, limit)).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------ public API

    def execute_step(
        self,
        org_id: str,
        recipient_email: str,
        step: SequenceStep,
        country_code: Optional[str] = None,
        lead_id: Optional[int] = None,
        recipient_name: str = "",
        company_name: str = "",
        deal_value: Optional[float] = None,
        enrollment_id: Optional[int] = None,
        created_by: str = "api",
    ) -> SequenceExecutionResult:
        email = recipient_email.strip().lower()
        bad_content = check_outreach_text(step.subject, step.body)
        if bad_content:
            return SequenceExecutionResult(status="blocked_by_policy", step_number=step.step_number, recipient_email=email, reason=bad_content)
        blocked = self._guards(org_id, email, country_code, step.step_number, deal_value)
        if blocked:
            return blocked
        decision = self._tl.decision

        draft_id = self._create_draft(org_id, email, step, country_code or "", lead_id, recipient_name, company_name,
                                      deal_value, enrollment_id, decision.rule_name, created_by)
        if decision.requires_human_approval:
            ApprovalRepository.create_approval_request(
                subject_type="outbound_draft", subject_id=draft_id, requested_by=created_by, org_id=org_id,
                reason=f"{decision.autonomy_level}: {decision.reason}")
            return SequenceExecutionResult(status="pending_approval", step_number=step.step_number, recipient_email=email,
                                           reason=decision.reason, draft_id=draft_id)
        return self._deliver(org_id, draft_id)

    def send_approved_draft(self, org_id: str, draft_id: int) -> SequenceExecutionResult:
        draft = self.get_draft(org_id, draft_id)
        if not draft:
            raise LookupError("Draft not found")
        if draft["status"] != "approved":
            return SequenceExecutionResult(status="blocked_by_policy", step_number=draft["step_number"],
                                           recipient_email=draft["recipient_email"], draft_id=draft_id,
                                           reason=f"Draft is '{draft['status']}', not approved.")
        bad_content = check_outreach_text(draft["subject"], draft["body"])
        if bad_content:
            return SequenceExecutionResult(status="blocked_by_policy", step_number=draft["step_number"], recipient_email=draft["recipient_email"],
                                           draft_id=draft_id, reason=bad_content)
        # Re-check the world as it is NOW, not as it was at approval time.
        blocked = self._guards(org_id, draft["recipient_email"], draft["country_code"], draft["step_number"], draft["deal_value"])
        if blocked:
            blocked.draft_id = draft_id
            return blocked
        return self._deliver(org_id, draft_id)

    # ------------------------------------------------------------------ delivery

    def _deliver(self, org_id: str, draft_id: int) -> SequenceExecutionResult:
        draft = self.get_draft(org_id, draft_id)
        email, step_no = draft["recipient_email"], draft["step_number"]

        def finish(status: str, **kw) -> SequenceExecutionResult:
            return SequenceExecutionResult(status=status, step_number=step_no, recipient_email=email, draft_id=draft_id, **kw)

        mailbox = MailboxRegistry.select_best_mailbox(org_id, recipient_domain=email.split("@")[-1],
                                                      require_credentials=True)
        if not mailbox:
            return finish("no_mailbox", reason="No mailbox with credentials and remaining capacity (daily cap or warm-up ramp).")

        plain_footer, html_footer, headers = ComplianceFooterBuilder.build_footer(
            recipient_email=email, org_id=org_id, include_lia=self._tl.jurisdiction.requires_lia)
        message = OutboundMessage(
            to_email=email, from_email=mailbox["email"], subject=draft["subject"], body_text=draft["body"] + plain_footer,
            body_html=f"<div style='font-family: sans-serif; font-size: 14px; line-height: 1.6;'>{draft['body'].replace(chr(10), '<br/>')}</div>" + html_footer,
            headers=headers, org_id=org_id, lead_id=str(draft["lead_id"]) if draft["lead_id"] else None,
            metadata={"step_number": step_no, "draft_id": draft_id})
        result: SendResult = self.provider.send(message)

        with get_db() as db:
            if result.success:
                db.execute("UPDATE outbound_drafts SET status = 'sent', sent_at = CURRENT_TIMESTAMP, send_result_json = ? WHERE id = ?",
                           (json.dumps({"message_id": result.provider_message_id, "mailbox": mailbox["email"]}), draft_id))
            else:
                db.execute("UPDATE outbound_drafts SET status = 'failed', send_result_json = ? WHERE id = ?",
                           (json.dumps({"error": result.error, "status": result.status}), draft_id))
            db.commit()
        if result.success:
            MailboxRegistry.record_send(org_id, mailbox["id"], email, draft["lead_id"], result.provider_message_id)
            return finish("sent", mailbox_used=mailbox["email"], message_id=result.provider_message_id, diagnostics=result.diagnostics)
        return finish("failed", mailbox_used=mailbox["email"], reason=result.error or "Provider failure")
