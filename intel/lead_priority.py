"""
Lead priority: a transparent 0-100 score for "who should a human look at first".

It is NOT a probability of winning. Each component is built from something observed (audit findings, how the business is
present on the web, reviews, the source signal, whether a verified contact exists) and every point is explained in
`reasons`. Calibration against YOUR outcomes (won vs lost) is reported by `calibration()`, and only becomes a statement about
win rates once enough deals have closed.
"""

import json
import re
from typing import Any, Dict, List, Optional

from database.db import get_db
from database.models import AuditRunRepository

WEIGHTS = {"need": 45, "presence": 20, "reputation": 15, "signal": 15, "reachability": 5}   # sums to 100
SEVERITY_POINTS = {"critical": 12, "high": 8, "medium": 4, "low": 1, "info": 0}
SIGNAL_POINTS = {"hiring_intent": 15, "sec_edgar_form_d": 12, "google_maps": 8, "map_osm": 6, "crm_pipeline": 5}
PRESENCE_POINTS = {"no_website_listed": 20, "no_website_in_osm": 12, "social_only": 18, "domain_unreachable": 18,
                   "domain_parked": 18, "tls_broken": 16}
HOT, WARM = 60, 35
MIN_CLOSED_FOR_CALIBRATION = 20


def _band(score: int) -> str:
    return "hot" if score >= HOT else "warm" if score >= WARM else "cold"


def score_lead(lead_id: int, org_id: str, persist: bool = True) -> Dict[str, Any]:
    with get_db() as db:
        lead = db.execute("SELECT * FROM leads WHERE id = ? AND org_id = ?", (lead_id, org_id)).fetchone()
        if not lead:
            raise LookupError("Lead not found")
        lead = dict(lead)
        company = db.execute("SELECT id FROM companies WHERE org_id = ? AND LOWER(domain) = LOWER(?) ORDER BY id LIMIT 1",
                             (org_id, lead["domain"])).fetchone()
        contacts = db.execute("SELECT verification_status FROM decision_makers WHERE lead_id = ? AND org_id = ?", (lead_id, org_id)).fetchall()

    reasons: List[str] = []
    comp = {k: 0 for k in WEIGHTS}
    needs: List[str] = []
    notes = lead.get("notes") or ""

    # need: what the audit measured
    audit = AuditRunRepository.latest_for_company(company["id"], org_id) if company else None
    if audit and audit["status"] == "completed":
        findings = AuditRunRepository.get_findings(audit["id"], org_id=org_id)
        pts = sum(SEVERITY_POINTS.get(f["severity"], 0) for f in findings)
        comp["need"] = min(WEIGHTS["need"], pts)
        counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("critical", "high", "medium")}
        if comp["need"]:
            reasons.append("Audit found " + ", ".join(f"{n} {s}" for s, n in counts.items() if n) + " issue(s)" if any(counts.values())
                           else f"Audit found {len(findings)} minor issue(s)")
    else:
        needs.append("run_audit")
        reasons.append("Not audited yet, so need is unknown")

    # presence: how the business shows up on the web
    m = re.search(r"WEB PRESENCE:\s*([a-z_]+)", notes)
    if m and m.group(1) in PRESENCE_POINTS:
        comp["presence"] = PRESENCE_POINTS[m.group(1)]
        reasons.append(f"Web presence: {m.group(1).replace('_', ' ')}")

    # reputation: an established business can pay
    reviews = lead.get("reviews_count") or 0
    if reviews >= 50:
        comp["reputation"] = 15
    elif reviews >= 15:
        comp["reputation"] = 10
    elif reviews >= 5:
        comp["reputation"] = 5
    if comp["reputation"]:
        reasons.append(f"{reviews} reviews (established business)")

    # signal: why now
    channel = lead.get("source_channel") or ""
    comp["signal"] = SIGNAL_POINTS.get(channel, 0)
    if comp["signal"]:
        reasons.append({"hiring_intent": "Currently hiring engineers", "sec_edgar_form_d": "Recent funding filing",
                        "google_maps": "Local business found on a map", "map_osm": "Local business found on a map"}.get(channel, f"Source: {channel}"))

    # reachability: can we actually contact someone
    if any(c["verification_status"] == "verified" for c in contacts):
        comp["reachability"] = 5
        reasons.append("A verified contact exists")
    else:
        needs.append("find_contact")
        if lead.get("phone"):
            comp["reachability"] = 2
            reasons.append("Phone number available (no verified email)")

    score = int(sum(comp.values()))
    result = {"lead_id": lead_id, "score": score, "band": _band(score), "components": comp, "weights": WEIGHTS, "reasons": reasons,
              "needs": needs, "confidence": "low" if "run_audit" in needs else "medium"}
    if persist:
        with get_db() as db:
            db.execute("INSERT INTO lead_scores (org_id, lead_id, score, band, components_json) VALUES (?, ?, ?, ?, ?)",
                       (org_id, lead_id, score, result["band"], json.dumps({"components": comp, "reasons": reasons})))
            db.commit()
    return result


def calibration(org_id: str) -> Dict[str, Any]:
    """Win rate by band, from leads that actually closed. Says so plainly when there is not enough data."""
    with get_db() as db:
        rows = db.execute("""
            SELECT l.status AS outcome, (SELECT band FROM lead_scores s WHERE s.lead_id = l.id AND s.org_id = l.org_id
                                         ORDER BY s.id ASC LIMIT 1) AS band
            FROM leads l WHERE l.org_id = ? AND l.status IN ('won', 'lost')""", (org_id,)).fetchall()
    closed = len(rows)
    if closed < MIN_CLOSED_FOR_CALIBRATION:
        return {"calibrated": False, "closed_deals": closed, "needed": MIN_CLOSED_FOR_CALIBRATION,
                "message": f"{closed} closed deals so far; the score is a ranking aid until {MIN_CLOSED_FOR_CALIBRATION} have closed."}
    out: Dict[str, Any] = {"calibrated": True, "closed_deals": closed, "bands": {}}
    for band in ("hot", "warm", "cold"):
        sub = [r for r in rows if r["band"] == band]
        if sub:
            won = sum(1 for r in sub if r["outcome"] == "won")
            out["bands"][band] = {"closed": len(sub), "won": won, "win_rate_percent": round(won / len(sub) * 100, 1)}
    return out
