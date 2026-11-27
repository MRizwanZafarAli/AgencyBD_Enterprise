"""
Universal Scraper & Interactive Browser Sidepanel API Router.
Provides endpoints for sovereign Fit-Markdown scraping, live browser frame streaming,
native headed Chrome window popout, and Human-in-the-Loop challenge resolution.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from engines.universal_scraper import universal_scraper, ScrapeResult
from engines.interactive_browser_session import get_browser_session
from security.auth import Principal, get_current_principal, require_permission
from database.db import get_db

router = APIRouter(prefix="/api/v1/browser", tags=["Universal Scraper & Browser"])


class ScrapeRequest(BaseModel):
    target: str = Field(..., description="Target website URL or apex domain")
    query_keywords: Optional[List[str]] = Field(default=None, description="Keywords to isolate in Fit-Markdown")
    mode: Optional[str] = Field(default="general", description="Scrape mode: client_audit | job_spec | local_audit | general")
    context_title: Optional[str] = Field(default=None, description="Display title or company name")


class BrowserNavigateRequest(BaseModel):
    target: str = Field(..., description="Target URL to navigate and preview")
    session_id: str = Field(default="default_session", description="Unique interactive session ID")
    viewport: str = Field(default="desktop", description="'desktop' or 'mobile'")
    mode: Optional[str] = Field(default="general")


class LaunchHeadedRequest(BaseModel):
    target: Optional[str] = Field(default=None, description="Target URL for headed Chrome window")
    session_id: str = Field(default="default_session", description="Session ID")


class ResolveChallengeRequest(BaseModel):
    session_id: str = Field(default="default_session")
    domain: Optional[str] = None


@router.post("/scrape")
def execute_universal_scrape(
    req: ScrapeRequest,
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Executes sovereign universal scraping on target URL/domain.
    Returns clean Fit-Markdown, compression ratio, challenge radar status, and extracted entities.
    """
    try:
        res = universal_scraper.scrape_url(
            target=req.target,
            query_keywords=req.query_keywords,
            mode=req.mode or "general",
            org_id=principal.org_id,
        )
        return {
            "ok": True,
            "result": res.model_dump(),
        }
    except SSRFSecurityError as exc:
        raise HTTPException(status_code=400, detail=f"Blocked target: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scraper error: {exc}")


@router.get("/markdown")
def get_fit_markdown(
    target: str = Query(..., description="Target domain or URL"),
    keywords: Optional[str] = Query(default=None, description="Comma-separated keywords"),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Quickly returns clean, token-efficient Fit-Markdown for any target web page."""
    kw_list = [k.strip() for k in keywords.split(",")] if keywords else None
    try:
        res = universal_scraper.scrape_url(target=target, query_keywords=kw_list, org_id=principal.org_id)
        return {
            "ok": True,
            "domain": res.domain,
            "title": res.title,
            "fit_markdown": res.fit_markdown,
            "compression_ratio": f"{res.compression_ratio}%",
            "challenge_detected": res.challenge_detected,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/scraped")
def get_saved_scrape(
    domain: str = Query(..., description="Domain or URL to look up saved scrape"),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Returns the latest persisted site scrape for a specific domain/site."""
    import json
    from urllib.parse import urlparse

    raw = domain.strip().lower()
    if "://" in raw:
        raw = urlparse(raw).hostname or raw
    clean = raw.split(":")[0].removeprefix("www.")
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, url, domain, title, fit_markdown, extracted_json, status, created_at
            FROM scraped_pages
            WHERE org_id = ? AND (LOWER(domain) = ? OR LOWER(domain) = ?)
            ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (principal.org_id, clean, f"www.{clean}"),
        ).fetchone()
    if not row:
        return {"found": False, "scrape": None}
    extracted = {}
    try:
        extracted = json.loads(row["extracted_json"] or "{}")
    except Exception:
        extracted = {}
    return {
        "found": True,
        "scrape": {
            "id": row["id"],
            "url": row["url"],
            "domain": row["domain"],
            "title": row["title"],
            "fit_markdown": row["fit_markdown"] or "",
            "extracted_data": extracted,
            "developer_audit": extracted.get("developer_audit", {}),
            "status": row["status"],
            "created_at": row["created_at"],
        },
    }


@router.post("/session/navigate")
def navigate_browser_sidepanel(
    req: BrowserNavigateRequest,
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Drives the headless browser session, renders DOM, checks for anti-bot challenges,
    and returns a live viewport screenshot data URI for the slide-out sidepanel.
    """
    session = get_browser_session(req.session_id)
    try:
        nav_res = session.navigate(req.target, viewport=req.viewport)
        return {
            "ok": True,
            "navigation": nav_res,
        }
    except SSRFSecurityError as exc:
        raise HTTPException(status_code=400, detail=f"Blocked target: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Navigation failed: {exc}")


@router.post("/session/launch-headed")
def launch_headed_chrome_window(
    req: LaunchHeadedRequest,
    principal: Principal = Depends(require_permission("lead:write")),
) -> Dict[str, Any]:
    """
    One-click popout launcher: launches an isolated, physical Chrome window on the host machine
    with its own sandboxed profile directory for manual human-in-the-loop intervention.
    """
    session = get_browser_session(req.session_id)
    res = session.launch_headed_window(url=req.target)
    return {
        "ok": res.get("status") in ("launched", "success"),
        "result": res,
    }


@router.post("/session/resolve")
def resolve_human_challenge(
    req: ResolveChallengeRequest,
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Marks that the human operator has solved the captcha or 2FA challenge,
    saving session cookies and allowing autonomous scraping to resume.
    """
    session = get_browser_session(req.session_id)
    res = session.resolve_challenge(operator_id=principal.user_id, org_id=principal.org_id)
    return {
        "ok": True,
        "result": res,
    }


@router.get("/session/clearance-status")
def get_session_clearance_status(
    session_id: str = Query(default="default_session"),
    target: Optional[str] = Query(default=None),
    auto_resume: bool = Query(default=True),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Intelligent Bot Challenge Radar & Clearance Verifier.
    Checks whether the anti-bot challenge (Cloudflare, Turnstile, Captcha) has been cleared in the session.
    If cleared and auto_resume=True, automatically executes Fit-Markdown scrape and persists the result.
    If re-challenged on subsequent pages, detects and returns re_challenged=True.
    """
    session = get_browser_session(session_id)
    target_url = target or session.current_url
    if not target_url:
        return {"ok": False, "cleared": False, "message": "No target URL provided"}

    clearance = session.check_live_clearance(target_url)
    if clearance.get("cleared") and auto_resume:
        resume_res = session.auto_resume_and_scrape(target_url, org_id=principal.org_id)
        return {
            "ok": True,
            "cleared": True,
            "resumed": True,
            "status": resume_res.get("status"),
            "re_challenged": resume_res.get("re_challenged", False),
            "challenge_count": session.challenge_count,
            "clearance": clearance,
            "resume_result": resume_res,
        }
    else:
        return {
            "ok": True,
            "cleared": clearance.get("cleared", False),
            "resumed": False,
            "status": "waiting_for_clearance" if not clearance.get("cleared") else "cleared_pending_resume",
            "challenge_count": session.challenge_count,
            "clearance": clearance,
        }


@router.post("/session/auto-resume")
def trigger_auto_resume(
    req: ResolveChallengeRequest,
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Manually or programmatically triggers auto-resume on the session once cleared."""
    session = get_browser_session(req.session_id)
    target_url = req.domain or session.current_url
    resume_res = session.auto_resume_and_scrape(target_url, org_id=principal.org_id)
    return {
        "ok": True,
        "result": resume_res,
    }


@router.get("/session/vault")
def list_session_vault(
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Lists saved authenticated sessions in browser_session_vault."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, domain, status, last_intervened_by, updated_at
                FROM browser_session_vault
                WHERE org_id = ?
                ORDER BY updated_at DESC
                LIMIT 50
                """,
                (principal.org_id,),
            )
            rows = cursor.fetchall()
            return {
                "ok": True,
                "sessions": [
                    {
                        "id": r[0],
                        "domain": r[1],
                        "status": r[2],
                        "last_intervened_by": r[3],
                        "updated_at": r[4],
                    }
                    for r in rows
                ],
            }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class CapturedLeadItem(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=120)
    domain: str = ""
    contact_name: str = ""
    contact_title: str = ""
    linkedin_url: str = ""
    email: str = ""


class CaptureLeadsRequest(BaseModel):
    leads: List[CapturedLeadItem] = Field(..., min_length=1, max_length=50)
    source: str = "sales_nav_companion"


@router.post("/session/capture-leads")
def capture_sales_nav_leads(
    req: CaptureLeadsRequest,
    principal: Principal = Depends(require_permission("leads:write")),
) -> Dict[str, Any]:
    """
    Sales Navigator Companion Capture:
    Saves leads captured from an authenticated human Chrome session into CRM `leads` & `decision_makers`.
    """
    from database.models import ContactRepository, LeadRepository

    saved = []
    for item in req.leads:
        dom = (item.domain or "").strip() or f"{item.company_name.lower().replace(' ', '')[:24]}.invalid"
        lead = LeadRepository.create_or_get_lead(
            company_name=item.company_name.strip(),
            domain=dom,
            source_channel=req.source,
            notes=f"Captured via Sales Navigator Companion ({item.linkedin_url})" if item.linkedin_url else "Captured via Sales Navigator Companion",
            org_id=principal.org_id,
        )
        if item.contact_name.strip() and item.email.strip():
            parts = item.contact_name.strip().split(" ", 1)
            first_n = parts[0]
            last_n = parts[1] if len(parts) > 1 else ""
            ContactRepository.add_decision_maker(
                lead_id=lead["id"],
                first_name=first_n,
                last_name=last_n,
                title=item.contact_title.strip() or "Decision Maker",
                email=item.email.strip(),
                linkedin_url=item.linkedin_url.strip() or None,
                org_id=principal.org_id,
            )
        saved.append({"lead_id": lead["id"], "company_name": lead["company_name"], "domain": lead["domain"]})

    return {"ok": True, "captured_count": len(saved), "leads": saved}
