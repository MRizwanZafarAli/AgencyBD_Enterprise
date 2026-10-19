"""
AgencyBD_Enterprise: FastAPI High-Performance REST Service.
Provides enterprise endpoints for multi-channel lead sourcing, technical audits,
enrichment, sequence generation, dispatch, objection triage, CRM booking,
Prometheus observability, inbound webhooks, and global AI market intelligence.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Header, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from net.fetcher import SSRFSecurityError, HostUnreachableError
from config.honesty import NotConfiguredError, PreconditionFailedError
from pydantic import BaseModel, Field

from config.env import get_list, is_production
from orchestrator.swarm_engine import SwarmEngine
from database.models import ProposalRepository, LeadRepository, AuditRepository, ContactRepository, OutreachRepository
from schemas.lead import SourcingQueryRequest
from schemas.audit import AuditRequest
from schemas.outreach import ObjectionTriageRequest, BookingRequest
from data.geo_database import GeoDatabase
from agents.market_intelligence_agent import MarketIntelligenceAgent
from agents.inbound_webhook_router import InboundWebhookRouter
from security.webhook_verifier import WebhookSecurity, WebhookSecrets
from security.auth import (
    Principal,
    ROLE_PERMISSIONS,
    DEFAULT_ORG_ID,
    get_current_principal,
    require_permission,
    scoped_org,
)
from core.metrics import MetricsManager
from database.db import create_api_key_record, list_api_keys, revoke_api_key_record, get_db
from analytics.financial_ledger import FinancialLedger
from analytics.ab_testing_cohorts import SpintaxABOptimizer
from tasks.task_queue import TaskQueueEngine

logger = logging.getLogger("AgencyBD.api")

_docs_enabled = (not is_production()) or os.getenv("AGENCYBD_ENABLE_DOCS", "").lower() == "true"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Starts the sequence scheduler in-process when AGENCYBD_SCHEDULER=on (otherwise run scripts/run_scheduler.py)."""
    runner = None
    if os.getenv("AGENCYBD_SCHEDULER", "off").lower() in ("on", "true", "1"):
        from workflows.scheduler import SchedulerThread
        runner = SchedulerThread(int(os.getenv("AGENCYBD_SCHEDULER_INTERVAL", "60")))
        runner.start()
    yield
    if runner:
        runner.stop()


app = FastAPI(
    lifespan=lifespan,
    title="AgencyBD Enterprise Engine",
    description="Autonomous Multi-Agent Business Development & Lead Intelligence Swarm for Software Agencies",
    version="2.1.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Credentials travel in headers (X-API-Key / Bearer), never cookies, so credentialed CORS is not needed.
# Browsers may only call the API from the origins listed in AGENCYBD_CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_list("AGENCYBD_CORS_ORIGINS", "http://localhost:5173,http://localhost:8001"),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(SSRFSecurityError)
async def ssrf_policy_handler(request: Request, exc: SSRFSecurityError):
    """Requests for internal/non-public targets are a client error, never a 500."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(NotConfiguredError)
async def not_configured_handler(request: Request, exc: NotConfiguredError):
    """Missing credentials or data are reported honestly, never papered over with invented results."""
    return JSONResponse(status_code=503, content=exc.to_dict())


@app.exception_handler(PreconditionFailedError)
async def precondition_handler(request: Request, exc: PreconditionFailedError):
    return JSONResponse(status_code=422, content={"status": exc.code, "detail": exc.hint})


@app.exception_handler(HostUnreachableError)
async def unreachable_handler(request: Request, exc: HostUnreachableError):
    return JSONResponse(status_code=502, content={"status": "unreachable", "detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Domain validation failures raised by our own code are client errors."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


engine = SwarmEngine()
market_intel = MarketIntelligenceAgent()
webhook_router = InboundWebhookRouter()

MAX_WEBHOOK_BYTES = 1_000_000


def _fail(exc: Exception) -> HTTPException:
    """Maps domain errors to 400 and hides internal failures behind a generic 500."""
    if isinstance(exc, (NotConfiguredError, PreconditionFailedError, HostUnreachableError, SSRFSecurityError)):
        return exc  # handled by the dedicated exception handlers (503 / 422 / 502 / 400)
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    logger.exception("Unhandled error in request handler")
    return HTTPException(status_code=500, detail="Internal server error")


def _owned_lead(lead_id: int, principal: Principal) -> Dict[str, Any]:
    """Loads a lead only if it belongs to the caller's tenant (super_admin sees all)."""
    org = None if principal.role == "super_admin" else principal.org_id
    lead = LeadRepository.get_lead(lead_id, org_id=org)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


# ==================== Authentication ====================

@app.get("/api/auth/me")
def whoami(principal: Principal = Depends(get_current_principal)):
    """Returns the identity behind the presented credential (used by the UI to validate a key)."""
    return {
        "user_id": principal.user_id,
        "org_id": principal.org_id,
        "role": principal.role,
        "permissions": principal.permissions,
        "auth_method": principal.auth_method,
    }

# ==================== Observability & Health Probes (unauthenticated, no data) ====================

@app.get("/healthz/live")
def liveness_probe():
    """Kubernetes / Docker Liveness Probe."""
    return {"status": "alive"}

@app.get("/healthz/ready")
def readiness_probe():
    """Readiness Probe: verifies the database connection."""
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ready", "database": "connected"}
    except Exception:
        logger.exception("Readiness check failed")
        raise HTTPException(status_code=503, detail="Database unready")

@app.get("/api/health")
def legacy_health_check():
    return {"status": "healthy", "system": "AgencyBD_Enterprise Swarm"}

@app.get("/metrics")
def prometheus_metrics(principal: Principal = Depends(require_permission("metrics:read"))):
    """Prometheus scrape endpoint. Scrape with `authorization: {credentials: <JWT>}` or an X-API-Key header."""
    data = MetricsManager.export_prometheus_metrics()
    return Response(content=data, media_type="text/plain; version=0.0.4; charset=utf-8")

@app.get("/api/metrics")
def get_metrics_summary(principal: Principal = Depends(require_permission("metrics:read"))):
    return engine.get_pipeline_metrics(org_id=principal.org_id)

# ==================== Core Swarm Endpoints ====================

@app.get("/api/leads")
def list_leads(
    status: Optional[str] = None,
    org_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require_permission("leads:read")),
):
    return LeadRepository.list_leads(status=status, org_id=scoped_org(principal, org_id), limit=limit)

@app.get("/api/leads/{lead_id}")
def get_lead_detail(lead_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    lead = _owned_lead(lead_id, principal)
    org = lead.get("org_id")
    return {
        "lead": lead,
        "audit": AuditRepository.get_audit_by_lead(lead_id, org_id=org),
        "contacts": ContactRepository.get_contacts_by_lead(lead_id, org_id=org),
        "sequences": OutreachRepository.get_sequences_by_lead(lead_id, org_id=org),
    }

@app.post("/api/sourcing/run")
def run_sourcing(req: SourcingQueryRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    try:
        leads = engine.source_leads(
            channel=req.channel,
            query=req.query,
            location=req.location or "Austin, TX",
            limit=req.limit,
            org_id=principal.org_id,
        )
        MetricsManager.record_lead_sourced(channel=req.channel, org_id=principal.org_id)
        return {"status": "success", "count": len(leads), "leads": leads}
    except Exception as e:
        raise _fail(e)

class LinkedInPeopleRequest(BaseModel):
    company_name: str
    titles: Optional[List[str]] = None
    location: Optional[str] = "United States"
    limit: int = 5

class SiteCrawlRequest(BaseModel):
    domain: str

@app.post("/api/sourcing/linkedin/people")
def search_linkedin_people(req: LinkedInPeopleRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    try:
        profiles = engine.source_linkedin_people(
            company_name=req.company_name,
            titles=req.titles,
            location=req.location or "United States",
            limit=req.limit
        )
        return {"status": "success", "count": len(profiles), "profiles": profiles}
    except Exception as e:
        raise _fail(e)

@app.post("/api/enrich/site_crawl")
def crawl_website(req: SiteCrawlRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    try:
        contacts = engine.crawl_website_for_contacts(req.domain)
        return {"status": "success", "crawl_result": contacts}
    except Exception as e:
        raise _fail(e)

class XRayPeopleRequest(BaseModel):
    company_name: str
    titles: Optional[List[str]] = None
    location: Optional[str] = "United States"
    limit: int = 5
    domain_hint: Optional[str] = None

@app.post("/api/sourcing/xray_people")
def discover_xray_people(req: XRayPeopleRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Sovereign zero-key decision maker discovery using website DOM crawling & 1-click Google X-Ray."""
    try:
        profiles = engine.linkedin_agent.discover_xray_people(
            company_name=req.company_name,
            titles=req.titles,
            location=req.location or "United States",
            limit=req.limit,
            domain_hint=req.domain_hint
        )
        return {"status": "success", "count": len(profiles), "profiles": profiles}
    except Exception as e:
        raise _fail(e)

@app.get("/api/sourcing/venture/sec_edgar")
def get_sec_edgar_venture_leads(limit: int = 15, principal: Principal = Depends(require_permission("leads:read"))):
    """Sovereign real-time venture capital filings stream directly from SEC EDGAR Form D."""
    try:
        leads = engine.sourcing_agent.source_sec_edgar_venture(limit=min(limit, 50), org_id=principal.org_id)
        return {"status": "success", "count": len(leads), "leads": leads}
    except Exception as e:
        raise _fail(e)

@app.get("/api/sourcing/hiring/signals")
def get_hiring_signals_leads(query: str = "Engineer", limit: int = 15, principal: Principal = Depends(require_permission("leads:read"))):
    """Sovereign live hiring bottlenecks stream from Hacker News and RemoteOK."""
    try:
        leads = engine.sourcing_agent.source_hn_hiring_signals(role_keyword=query, limit=min(limit, 50), org_id=principal.org_id)
        return {"status": "success", "count": len(leads), "leads": leads}
    except Exception as e:
        raise _fail(e)

@app.post("/api/audit/run")
def run_audit(req: AuditRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    _owned_lead(req.lead_id, principal)
    try:
        audit = engine.audit_lead(req.lead_id)
        MetricsManager.record_audit(org_id=principal.org_id)
        return {"status": "success", "audit": audit}
    except Exception as e:
        raise _fail(e)

@app.post("/api/enrich/run")
def run_enrichment(req: AuditRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    _owned_lead(req.lead_id, principal)
    try:
        contact = engine.enrich_lead(req.lead_id)
        return {"status": "success", "contact": contact}
    except Exception as e:
        raise _fail(e)

@app.post("/api/sequence/generate")
def run_copywriting(req: AuditRequest, principal: Principal = Depends(require_permission("outreach:draft"))):
    _owned_lead(req.lead_id, principal)
    try:
        result = engine.generate_copywriting(req.lead_id)
        return {"status": "success", "package": result}
    except Exception as e:
        raise _fail(e)

@app.post("/api/dispatch/send")
def run_dispatch(req: AuditRequest, principal: Principal = Depends(require_permission("outreach:dispatch"))):
    _owned_lead(req.lead_id, principal)
    try:
        result = engine.dispatch_lead(req.lead_id)
        MetricsManager.record_dispatch(inbox=result.get("dispatched_from_inbox", "unknown"), org_id=principal.org_id)
        return {"status": "success", "dispatch": result}
    except Exception as e:
        raise _fail(e)

@app.post("/api/pipeline/run")
def run_pipeline(req: AuditRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    _owned_lead(req.lead_id, principal)
    try:
        result = engine.run_autonomous_pipeline(req.lead_id)
        return {"status": "success", "pipeline_result": result}
    except Exception as e:
        raise _fail(e)

@app.post("/api/replies/triage")
def triage_reply(req: ObjectionTriageRequest, principal: Principal = Depends(require_permission("replies:triage"))):
    _owned_lead(req.lead_id, principal)
    try:
        result = engine.triage_reply(req.lead_id, req.reply_text)
        MetricsManager.record_reply(sentiment=result.get("sentiment", "neutral"), org_id=principal.org_id)
        return {"status": "success", "triage": result}
    except Exception as e:
        raise _fail(e)

@app.post("/api/booking/create")
def book_meeting(req: BookingRequest, principal: Principal = Depends(require_permission("booking:create"))):
    _owned_lead(req.lead_id, principal)
    try:
        result = engine.book_meeting(req.lead_id, req.booking_time, req.cal_link)
        MetricsManager.record_meeting_booked(org_id=principal.org_id)
        return {"status": "success", "booking": result}
    except Exception as e:
        raise _fail(e)

# ==================== Geographic & AI Market Intelligence ====================

@app.get("/api/geo/countries")
def get_all_countries(principal: Principal = Depends(require_permission("leads:read"))):
    return {"countries": GeoDatabase.get_all_countries()}

@app.get("/api/geo/states")
def get_states(country: str = Query(..., description="Country name"), principal: Principal = Depends(require_permission("leads:read"))):
    return {"country": country, "states_provinces": GeoDatabase.get_states_provinces(country)}

@app.get("/api/geo/cities")
def get_cities(country: str = Query(...), state: str = Query(...), principal: Principal = Depends(require_permission("leads:read"))):
    cities = GeoDatabase.get_cities(country, state)
    tags = GeoDatabase.get_tech_tags(country, state)
    return {"country": country, "state": state, "cities": cities, "tech_tags": tags}

@app.get("/api/geo/search")
def search_cities(query: str = Query(..., max_length=100), principal: Principal = Depends(require_permission("leads:read"))):
    return {"query": query, "results": GeoDatabase.search_cities_globally(query)}

class MarketDemandRequest(BaseModel):
    project_demand: str
    ticket_size: Optional[str] = "$25k-$75k"
    target_countries: Optional[List[str]] = None

@app.post("/api/intelligence/recommend_markets")
def recommend_markets_endpoint(req: MarketDemandRequest, principal: Principal = Depends(require_permission("leads:read"))):
    return market_intel.analyze_demand(
        project_demand=req.project_demand,
        ticket_size=req.ticket_size or "$25k-$75k",
        target_countries=req.target_countries
    )

# ==================== Live Inbound Webhook Ingress ====================

@app.post("/api/webhooks/inbound")
async def inbound_webhook_endpoint(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-AgencyBD-Signature"),
    x_timestamp: Optional[str] = Header(None, alias="X-AgencyBD-Timestamp"),
    x_org: Optional[str] = Header(None, alias="X-AgencyBD-Org"),
):
    """
    Ingress for inbound replies relayed from ESPs (Resend, SendGrid, Instantly, Smartlead).
    The signature is mandatory: HMAC-SHA256 over f"{timestamp}.{raw_body}" using
    AGENCYBD_WEBHOOK_SECRET, with a 5-minute replay window. Events are attributed to the tenant in
    AGENCYBD_WEBHOOK_ORG_ID.
    """
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")

    try:
        timestamp = int(x_timestamp) if x_timestamp else None
    except ValueError:
        timestamp = None

    # Per-tenant secret when the sender names its workspace; the single legacy secret otherwise.
    if x_org:
        org_id = x_org.strip()
        secret = WebhookSecrets.get(org_id)           # None if the tenant has no secret (indistinguishable from a bad signature)
    else:
        org_id = os.getenv("AGENCYBD_WEBHOOK_ORG_ID", DEFAULT_ORG_ID)
        secret = None                                  # None -> WebhookSecurity falls back to AGENCYBD_WEBHOOK_SECRET
    if (x_org and secret is None) or not x_signature or timestamp is None or not WebhookSecurity.verify_signature(
        raw_body, x_signature, secret=secret, timestamp=timestamp
    ):
        MetricsManager.record_webhook(provider="inbound", status="rejected")
        raise HTTPException(status_code=401, detail="Invalid or missing webhook signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object expected")

    result = webhook_router.process_inbound_reply(payload, org_id=org_id)
    MetricsManager.record_webhook(provider=result.get("provider", "generic"), status="success")
    return result

# ==================== Financial Analytics & DLQ ====================

@app.get("/api/analytics/unit_economics")
def get_unit_economics_endpoint(
    org_id: Optional[str] = None,
    deal_size: float = Query(35000.0, gt=0),
    principal: Principal = Depends(require_permission("metrics:read")),
):
    return FinancialLedger.get_unit_economics(org_id=scoped_org(principal, org_id), pipeline_deal_size=deal_size)

@app.get("/api/analytics/spintax_cohorts")
def get_spintax_cohorts_endpoint(org_id: Optional[str] = None, principal: Principal = Depends(require_permission("metrics:read"))):
    return SpintaxABOptimizer.get_cohort_report(org_id=scoped_org(principal, org_id))

@app.get("/api/tasks/dead_letters")
def get_dead_letter_tasks(org_id: Optional[str] = None, principal: Principal = Depends(require_permission("tasks:manage"))):
    return {"dead_letters": TaskQueueEngine.list_dead_letters(org_id=scoped_org(principal, org_id))}

class RetryTaskRequest(BaseModel):
    task_id: str

@app.post("/api/tasks/retry_dead_letter")
def retry_dead_letter_task(req: RetryTaskRequest, principal: Principal = Depends(require_permission("tasks:manage"))):
    org = None if principal.role == "super_admin" else principal.org_id
    success = TaskQueueEngine.retry_dead_letter(req.task_id, org_id=org)
    return {"task_id": req.task_id, "requeued": success}

# ==================== Zero-Trust Key Management (super_admin only) ====================

class CreateKeyRequest(BaseModel):
    name: str
    user_id: str
    role: str = "growth_lead"
    org_id: Optional[str] = None

class RevokeKeyRequest(BaseModel):
    key_id: int
    org_id: Optional[str] = None

@app.post("/api/security/create_key")
def create_api_key_endpoint(req: CreateKeyRequest, principal: Principal = Depends(require_permission("apikeys:manage"))):
    if req.role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"Unknown role. Valid roles: {sorted(ROLE_PERMISSIONS)}")
    org_id = scoped_org(principal, req.org_id)
    plaintext_key = create_api_key_record(name=req.name, user_id=req.user_id, role=req.role, org_id=org_id)
    return {
        "status": "created",
        "api_key": plaintext_key,
        "name": req.name,
        "role": req.role,
        "org_id": org_id,
        "note": "Copy this key now. It will never be shown again in plaintext."
    }

@app.post("/api/security/webhook_secret")
def rotate_webhook_secret(principal: Principal = Depends(require_permission("webhooks:manage"))):
    """Creates (or rotates) this workspace's webhook signing secret. Shown once. Send it as the HMAC key and add
    `X-AgencyBD-Org: <your org id>` to every inbound webhook."""
    secret = WebhookSecrets.rotate(principal.org_id)
    return {"org_id": principal.org_id, "webhook_secret": secret,
            "note": "Copy this now; it cannot be shown again. Sign f'{timestamp}.{raw_body}' with HMAC-SHA256 and send X-AgencyBD-Org, X-AgencyBD-Timestamp and X-AgencyBD-Signature."}

@app.get("/api/security/list_keys")
def list_api_keys_endpoint(org_id: Optional[str] = None, principal: Principal = Depends(require_permission("apikeys:manage"))):
    return {"keys": list_api_keys(org_id=scoped_org(principal, org_id))}

@app.post("/api/security/revoke_key")
def revoke_api_key_endpoint(req: RevokeKeyRequest, principal: Principal = Depends(require_permission("apikeys:manage"))):
    revoked = revoke_api_key_record(req.key_id, scoped_org(principal, req.org_id))
    return {"revoked": revoked, "key_id": req.key_id}

# ==================== Native Replacement Engines (Zero-Cost / No API Keys) ====================

from engines.native_smtp_verifier import NativeSMTPVerifier
from engines.native_tech_stack_fingerprinter import NativeTechStackFingerprinter
from engines.native_visitor_deanonymizer import NativeVisitorDeanonymizer
from engines.native_warmup_engine import NativeWarmupEngine
from engines.native_sales_intelligence import NativeSalesIntelligence
from engines.native_multimodal_generator import NativeMultimodalGenerator
from engines.native_copy_coach import NativeCopyCoach
from engines.native_waterfall_orchestrator import NativeWaterfallOrchestrator
from engines.native_smartlead_router import NativeSmartleadRouter

native_verifier = NativeSMTPVerifier()
native_fingerprinter = NativeTechStackFingerprinter()
native_deanonymizer = NativeVisitorDeanonymizer()
native_warmup = NativeWarmupEngine()
native_sales_intel = NativeSalesIntelligence()
native_waterfall = NativeWaterfallOrchestrator()

class EmailVerifyRequest(BaseModel):
    email: str

class DomainAuditRequest(BaseModel):
    domain: str

class IPDeanonymizeRequest(BaseModel):
    ip_address: str

class SalesTranscriptRequest(BaseModel):
    transcript: str
    founder_speaker_label: Optional[str] = "Alex"

class VideoPitchRequest(BaseModel):
    prospect_name: str
    company_name: str
    domain: str
    lcp_score: Optional[float] = None
    missing_headers: Optional[List[str]] = None
    proof_point: Optional[str] = None

class CopyScoreRequest(BaseModel):
    subject: str
    body: str

class WaterfallEnrichRequest(BaseModel):
    first_name: str
    last_name: str
    company_name: str
    domain: str
    title: Optional[str] = "Decision Maker"

class SmartleadRouteRequest(BaseModel):
    recipient_mx_host: str
    available_inboxes: List[Dict[str, str]]

class SpintaxRequest(BaseModel):
    template_text: str

@app.post("/api/native/verify_email")
def native_verify_email_endpoint(req: EmailVerifyRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    return native_verifier.verify_email(req.email)

@app.post("/api/native/fingerprint_tech")
def native_fingerprint_tech_endpoint(req: DomainAuditRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    return native_fingerprinter.analyze_domain(req.domain)

@app.post("/api/native/deanonymize_visitor")
def native_deanonymize_visitor_endpoint(req: IPDeanonymizeRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    return native_deanonymizer.resolve_ip(req.ip_address)

@app.post("/api/native/analyze_sales_call")
def native_analyze_sales_call_endpoint(req: SalesTranscriptRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    return native_sales_intel.analyze_transcript(req.transcript, req.founder_speaker_label or "Alex")

@app.post("/api/native/generate_video_storyboard")
def native_generate_video_storyboard_endpoint(req: VideoPitchRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    return NativeMultimodalGenerator.generate_video_pitch_storyboard(
        prospect_name=req.prospect_name,
        company_name=req.company_name,
        domain=req.domain,
        lcp_score=req.lcp_score,
        missing_headers=req.missing_headers,
        proof_point=req.proof_point,
    )

@app.post("/api/native/score_copy")
def native_score_copy_endpoint(req: CopyScoreRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    return NativeCopyCoach.score_draft(req.subject, req.body)

@app.post("/api/native/waterfall_enrich")
def native_waterfall_enrich_endpoint(req: WaterfallEnrichRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    return native_waterfall.run_waterfall_enrichment(
        first_name=req.first_name,
        last_name=req.last_name,
        company_name=req.company_name,
        domain=req.domain,
        title=req.title or "Decision Maker"
    )

@app.post("/api/native/route_smartlead")
def native_route_smartlead_endpoint(req: SmartleadRouteRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    return NativeSmartleadRouter.match_esp_sender(req.recipient_mx_host, req.available_inboxes)

@app.post("/api/native/parse_spintax")
def native_parse_spintax_endpoint(req: SpintaxRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    return {"generated_variant": NativeSmartleadRouter.parse_spintax(req.template_text)}

class ObjectionSimulateRequest(BaseModel):
    objection_text: str

@app.post("/api/native/simulate_objection")
def native_simulate_objection_endpoint(req: ObjectionSimulateRequest, principal: Principal = Depends(require_permission("leads:read"))):
    return NativeSalesIntelligence().simulate_objection(req.objection_text)

@app.get("/api/native/objection_battlecards")
def native_objection_battlecards_endpoint(principal: Principal = Depends(require_permission("leads:read"))):
    return NativeSalesIntelligence().list_battlecards()

from orchestrator.autonomous_autopilot import AutonomousAutopilot
from engines.math_pipeline_engine import MathPipelineEngine

autopilot_engine = AutonomousAutopilot()

class AutopilotRunRequest(BaseModel):
    channel: Optional[str] = "sec_edgar"
    query: Optional[str] = "Form D"
    location: Optional[str] = "United States"
    limit: Optional[int] = 5
    auto_enroll: Optional[bool] = True

class MathScoreRequest(BaseModel):
    source_channel: Optional[str] = "sec_edgar_form_d"
    title: Optional[str] = "CTO"
    lcp_seconds: Optional[float] = 3.2
    detected_stack: Optional[List[str]] = None
    email_confidence: Optional[int] = 90
    catch_all_decoded: Optional[bool] = False

@app.post("/api/swarm/autopilot/run")
def run_swarm_autopilot(req: AutopilotRunRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Executes a fully autonomous multi-agent swarm cycle with Bayesian scoring and cadence dispatch."""
    try:
        result = autopilot_engine.run_autopilot_cycle(
            channel=req.channel or "sec_edgar",
            query=req.query or "Form D",
            location=req.location or "United States",
            limit=min(req.limit or 5, 20),
            auto_enroll=req.auto_enroll if req.auto_enroll is not None else True,
            org_id=principal.org_id
        )
        return {"status": "success", "result": result}
    except Exception as e:
        raise _fail(e)

@app.post("/api/swarm/math/score")
def calculate_lead_math_score(req: MathScoreRequest, principal: Principal = Depends(require_permission("leads:read"))):
    """Calculates Bayesian P(Close), Expected Deal Value, and Cost of Delay."""
    prob = MathPipelineEngine.predict_close_probability(
        source_channel=req.source_channel or "sec_edgar_form_d",
        title=req.title or "CTO",
        lcp_seconds=req.lcp_seconds or 3.2,
        detected_stack=req.detected_stack or ["Next.js"],
        email_confidence=req.email_confidence or 90,
        catch_all_decoded=req.catch_all_decoded or False
    )
    deal = MathPipelineEngine.calculate_expected_deal_value(
        p_close=prob["p_close"],
        source_channel=req.source_channel or "sec_edgar_form_d",
        detected_stack=req.detected_stack or ["Next.js"]
    )
    delay = MathPipelineEngine.calculate_cost_of_delay(lcp_seconds=req.lcp_seconds or 3.2)
    return {
        "status": "success",
        "probability": prob,
        "deal_economics": deal,
        "cost_of_delay": delay
    }

from engines.native_browser_service import NativeBrowserService
from engines.brain_gateway import BrainGateway

browser_service = NativeBrowserService()
brain_gateway = BrainGateway()

class BrainPlanRequest(BaseModel):
    goal: str
    context: Optional[Dict[str, Any]] = None

class BrainChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    context: Optional[Dict[str, Any]] = None

class BrainObjectionRequest(BaseModel):
    objection: str
    prospect_name: Optional[str] = "Lead"
    company: Optional[str] = "Target Corp"
    context: Optional[Dict[str, Any]] = None

class BrainArtifactRequest(BaseModel):
    lead: Dict[str, Any]
    tech_audit: Optional[Dict[str, Any]] = None
    deal_metrics: Optional[Dict[str, Any]] = None

class BrowserRenderRequest(BaseModel):
    domain: str

class BrowserScreenshotRequest(BaseModel):
    domain: str
    viewport: Optional[str] = "desktop"

@app.get("/api/brain/status")
def get_brain_status_endpoint(principal: Principal = Depends(require_permission("leads:read"))):
    """Returns real-time status of active cognitive brain (Ollama, Free Cloud, Claude BYOK, Native)."""
    return {"status": "success", "brain": brain_gateway.detect_active_brain()}

@app.post("/api/brain/plan")
def get_brain_plan_endpoint(req: BrainPlanRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Generates Claude-style ReAct execution plan with tool calling sequence and chain-of-thought."""
    return brain_gateway.think_and_plan(req.goal, req.context)

@app.post("/api/brain/chat")
def get_brain_chat_endpoint(req: BrainChatRequest, principal: Principal = Depends(require_permission("leads:read"))):
    """Conversational Big Brain Co-Pilot for autonomous swarm guidance."""
    return brain_gateway.chat_copilot(req.messages, req.context)

@app.post("/api/brain/triage-objection")
def get_brain_objection_endpoint(req: BrainObjectionRequest, principal: Principal = Depends(require_permission("leads:read"))):
    """Categorizes inbound objection and generates evidence-based rebuttal battlecard."""
    return brain_gateway.triage_objection(req.objection, req.prospect_name or "Lead", req.company or "Target Corp", req.context)

@app.post("/api/brain/artifact")
def get_brain_artifact_endpoint(req: BrainArtifactRequest, principal: Principal = Depends(require_permission("leads:read"))):
    """Generates Claude-style rich interactive markdown proposal with KaTeX math and sprint milestones."""
    return brain_gateway.generate_proposal_artifact(req.lead, req.tech_audit, req.deal_metrics)

@app.post("/api/browser/render")
def browser_render_endpoint(req: BrowserRenderRequest, principal: Principal = Depends(require_permission("leads:read"))):
    """Renders virtual DOM of target website using sovereign headless Chromium and extracts contacts."""
    try:
        return browser_service.render_spa_dom(req.domain)
    except Exception as e:
        raise _fail(e)

@app.post("/api/browser/screenshot")
def browser_screenshot_endpoint(req: BrowserScreenshotRequest, principal: Principal = Depends(require_permission("leads:read"))):
    """Captures high-resolution desktop or mobile screenshot using sovereign headless Chromium."""
    try:
        return browser_service.capture_screenshot(req.domain, viewport=req.viewport or "desktop")
    except Exception as e:
        raise _fail(e)

# ==================== Phase 1: Website Doctor, Briefing & Presence Rescue ====================
from intel.resolver import CompanyResolver
from intel.company_brief import CompanyBriefEngine
from intel.services import ServiceCatalog
from intel.presence import PresenceRescueEngine
from intel import local_hunt
from auditors.engine import WebsiteDoctorEngine
from database.models import AuditRunRepository, CompanyRepository

class ResolveCompanyRequest(BaseModel):
    company_name: str
    hint_domain: Optional[str] = None

class WebsiteDoctorAuditRequest(BaseModel):
    domain: str
    company_id: Optional[int] = None

class PresenceEvaluationRequest(BaseModel):
    business_name: str
    city: str
    domain: Optional[str] = None

@app.post("/api/companies/resolve")
def resolve_company_endpoint(req: ResolveCompanyRequest, principal: Principal = Depends(require_permission("leads:create"))):
    org = principal.org_id
    return CompanyResolver.resolve_domain_from_name(req.company_name, req.hint_domain, org_id=org)

@app.get("/api/companies/{company_id}/brief")
def get_company_brief_endpoint(company_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    """Read-only: builds the brief from evidence already stored. Never fetches or audits."""
    try:
        return CompanyBriefEngine.generate_brief(company_id, principal.org_id, refresh=False)
    except LookupError:
        raise HTTPException(status_code=404, detail="Company not found")

@app.post("/api/companies/{company_id}/brief")
def refresh_company_brief_endpoint(company_id: int, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Fetches the homepage, runs the Website Doctor, stores new evidence, and returns the refreshed brief."""
    try:
        return CompanyBriefEngine.generate_brief(company_id, principal.org_id, refresh=True)
    except LookupError:
        raise HTTPException(status_code=404, detail="Company not found")

@app.post("/api/companies/presence")
def evaluate_presence_endpoint(req: PresenceEvaluationRequest, principal: Principal = Depends(require_permission("leads:read"))):
    return PresenceRescueEngine.evaluate_presence(req.business_name, req.city, req.domain, org_id=principal.org_id)

class LocalHuntRequest(BaseModel):
    category: str
    city: str
    limit: int = 20
    provider: Optional[str] = None  # "google" | "osm"; default google if keyed, else osm

class LocalHuntSaveRequest(BaseModel):
    name: str
    city: str
    domain: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    rating: float = 0.0
    reviews: int = 0
    classification: str
    place_id: Optional[str] = None
    category: Optional[str] = None
    provider: Optional[str] = None
    pitch_strategy: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

@app.get("/api/hunt/local/providers")
def local_hunt_providers(principal: Principal = Depends(require_permission("leads:read"))):
    return local_hunt.provider_status()

@app.post("/api/hunt/local")
def local_hunt_search(req: LocalHuntRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Finds local businesses and ranks how winnable they are. Results are not stored until you save one."""
    return local_hunt.hunt(req.category, req.city, req.limit, req.provider)

@app.post("/api/hunt/local/save")
def local_hunt_save(req: LocalHuntSaveRequest, principal: Principal = Depends(require_permission("leads:create"))):
    """Saves one result as a lead with full pitch strategy attached."""
    key = req.domain or f"nosite-{(req.place_id or req.name).lower().replace(' ', '-')[:60]}.invalid"
    note_parts = [f"WEB PRESENCE: {req.classification}"]
    if req.pitch_strategy:
        if req.pitch_strategy.get("angle"):
            note_parts.append(f"PITCH ANGLE: {req.pitch_strategy.get('angle')}")
        if req.pitch_strategy.get("value_estimate"):
            note_parts.append(f"EST VALUE: {req.pitch_strategy.get('value_estimate')}")
        if req.pitch_strategy.get("cold_pitch_hook"):
            note_parts.append(f"COLD HOOK: {req.pitch_strategy.get('cold_pitch_hook')}")
    if req.notes:
        note_parts.append(req.notes)

    channel = "google_maps" if req.provider == "google" else "map_osm"
    lead = LeadRepository.create_or_get_lead(
        company_name=req.name, domain=key, phone=req.phone, address=req.address, rating=req.rating or 0.0,
        reviews_count=req.reviews, source_channel=channel, source_query=f"{req.category or ''} in {req.city}".strip(),
        notes=" | ".join(note_parts), org_id=principal.org_id)
    return lead

@app.post("/api/hunt/local/batch_save")
def local_hunt_batch_save(items: List[LocalHuntSaveRequest], principal: Principal = Depends(require_permission("leads:create"))):
    """Saves multiple hunt results as leads in a single 1-click batch action."""
    saved_leads = []
    for req in items:
        key = req.domain or f"nosite-{(req.place_id or req.name).lower().replace(' ', '-')[:60]}.invalid"
        note_parts = [f"WEB PRESENCE: {req.classification}"]
        if req.pitch_strategy:
            if req.pitch_strategy.get("angle"):
                note_parts.append(f"PITCH ANGLE: {req.pitch_strategy.get('angle')}")
            if req.pitch_strategy.get("value_estimate"):
                note_parts.append(f"EST VALUE: {req.pitch_strategy.get('value_estimate')}")
        channel = "google_maps" if req.provider == "google" else "map_osm"
        lead = LeadRepository.create_or_get_lead(
            company_name=req.name, domain=key, phone=req.phone, address=req.address, rating=req.rating or 0.0,
            reviews_count=req.reviews, source_channel=channel, source_query=f"{req.category or ''} in {req.city}".strip(),
            notes=" | ".join(note_parts), org_id=principal.org_id)
        saved_leads.append(lead)
    return {"saved_count": len(saved_leads), "leads": saved_leads}


class LocalHuntProbeRequest(BaseModel):
    name: str
    city: str
    website: Optional[str] = None


class DealStageUpdateRequest(BaseModel):
    lead_id: int
    new_stage: str


class DealCreateRequest(BaseModel):
    company_name: str
    domain: str
    stage: str = "sourced"
    deal_value: float = 4500.0
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/hunt/local/probe_presence")
def local_hunt_probe_presence(req: LocalHuntProbeRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Probes web presence and DNS/SSL reachability for a specific business."""
    return local_hunt.probe_presence_live(req.name, req.city, req.website)


@app.get("/api/pipeline/deals")
def get_pipeline_deals(principal: Principal = Depends(require_permission("leads:read"))):
    """Returns structured CRM pipeline deals grouped by stage with live revenue forecasting."""
    return LeadRepository.get_pipeline(org_id=principal.org_id)


@app.post("/api/pipeline/deals/stage")
def update_pipeline_deal_stage(req: DealStageUpdateRequest, principal: Principal = Depends(require_permission("leads:create"))):
    """Updates deal stage in the CRM pipeline with audit logging."""
    res = LeadRepository.update_deal_stage(req.lead_id, req.new_stage, org_id=principal.org_id)
    if not res:
        raise HTTPException(status_code=404, detail="Lead not found in this organization")
    return res


@app.post("/api/pipeline/deals/create")
def create_pipeline_deal(req: DealCreateRequest, principal: Principal = Depends(require_permission("leads:create"))):
    """Creates a deal in the CRM pipeline."""
    note_parts = [f"EST VALUE: ${req.deal_value:,.0f}"]
    if req.notes:
        note_parts.append(req.notes)
    lead = LeadRepository.create_or_get_lead(
        company_name=req.company_name,
        domain=req.domain,
        phone=req.phone,
        address=req.address,
        source_channel="crm_pipeline",
        notes=" | ".join(note_parts),
        org_id=principal.org_id
    )
    if req.stage != "sourced":
        lead = LeadRepository.update_deal_stage(lead["id"], req.stage, org_id=principal.org_id)
    else:
        lead["deal_stage"] = lead.get("status", "sourced")
    return lead


from llm import reasoning as llm_reasoning

@app.post("/api/opportunities/{opportunity_id}/analyze")
def analyze_opportunity_fit(opportunity_id: int, principal: Principal = Depends(require_permission("outreach:draft"))):
    """LLM go/no-go reasoning, grounded in quotes from the job post. 503 if no model is configured."""
    try:
        return llm_reasoning.analyze_fit(opportunity_id, principal.org_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Opportunity not found")

@app.post("/api/companies/{company_id}/brief/summary")
def summarize_company_brief(company_id: int, principal: Principal = Depends(require_permission("outreach:draft"))):
    """LLM summary of the stored brief; every sentence cites evidence ids."""
    try:
        brief = CompanyBriefEngine.generate_brief(company_id, principal.org_id, refresh=False)
    except LookupError:
        raise HTTPException(status_code=404, detail="Company not found")
    return llm_reasoning.summarize_brief(brief, principal.org_id)

from workflows import digest as digest_mod

@app.get("/api/digest")
def preview_digest(limit: int = 10, min_score: float = 0.0, principal: Principal = Depends(require_permission("leads:read"))):
    return digest_mod.build_digest(principal.org_id, limit=min(limit, 30), min_score=min_score)

@app.post("/api/digest/send")
def send_digest(principal: Principal = Depends(require_permission("outreach:dispatch"))):
    d = digest_mod.build_digest(principal.org_id)
    return {"delivered": digest_mod.send_to_slack(d["text"]), "opportunity_count": d["opportunity_count"]}

from workflows import controls as org_controls

class HaltRequest(BaseModel):
    halted: bool
    reason: str = ""

@app.get("/api/controls/outbound")
def get_outbound_halt(principal: Principal = Depends(require_permission("leads:read"))):
    return org_controls.halt_state(principal.org_id)

@app.post("/api/controls/outbound")
def set_outbound_halt(req: HaltRequest, principal: Principal = Depends(require_permission("outbound:manage"))):
    """The kill switch: halted=true stops every send for this tenant immediately (manual and scheduled)."""
    return org_controls.set_halted(principal.org_id, req.halted, principal.user_id, req.reason)

class ServiceRequest(BaseModel):
    service_key: str
    name: str
    offer: str
    price_band: Optional[str] = None
    objections: Optional[List[str]] = None

@app.get("/api/services")
def list_services(principal: Principal = Depends(require_permission("leads:read"))):
    return ServiceCatalog.list(principal.org_id)

@app.post("/api/services")
def upsert_service(req: ServiceRequest, principal: Principal = Depends(require_permission("portfolio:manage"))):
    return ServiceCatalog.upsert(principal.org_id, req.service_key, req.name, req.offer, req.price_band, req.objections)

@app.delete("/api/services/{service_key}")
def delete_service(service_key: str, principal: Principal = Depends(require_permission("portfolio:manage"))):
    if not ServiceCatalog.delete(principal.org_id, service_key):
        raise HTTPException(status_code=404, detail="Service not found")
    return {"deleted": service_key}

@app.post("/api/audits/run")
def run_website_doctor_endpoint(req: WebsiteDoctorAuditRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    org = principal.org_id
    return WebsiteDoctorEngine.run_audit(req.domain, req.company_id, org_id=org)

@app.get("/api/audits/{audit_id}")
def get_audit_findings_endpoint(audit_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    org = principal.org_id
    findings = AuditRunRepository.get_findings(audit_id, org_id=org)
    return {"audit_id": audit_id, "findings": findings}

# ==================== Phase 2 & 3: Opportunity Radar & Proposal Studio ====================
from radar.engine import OpportunityRadarEngine
from agents.proposal_agent import ProposalAgent
from portfolio.library import PortfolioLibrary
from database.models import OpportunityRepository, ApprovalRepository

class DraftProposalRequest(BaseModel):
    opportunity_id: int
    title: Optional[str] = None        # ignored: the stored opportunity is the source of truth
    description: Optional[str] = None  # ignored
    client_name: Optional[str] = None

class DecideApprovalRequest(BaseModel):
    decision: str
    reason: Optional[str] = None

@app.get("/api/opportunities")
def list_opportunities_endpoint(source: Optional[str] = None, limit: int = 50, principal: Principal = Depends(require_permission("leads:read"))):
    org = principal.org_id
    """Read-only. Fetching from the internet happens only via POST /api/radar/scan."""
    return OpportunityRepository.list_opportunities(source=source, limit=min(limit, 200), org_id=org)

@app.post("/api/radar/scan")
def scan_radar_endpoint(principal: Principal = Depends(require_permission("pipeline:run"))):
    org = principal.org_id
    return OpportunityRadarEngine().scan_all_sources(limit_per_source=10, org_id=org)

@app.post("/api/proposals/draft")
def draft_proposal_endpoint(req: DraftProposalRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    try:
        return ProposalAgent.draft_proposal(
            opportunity_id=req.opportunity_id,
            title=req.title,
            description=req.description,
            client_name=req.client_name,
            org_id=principal.org_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Opportunity not found")

class PortfolioAssetRequest(BaseModel):
    title: str
    body: str
    industry: Optional[str] = None
    services: Optional[List[str]] = None
    tech: Optional[List[str]] = None
    metrics: Optional[Dict[str, Any]] = None
    source_url: Optional[str] = None

@app.get("/api/portfolio/assets")
def list_portfolio_assets(principal: Principal = Depends(require_permission("leads:read"))):
    return PortfolioLibrary.list_assets(principal.org_id)

@app.post("/api/portfolio/assets")
def add_portfolio_asset(req: PortfolioAssetRequest, principal: Principal = Depends(require_permission("portfolio:manage"))):
    return PortfolioLibrary.add_asset(principal.org_id, req.title, req.body, req.industry, req.services, req.tech, req.metrics, req.source_url)

@app.delete("/api/portfolio/assets/{asset_id}")
def delete_portfolio_asset(asset_id: int, principal: Principal = Depends(require_permission("portfolio:manage"))):
    if not PortfolioLibrary.delete_asset(principal.org_id, asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": asset_id}

class ProposalOutcomeRequest(BaseModel):
    status: str  # submitted | won | lost
    reason: Optional[str] = None

@app.post("/api/proposals/{proposal_id}/outcome")
def record_proposal_outcome(proposal_id: int, req: ProposalOutcomeRequest, principal: Principal = Depends(require_permission("outreach:draft"))):
    """Records what happened to a proposal after a human sent it. This is the data the learning loop learns from."""
    if req.status not in ("submitted", "won", "lost"):
        raise HTTPException(status_code=400, detail="status must be submitted, won or lost")
    with get_db() as conn:
        row = conn.execute("SELECT status FROM proposals WHERE id = ? AND org_id = ?", (proposal_id, principal.org_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if req.status in ("won", "lost") and row["status"] not in ("approved", "submitted", "won", "lost"):
        raise HTTPException(status_code=409, detail="Only an approved proposal can have an outcome. Approve it first.")
    ProposalRepository.update_status(proposal_id, req.status, req.reason, org_id=principal.org_id)
    return {"proposal_id": proposal_id, "status": req.status}

class ExpenseRequest(BaseModel):
    expense_type: str
    amount_usd: float = Field(..., gt=0, le=1_000_000)
    note: Optional[str] = None

@app.post("/api/analytics/expenses")
def record_expense(req: ExpenseRequest, principal: Principal = Depends(require_permission("pipeline:write"))):
    """Records a cost the system cannot see itself (verifier credits, Upwork Connects, subscriptions)."""
    return FinancialLedger.record_expense(principal.org_id, req.expense_type.strip()[:60], req.amount_usd, metadata={"note": req.note})

@app.get("/api/approvals/pending")
def list_pending_approvals_endpoint(principal: Principal = Depends(require_permission("approvals:read"))):
    org = principal.org_id
    return ApprovalRepository.list_pending(org_id=org)

@app.post("/api/approvals/{approval_id}/decide")
def decide_approval_endpoint(approval_id: int, req: DecideApprovalRequest, principal: Principal = Depends(require_permission("approvals:write"))):
    org = principal.org_id
    ApprovalRepository.decide(
        approval_id=approval_id,
        decision=req.decision,
        decided_by=principal.user_id,
        reason=req.reason,
        org_id=org
    )
    return {"status": "success", "approval_id": approval_id, "decision": req.decision}

# ==================== Phase 4 & 5 Modular Routers ====================
from routers import outbound_router, compliance_router, policy_router, analytics_router, replies_router, sequences_router, connectors_router, system_router

app.include_router(outbound_router)
app.include_router(compliance_router)
app.include_router(policy_router)
app.include_router(analytics_router)
app.include_router(replies_router)
app.include_router(sequences_router)
app.include_router(connectors_router)
app.include_router(system_router)

# ==================== Unified Sovereign Frontend Mount ====================
frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static_frontend")




