"""
AgencyBD_Enterprise: FastAPI High-Performance REST Service.
Provides enterprise endpoints for multi-channel lead sourcing, technical audits,
enrichment, sequence generation, dispatch, objection triage, CRM booking,
Prometheus observability, inbound webhooks, and global AI market intelligence.
"""

import logging
import os
import hashlib
import re
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Header, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from net.fetcher import SSRFSecurityError, HostUnreachableError
from config.honesty import NotConfiguredError, PreconditionFailedError
from llm.client import LLMError
from pydantic import BaseModel, Field

from config.env import get_list, is_production
from orchestrator.swarm_engine import SwarmEngine
from database.models import ProposalRepository, LeadRepository, AuditRepository, ContactRepository, OutreachRepository
from schemas.lead import SourcingQueryRequest
from schemas.audit import AuditRequest
from schemas.outreach import ObjectionTriageRequest, BookingRequest
from data.geo_database import GeoDatabase
from agents.inbound_webhook_router import InboundWebhookRouter
from security.webhook_verifier import WebhookSecurity, WebhookSecrets
from security.auth import (
    Principal,
    ROLE_PERMISSIONS,
    DEFAULT_ORG_ID,
    get_current_principal,
    require_permission,
    require_role,
    scoped_org,
)
from core.metrics import MetricsManager
from database.db import get_db
from analytics.financial_ledger import FinancialLedger
from analytics.ab_testing_cohorts import SpintaxABOptimizer
from tasks.task_queue import TaskQueueEngine

logger = logging.getLogger("AgencyBD.api")

_docs_enabled = (not is_production()) or os.getenv("AGENCYBD_ENABLE_DOCS", "").lower() == "true"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Starts the sequence scheduler in-process when AGENCYBD_SCHEDULER=on (otherwise run scripts/run_scheduler.py)."""
    runner = None
    try:
        from config import integrations as _integrations
        _integrations.apply_all()                       # keys saved in Settings take effect after a restart too
    except Exception:
        logger.exception("could not apply saved integration keys")
    try:
        from config import agency_profile as _profile
        _profile.apply_all()                            # the agency identity saved in Settings survives a restart
    except Exception:
        logger.exception("could not apply the saved agency profile")
    alert_worker = None
    try:
        from alertdesk import worker as _alerts
        alert_worker = _alerts.start()                  # idles until a workspace switches the Alert Desk on
    except Exception:
        logger.exception("could not start the alert desk")
    lead_worker = None
    try:
        from leadfinder import worker as _leads
        lead_worker = _leads.start()                    # idles until a search is saved
    except Exception:
        logger.exception("could not start the lead finder")
    if os.getenv("AGENCYBD_SCHEDULER", "off").lower() in ("on", "true", "1"):
        from workflows.scheduler import SchedulerThread
        runner = SchedulerThread(int(os.getenv("AGENCYBD_SCHEDULER_INTERVAL", "60")))
        runner.start()
    yield
    if runner:
        runner.stop()
    if alert_worker:
        alert_worker.stop()
    if lead_worker:
        lead_worker.stop()


app = FastAPI(
    lifespan=lifespan,
    title="AgencyBD Enterprise Engine",
    description="Autonomous Multi-Agent Business Development & Lead Intelligence Swarm for Software Agencies",
    version="2.1.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Credentials travel in the Authorization header (Bearer session token), never cookies, so credentialed CORS is not needed.
# Browsers may only call the API from the origins listed in AGENCYBD_CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_list("AGENCYBD_CORS_ORIGINS", "http://localhost:5173,http://localhost:8001"),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Adds security headers, a request id, a structured access log line and request metrics (route templates, so labels stay bounded)."""
    import time
    import uuid
    from core import metrics as m
    request_id = request.headers.get("X-Request-ID", "")[:64] or uuid.uuid4().hex[:16]
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        logger.exception("unhandled error", extra={"event": "http_error", "trace_id": request_id})
        raise
    finally:
        elapsed = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", None) or "unmatched"
        if not route.startswith("/healthz"):
            m.HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
            m.HTTP_LATENCY.labels(route).observe(elapsed)
            logger.info("request", extra={"event": "http_request", "trace_id": request_id,
                                          "extra_data": {"method": request.method, "route": route, "status": status, "ms": int(elapsed * 1000)}})
    response.headers.setdefault("X-Request-ID", request_id)
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


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    """Language model provider errors (network, auth, quota) are mapped to 502 with detail."""
    return JSONResponse(status_code=502, content={"status": "llm_error", "detail": f"Language model error: {exc}"})


engine = SwarmEngine()
webhook_router = InboundWebhookRouter()

MAX_WEBHOOK_BYTES = 1_000_000


def _fail(exc: Exception) -> HTTPException:
    """Maps domain errors to 400 and hides internal failures behind a generic 500."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, (NotConfiguredError, PreconditionFailedError, HostUnreachableError, SSRFSecurityError, LLMError)):
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
    """Returns the identity behind the presented session token (used by the UI to validate a session)."""
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
    """Prometheus scrape endpoint. Scrape with `authorization: {credentials: <JWT>}`."""
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
        out = engine.sourcing_agent.source_sec_edgar_venture(limit=min(limit, 50), org_id=principal.org_id)
        return {"status": "success", "count": len(out["leads"]), "leads": out["leads"], "skipped": out["skipped"]}
    except Exception as e:
        raise _fail(e)

@app.get("/api/sourcing/hiring/signals")
def get_hiring_signals_leads(query: str = "Engineer", limit: int = 15, principal: Principal = Depends(require_permission("leads:read"))):
    """Sovereign live hiring bottlenecks stream from Hacker News and RemoteOK."""
    try:
        out = engine.sourcing_agent.source_hn_hiring_signals(role_keyword=query, limit=min(limit, 50), org_id=principal.org_id)
        return {"status": "success", "count": len(out["leads"]), "leads": out["leads"], "skipped": out["skipped"], "errors": out["errors"]}
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

# ==================== Webhook signing secret ====================

@app.post("/api/security/webhook_secret")
def rotate_webhook_secret(principal: Principal = Depends(require_permission("webhooks:manage"))):
    """Creates (or rotates) this workspace's webhook signing secret. Shown once. Send it as the HMAC key and add
    `X-AgencyBD-Org: <your org id>` to every inbound webhook."""
    secret = WebhookSecrets.rotate(principal.org_id)
    return {"org_id": principal.org_id, "webhook_secret": secret,
            "note": "Copy this now; it cannot be shown again. Sign f'{timestamp}.{raw_body}' with HMAC-SHA256 and send X-AgencyBD-Org, X-AgencyBD-Timestamp and X-AgencyBD-Signature."}

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







from engines.native_browser_service import NativeBrowserService

browser_service = NativeBrowserService()





class BrowserRenderRequest(BaseModel):
    domain: str

class BrowserScreenshotRequest(BaseModel):
    domain: str
    viewport: Optional[str] = "desktop"






@app.post("/api/browser/render")
def browser_render_endpoint(req: BrowserRenderRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Renders virtual DOM of target website using sovereign headless Chromium and extracts contacts."""
    try:
        return browser_service.render_spa_dom(req.domain)
    except Exception as e:
        raise _fail(e)

@app.post("/api/browser/screenshot")
def browser_screenshot_endpoint(req: BrowserScreenshotRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Captures high-resolution desktop or mobile screenshot using sovereign headless Chromium."""
    try:
        return browser_service.capture_screenshot(req.domain, viewport=req.viewport or "desktop")
    except Exception as e:
        raise _fail(e)

from database.models import EvidenceRepository


@app.get("/api/evidence/{evidence_id}")
def get_evidence_record_endpoint(evidence_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    """One stored evidence row (claim, measured value, source, method, time). Tenant-scoped."""
    rec = EvidenceRepository.get_by_ids([evidence_id], principal.org_id).get(evidence_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    return {"status": "success", "evidence": rec}


# ==================== Interactive browser viewer ====================
from engines.interactive_browser_session import InteractiveBrowserSession

_interactive_sessions: Dict[str, InteractiveBrowserSession] = {}
MAX_INTERACTIVE_SESSIONS = 20
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

def _get_interactive_session(session_id: str, principal: Principal) -> InteractiveBrowserSession:
    """Sessions are private to the tenant and user that opened them; the id never reaches the filesystem unvalidated."""
    if not _SESSION_ID_RE.match(session_id or ""):
        raise HTTPException(status_code=422, detail="session_id must be 1-40 letters, digits, '-' or '_'.")
    key = hashlib.sha256(f"{principal.org_id}:{principal.user_id}:{session_id}".encode()).hexdigest()[:24]
    if key not in _interactive_sessions:
        if len(_interactive_sessions) >= MAX_INTERACTIVE_SESSIONS:
            _interactive_sessions.pop(next(iter(_interactive_sessions)))
        _interactive_sessions[key] = InteractiveBrowserSession(session_id=key)
    return _interactive_sessions[key]


class InteractiveNavigateRequest(BaseModel):
    target: str
    session_id: Optional[str] = "default"
    viewport: Optional[str] = "desktop"


class InteractiveHeadedRequest(BaseModel):
    url: Optional[str] = None
    session_id: Optional[str] = "default"



@app.post("/api/browser/interactive/navigate")
def interactive_browser_navigate(req: InteractiveNavigateRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Navigates the interactive browser session with Human Touch support and returns viewport screenshot."""
    try:
        session = _get_interactive_session(req.session_id or "default", principal)
        return session.navigate(req.target, viewport=req.viewport or "desktop")
    except Exception as e:
        raise _fail(e)


@app.post("/api/browser/interactive/headed-window")
def interactive_browser_launch_headed(req: InteractiveHeadedRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Launches a live headed Chrome window on host system for direct physical human takeover."""
    try:
        session = _get_interactive_session(req.session_id or "default", principal)
        return session.launch_headed_window(url=req.url)
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
    return local_hunt.hunt(req.category, req.city, req.limit, req.provider, org_id=principal.org_id)

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
    deal_value: Optional[float] = Field(None, ge=0)     # optional: a value exists only if a person enters one
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/hunt/local/probe_presence")
def local_hunt_probe_presence(req: LocalHuntProbeRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Probes web presence and DNS/SSL reachability for a specific business."""
    return local_hunt.probe_presence_live(req.name, req.city, req.website, org_id=principal.org_id)


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
    if req.new_stage.lower() == "won":
        try:
            from workflows import client_notes as _cn
            lead = LeadRepository.get_lead(req.lead_id, principal.org_id)
            task = _cn.ask_for_review(principal.org_id, req.lead_id, (lead or {}).get("company_name") or "the client")
            if task and isinstance(res, dict):
                res = {**res, "review_task": {"id": task["id"], "due_date": task["due_date"]}}
        except Exception:
            logger.exception("could not plan the review request")
    try:
        from routers.webhooks import dispatch_webhook_event
        dispatch_webhook_event(principal.org_id, "client.stage_changed", {"lead_id": req.lead_id, "new_stage": req.new_stage})
        if req.new_stage.lower() == "won":
            dispatch_webhook_event(principal.org_id, "deal.won", {"lead_id": req.lead_id, "stage": "won"})
    except Exception:
        pass
    return res


@app.post("/api/pipeline/deals/create")
def create_pipeline_deal(req: DealCreateRequest, principal: Principal = Depends(require_permission("leads:create"))):
    """Creates a deal in the CRM pipeline."""
    note_parts = [f"EST VALUE: ${req.deal_value:,.0f}"] if req.deal_value else []
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
    try:
        from routers.webhooks import dispatch_webhook_event
        dispatch_webhook_event(principal.org_id, "client.created", {"lead_id": lead["id"], "company_name": req.company_name, "domain": req.domain})
    except Exception:
        pass
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
def draft_proposal_endpoint(req: DraftProposalRequest, principal: Principal = Depends(require_permission("outreach:draft"))):
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

class ProposalSendRequest(BaseModel):
    channel: str = "email"
    recipient: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    next_followup_days: int = 3

@app.post("/api/proposals/{proposal_id}/send")
def send_proposal_endpoint(proposal_id: int, req: ProposalSendRequest, principal: Principal = Depends(require_permission("outreach:draft"))):
    """Sends or logs proposal dispatch via email or source platform, setting follow-up in Channels."""
    from datetime import date, timedelta
    from workflows import channels as ch

    org_id = principal.org_id
    with get_db() as conn:
        cursor = conn.cursor()
        prop = cursor.execute("SELECT * FROM proposals WHERE id = ? AND org_id = ?", (proposal_id, org_id)).fetchone()
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")
        opp = cursor.execute("SELECT * FROM opportunities WHERE id = ? AND org_id = ?", (prop["opportunity_id"], org_id)).fetchone()

    opp_dict = dict(opp) if opp else {}
    body_text = (req.body or prop["body"] or "").strip()
    channel = req.channel.lower().strip() or "email"

    # 1. Update proposal status to submitted and update body if edited
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE proposals SET status = 'submitted', body = ?, outcome_reason = ? WHERE id = ? AND org_id = ?",
            (body_text, f"Dispatched via {channel}", proposal_id, org_id)
        )
        cursor.execute(
            "UPDATE approvals SET decision = 'approved', decided_by = ?, decided_at = CURRENT_TIMESTAMP WHERE subject_type = 'proposal' AND subject_id = ? AND org_id = ?",
            (principal.user_id, proposal_id, org_id)
        )
        conn.commit()

    followup_date = (date.today() + timedelta(days=max(1, req.next_followup_days))).isoformat()
    channel_record_id = None

    if channel == "email":
        recipient_email = (req.recipient or "").strip()
        if not recipient_email:
            raise HTTPException(status_code=400, detail="Recipient email is required for email channel")
        from adapters.vendor_connectors import VendorConnectors
        try:
            VendorConnectors.dispatch_email(
                to_email=recipient_email,
                subject=req.subject or f"Proposal: {opp_dict.get('title') or 'Project'}",
                body=body_text
            )
        except Exception as exc:
            logger.warning("Email dispatch note: %s", exc)

        try:
            rec = ch.add_record(org_id, "other", "pipeline", {
                "title": f"Email: {opp_dict.get('title') or 'Proposal'}",
                "counterparty": opp_dict.get("company_name") or recipient_email,
                "url": opp_dict.get("url"),
                "status": "applied",
                "next_followup": followup_date,
                "notes": f"Sent proposal to {recipient_email}\n\n{body_text[:500]}"
            })
            channel_record_id = rec.get("id")
        except Exception:
            pass

        return {
            "ok": True,
            "status": "submitted",
            "channel": "email",
            "recipient": recipient_email,
            "channel_record_id": channel_record_id,
            "followup_date": followup_date,
            "message": f"Proposal successfully dispatched to {recipient_email}!"
        }

    plat = channel if channel in ch.PLATFORMS else "other"
    try:
        rec = ch.add_record(org_id, plat, "pipeline", {
            "title": opp_dict.get("title") or "Opportunity",
            "counterparty": opp_dict.get("company_name") or opp_dict.get("source") or plat,
            "url": req.recipient or opp_dict.get("url"),
            "status": "applied",
            "next_followup": followup_date,
            "notes": body_text[:1000]
        })
        channel_record_id = rec.get("id")
        ch.add_record(org_id, plat, "activity", {
            "kind": "proposal_sent",
            "qty": 1,
            "day": date.today().isoformat()
        })
    except Exception as exc:
        logger.warning("Channel record note: %s", exc)

    return {
        "ok": True,
        "status": "submitted",
        "channel": channel,
        "recipient": req.recipient or opp_dict.get("url") or plat,
        "channel_record_id": channel_record_id,
        "followup_date": followup_date,
        "message": f"Proposal logged as submitted on {plat.capitalize()}! Follow-up reminder set for {followup_date}."
    }


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

from routers.integrations import router as integrations_router
app.include_router(integrations_router)
from routers.channels import router as channels_router
from routers.today import router as today_router
app.include_router(channels_router)
app.include_router(today_router)
from routers.client_notes import router as client_notes_router
app.include_router(client_notes_router)
from routers.workspace import router as workspace_router
app.include_router(workspace_router)
from routers.alerts import router as alerts_router
from routers.leadfinder import router as leadfinder_router
from routers.auth import router as auth_router
from routers.partners import router as partners_router
app.include_router(alerts_router)
app.include_router(leadfinder_router)
app.include_router(auth_router)
app.include_router(partners_router)
app.include_router(outbound_router)
app.include_router(compliance_router)
app.include_router(policy_router)
app.include_router(analytics_router)
app.include_router(replies_router)
app.include_router(sequences_router)
app.include_router(connectors_router)
app.include_router(system_router)
from routers.visitor_intent import router as visitor_intent_router
app.include_router(visitor_intent_router)
from routers.webhooks import router as webhooks_router, dispatch_webhook_event
app.include_router(webhooks_router)
from routers.tasks import router as tasks_router
app.include_router(tasks_router)
from routers.crm_sync import router as crm_sync_router
app.include_router(crm_sync_router)
from routers.video_pitch import router as video_pitch_router
app.include_router(video_pitch_router)
from routers.voice_relay import router as voice_relay_router
app.include_router(voice_relay_router)

# ==================== Autopilot, priority, inbox, reports, assistant ====================
from orchestrator.autopilot import DiscoveryRun
from orchestrator import jobs as discovery_jobs
from intel import lead_priority
from intel.comparison import compare_domains
from reports.client_report import ClientReport
from reports.deck_generator import ExecutiveDeckGenerator
from routers.system import build_checks
from workflows.inbox import WorkItemRepository
from llm.client import LLMGateway
from outbound.verify import EmailVerificationGate

client_report = ClientReport()
deck_generator = ExecutiveDeckGenerator()


class DiscoveryRunRequest(BaseModel):
    channel: str = "hiring"          # hiring | sec_edgar | local
    query: str = ""                  # role keyword, or business type for "local"
    location: str = ""               # city, for "local"
    limit: int = 5


@app.post("/api/autopilot/run")
def run_discovery(req: DiscoveryRunRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Starts a Discovery Run in the background and returns its id. Poll GET /api/autopilot/runs/{id}. Never invents data."""
    try:
        return discovery_jobs.start(principal.org_id, req.model_dump(), principal.user_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/radar/scan/start")
def start_radar_scan(principal: Principal = Depends(require_permission("pipeline:run"))):
    """Starts a source scan in the background (sources are read in parallel). Poll GET /api/autopilot/runs/{id}."""
    return discovery_jobs.start(principal.org_id, {"channel": "radar_scan"}, principal.user_id)


@app.get("/api/autopilot/runs/{run_id}")
def get_discovery_run(run_id: str, principal: Principal = Depends(require_permission("leads:read"))):
    out = discovery_jobs.get(principal.org_id, run_id)
    if not out:
        raise HTTPException(status_code=404, detail="Run not found")
    return out


@app.get("/api/leads/{lead_id}/priority")
def get_lead_priority(lead_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    try:
        return lead_priority.score_lead(lead_id, principal.org_id, persist=False)
    except LookupError:
        raise HTTPException(status_code=404, detail="Lead not found")


@app.post("/api/leads/{lead_id}/priority")
def recompute_lead_priority(lead_id: int, principal: Principal = Depends(require_permission("leads:write"))):
    try:
        return lead_priority.score_lead(lead_id, principal.org_id, persist=True)
    except LookupError:
        raise HTTPException(status_code=404, detail="Lead not found")


@app.get("/api/analytics/priority_calibration")
def priority_calibration(principal: Principal = Depends(require_permission("metrics:read"))):
    return lead_priority.calibration(principal.org_id)


@app.get("/api/inbox")
def today_inbox(principal: Principal = Depends(require_permission("leads:read"))):
    """One ranked list of what needs a person: approvals, work items opened by automation, and blocking setup gaps."""
    org = principal.org_id
    items: List[Dict[str, Any]] = []
    for a in ApprovalRepository.list_pending(org):
        items.append({"type": "approval", "priority": 90, "id": a["id"], "title": a.get("draft_subject") or f"Approve {a['subject_type']}",
                      "detail": a.get("draft_recipient") or a.get("reason") or "", "data": a})
    for w in WorkItemRepository.list_open(org, 100):
        items.append({"type": "work_item", "priority": w["priority"], "id": w["id"], "kind": w["kind"], "title": w["title"],
                      "detail": w["detail"], "entity_type": w["entity_type"], "entity_id": w["entity_id"]})
    for c in build_checks(org):
        if c["status"] == "missing" and c["required"]:
            items.append({"type": "setup", "priority": 60, "id": c["key"], "title": c["label"], "detail": c.get("fix") or ""})
    items.sort(key=lambda i: -i["priority"])
    return {"count": len(items), "items": items}


class ResolveWorkItemRequest(BaseModel):
    status: str = "done"             # done | dismissed


@app.post("/api/inbox/work_items/{item_id}/resolve")
def resolve_work_item(item_id: int, req: ResolveWorkItemRequest, principal: Principal = Depends(require_permission("leads:write"))):
    if not WorkItemRepository.resolve(principal.org_id, item_id, req.status):
        raise HTTPException(status_code=404, detail="Open work item not found")
    return {"resolved": item_id, "status": req.status}


from intel import advisor


@app.get("/api/companies/{company_id}/advice")
def company_advice(company_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    """Recommendations from stored audit findings, mapped to your services. No AI key needed."""
    return advisor.recommendations(company_id, principal.org_id)


@app.get("/api/companies/{company_id}/audit_history")
def company_audit_history(company_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    """Past checks of this site and what changed between the last two."""
    from intel import clinic
    return {"audits": clinic.history(principal.org_id, company_id), "change": clinic.change(principal.org_id, company_id)}


@app.get("/api/companies/{company_id}/teardown")
def company_teardown(company_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    """A written teardown (Markdown) built only from the latest completed audit. 422 if the site has not been examined."""
    from intel import clinic
    try:
        out = clinic.teardown(principal.org_id, company_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Company not found")
    if out is None:
        raise HTTPException(status_code=422, detail="Examine the site first; there is no completed audit to write about.")
    return out


@app.get("/api/companies/{company_id}/offer")
def company_offer(company_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    """A one-page fixed-price offer (Markdown) from the latest completed check and your own service prices. Blanks are listed in `needs`; 422 without a completed check."""
    from proposals.offer import build_offer
    try:
        return build_offer(principal.org_id, company_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Company not found")


@app.post("/api/companies/{company_id}/advice/ai")
def company_advice_ai(company_id: int, principal: Principal = Depends(require_permission("outreach:draft"))):
    """Plain-language recommendations written by the model; uncited or off-catalog items are dropped. 503 without a model."""
    return advisor.advise(company_id, principal.org_id)


from workflows import rescan as rescan_mod


@app.post("/api/rescan/run")
def run_rescan_now(principal: Principal = Depends(require_permission("pipeline:run"))):
    """Re-audits this tenant's tracked clients now and opens a work item for every NEWLY matching CVE."""
    try:
        return rescan_mod.rescan_org(principal.org_id, limit=15, delay=1.0)
    except Exception as e:
        raise _fail(e)


@app.get("/api/clients/{lead_id}")
def client_detail(lead_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    """Everything the client page needs in one call: lead, company, priority, contacts, latest audit headline, open work items."""
    from database.models import CompanyRepository
    lead = _owned_lead(lead_id, principal)
    org = lead.get("org_id") or principal.org_id
    with get_db() as conn:
        crow = conn.execute("SELECT id FROM companies WHERE org_id = ? AND LOWER(domain) = LOWER(?) ORDER BY id LIMIT 1", (org, lead["domain"])).fetchone()
        items = [dict(r) for r in conn.execute("SELECT * FROM work_items WHERE org_id = ? AND entity_type = 'lead' AND entity_id = ? AND status = 'open' ORDER BY priority DESC", (org, lead_id)).fetchall()]
    company_id = crow["id"] if crow else CompanyRepository.create_or_get(name=lead["company_name"], domain=lead["domain"] if not lead["domain"].endswith(".invalid") else None, org_id=org)["id"]
    audit = AuditRunRepository.latest_for_company(company_id, org)
    return {"lead": lead, "company_id": company_id, "priority": lead_priority.score_lead(lead_id, org, persist=False),
            "contacts": ContactRepository.get_contacts_by_lead(lead_id, org),
            "audit": ({"id": audit["id"], "status": audit["status"], "overall_score": audit["overall_score"], "created_at": audit["created_at"]} if audit else None),
            "work_items": items, "has_website": not lead["domain"].endswith(".invalid")}


class ContactRequest(BaseModel):
    first_name: str
    last_name: str = ""
    title: str = ""
    email: str
    linkedin_url: Optional[str] = None


@app.post("/api/clients/{lead_id}/contacts")
def add_client_contact(lead_id: int, req: ContactRequest, principal: Principal = Depends(require_permission("leads:write"))):
    """Adds a contact a person found. It is stored UNVERIFIED; only the email verifier can change that."""
    lead = _owned_lead(lead_id, principal)
    if not EmailVerificationGate.is_valid_syntax(req.email.strip().lower()):
        raise HTTPException(status_code=422, detail="That does not look like a valid email address.")
    return ContactRepository.add_decision_maker(lead_id, req.first_name.strip(), req.last_name.strip() or "-", req.title.strip() or "Contact",
                                                req.email, linkedin_url=req.linkedin_url, email_source="entered by a person", org_id=lead.get("org_id") or principal.org_id)


@app.post("/api/clients/{lead_id}/contacts/{contact_id}/verify")
def verify_client_contact(lead_id: int, contact_id: int, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Runs the real email verifier (vendor, MX, syntax). Without a vendor key the contact stays unverified and you are told why."""
    lead = _owned_lead(lead_id, principal)
    org = lead.get("org_id") or principal.org_id
    with get_db() as conn:
        row = conn.execute("SELECT * FROM decision_makers WHERE id = ? AND lead_id = ? AND org_id = ?", (contact_id, lead_id, org)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        result = EmailVerificationGate().verify(row["email"])
        verified = result.status == "verified" and result.is_deliverable
        conn.execute("UPDATE decision_makers SET verification_status = ?, mx_verified = ? WHERE id = ?",
                     ("verified" if verified else ("invalid" if result.status in ("invalid", "disposable", "spamtrap") else "unverified"), int(verified), contact_id))
        conn.commit()
    return {"verified": verified, "status": result.status, "reason": result.reason, "provider": result.provider}


@app.post("/api/clients/{lead_id}/find_contacts")
def find_client_contacts(lead_id: int, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Reads the company's own team/about/contact pages and reports the people and emails they publish (nothing guessed)."""
    from intel import contacts as contact_finder
    lead = _owned_lead(lead_id, principal)
    if lead["domain"].endswith(".invalid"):
        raise HTTPException(status_code=422, detail="This business has no website to read. Ask by phone, or find the owner on a map listing or LinkedIn.")
    try:
        return contact_finder.find_contacts(lead["domain"])
    except Exception as e:
        raise _fail(e)


class PrepareRequest(BaseModel):
    country_code: Optional[str] = None


@app.post("/api/clients/{lead_id}/prepare")
def prepare_client(lead_id: int, req: PrepareRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Audit, score, check for a verified contact, and draft a first email for approval (never sends)."""
    lead = _owned_lead(lead_id, principal)
    try:
        return DiscoveryRun().prepare_lead(lead, lead.get("org_id") or principal.org_id, principal.user_id, (req.country_code or "").upper() or None)
    except Exception as e:
        raise _fail(e)


from intel.nlp import parser as nlp_search


class ParseRequest(BaseModel):
    q: str = Field(..., max_length=300)


@app.post("/api/search/parse")
def parse_search(req: ParseRequest, principal: Principal = Depends(require_permission("leads:read"))):
    """Understands a natural-language search (typos, skills, places, budgets, filters) and says what it understood."""
    return nlp_search.parse(req.q)


@app.get("/api/search/catalog")
def search_catalog(principal: Principal = Depends(require_permission("leads:read"))):
    """Everything the smart search knows, grouped, for the Browse lists."""
    from intel.nlp import taxonomy
    return {"business": sorted(taxonomy.BUSINESS), "skills": sorted(taxonomy.SKILLS), "cities": [c.title() for c in taxonomy.CITIES]}


@app.get("/api/search/suggest")
def suggest_search(q: str = "", kinds: str = "", principal: Principal = Depends(require_permission("leads:read"))):
    """Typo-tolerant suggestions while typing: business types, skills and cities."""
    return {"suggestions": nlp_search.suggest(q[:80], kinds=[k for k in kinds.split(",") if k] or None)}


class CompareRequest(BaseModel):
    target_domain: str
    competitor_domain: str


@app.post("/api/compare")
def compare_sites(req: CompareRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    """Same real audit on both sites; reports measured differences only (no revenue estimates)."""
    try:
        return compare_domains(req.target_domain, req.competitor_domain, principal.org_id)
    except Exception as e:
        raise _fail(e)


class ClientReportRequest(BaseModel):
    domain: str
    competitor_domain: Optional[str] = None
    output_format: str = "both"      # html | pdf | both


@app.post("/api/reports/client")
def export_client_report(req: ClientReportRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    try:
        res = client_report.export(principal.org_id, req.domain, req.competitor_domain, req.output_format)
        dispatch_webhook_event(principal.org_id, "audit.completed", {"domain": req.domain, "score": res.get("overall_score")})
        return res
    except Exception as e:
        raise _fail(e)


@app.post("/api/reports/deck")
def export_executive_deck(req: ClientReportRequest, principal: Principal = Depends(require_permission("pipeline:run"))):
    try:
        res = deck_generator.export(principal.org_id, req.domain, req.competitor_domain, req.output_format)
        dispatch_webhook_event(principal.org_id, "audit.completed", {"domain": req.domain, "deck_url": res.get("view_url")})
        return res
    except Exception as e:
        raise _fail(e)


@app.get("/api/reports/view/{filename}")
def view_client_report(filename: str, principal: Principal = Depends(require_permission("leads:read"))):
    name = os.path.basename(filename)
    if not (name.startswith(f"report_{principal.org_id}_") or name.startswith(f"deck_{principal.org_id}_")):      # tenants only see their own reports & decks
        raise HTTPException(status_code=404, detail="Report not found")
    path = client_report.storage_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    if name.endswith(".html"):
        return HTMLResponse(content=path.read_text(encoding="utf-8"))
    return FileResponse(path=str(path), media_type="application/pdf", filename=name)


class AssistantChatRequest(BaseModel):
    messages: List[Dict[str, str]]


@app.post("/api/assistant/chat")
def assistant_chat(req: AssistantChatRequest, principal: Principal = Depends(require_permission("leads:read"))):
    """Workspace assistant on the single LLM gateway (503 when no model is configured). It sees a small workspace summary only."""
    org = principal.org_id
    with get_db() as conn:
        hot = [dict(r) for r in conn.execute(
            "SELECT l.company_name, s.score, s.band FROM lead_scores s JOIN leads l ON l.id = s.lead_id WHERE s.org_id = ? "
            "AND s.id IN (SELECT MAX(id) FROM lead_scores WHERE org_id = ? GROUP BY lead_id) ORDER BY s.score DESC LIMIT 5", (org, org)).fetchall()]
    context = "WORKSPACE SUMMARY\n" + f"Open work items: {len(WorkItemRepository.list_open(org))}\nTop leads by priority: " + \
        ("; ".join(f"{r['company_name']} ({r['score']}, {r['band']})" for r in hot) or "none scored yet")
    history = "\n".join(f"{m.get('role', 'user').upper()}: {str(m.get('content', ''))[:1500]}" for m in req.messages[-8:])
    system = ("You assist a business-development team at a software agency. Answer only from the workspace summary and the "
              "conversation. If you do not know something, say so. Never invent companies, people, metrics or results.")
    out = LLMGateway.complete(f"{context}\n\n{history}\n\nASSISTANT:", system=system, agent_name="Assistant", org_id=org, max_tokens=700)
    return {"reply": out["text"], "model": out.get("model")}


# ==================== Unified Sovereign Frontend Mount ====================
def safe_static_path(root: str, requested: str) -> Optional[str]:
    """The file a URL may download from the web app's folder, or None. Refuses anything that resolves outside the folder
    (`../`, encoded `..%2f`, an absolute path after `//`, symlinks) and hidden files such as .env. QA found the earlier plain
    os.path.join let anyone read /etc/passwd and the project's .env without signing in."""
    try:
        base = os.path.realpath(root)
        path = os.path.realpath(os.path.join(base, requested.lstrip("/\\")))
    except (ValueError, OSError):                              # for example a null byte
        return None
    if not requested or not (path == base or path.startswith(base + os.sep)) or not os.path.isfile(path):
        return None
    if any(part.startswith(".") for part in os.path.relpath(path, base).split(os.sep)):
        return None
    return path


frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static_assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa_frontend(full_path: str):
        # Never hijack API, health, or telemetry endpoints
        if full_path.startswith("api/") or full_path.startswith("healthz/") or full_path == "metrics":
            raise HTTPException(status_code=404, detail="API route not found")

        file_path = safe_static_path(frontend_dist, full_path)
        if file_path:
            return FileResponse(file_path)

        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            response = FileResponse(index_file)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
        raise HTTPException(status_code=404, detail="Frontend index.html not found")




