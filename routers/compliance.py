"""
Compliance, Suppression Vault & Unsubscribe Router.
Handles jurisdiction checks, global keyed suppression, and 1-click opt-out.
"""

import html
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from security.auth import Principal, require_permission
from compliance.country_policy import CountryComplianceEngine
from compliance.suppression import KeyedSuppressionVault
from compliance.footer import ComplianceFooterBuilder

router = APIRouter(prefix="/api/compliance", tags=["Compliance & Suppression"])

class AddSuppressionRequest(BaseModel):
    entity: str
    entity_type: Optional[str] = "email"
    reason: Optional[str] = "user_unsubscribe"

@router.get("/country/{code}")
def evaluate_country_jurisdiction(code: str, principal: Principal = Depends(require_permission("leads:read"))):
    decision = CountryComplianceEngine.evaluate(code)
    return {
        "country_code": decision.country_code,
        "status": decision.status,
        "allowed": decision.allowed,
        "requires_lia": decision.requires_lia,
        "reason": decision.reason,
        "required_disclosures": decision.required_disclosures
    }

@router.get("/suppression/check")
def check_suppression(email: str = Query(...), principal: Principal = Depends(require_permission("leads:read"))):
    is_suppressed = KeyedSuppressionVault.is_suppressed(email, principal.org_id)
    return {"email": email, "is_suppressed": is_suppressed}

@router.post("/suppression/add")
def add_suppression(req: AddSuppressionRequest, principal: Principal = Depends(require_permission("leads:create"))):
    ok = KeyedSuppressionVault.suppress(
        entity=req.entity,
        entity_type=req.entity_type or "email",
        reason=req.reason or "user_unsubscribe",
        source="manual_admin",
        org_id=principal.org_id
    )
    return {"status": "success" if ok else "failed", "entity": req.entity}

def _page(title: str, message: str, form: str = "", status: int = 200) -> Response:
    html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 80vh; background: #f7fafc;">
<div style="background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; max-width: 480px;">
<h2 style="color: #2d3748; margin-bottom: 12px;">{html.escape(title)}</h2>
<p style="color: #718096; font-size: 14px; line-height: 1.5;">{message}</p>{form}
</div></body></html>"""
    return Response(content=html_doc, media_type="text/html", status_code=status,
                    headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


def _invalid_link() -> Response:
    return _page("This link is not valid",
                 "The unsubscribe link is invalid or has been altered. Reply to the email and ask to be removed instead.",
                 status=400)


@router.get("/unsubscribe")
def unsubscribe_confirmation_page(email: str = Query(...), token: str = Query(""), org_id: str = Query("")):
    """
    Landing page for the footer link. Link scanners and mail previewers issue GET requests, so a GET
    never changes state: it asks for confirmation, and the confirmation is a signed POST.
    """
    if not ComplianceFooterBuilder.verify_unsubscribe_token(email, org_id, token):
        return _invalid_link()
    form = (f'<form method="post" action="/api/compliance/unsubscribe?{urlencode({"email": email, "org_id": org_id, "token": token})}">'
            f'<button type="submit" style="margin-top:16px;padding:10px 20px;border:0;border-radius:6px;background:#2d3748;color:#fff;cursor:pointer;">'
            f'Confirm unsubscribe</button></form>')
    return _page("Unsubscribe", f"Stop all emails to <strong>{html.escape(email)}</strong>?", form)


@router.post("/unsubscribe")
def handle_one_click_unsubscribe(email: str = Query(...), token: str = Query(""), org_id: str = Query("")):
    """
    RFC 8058 one-click endpoint (also the target of the confirmation form). Unauthenticated by design,
    so it only acts when the signed token matches this exact (org, email) pair. The tenant comes from
    the verified token binding, never from an unauthenticated guess.
    """
    if not ComplianceFooterBuilder.verify_unsubscribe_token(email, org_id, token):
        return _invalid_link()
    KeyedSuppressionVault.suppress(
        entity=email,
        entity_type="email",
        reason="one_click_unsubscribe",
        source="signed_unsubscribe_link",
        org_id=org_id
    )
    return _page("You have been unsubscribed",
                 f"<strong>{html.escape(email)}</strong> will not receive further emails from us.")
