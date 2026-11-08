"""Saved searches: create, run, keep only what is new, tell the person once. Runs never invent results; a failing source is recorded and shown."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from alertdesk import engine as alerts
from database.db import get_db
from database.models import LeadRepository
from leadfinder import sources

logger = logging.getLogger("AgencyBD.leadfinder")
MAX_SEARCHES = 30
MAX_NOTIFY_LINES = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _search(r) -> Dict[str, Any]:
    d = dict(r)
    d["params"] = json.loads(d.pop("params_json") or "{}")
    d["notify"], d["active"] = bool(d["notify"]), bool(d["active"])
    with get_db() as db:
        d["new_hits"] = db.execute("SELECT COUNT(*) FROM lead_hits WHERE search_id = ? AND status = 'new'", (d["id"],)).fetchone()[0]
    return d


def list_searches(org_id: str) -> List[Dict[str, Any]]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM lead_searches WHERE org_id = ? ORDER BY id DESC", (org_id,)).fetchall()
    return [_search(r) for r in rows]


def get_search(org_id: str, search_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as db:
        r = db.execute("SELECT * FROM lead_searches WHERE id = ? AND org_id = ?", (search_id, org_id)).fetchone()
    return _search(r) if r else None


def _check(name: str, source: str, params: Dict[str, Any], every_hours: int) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name or len(name) > 80:
        raise ValueError("Give the search a short name (up to 80 characters).")
    if source not in sources.SOURCES:
        raise ValueError("Unknown source.")
    if not 1 <= every_hours <= 168:
        raise ValueError("Re-run every 1 to 168 hours.")
    return sources.clean_params(source, params)


def create_search(org_id: str, name: str, source: str, params: Dict[str, Any], notify: bool = True, every_hours: int = 24) -> Dict[str, Any]:
    clean = _check(name, source, params, every_hours)
    with get_db() as db:
        if db.execute("SELECT COUNT(*) FROM lead_searches WHERE org_id = ?", (org_id,)).fetchone()[0] >= MAX_SEARCHES:
            raise ValueError(f"You can keep up to {MAX_SEARCHES} saved searches. Delete one first.")
        cur = db.execute("INSERT INTO lead_searches (org_id, name, source, params_json, notify, every_hours) VALUES (?, ?, ?, ?, ?, ?)",
                         (org_id, name.strip(), source, json.dumps(clean), int(notify), every_hours))
        db.commit()
        sid = cur.lastrowid
    return get_search(org_id, sid)


def update_search(org_id: str, search_id: int, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cur = get_search(org_id, search_id)
    if not cur:
        return None
    name = patch.get("name", cur["name"])
    params = patch.get("params", cur["params"])
    every = int(patch.get("every_hours", cur["every_hours"]))
    clean = _check(name, cur["source"], params, every)
    with get_db() as db:
        db.execute("UPDATE lead_searches SET name = ?, params_json = ?, notify = ?, active = ?, every_hours = ? WHERE id = ? AND org_id = ?",
                   (name.strip(), json.dumps(clean), int(bool(patch.get("notify", cur["notify"]))), int(bool(patch.get("active", cur["active"]))), every, search_id, org_id))
        db.commit()
    return get_search(org_id, search_id)


def delete_search(org_id: str, search_id: int) -> bool:
    with get_db() as db:
        hit = db.execute("DELETE FROM lead_searches WHERE id = ? AND org_id = ?", (search_id, org_id)).rowcount
        if hit:
            db.execute("DELETE FROM lead_hits WHERE search_id = ? AND org_id = ?", (search_id, org_id))
        db.commit()
    return bool(hit)


def run_search(org_id: str, search_id: int) -> Dict[str, Any]:
    """Runs one search now. Returns {new, total, status, detail}. A failure is stored on the search, never raised."""
    s = get_search(org_id, search_id)
    if not s:
        raise LookupError("search not found")
    status, detail, found = "ok", "", []
    try:
        found = sources.SOURCES[s["source"]]["run"](org_id, s["params"])
    except sources.NotConfigured as exc:
        status, detail = "error", str(exc)
    except Exception as exc:
        logger.warning("lead search %s failed: %s", search_id, type(exc).__name__)
        status, detail = "error", str(exc)[:200] or "The source could not be reached. It will be tried again."
    new = 0
    now = _fmt(_now())
    with get_db() as db:
        first_run = s["last_run_at"] is None
        for h in found:
            cur = db.execute("INSERT OR IGNORE INTO lead_hits (org_id, search_id, key, title, detail, url, data_json, first_seen_at, notified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (org_id, search_id, h["key"], h["title"][:200], (h.get("detail") or "")[:300], h.get("url"), json.dumps(h.get("data") or {}), now, 0))
            new += cur.rowcount
        db.execute("UPDATE lead_searches SET last_run_at = ?, last_status = ?, last_detail = ? WHERE id = ?",
                   (now, status, detail or f"{len(found)} found, {new} new.", search_id))
        db.commit()
    return {"search_id": search_id, "status": status, "detail": detail, "total": len(found), "new": new, "first_run": first_run}


def due(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    now = now or _now()
    with get_db() as db:
        rows = db.execute("SELECT id, org_id, last_run_at, every_hours FROM lead_searches WHERE active = 1").fetchall()
    out = []
    for r in rows:
        if r["last_run_at"] is None or datetime.strptime(r["last_run_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) + timedelta(hours=r["every_hours"]) <= now:
            out.append({"id": r["id"], "org_id": r["org_id"]})
    return out


# ------------------------------------------------------------------ hits

def list_hits(org_id: str, status: Optional[str] = None, search_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
    q, args = "SELECT h.*, s.name AS search_name FROM lead_hits h JOIN lead_searches s ON s.id = h.search_id WHERE h.org_id = ?", [org_id]
    if status:
        q += " AND h.status = ?"
        args.append(status)
    if search_id:
        q += " AND h.search_id = ?"
        args.append(search_id)
    q += " ORDER BY h.id DESC LIMIT ?"
    args.append(limit)
    with get_db() as db:
        rows = db.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d.pop("data_json") or "{}")
        out.append(d)
    return out


def dismiss(org_id: str, hit_id: int) -> bool:
    with get_db() as db:
        n = db.execute("UPDATE lead_hits SET status = 'dismissed' WHERE id = ? AND org_id = ? AND status != 'saved'", (hit_id, org_id)).rowcount
        db.commit()
    return bool(n)


_DOMAIN = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


def save_to_clients(org_id: str, hit_id: int, website: Optional[str] = None) -> Dict[str, Any]:
    """Keeps a hit. When there is a website (given by you, or already known from your own check) it also becomes a client you can
    work on. A website is never guessed: without one the hit is kept and no client is created."""
    with get_db() as db:
        r = db.execute("SELECT h.*, s.name AS search_name FROM lead_hits h JOIN lead_searches s ON s.id = h.search_id WHERE h.id = ? AND h.org_id = ?", (hit_id, org_id)).fetchone()
    if not r:
        raise LookupError("hit not found")
    data = json.loads(r["data_json"] or "{}")
    domain = (website or data.get("domain") or "").lower().strip().replace("https://", "").replace("http://", "").split("/")[0].removeprefix("www.")
    if website and not _DOMAIN.match(domain):
        raise ValueError("That does not look like a website address. Use something like example.com.")
    lead_id = None
    if domain and _DOMAIN.match(domain):
        lead = LeadRepository.create_or_get_lead(company_name=(data.get("company") or r["title"]), domain=domain, source_channel="lead_finder", source_query=r["search_name"], org_id=org_id)
        lead_id = lead["id"]
    with get_db() as db:
        db.execute("UPDATE lead_hits SET status = 'saved', lead_id = COALESCE(?, lead_id) WHERE id = ?", (lead_id, hit_id))
        db.commit()
    return {"hit_id": hit_id, "lead_id": lead_id}


# ------------------------------------------------------------------ telling the person (one quiet digest, never a phone call)

def notify_new(org_id: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Sends one short message about new hits from searches that have notifications on. Held back during quiet hours and when
    the alert desk is paused; hits stay marked as not yet announced so nothing is lost or repeated."""
    now = now or _now()
    with get_db() as db:
        rows = db.execute("""SELECT h.id, h.title, s.name AS search_name FROM lead_hits h JOIN lead_searches s ON s.id = h.search_id
                             WHERE h.org_id = ? AND h.status = 'new' AND h.notified = 0 AND s.notify = 1 ORDER BY h.id""", (org_id,)).fetchall()
    if not rows:
        return {"sent": 0, "reason": "nothing new"}
    lines = [f"• {r['title']} ({r['search_name']})" for r in rows[:MAX_NOTIFY_LINES]]
    more = len(rows) - MAX_NOTIFY_LINES
    text = f"{len(rows)} new lead{'s' if len(rows) != 1 else ''} from your saved searches:\n" + "\n".join(lines) + (f"\n…and {more} more in Find." if more > 0 else "")
    ok, detail = alerts.tell(org_id, text, "New leads", now)
    if ok:
        with get_db() as db:
            db.executemany("UPDATE lead_hits SET notified = 1 WHERE id = ?", [(r["id"],) for r in rows])
            db.commit()
    return {"sent": len(rows) if ok else 0, "reason": detail}


def cycle(now: Optional[datetime] = None) -> Dict[str, Any]:
    ran = 0
    for d in due(now):
        try:
            run_search(d["org_id"], d["id"])
            ran += 1
        except Exception:
            logger.exception("lead search %s crashed", d["id"])
    with get_db() as db:
        pending = [r["org_id"] for r in db.execute("SELECT DISTINCT org_id FROM lead_hits WHERE status = 'new' AND notified = 0").fetchall()]
    for org in pending:                                  # also picks up hits held back by quiet hours earlier
        notify_new(org, now)
    return {"ran": ran}
