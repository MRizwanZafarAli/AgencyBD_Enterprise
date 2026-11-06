"""
Visitor Intent Radar Router: tracks website visitors, resolves corporate networks
without paid API credits, scores buyer intent, and enables 1-click conversion into Clients.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.db import get_db
from database.models import LeadRepository
from engines.native_visitor_deanonymizer import NativeVisitorDeanonymizer
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/analytics", tags=["Visitor Intent"])
deanonymizer = NativeVisitorDeanonymizer()

READ = require_permission("leads:read")
MANAGE = require_permission("pipeline:run")


class TrackVisitorRequest(BaseModel):
    ip_address: str
    page_url: str
    referrer: Optional[str] = None


@router.get("/visitor-intent")
def list_visitor_intent(principal: Principal = Depends(READ)) -> Dict[str, Any]:
    org = principal.org_id
    with get_db() as db:
        rows = db.execute(
            "SELECT id, ip_address, hostname, company_name, domain, page_url, referrer, intent_score, converted_lead_id, created_at "
            "FROM visitor_intent_events WHERE org_id = ? ORDER BY id DESC LIMIT 50",
            (org,)
        ).fetchall()
        
        events = [dict(r) for r in rows]
        total = len(events)
        high_intent = sum(1 for e in events if e.get("intent_score", 0) >= 70)
        converted = sum(1 for e in events if e.get("converted_lead_id") is not None)

    return {
        "events": events,
        "summary": {
            "total_visitors": total,
            "high_intent_count": high_intent,
            "converted_count": converted
        },
        "tracking_snippet": None,
        "note": "Companies are not identified: reverse DNS cannot do that. There is no tracker script yet, so visits appear only if your own site posts them here."
    }


@router.post("/visitor-track")
def track_visitor(req: TrackVisitorRequest, principal: Optional[Principal] = Depends(READ)) -> Dict[str, Any]:
    org = principal.org_id if principal else "org_default"
    resolution = deanonymizer.resolve_ip(req.ip_address)
    
    hostname = resolution.get("hostname")
    domain = resolution.get("candidate_domain")
    company_name = None                      # a reverse-DNS name does not identify a company, so none is stated

    # Intent Scoring logic
    score = 45
    page_lower = req.page_url.lower()
    if any(k in page_lower for k in ["/pricing", "/quote", "/rates", "/cost"]):
        score += 40
    elif any(k in page_lower for k in ["/case-studies", "/work", "/portfolio", "/clients"]):
        score += 25
    elif any(k in page_lower for k in ["/contact", "/book", "/demo"]):
        score += 35

    if not resolution.get("is_residential", True):
        score += 15

    score = min(99, max(10, score))

    with get_db() as db:
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO visitor_intent_events (org_id, ip_address, hostname, company_name, domain, page_url, referrer, intent_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (org, req.ip_address, hostname, company_name, domain, req.page_url, req.referrer, score)
        )
        event_id = cursor.lastrowid
        db.commit()

    return {
        "status": "recorded",
        "id": event_id,
        "company_name": company_name,
        "domain": domain,
        "intent_score": score
    }


@router.post("/visitor-intent/{event_id}/convert")
def convert_visitor_to_client(event_id: int, principal: Principal = Depends(MANAGE)) -> Dict[str, Any]:
    org = principal.org_id
    with get_db() as db:
        event = db.execute(
            "SELECT * FROM visitor_intent_events WHERE id = ? AND org_id = ?",
            (event_id, org)
        ).fetchone()
        
        if not event:
            raise HTTPException(status_code=404, detail="Visitor event not found")
        
        if event["converted_lead_id"]:
            return {"status": "already_converted", "lead_id": event["converted_lead_id"]}
        
        if not event["domain"]:
            raise HTTPException(status_code=422, detail="This visit has no website name to work from, and the app will not make one up. Find the company yourself and add it in Find or Clients.")
        domain = event["domain"]
        name = event["company_name"] or domain

        # Create or fetch lead
        lead = LeadRepository.create_or_get_lead(
            company_name=name,
            domain=domain,
            source_channel="visitor_intent",
            notes=f"Added from a website visit to {event['page_url']}. The website name comes from reverse DNS and is not verified.",
            org_id=org
        )
        lead_id = lead["id"]

        db.execute(
            "UPDATE visitor_intent_events SET converted_lead_id = ? WHERE id = ? AND org_id = ?",
            (lead_id, event_id, org)
        )
        db.commit()

    return {"status": "converted", "lead_id": lead_id, "company_name": name, "domain": domain}
