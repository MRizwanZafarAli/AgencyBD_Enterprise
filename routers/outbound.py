"""
Outbound router: mailboxes, verification, guarded sends, approval-gated drafts.

There is no endpoint that sends arbitrary content to an arbitrary address. Every send runs the full guard chain
(jurisdiction, suppression, stop-on-reply, verification, policy) and, by default, waits for human approval.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from security.auth import Principal, require_permission
from outbound.providers.registry import MailboxRegistry
from outbound.verify import EmailVerificationGate
from workflows.sequence import OutreachSequenceWorkflow, SequenceStep
from workflows.scheduler import SequenceScheduler
from database.db import get_db

router = APIRouter(prefix="/api/outbound", tags=["Outbound Engine"])


class RegisterMailboxRequest(BaseModel):
    email: str
    display_name: Optional[str] = ""
    provider_type: Optional[str] = "smtp"
    daily_cap: Optional[int] = Field(35, ge=1, le=200)
    skip_warmup: bool = False  # set true only for a mailbox that is already warmed up
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = Field(None, repr=False)
    use_tls: bool = True


class VerifyEmailRequest(BaseModel):
    email: str


class ExecuteSequenceStepRequest(BaseModel):
    recipient_email: str
    step_number: int = Field(1, ge=1, le=10)
    delay_days: int = 0
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=10, max_length=5000)
    channel: Optional[str] = "email"
    country_code: str = Field(..., min_length=2, max_length=3, description="Recipient country (ISO code). Required: rules depend on it.")
    lead_id: Optional[int] = None
    recipient_name: Optional[str] = ""
    company_name: Optional[str] = ""
    deal_value: Optional[float] = Field(None, ge=0)


@router.get("/mailboxes")
def list_mailboxes(principal: Principal = Depends(require_permission("leads:read"))):
    return MailboxRegistry.list_mailboxes(org_id=principal.org_id)


@router.post("/mailboxes")
def register_mailbox(req: RegisterMailboxRequest, principal: Principal = Depends(require_permission("outbound:manage"))):
    """Registers a sending mailbox. SMTP credentials are encrypted at rest and never returned."""
    return MailboxRegistry.register_mailbox(
        org_id=principal.org_id, email=req.email, display_name=req.display_name or "",
        provider_type=req.provider_type or "smtp", daily_cap=req.daily_cap or 35, skip_warmup=req.skip_warmup,
        smtp_host=req.smtp_host, smtp_port=req.smtp_port, smtp_username=req.smtp_username,
        smtp_password=req.smtp_password, use_tls=req.use_tls)


@router.post("/verify")
def verify_email(req: VerifyEmailRequest, principal: Principal = Depends(require_permission("leads:read"))):
    return EmailVerificationGate().verify(req.email).to_dict()


@router.post("/sequence/step")
def execute_sequence_step(req: ExecuteSequenceStepRequest, principal: Principal = Depends(require_permission("outreach:dispatch"))):
    """Runs one outreach step through the full guard chain. First touches normally return `pending_approval`."""
    res = OutreachSequenceWorkflow().execute_step(
        org_id=principal.org_id, recipient_email=req.recipient_email,
        step=SequenceStep(step_number=req.step_number, delay_days=req.delay_days, subject=req.subject, body=req.body,
                          channel=req.channel or "email"),
        country_code=req.country_code, lead_id=req.lead_id, recipient_name=req.recipient_name or "",
        company_name=req.company_name or "", deal_value=req.deal_value, created_by=principal.user_id)
    return {"status": res.status, "step_number": res.step_number, "recipient_email": res.recipient_email,
            "mailbox_used": res.mailbox_used, "message_id": res.message_id, "reason": res.reason,
            "draft_id": res.draft_id, "diagnostics": res.diagnostics}


@router.get("/drafts")
def list_drafts(status: Optional[str] = None, limit: int = 100, principal: Principal = Depends(require_permission("leads:read"))):
    return OutreachSequenceWorkflow.list_drafts(principal.org_id, status=status, limit=min(limit, 500))


@router.post("/drafts/{draft_id}/send")
def send_approved_draft(draft_id: int, principal: Principal = Depends(require_permission("outreach:dispatch"))):
    """Sends a draft a human has approved. Sends the stored text and re-checks every guard at send time."""
    workflow = OutreachSequenceWorkflow()
    try:
        res = workflow.send_approved_draft(principal.org_id, draft_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft = workflow.get_draft(principal.org_id, draft_id)
    if res.status == "sent" and draft and draft.get("enrollment_id"):
        SequenceScheduler.advance_after_send(principal.org_id, draft["enrollment_id"])
    return {"status": res.status, "draft_id": draft_id, "recipient_email": res.recipient_email,
            "mailbox_used": res.mailbox_used, "message_id": res.message_id, "reason": res.reason}


class DnsRecordsRequest(BaseModel):
    domain: str
    esp_provider: str = "google_workspace"
    dmarc_policy: str = "none"


@router.post("/dns/records")
def dns_records(req: DnsRecordsRequest, principal: Principal = Depends(require_permission("leads:read"))):
    """The DNS records to publish for a sending domain (nothing invented: the DKIM key comes from your mail provider)."""
    from config.dns_fleet_configurator import DNSFleetConfigurator
    return DNSFleetConfigurator.generate_dns_records(req.domain, req.esp_provider, req.dmarc_policy)


class DomainRequest(BaseModel):
    domain: str


@router.post("/dns/audit")
def dns_audit(req: DomainRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Live MX/SPF/DKIM/DMARC check for a domain."""
    from config.dns_fleet_configurator import DNSFleetConfigurator
    return DNSFleetConfigurator.audit_live_dns(req.domain)


@router.get("/events")
def list_outreach_events(limit: int = 50, principal: Principal = Depends(require_permission("leads:read"))):
    with get_db() as db:
        rows = db.execute("SELECT * FROM outreach_events WHERE org_id = ? ORDER BY id DESC LIMIT ?",
                          (principal.org_id, min(limit, 500))).fetchall()
        return [dict(r) for r in rows]
