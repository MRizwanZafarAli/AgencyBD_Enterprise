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
MAX_AUTO_PLAY_PER_RUN = 10


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
        d["total_hits"] = db.execute("SELECT COUNT(*) FROM lead_hits WHERE search_id = ?", (d["id"],)).fetchone()[0]
        d["kept_hits"] = db.execute("SELECT COUNT(*) FROM lead_hits WHERE search_id = ? AND status = 'saved'", (d["id"],)).fetchone()[0]
    d["hit_rate_pct"] = round((d["kept_hits"] / d["total_hits"]) * 100) if d["total_hits"] else 0
    d["auto_play"] = bool(d["params"].get("auto_play", False))
    d["min_score_alert"] = int(d["params"].get("min_score_alert") or 80)
    d["alert_mode"] = d["params"].get("alert_mode") or ("instant" if d["notify"] else "digest")
    d["channels"] = d["params"].get("channels") or (["Telegram", "Email Digest"] if d["notify"] else ["Email Digest"])
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
        cur = db.execute("INSERT INTO lead_searches (org_id, name, source, params_json, notify, every_hours) "
                         "SELECT ?, ?, ?, ?, ?, ? WHERE (SELECT COUNT(*) FROM lead_searches WHERE org_id = ?) < ?",
                         (org_id, name.strip(), source, json.dumps(clean), int(notify), every_hours, org_id, MAX_SEARCHES))
        db.commit()
        if cur.rowcount == 0:
            raise ValueError(f"You can keep up to {MAX_SEARCHES} saved searches. Delete one first.")
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
    auto_played = 0
    now = _fmt(_now())
    auto_play = bool(s["params"].get("auto_play", False))
    min_score = int(s["params"].get("min_score_alert") or 80)
    with get_db() as db:
        first_run = s["last_run_at"] is None
        existing_urls = {
            _canonical_url(row[0])
            for row in db.execute("SELECT url FROM lead_hits WHERE search_id = ? AND url IS NOT NULL", (search_id,)).fetchall()
            if _canonical_url(row[0])
        }
        for h in found:
            canon_u = _canonical_url(h.get("url"))
            if canon_u and canon_u in existing_urls:
                continue
            cur = db.execute("INSERT OR IGNORE INTO lead_hits (org_id, search_id, key, title, detail, url, data_json, first_seen_at, notified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (org_id, search_id, h["key"], h["title"][:200], (h.get("detail") or "")[:300], h.get("url"), json.dumps(h.get("data") or {}), now, 0))
            if cur.rowcount:
                new += 1
                if canon_u:
                    existing_urls.add(canon_u)
                if auto_play and auto_played < MAX_AUTO_PLAY_PER_RUN:
                    sc = _infer_score(s["source"], h.get("data") or {})
                    if sc >= min_score and cur.lastrowid:
                        try:
                            res = save_to_clients(org_id, cur.lastrowid, source_stamp=f"Auto-saved by {s['name']}")
                            if res.get("lead_id"):
                                auto_played += 1
                        except Exception:
                            pass
        db.execute("UPDATE lead_searches SET last_run_at = ?, last_status = ?, last_detail = ? WHERE id = ?",
                   (now, status, detail or f"{len(found)} found, {new} new" + (f", {auto_played} auto-played." if auto_played else "."), search_id))
        db.commit()
    return {"search_id": search_id, "status": status, "detail": detail, "total": len(found), "new": new, "auto_played": auto_played, "first_run": first_run}


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

def _canonical_url(url: Optional[str]) -> str:
    if not url:
        return ""
    base = url.strip().split("#")[0].split("?")[0].rstrip("/").lower()
    return base.replace("https://www.", "https://").replace("http://www.", "http://")


def _domain(url: Optional[str]) -> str:
    if not url:
        return ""
    host = url.lower().strip().replace("https://", "").replace("http://", "").split("/")[0].split("?")[0].removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] not in ("co", "com", "org", "net", "gov", "ac"):
        return ".".join(parts[-2:])
    return host


_CORP_SUFFIX_RE = re.compile(r"\b(inc|incorporated|ltd|limited|llc|llp|plc|corp|corporation|gmbh|co|company|group|holdings)\b\.?", re.I)


def _normalize_company_name(name: str) -> str:
    cleaned = _CORP_SUFFIX_RE.sub("", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", "", cleaned)


def _infer_score(source: str, data: Dict[str, Any]) -> int:
    if data.get("intent_score") is not None:
        return int(data["intent_score"])
    if data.get("fit_score") is not None:
        val = float(data["fit_score"])
        return round(val * 100) if val <= 1.0 else int(val)
    return 78 if source in ("social_intent", "tender_cpv") else 72


def _infer_domain(url: Optional[str], data: Dict[str, Any]) -> str:
    if data.get("domain"):
        return str(data["domain"]).lower().lstrip("www.")
    if data.get("website"):
        return _domain(str(data["website"])) or ""
    ext = data.get("external_urls") or []
    if ext:
        return _domain(str(ext[0])) or ""
    if url:
        dom = _domain(url) or ""
        if dom and not any(b in dom for b in ("reddit.com", "news.ycombinator.com", "github.com", "bsky.app", "dev.to", "lobste.rs")):
            return dom
    return ""


def _action_window(source: str, data: Dict[str, Any]) -> str:
    if source == "social_intent":
        return "Act within 24h"
    if source == "tender_cpv":
        dl = data.get("deadline")
        return f"Deadline {str(dl)[:10]}" if dl else "Portal deadline"
    if source == "site_signals":
        return "Technical pain active"
    return "7d hiring window"


def list_hits(org_id: str, status: Optional[str] = None, search_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
    q, args = "SELECT h.*, s.name AS search_name, s.source AS search_source FROM lead_hits h JOIN lead_searches s ON s.id = h.search_id WHERE h.org_id = ?", [org_id]
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
    company_counts: Dict[str, int] = {}
    for r in rows:
        d = dict(r)
        data = json.loads(d.pop("data_json") or "{}")
        d["data"] = data
        src = d.get("search_source") or "hiring"
        d["score"] = _infer_score(src, data)
        d["auto_domain"] = _infer_domain(d.get("url"), data)
        d["company_name"] = (data.get("company_name") or d.get("title") or "").strip()[:80]
        d["action_window"] = _action_window(src, data)
        stack_key = d["auto_domain"] or _normalize_company_name(d["company_name"])
        if stack_key:
            company_counts[stack_key] = company_counts.get(stack_key, 0) + 1
        d["_stack_key"] = stack_key
        out.append(d)
    for d in out:
        sk = d.pop("_stack_key", "")
        d["multi_signal_count"] = company_counts.get(sk, 1) if sk else 1
    return out


def dismiss(org_id: str, hit_id: int) -> bool:
    with get_db() as db:
        n = db.execute("UPDATE lead_hits SET status = 'dismissed' WHERE id = ? AND org_id = ? AND status != 'saved'", (hit_id, org_id)).rowcount
        db.commit()
    return bool(n)


_DOMAIN = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


def save_to_clients(org_id: str, hit_id: int, website: Optional[str] = None, source_stamp: Optional[str] = None) -> Dict[str, Any]:
    """Keeps a hit. When there is a website (given by you, or already known from your own check) it also becomes a client you can
    work on. A website is never guessed: without one the hit is kept and no client is created."""
    with get_db() as db:
        r = db.execute("SELECT h.*, s.name AS search_name FROM lead_hits h JOIN lead_searches s ON s.id = h.search_id WHERE h.id = ? AND h.org_id = ?", (hit_id, org_id)).fetchone()
    if not r:
        raise LookupError("hit not found")
    data = json.loads(r["data_json"] or "{}")
    inferred = _infer_domain(r["url"], data)
    domain = (website or inferred or "").lower().strip().replace("https://", "").replace("http://", "").split("/")[0].removeprefix("www.")
    if website and not _DOMAIN.match(domain):
        raise ValueError("That does not look like a website address. Use something like example.com.")
    lead_id = None
    if domain and _DOMAIN.match(domain):
        lead = LeadRepository.create_or_get_lead(
            company_name=(data.get("company_name") or data.get("company") or r["title"]),
            domain=domain,
            source_channel="lead_finder",
            source_query=source_stamp or r["search_name"],
            org_id=org_id,
        )
        lead_id = lead["id"]
    with get_db() as db:
        db.execute("UPDATE lead_hits SET status = 'saved', lead_id = COALESCE(?, lead_id) WHERE id = ?", (lead_id, hit_id))
        db.commit()
    return {"hit_id": hit_id, "lead_id": lead_id}


def bulk_save(org_id: str, hit_ids: List[int]) -> Dict[str, Any]:
    saved = 0
    for hid in hit_ids[:100]:
        try:
            save_to_clients(org_id, int(hid))
            saved += 1
        except Exception:
            pass
    return {"saved": saved}


def bulk_dismiss(org_id: str, hit_ids: List[int]) -> Dict[str, Any]:
    dismissed = 0
    for hid in hit_ids[:100]:
        if dismiss(org_id, int(hid)):
            dismissed += 1
    return {"dismissed": dismissed}


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
