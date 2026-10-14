"""System readiness: what is configured, what is missing and how to fix it. Never exposes a secret value."""

import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from config.env import environment

from connectors.oauth import TokenStore
from database.db import get_db
from outbound.verify import configured_vendor
from security.auth import Principal, ROLE_PERMISSIONS, get_current_principal, require_permission
from security.webhook_verifier import WebhookSecrets

router = APIRouter(prefix="/api", tags=["System"])


def _set(*names: str) -> bool:
    return any((os.getenv(n) or "") and not (os.getenv(n) or "").startswith("your_") for n in names)


def build_checks(org_id: str) -> List[Dict[str, Any]]:
    with get_db() as db:
        assets = db.execute("SELECT COUNT(*) FROM portfolio_assets WHERE org_id = ?", (org_id,)).fetchone()[0]
        priced = db.execute("SELECT COUNT(*) FROM services WHERE org_id = ? AND price_band IS NOT NULL AND price_band != ''", (org_id,)).fetchone()[0]
        boxes = db.execute("SELECT COUNT(*) FROM mailboxes WHERE org_id = ?", (org_id,)).fetchone()[0]
        sendable = db.execute("SELECT COUNT(*) FROM mailbox_credentials WHERE org_id = ?", (org_id,)).fetchone()[0]

    def check(key, label, ok, fix, required=True, detail=None):
        return {"key": key, "label": label, "status": "ok" if ok else ("missing" if required else "optional_missing"),
                "required": required, "detail": detail, "fix": None if ok else fix}

    return [
        check("llm", "Language model (proposals)", _set("ANTHROPIC_API_KEY", "OLLAMA_HOST"), "Set ANTHROPIC_API_KEY in .env."),
        check("portfolio", "Portfolio case studies", assets > 0, "Add at least one real case study under Portfolio & Proof.", detail=f"{assets} case studies"),
        check("services", "Service price bands", priced > 0, "Add price bands under Services so briefs can quote them.", detail=f"{priced} priced services"),
        check("verifier", "Email verifier", configured_vendor() is not None, "Set ZEROBOUNCE_API_KEY or MILLIONVERIFIER_API_KEY. Without one, nothing can be emailed."),
        check("mailbox", "Sending mailbox with credentials", sendable > 0, "Register a mailbox with SMTP credentials under Governance > Mailbox Fleet.",
              detail=f"{boxes} mailboxes, {sendable} with credentials"),
        check("sender_identity", "Sender identity for the email footer (legal requirement)",
              _set("AGENCYBD_SENDER_ADDRESS") and _set("AGENCYBD_PUBLIC_BASE_URL"),
              "Set AGENCYBD_SENDER_COMPANY, AGENCYBD_SENDER_ADDRESS and AGENCYBD_PUBLIC_BASE_URL."),
        check("scheduler", "Sequence scheduler", _set("AGENCYBD_SCHEDULER") and os.getenv("AGENCYBD_SCHEDULER", "").lower() in ("on", "true", "1"),
              "Set AGENCYBD_SCHEDULER=on or run `python scripts/run_scheduler.py` as a worker (a separate worker cannot be detected from here).", required=False),
        check("webhook_secret", "Inbound reply webhook secret", WebhookSecrets.get(org_id) is not None, "POST /api/security/webhook_secret and configure your mail provider.", required=False),
        check("pagespeed", "PageSpeed API (Core Web Vitals, accessibility audit)", _set("PAGESPEED_API_KEY"), "Set PAGESPEED_API_KEY (free from Google Cloud).", required=False),
        check("places", "Google Places API (local-business presence check)", _set("GOOGLE_PLACES_API_KEY"), "Set GOOGLE_PLACES_API_KEY.", required=False),
        check("search", "Web search for company resolution", _set("BRAVE_SEARCH_API_KEY"), "Optional: set BRAVE_SEARCH_API_KEY to improve company-name lookup.", required=False),
        check("upwork", "Upwork connected", TokenStore.load(org_id, "upwork") is not None, "Apply for Upwork API access, set the UPWORK_* variables, then use Connect Upwork in the Radar.", required=False),
        check("sam_gov", "SAM.gov key (US federal tenders)", _set("SAM_GOV_API_KEY"), "Set SAM_GOV_API_KEY.", required=False),
    ]


@router.get("/system/status")
def system_status(principal: Principal = Depends(require_permission("leads:read"))):
    checks = build_checks(principal.org_id)
    warnings = []
    if environment() != "production":
        warnings.append(f"Running in '{environment()}' mode.")
    missing = [c for c in checks if c["status"] == "missing"]
    return {"environment": environment(), "ready_to_send_email": all(c["status"] == "ok" for c in checks
            if c["key"] in ("verifier", "mailbox", "sender_identity")), "required_missing": len(missing), "checks": checks, "warnings": warnings}


@router.get("/security/roles")
def list_roles(principal: Principal = Depends(get_current_principal)):
    """The server's authoritative role/permission table (what each key type may do)."""
    return {"roles": ROLE_PERMISSIONS, "you": {"role": principal.role, "org_id": principal.org_id, "user_id": principal.user_id}}
