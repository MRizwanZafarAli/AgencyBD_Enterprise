"""
Interactive Web Proposals, E-Signature & Smart Links Telemetry Router.
Also exposes Account IQ executive briefs for ClientPage.
"""

import html
import json
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from core.hooks import event_bus
from database.db import get_db
from intel.account_iq import build_account_iq
from security.auth import Principal, require_permission

router = APIRouter(tags=["Proposals, Smart Links & Account IQ"])

HOOK_PROPOSAL_ACCEPTED = "on_proposal_accepted"


class CreateProposalRequest(BaseModel):
    lead_id: int
    title: str = Field(..., min_length=2, max_length=160)
    summary: str = ""
    scope_items: List[str] = Field(default_factory=list)
    price_amount: Optional[float] = Field(default=None, ge=0)
    currency: str = "USD"
    booking_link: str = ""


class AcceptProposalRequest(BaseModel):
    signed_by: str = Field(..., min_length=2, max_length=120)


@router.get("/api/clients/{lead_id}/account-iq")
def get_client_account_iq(lead_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    try:
        return build_account_iq(principal.org_id, lead_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Client not found")


@router.get("/api/proposals/lead/{lead_id}")
def list_client_proposals(lead_id: int, principal: Principal = Depends(require_permission("leads:read"))):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM interactive_proposals WHERE org_id = ? AND lead_id = ? ORDER BY id DESC",
            (principal.org_id, lead_id),
        ).fetchall()
        views = conn.execute(
            "SELECT token, report_type, COUNT(*) AS view_count, MAX(viewed_at) AS last_viewed_at FROM smart_link_events WHERE org_id = ? AND lead_id = ? GROUP BY token, report_type",
            (principal.org_id, lead_id),
        ).fetchall()
    return {
        "proposals": [dict(r) for r in rows],
        "smart_link_views": [dict(v) for v in views],
    }


@router.post("/api/proposals/create")
def create_interactive_proposal(
    req: CreateProposalRequest,
    principal: Principal = Depends(require_permission("leads:write")),
):
    token = f"prop_{uuid.uuid4().hex[:16]}"
    with get_db() as conn:
        lead = conn.execute(
            "SELECT id, company_name FROM leads WHERE id = ? AND org_id = ?",
            (req.lead_id, principal.org_id),
        ).fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="Client not found")
        cur = conn.execute(
            """
            INSERT INTO interactive_proposals
            (org_id, lead_id, token, title, summary, scope_json, price_amount, currency, booking_link, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'sent')
            """,
            (
                principal.org_id,
                req.lead_id,
                token,
                req.title.strip(),
                req.summary.strip(),
                json.dumps(req.scope_items),
                req.price_amount,
                req.currency.upper(),
                req.booking_link.strip(),
            ),
        )
        pid = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM interactive_proposals WHERE id = ?", (pid,)).fetchone()
    return {"ok": True, "proposal": dict(row), "share_path": f"/p/{token}"}


@router.get("/p/{token}", response_class=HTMLResponse)
def view_public_proposal(token: str, request: Request):
    """Public interactive proposal page with automatic Smart Link view telemetry."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM interactive_proposals WHERE token = ?", (token,)).fetchone()
        if not row:
            return HTMLResponse("<h1>Proposal not found</h1>", status_code=404)
        prop = dict(row)
        conn.execute(
            """
            INSERT INTO smart_link_events (org_id, token, lead_id, report_type, viewer_ip, user_agent, referrer)
            VALUES (?, ?, ?, 'proposal', ?, ?, ?)
            """,
            (
                prop["org_id"],
                token,
                prop["lead_id"],
                request.client.host if request.client else "",
                request.headers.get("user-agent", "")[:240],
                request.headers.get("referer", "")[:240],
            ),
        )
        if prop["status"] == "sent":
            conn.execute("UPDATE interactive_proposals SET status = 'viewed' WHERE id = ?", (prop["id"],))
        conn.commit()

    scope_items = []
    try:
        scope_items = json.loads(prop.get("scope_json") or "[]")
    except Exception:
        scope_items = []

    title_safe = html.escape(prop["title"])
    summary_safe = html.escape(prop.get("summary") or "")
    price_html = (
        f"<div class='price'>{html.escape(prop['currency'])} {prop['price_amount']:,.0f}</div>"
        if prop.get("price_amount") is not None
        else ""
    )
    scope_lis = "".join(f"<li>{html.escape(str(item))}</li>" for item in scope_items) or "<li>Custom technical delivery scope</li>"
    signed_badge = (
        f"<div class='accepted'>Accepted &amp; Signed by {html.escape(prop['signed_by'] or '')} ({html.escape(str(prop['signed_at'] or ''))})</div>"
        if prop["status"] == "accepted"
        else f"""
        <form method="post" action="/p/{html.escape(token)}/accept" class="sign-box">
          <input type="text" name="signed_by" required placeholder="Your Full Name &amp; Title" />
          <button type="submit">Accept &amp; E-Sign Scope</button>
        </form>
        """
    )

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_safe}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#09090b;color:#f4f4f5;margin:0;padding:40px 16px}}
.card{{max-width:720px;margin:0 auto;background:#18181b;border:1px solid #27272a;border-radius:16px;padding:32px}}
h1{{margin:0 0 12px;font-size:24px}} .price{{font-size:28px;font-weight:700;color:#2dd4bf;margin:16px 0}}
ul{{line-height:1.7;color:#d4d4d8}} .sign-box{{margin-top:24px;display:flex;gap:10px;flex-wrap:wrap}}
input{{flex:1;min-width:200px;padding:10px 12px;border-radius:8px;border:1px solid #3f3f46;background:#09090b;color:#fff}}
button{{padding:10px 18px;border-radius:8px;border:0;background:#14b8a6;color:#09090b;font-weight:700;cursor:pointer}}
.accepted{{margin-top:24px;padding:14px;border-radius:10px;background:#064e3b;color:#a7f3d0;font-weight:600}}
</style></head>
<body><div class="card">
<h1>{title_safe}</h1><p>{summary_safe}</p>{price_html}
<h3>Included Deliverables</h3><ul>{scope_lis}</ul>
{signed_badge}
</div></body></html>"""
    return HTMLResponse(page, headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


@router.post("/p/{token}/accept", response_class=HTMLResponse)
async def accept_public_proposal(token: str, request: Request):
    form = await request.form()
    signed_by = str(form.get("signed_by") or "").strip()
    if len(signed_by) < 2:
        return HTMLResponse("<h3>Please enter your full name to sign.</h3>", status_code=422)

    with get_db() as conn:
        row = conn.execute("SELECT * FROM interactive_proposals WHERE token = ?", (token,)).fetchone()
        if not row:
            return HTMLResponse("<h3>Proposal not found.</h3>", status_code=404)
        prop = dict(row)
        conn.execute(
            "UPDATE interactive_proposals SET status = 'accepted', signed_by = ?, signed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (signed_by, prop["id"]),
        )
        try:
            conn.execute(
                "UPDATE leads SET pipeline_stage = 'won' WHERE id = ? AND org_id = ?",
                (prop["lead_id"], prop["org_id"]),
            )
        except Exception:
            pass
        conn.commit()

    try:
        event_bus.emit(
            HOOK_PROPOSAL_ACCEPTED,
            {"org_id": prop["org_id"], "proposal_id": prop["id"], "lead_id": prop["lead_id"], "signed_by": signed_by},
        )
    except Exception:
        pass

    return HTMLResponse(
        f"<html><body style='font-family:sans-serif;background:#09090b;color:#a7f3d0;padding:40px'><h2>Proposal Accepted!</h2><p>Thank you, {html.escape(signed_by)}. Your scope agreement has been recorded.</p></body></html>"
    )
