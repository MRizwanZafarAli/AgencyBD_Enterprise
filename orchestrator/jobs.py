"""
Background Discovery Runs. A run can take a minute (it verifies websites, audits sites and checks vulnerability databases), so the
API starts it in a worker thread and returns an id; the UI polls for progress. State is persisted in `discovery_runs`, so a page
reload or a second tab sees the same run. Runs interrupted by a restart are reported as failed, never left "running" forever.
"""

import json
import threading
import uuid
from typing import Any, Dict, Optional

from core import metrics
from database.db import get_db
from orchestrator.autopilot import DiscoveryRun

MAX_CONCURRENT_PER_ORG = 1


def _update(run_id: str, **cols: Any) -> None:
    sets = ", ".join(f"{k} = ?" for k in cols)
    with get_db() as db:
        db.execute(f"UPDATE discovery_runs SET {sets} WHERE id = ?", (*cols.values(), run_id))
        db.commit()


def _finish(run_id: str, status: str, result_json: Optional[str] = None, error: Optional[str] = None) -> None:
    with get_db() as db:
        db.execute("UPDATE discovery_runs SET status = ?, result_json = ?, error = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (status, result_json, error, run_id))
        db.commit()
    metrics.DISCOVERY_RUNS.labels(status).inc()


def _worker(run_id: str, org_id: str, params: Dict[str, Any], user: str) -> None:
    try:
        report = lambda p: _update(run_id, progress_json=json.dumps(p))
        if params.get("channel") == "radar_scan":
            from radar.engine import OpportunityRadarEngine
            found = OpportunityRadarEngine().scan_all_sources(limit_per_source=10, org_id=org_id, progress=report)
            result = {"channel": "radar_scan", "stored": len(found)}
        else:
            result = DiscoveryRun().run(org_id, params["channel"], params.get("query", ""), params.get("location", ""), params.get("limit", 5), user=user, progress=report)
        _finish(run_id, "done", result_json=json.dumps(result, default=str))
    except Exception as exc:                       # surfaced to the person, never swallowed
        _finish(run_id, "failed", error=str(exc)[:300])


def start(org_id: str, params: Dict[str, Any], user: str) -> Dict[str, Any]:
    if params.get("channel") not in ("hiring", "sec_edgar", "local", "radar_scan"):
        raise ValueError("channel must be hiring, sec_edgar, local or radar_scan")
    with get_db() as db:
        running = db.execute("SELECT id FROM discovery_runs WHERE org_id = ? AND status = 'running' AND started_at > datetime('now', '-15 minutes')", (org_id,)).fetchone()
        if running:
            return {"run_id": running["id"], "status": "running", "already_running": True}
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        db.execute("INSERT INTO discovery_runs (id, org_id, params_json) VALUES (?, ?, ?)", (run_id, org_id, json.dumps(params)))
        db.commit()
    threading.Thread(target=_worker, args=(run_id, org_id, params, user), name=f"discovery-{run_id}", daemon=True).start()
    return {"run_id": run_id, "status": "running", "already_running": False}


def get(org_id: str, run_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as db:
        row = db.execute("SELECT * FROM discovery_runs WHERE id = ? AND org_id = ?", (run_id, org_id)).fetchone()
        if row and row["status"] == "running":
            stale = db.execute("SELECT 1 FROM discovery_runs WHERE id = ? AND started_at < datetime('now', '-15 minutes')", (run_id,)).fetchone()
            if stale:
                db.execute("UPDATE discovery_runs SET status = 'failed', error = 'The run was interrupted (server restart or timeout).' WHERE id = ?", (run_id,))
                db.commit()
                row = db.execute("SELECT * FROM discovery_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    out = {"run_id": row["id"], "status": row["status"], "error": row["error"], "progress": json.loads(row["progress_json"] or "null"),
           "started_at": row["started_at"], "finished_at": row["finished_at"]}
    if row["result_json"]:
        out["result"] = json.loads(row["result_json"])
    return out
