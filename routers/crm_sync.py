"""
Bi-directional CRM Synchronization Router for AgencyBD Enterprise.
Handles inbound webhook updates from HubSpot, Salesforce, Zapier, Make, and n8n,
keeping deal stages, client notes, and win states bidirectionally in sync.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from database.db import get_db, log_audit_trail
from database.models import LeadRepository
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/integrations/crm", tags=["CRM Sync"])
MANAGE = require_permission("apikeys:manage")
READ = require_permission("leads:read")

STAGE_MAP = {
    "subscriber": "sourced",
    "lead": "sourced",
    "marketingqualifiedlead": "sourced",
    "salesqualifiedlead": "audited",
    "opportunity": "proposal_sent",
    "customer": "won",
    "evangelist": "won",
    "other": "sourced",
    "closed_won": "won",
    "closed_lost": "lost",
    "meeting_booked": "meeting_booked",
    "in_negotiation": "sequence_active",
}


class GenericCrmSyncRequest(BaseModel):
    domain: str
    deal_stage: Optional[str] = None
    deal_value: Optional[float] = None
    note: Optional[str] = None
    external_crm_id: Optional[str] = None


@router.post("/sync")
def sync_generic_crm_update(
    req: GenericCrmSyncRequest,
    principal: Principal = Depends(MANAGE)
):
    """
    Inbound update from external CRM (Salesforce, Make, Zapier, n8n).
    Updates deal stage, pipeline valuation, and client notes.
    """
    org = principal.org_id
    clean_domain = re.sub(r"^https?://", "", req.domain.strip().lower()).split("/")[0]

    with get_db() as db:
        lead = db.execute(
            "SELECT id, company_name, status, notes FROM leads WHERE org_id = ? AND domain = ?",
            (org, clean_domain)
        ).fetchone()

        if not lead:
            raise HTTPException(status_code=404, detail=f"No prospect or client found matching domain '{clean_domain}'")

        lead_id = lead["id"]
        current_notes = lead["notes"] or ""

        normalized_stage = req.deal_stage.lower().strip() if req.deal_stage else None
        if normalized_stage and normalized_stage in STAGE_MAP:
            normalized_stage = STAGE_MAP[normalized_stage]

        if normalized_stage:
            LeadRepository.update_deal_stage(lead_id, normalized_stage, org_id=org)

        if req.deal_value is not None and req.deal_value >= 0:
            val_str = f"EST VALUE: ${int(req.deal_value):,}"
            if "EST VALUE:" in current_notes:
                new_notes = re.sub(r"EST VALUE:\s*\$[0-9,]+", val_str, current_notes)
            else:
                new_notes = f"{val_str} | {current_notes}".strip(" |")
            db.execute(
                "UPDATE leads SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND org_id = ?",
                (new_notes, lead_id, org)
            )

        if req.note:
            db.execute(
                "INSERT INTO client_notes (org_id, lead_id, kind, body, created_by) VALUES (?, ?, 'note', ?, ?)",
                (org, lead_id, f"[CRM Sync] {req.note.strip()}", principal.user_id)
            )

        db.commit()

        log_audit_trail(
            lead_id=lead_id,
            actor=f"crm_sync:{principal.user_id}",
            action="inbound_crm_update",
            metadata={
                "stage": normalized_stage,
                "deal_value": req.deal_value,
                "note_added": bool(req.note),
                "external_id": req.external_crm_id
            }
        )

    return {
        "status": "synced",
        "lead_id": lead_id,
        "domain": clean_domain,
        "deal_stage": normalized_stage or lead["status"],
        "deal_value": req.deal_value
    }


def _hubspot_signature_ok(request: Request, body: bytes, secret: str) -> bool:
    """HubSpot v3 signature: base64(HMAC-SHA256(client secret, "POST" + public URL + body + timestamp)), valid for 5 minutes."""
    sig, ts = request.headers.get("x-hubspot-signature-v3"), request.headers.get("x-hubspot-request-timestamp")
    if not sig or not ts:
        return False
    try:
        sent_ms = int(ts)
    except ValueError:
        return False
    if abs(time.time() * 1000 - sent_ms) > 5 * 60 * 1000:
        return False                                                  # stale or replayed
    base = (os.getenv("AGENCYBD_PUBLIC_BASE_URL") or "").rstrip("/")
    uri = (base + request.url.path) if base else str(request.url)
    message = f"POST{uri}{body.decode('utf-8', 'replace')}{ts}".encode("utf-8")
    expected = base64.b64encode(hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, sig)


@router.post("/hubspot")
async def hubspot_inbound_webhook(request: Request):
    """
    Inbound HubSpot change events. Open to HubSpot only: every call must carry a valid HubSpot v3 signature made with your
    HUBSPOT_CLIENT_SECRET, and without that secret the endpoint refuses everything. Changes apply only to this installation's workspace.
    """
    from config.honesty import NotConfiguredError
    secret = (os.getenv("HUBSPOT_CLIENT_SECRET") or "").strip()
    if not secret:
        raise NotConfiguredError("hubspot_webhook", "Set HUBSPOT_CLIENT_SECRET (Settings > Integrations and keys) before HubSpot can send events here.")
    body_bytes = await request.body()
    if not _hubspot_signature_ok(request, body_bytes, secret):
        raise HTTPException(status_code=401, detail="Invalid or missing HubSpot signature.")
    try:
        events = json.loads(body_bytes.decode("utf-8"))
        if not isinstance(events, list):
            events = [events]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    org = os.getenv("AGENCYBD_WEBHOOK_ORG_ID", "org_default")
    synced_events = []
    with get_db() as db:
        for ev in events:
            if not isinstance(ev, dict):
                continue
            prop_name = ev.get("propertyName", "")
            prop_val = str(ev.get("propertyValue", "")).lower()
            obj_id = ev.get("objectId")

            if prop_name in ("lifecyclestage", "dealstage", "hs_pipeline_stage") and prop_val in STAGE_MAP:
                target_stage = STAGE_MAP[prop_val]
                changed = db.execute("UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND org_id = ?", (target_stage, obj_id, org)).rowcount
                if changed:
                    synced_events.append({"object_id": obj_id, "new_stage": target_stage})

        db.commit()

    return {"status": "success", "processed_events": len(synced_events), "synced": synced_events}


@router.get("/export-all")
def export_all_for_crm(principal: Principal = Depends(READ)):
    """
    Returns full client and pipeline catalog formatted with standard CRM fields
    for 1-click import into HubSpot, Salesforce, or Pipedrive.
    """
    org = principal.org_id
    with get_db() as db:
        rows = db.execute(
            "SELECT id, company_name, domain, phone, rating, reviews_count, source_channel, "
            "status, notes, created_at, updated_at "
            "FROM leads WHERE org_id = ? ORDER BY id DESC",
            (org,)
        ).fetchall()

    leads = []
    for r in rows:
        d = dict(r)
        d["deal_stage"] = d["status"]
        leads.append(d)

    return {
        "org_id": org,
        "count": len(leads),
        "crm_schema_version": "2.4",
        "leads": leads
    }
