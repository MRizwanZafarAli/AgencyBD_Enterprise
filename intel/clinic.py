"""Site Clinic support: audit history, what changed since the last check, and a written teardown.

Everything is read from stored audits and the evidence behind them. The teardown contains measured findings and the fix for each, and says what was
not measured. It has no invented price, timeline or result; a price appears only if the person set one for that service.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.db import get_db
from intel import advisor

SEVERITIES = ("critical", "high", "medium", "low", "info")


def _findings(db, org_id: str, run_id: int) -> List[Dict[str, Any]]:
    return [dict(r) for r in db.execute("SELECT category, check_id, severity, finding, fix, estimated_impact, service_id, evidence_id FROM audit_findings "
                                        "WHERE audit_run_id = ? AND org_id = ?", (run_id, org_id)).fetchall()]


def history(org_id: str, company_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    with get_db() as db:
        runs = db.execute("SELECT id, domain, overall_score, status, created_at FROM audit_runs WHERE org_id = ? AND company_id = ? ORDER BY id DESC LIMIT ?",
                          (org_id, company_id, limit)).fetchall()
        out = []
        for r in runs:
            by = {s: 0 for s in SEVERITIES}
            for f in _findings(db, org_id, r["id"]):
                by[f["severity"]] = by.get(f["severity"], 0) + 1
            out.append({"audit_id": r["id"], "domain": r["domain"], "score": r["overall_score"], "status": r["status"], "at": r["created_at"], "by_severity": by})
    return out


def change(org_id: str, company_id: int) -> Optional[Dict[str, Any]]:
    """Latest completed check against the one before it. None until a site has been checked twice."""
    with get_db() as db:
        runs = db.execute("SELECT id, overall_score, created_at FROM audit_runs WHERE org_id = ? AND company_id = ? AND status = 'completed' ORDER BY id DESC LIMIT 2",
                          (org_id, company_id)).fetchall()
        if len(runs) < 2:
            return None
        latest, before = runs[0], runs[1]
        now = {f["check_id"]: f for f in _findings(db, org_id, latest["id"])}
        then = {f["check_id"]: f for f in _findings(db, org_id, before["id"])}
    pick = lambda d: [{"check_id": k, "severity": v["severity"], "finding": v["finding"], "category": v["category"]} for k, v in d.items()]
    return {"latest_audit_id": latest["id"], "previous_audit_id": before["id"], "latest_at": latest["created_at"], "previous_at": before["created_at"],
            "score_before": before["overall_score"], "score_after": latest["overall_score"], "score_delta": (latest["overall_score"] or 0) - (before["overall_score"] or 0),
            "fixed": pick({k: v for k, v in then.items() if k not in now}), "new": pick({k: v for k, v in now.items() if k not in then}),
            "still_open": sum(1 for k in now if k in then)}


def teardown(org_id: str, company_id: int) -> Optional[Dict[str, str]]:
    """A written teardown from the latest completed audit, or None if the site has not been examined yet."""
    with get_db() as db:
        company = db.execute("SELECT name, domain FROM companies WHERE id = ? AND org_id = ?", (company_id, org_id)).fetchone()
        if not company:
            raise LookupError("Company not found")
        run = db.execute("SELECT id, domain, overall_score, created_at FROM audit_runs WHERE org_id = ? AND company_id = ? AND status = 'completed' ORDER BY id DESC LIMIT 1",
                         (org_id, company_id)).fetchone()
        findings = _findings(db, org_id, run["id"]) if run else []
    if not run:
        return None
    findings.sort(key=lambda f: SEVERITIES.index(f["severity"]) if f["severity"] in SEVERITIES else 9)
    notable = [f for f in findings if f["severity"] != "info"]
    advice = advisor.recommendations(company_id, org_id)["recommendations"]
    delta = change(org_id, company_id)
    date = datetime.now(timezone.utc).strftime("%d %B %Y")

    lines = [f"# Website teardown: {company['name']}", "", f"Site: {run['domain']}  ", f"Checked: {run['created_at']} (report written {date})  ", f"Health score: {run['overall_score']}/100", "",
             "This report lists only what the checks measured on the public site. It does not test anything intrusively, and a check that could not run is not counted as a pass.", ""]
    if delta:
        lines += ["## Since the last check", f"Score {delta['score_before']} to {delta['score_after']} ({delta['score_delta']:+d}). Fixed: {len(delta['fixed'])}. New: {len(delta['new'])}. Still open: {delta['still_open']}.", ""]
    lines += [f"## Findings ({len(notable)})", ""]
    if not notable:
        lines.append("Nothing above informational level was found.")
    for i, f in enumerate(notable, 1):
        lines += [f"### {i}. [{f['severity'].upper()}] {f['finding']}", f"- Why it matters: {f['estimated_impact'] or 'not stated'}", f"- Fix: {f['fix'] or 'not stated'}", f"- Category: {f['category']} (evidence #{f['evidence_id']})", ""]
    if advice:
        lines += ["## Suggested services", ""]
        for a in advice:
            price = f" Price band: {a['price_band']}." if a.get("price_band") else ""
            lines.append(f"- {a['service']} ({a['priority']} priority): {a['summary']}.{price}")
        lines.append("")
    lines += ["## Not measured", "Revenue impact, real-user speed, and anything behind a login. Say so plainly if the client asks.", ""]
    safe = "".join(c if c.isalnum() else "_" for c in company["name"]).strip("_") or "client"
    return {"markdown": "\n".join(lines), "filename": f"Teardown_{safe}.md"}
