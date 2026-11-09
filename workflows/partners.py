"""Referral partners: agencies, accountants, designers and others who could send you work. You type everything here; nothing is looked up or guessed."""

import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from database.db import get_db

KINDS = {"agency": "Design, marketing or SEO agency", "accountant": "Accountant or bookkeeper", "lawyer": "Lawyer or company formation agent",
         "designer": "Freelance designer or photographer", "developer": "Another developer", "it_support": "IT support or hosting firm",
         "space": "Coworking space, incubator or association", "other": "Other"}
STAGES = {"to_contact": "To contact", "contacted": "Contacted", "talking": "In conversation", "active_partner": "Active partner", "not_a_fit": "Not a fit"}
EVENTS = ("contacted", "note", "referral_in", "referral_out")
LIMIT = 200
QUIET_DAYS = {"contacted": 7, "talking": 14, "active_partner": 45}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _text(v: Any, label: str, hi: int, required: bool = False) -> Optional[str]:
    v = (v or "").strip() if isinstance(v, str) or v is None else ""
    if required and not v:
        raise ValueError(f"{label} is required.")
    if len(v) > hi:
        raise ValueError(f"{label} is too long (max {hi} characters).")
    return v or None


def _day(v: Any) -> Optional[str]:
    if v in (None, ""):
        return None
    try:
        date.fromisoformat(str(v))
    except ValueError:
        raise ValueError("The date must look like 2026-11-20.")
    return str(v)


def clean(data: Dict[str, Any], current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cur = current or {}
    pick = lambda k: data[k] if k in data else cur.get(k)
    kind, stage = pick("kind") or "other", pick("stage") or "to_contact"
    if kind not in KINDS:
        raise ValueError("Unknown kind of partner.")
    if stage not in STAGES:
        raise ValueError("Unknown stage.")
    website = _text(pick("website"), "Website", 200)
    if website and not re.fullmatch(r"(https?://)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/\S*)?", website):
        raise ValueError("The website should look like example.com.")
    return {"name": _text(pick("name"), "Name", 100, True), "kind": kind, "stage": stage, "contact_name": _text(pick("contact_name"), "Contact name", 100),
            "contact_where": _text(pick("contact_where"), "How to reach them", 200), "website": website, "offer": _text(pick("offer"), "What you offered", 500),
            "next_step_date": _day(pick("next_step_date")), "notes": _text(pick("notes"), "Notes", 2000)}


def _attention(p: Dict[str, Any], today: date) -> Optional[str]:
    if p["stage"] in ("to_contact", "not_a_fit"):
        return None
    if p["next_step_date"] and p["next_step_date"] <= today.isoformat():
        return "Your next step is due."
    last = p["last_contact_at"]
    if last and p["stage"] in QUIET_DAYS:
        quiet = (today - date.fromisoformat(last[:10])).days
        if quiet >= QUIET_DAYS[p["stage"]]:
            return ("No reply for %d days. Follow up once, then leave it." % quiet) if p["stage"] == "contacted" else f"No contact for {quiet} days."
    return None


def _decorate(db, org_id: str, rows, today: date) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        p = dict(r)
        counts = {k: n for k, n in db.execute("SELECT kind, COUNT(*) FROM partner_events WHERE org_id = ? AND partner_id = ? AND kind IN ('referral_in', 'referral_out') GROUP BY kind", (org_id, p["id"]))}
        p["referrals_in"], p["referrals_out"] = counts.get("referral_in", 0), counts.get("referral_out", 0)
        p["attention"] = _attention(p, today)
        out.append(p)
    return out


def list_partners(org_id: str, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    with get_db() as db:
        rows = db.execute("SELECT * FROM partners WHERE org_id = ? ORDER BY id DESC LIMIT ?", (org_id, LIMIT)).fetchall()
        items = _decorate(db, org_id, rows, today)
    return {"partners": items, "summary": {"total": len(items), "active": sum(p["stage"] == "active_partner" for p in items), "needs_attention": sum(bool(p["attention"]) for p in items),
                                         "referrals_in": sum(p["referrals_in"] for p in items), "referrals_out": sum(p["referrals_out"] for p in items)}}


def create(org_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    c = clean(data)
    with get_db() as db:
        # one statement: the limit check and the insert cannot be split by another request (QA saw 210 saved against a limit of 200)
        cur = db.execute("INSERT INTO partners (org_id, name, kind, contact_name, contact_where, website, stage, offer, next_step_date, notes) "
                         "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ? WHERE (SELECT COUNT(*) FROM partners WHERE org_id = ?) < ?",
                         (org_id, c["name"], c["kind"], c["contact_name"], c["contact_where"], c["website"], c["stage"], c["offer"], c["next_step_date"], c["notes"], org_id, LIMIT))
        db.commit()
        if cur.rowcount == 0:
            raise ValueError(f"You can keep up to {LIMIT} partners.")
    return get(org_id, cur.lastrowid)


def get(org_id: str, partner_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as db:
        r = db.execute("SELECT * FROM partners WHERE id = ? AND org_id = ?", (partner_id, org_id)).fetchone()
        return _decorate(db, org_id, [r], datetime.now(timezone.utc).date())[0] if r else None


def update(org_id: str, partner_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cur = get(org_id, partner_id)
    if not cur:
        return None
    c = clean(data, cur)
    with get_db() as db:
        db.execute("UPDATE partners SET name=?, kind=?, contact_name=?, contact_where=?, website=?, stage=?, offer=?, next_step_date=?, notes=? WHERE id=? AND org_id=?",
                   (c["name"], c["kind"], c["contact_name"], c["contact_where"], c["website"], c["stage"], c["offer"], c["next_step_date"], c["notes"], partner_id, org_id))
        db.commit()
    return get(org_id, partner_id)


def delete(org_id: str, partner_id: int) -> bool:
    with get_db() as db:
        n = db.execute("DELETE FROM partners WHERE id = ? AND org_id = ?", (partner_id, org_id)).rowcount
        if n:
            db.execute("DELETE FROM partner_events WHERE partner_id = ? AND org_id = ?", (partner_id, org_id))
        db.commit()
    return n > 0


def add_event(org_id: str, partner_id: int, kind: str, body: Optional[str]) -> Optional[Dict[str, Any]]:
    if kind not in EVENTS:
        raise ValueError("kind must be contacted, note, referral_in or referral_out.")
    note = _text(body, "Note", 1000, required=kind == "note")
    p = get(org_id, partner_id)
    if not p:
        return None
    now = _now()
    with get_db() as db:
        db.execute("INSERT INTO partner_events (org_id, partner_id, kind, body, at) VALUES (?,?,?,?,?)", (org_id, partner_id, kind, note, now))
        if kind == "contacted":                                   # contacting someone moves a new partner on, and clears a due step
            db.execute("UPDATE partners SET last_contact_at = ?, stage = CASE WHEN stage = 'to_contact' THEN 'contacted' ELSE stage END, "
                       "next_step_date = CASE WHEN next_step_date <= ? THEN NULL ELSE next_step_date END WHERE id = ? AND org_id = ?", (now, now[:10], partner_id, org_id))
        elif kind in ("referral_in", "referral_out"):
            db.execute("UPDATE partners SET last_contact_at = ?, stage = CASE WHEN stage IN ('to_contact', 'contacted', 'talking') THEN 'active_partner' ELSE stage END WHERE id = ? AND org_id = ?", (now, partner_id, org_id))
        db.commit()
    return get(org_id, partner_id)


def events(org_id: str, partner_id: int) -> Optional[List[Dict[str, Any]]]:
    if not get(org_id, partner_id):
        return None
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT id, kind, body, at FROM partner_events WHERE org_id = ? AND partner_id = ? ORDER BY id DESC LIMIT 100", (org_id, partner_id))]
