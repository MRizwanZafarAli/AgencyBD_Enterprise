"""Settings: the agency profile, and a tenant's data summary and exports."""

import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from config import agency_profile as profile
from config.settings import DATA_DIR, DB_PATH
from database.db import get_db
from security.auth import Principal, require_permission

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])
READ = require_permission("leads:read")
MANAGE = require_permission("apikeys:manage")          # held only by the super-admin wildcard: these settings reach every tenant on this installation


class ValueBody(BaseModel):
    value: str = ""


@router.get("/profile")
def get_profile(principal: Principal = Depends(READ)):
    fields = profile.list_status()
    return {"fields": fields, "can_edit": principal.role == "super_admin", "ready_to_send": all(f["set"] for f in fields if f["needed_to_send"]),
            "note": "Shared by every workspace on this installation. A saved value overrides .env; Reset goes back to .env."}


@router.put("/profile/{key}")
def save_profile_field(key: str, body: ValueBody, principal: Principal = Depends(MANAGE)):
    try:
        return profile.set_field(key, body.value, principal.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/profile/{key}")
def reset_profile_field(key: str, principal: Principal = Depends(MANAGE)):
    try:
        return {"reset": profile.reset_field(key), "field": profile.field_status(key)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ---------------------------------------------------------------- data

COUNTS = {"clients": "SELECT COUNT(*) FROM leads WHERE org_id = ?", "contacts": "SELECT COUNT(*) FROM decision_makers WHERE org_id = ?",
          "audits": "SELECT COUNT(*) FROM audit_runs WHERE org_id = ?", "notes_and_tasks": "SELECT COUNT(*) FROM client_notes WHERE org_id = ?",
          "channel_entries": "SELECT COUNT(*) FROM channel_records WHERE org_id = ?", "emails_sent": "SELECT COUNT(*) FROM outbound_drafts WHERE org_id = ? AND status = 'sent'"}


@router.get("/data/summary")
def data_summary(principal: Principal = Depends(READ)) -> Dict[str, Any]:
    with get_db() as db:
        counts = {k: db.execute(q, (principal.org_id,)).fetchone()[0] for k, q in COUNTS.items()}
    out: Dict[str, Any] = {"counts": counts, "exports": list(EXPORTS)}
    if principal.role == "super_admin":                      # installation details are for the administrator only
        backups = sorted((DATA_DIR / "backups").glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True) if (DATA_DIR / "backups").exists() else []
        out["installation"] = {"database_bytes": os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0, "backups": len(backups),
                               "last_backup_at": datetime.fromtimestamp(backups[0].stat().st_mtime, timezone.utc).isoformat() if backups else None,
                               "backup_command": "python3 scripts/backup_db.py"}
    return out


def _safe(v: Any) -> Any:
    """Spreadsheet formula injection: a cell that starts with = + - @ is executed by Excel and Sheets, so it is prefixed to be plain text."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _clients(db, org: str) -> List[List[Any]]:
    rows = db.execute("SELECT id, company_name, domain, phone, address, status, source_channel, created_at FROM leads WHERE org_id = ? ORDER BY id", (org,)).fetchall()
    return [["id", "company", "website", "phone", "address", "stage", "source", "created_at"]] + [list(r) for r in rows]


def _notes(db, org: str) -> List[List[Any]]:
    rows = db.execute("SELECT l.company_name, n.kind, n.body, n.due_date, n.done_at, n.created_by, n.created_at FROM client_notes n JOIN leads l ON l.id = n.lead_id AND l.org_id = n.org_id "
                      "WHERE n.org_id = ? ORDER BY n.id", (org,)).fetchall()
    return [["company", "kind", "text", "due", "done_at", "created_by", "created_at"]] + [list(r) for r in rows]


def _channels(db, org: str) -> List[List[Any]]:
    rows = db.execute("SELECT platform, type, data_json, created_at FROM channel_records WHERE org_id = ? ORDER BY id", (org,)).fetchall()
    out = [["platform", "type", "title_or_name", "status", "value", "follow_up", "details_json", "created_at"]]
    for r in rows:
        d = json.loads(r["data_json"])
        out.append([r["platform"], r["type"], d.get("title") or d.get("name") or d.get("label") or d.get("what") or "", d.get("status", ""), d.get("value", ""), d.get("next_followup", ""),
                    json.dumps(d, ensure_ascii=False), r["created_at"]])
    return out


def _audits(db, org: str) -> List[List[Any]]:
    rows = db.execute("SELECT id, domain, overall_score, status, created_at FROM audit_runs WHERE org_id = ? ORDER BY id", (org,)).fetchall()
    return [["id", "website", "score", "status", "created_at"]] + [list(r) for r in rows]


EXPORTS = {"clients": _clients, "notes": _notes, "channels": _channels, "audits": _audits}


@router.get("/data/export/{kind}")
def export_data(kind: str, principal: Principal = Depends(READ)):
    """A CSV of this workspace's own records. Never includes another tenant's rows, keys or secrets."""
    if kind not in EXPORTS:
        raise HTTPException(status_code=404, detail=f"Unknown export. Choose one of: {', '.join(EXPORTS)}.")
    with get_db() as db:
        rows = EXPORTS[kind](db, principal.org_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow([_safe(c) for c in row])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="agencybd-{kind}-{stamp}.csv"'})
