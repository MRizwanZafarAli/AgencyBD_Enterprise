"""Opportunity-source status and the Upwork OAuth connection flow."""

import html
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from config.honesty import NotConfiguredError
from connectors.base import ConnectorNotConfigured
from connectors.oauth import TokenStore, verify_state
from connectors.upwork import UpworkConnector
from radar.engine import OpportunityRadarEngine
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/connectors", tags=["Opportunity sources"])


@router.get("")
def list_sources(principal: Principal = Depends(require_permission("leads:read"))):
    """Every source with its compliance rules, whether it is usable for this tenant, and what the last scan did."""
    return OpportunityRadarEngine.source_status(principal.org_id)


@router.get("/upwork/authorize")
def upwork_authorize(principal: Principal = Depends(require_permission("pipeline:run"))):
    try:
        return {"authorize_url": UpworkConnector.authorize_url(principal.org_id)}
    except ConnectorNotConfigured as exc:
        raise NotConfiguredError("upwork", str(exc))


@router.get("/upwork/callback", response_class=HTMLResponse)
def upwork_callback(code: str = Query(""), state: str = Query(""), error: str = Query("")):
    """Browser redirect target. Unauthenticated by necessity; trusted only through the signed, expiring `state`."""
    def page(title: str, msg: str, status: int = 200) -> HTMLResponse:
        return HTMLResponse(f"<!doctype html><meta charset='utf-8'><title>{html.escape(title)}</title>"
                            f"<body style='font-family:sans-serif;max-width:480px;margin:15vh auto'><h2>{html.escape(title)}</h2>"
                            f"<p>{html.escape(msg)}</p><p><a href='/'>Back to the app</a></p></body>", status_code=status)
    if error:
        return page("Upwork connection cancelled", error[:200], 400)
    org_id = verify_state(state, "upwork")
    if not org_id or not code:
        return page("Invalid or expired link", "Start the connection again from the Radar.", 400)
    try:
        UpworkConnector.exchange_code(org_id, code)
    except Exception as exc:
        return page("Upwork connection failed", str(exc)[:200], 502)
    return page("Upwork connected", "Job search is now available in your Radar.")


@router.delete("/upwork")
def upwork_disconnect(principal: Principal = Depends(require_permission("pipeline:run"))):
    if not TokenStore.delete(principal.org_id, "upwork"):
        raise HTTPException(status_code=404, detail="Upwork is not connected.")
    return {"disconnected": True}
