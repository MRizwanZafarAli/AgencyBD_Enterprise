"""
Nightly re-scan of saved clients: tell a person when something changed that gives a specific, checkable reason to get in touch:
a NEW vulnerability record matching software the site runs, a certificate that is now invalid or close to expiry, HTTPS that is
gone, or a site that has been unreachable on two checks in a row (one failed fetch is never reported as an outage).

For each tracked lead whose company has been audited before, the site is audited again. CVE findings that were not in the previous
run open a `new_cve` work item (deduplicated per lead and CVE), which gives you a legitimate, specific reason to get in touch. A
first-ever audit is a baseline and raises nothing. Sites that cannot be reached are skipped, not flagged.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from auditors.engine import WebsiteDoctorEngine
from core import metrics
from database.db import get_db
from database.models import AuditRunRepository
from net.fetcher import SSRFSecurityError
from workflows.inbox import WorkItemRepository

logger = logging.getLogger("AgencyBD.rescan")
JOB = "rescan"
EVERY_HOURS = 24
MAX_SITES_PER_RUN = 40
POLITE_DELAY_SECONDS = 2.0
OUTAGE_AFTER_MISSES = 2
SITE_CHECKS = {            # check id -> priority; each is reported once, when it first appears
    "tls_certificate_invalid": 85,
    "no_https": 80,
    "tls_certificate_expiring": 75,
}


def _misses(org_id: str, lead_id: int, reset: bool = False, add: bool = False) -> int:
    """Consecutive unreachable checks for one lead, kept in job_runs (job 'down:<lead>')."""
    job = f"down:{lead_id}"
    with get_db() as db:
        if reset:
            db.execute("DELETE FROM job_runs WHERE job = ? AND org_id = ?", (job, org_id))
            db.commit()
            return 0
        row = db.execute("SELECT detail FROM job_runs WHERE job = ? AND org_id = ?", (job, org_id)).fetchone()
        n = int(row["detail"]) if row and row["detail"] else 0
        if add:
            n += 1
            db.execute("INSERT INTO job_runs (job, org_id, last_run_at, detail) VALUES (?, ?, CURRENT_TIMESTAMP, ?) "
                       "ON CONFLICT(job, org_id) DO UPDATE SET last_run_at = CURRENT_TIMESTAMP, detail = excluded.detail", (job, org_id, str(n)))
            db.commit()
        return n


def _cve_ids(audit_id: int, org_id: str) -> Dict[str, Dict[str, Any]]:
    return {f["check_id"]: f for f in AuditRunRepository.get_findings(audit_id, org_id=org_id) if f["check_id"].startswith("cve_")}


def rescan_org(org_id: str, limit: int = MAX_SITES_PER_RUN, delay: float = POLITE_DELAY_SECONDS) -> Dict[str, Any]:
    with get_db() as db:
        rows = [dict(r) for r in db.execute("""
            SELECT l.id AS lead_id, l.company_name, l.domain, c.id AS company_id
            FROM leads l JOIN companies c ON c.org_id = l.org_id AND LOWER(c.domain) = LOWER(l.domain)
            WHERE l.org_id = ? AND l.status NOT IN ('lost', 'won') AND l.domain NOT LIKE '%.invalid'
            ORDER BY l.id DESC LIMIT ?""", (org_id, limit)).fetchall()]
    scanned, alerts, skipped = 0, [], []
    for row in rows:
        previous = AuditRunRepository.latest_for_company(row["company_id"], org_id)
        if not previous or previous["status"] != "completed":
            skipped.append({"domain": row["domain"], "reason": "no completed baseline audit"})
            continue
        before = set(_cve_ids(previous["id"], org_id))
        before_all = {f["check_id"] for f in AuditRunRepository.get_findings(previous["id"], org_id=org_id)}
        try:
            res = WebsiteDoctorEngine.run_audit(row["domain"], company_id=row["company_id"], org_id=org_id)
        except SSRFSecurityError:
            skipped.append({"domain": row["domain"], "reason": "blocked target"})
            continue
        scanned += 1
        if res["status"] == "unreachable" and _misses(org_id, row["lead_id"], add=True) >= OUTAGE_AFTER_MISSES:
            item = WorkItemRepository.add(
                org_id, "site_change", f"{row['company_name']}: the website has not loaded on {OUTAGE_AFTER_MISSES} checks in a row",
                f"{row['domain']} could not be reached on the last {OUTAGE_AFTER_MISSES} nightly checks. Open it yourself first: if it is really down, that is the most useful thing you can tell them today.",
                "lead", row["lead_id"], 88, f"down:{row['lead_id']}")
            if item["created"]:
                alerts.append({"lead_id": row["lead_id"], "company": row["company_name"], "kind": "site_change", "what": "the website is down", "work_item": item["id"]})
        if res["status"] != "completed":
            skipped.append({"domain": row["domain"], "reason": "refuses automated access this time" if res["status"] == "blocked" else "unreachable this time"})
            continue
        _misses(org_id, row["lead_id"], reset=True)
        for f in res["findings"]:
            if f["check_id"] in SITE_CHECKS and f["check_id"] not in before_all:
                item = WorkItemRepository.add(
                    org_id, "site_change", f"{row['company_name']}: {f['finding']}",
                    f"Seen in tonight's re-check and not in the one before. {f.get('estimated_impact') or ''} Confirm it yourself before you write.".strip(),
                    "lead", row["lead_id"], SITE_CHECKS[f["check_id"]], f"site:{row['lead_id']}:{f['check_id']}")
                if item["created"]:
                    alerts.append({"lead_id": row["lead_id"], "company": row["company_name"], "kind": "site_change", "what": f["finding"], "work_item": item["id"]})
            if f["check_id"].startswith("cve_") and f["check_id"] not in before:
                cve = f["check_id"].replace("cve_", "").upper()
                kev = "exploited in the wild" in f["estimated_impact"].lower()
                item = WorkItemRepository.add(
                    org_id, "new_cve", f"New vulnerability match for {row['company_name']}: {cve}",
                    f"{f['finding']} {f['estimated_impact']} This is a reason to get in touch; confirm the real patch level first.",
                    "lead", row["lead_id"], 90 if kev else 70, f"cve:{row['lead_id']}:{cve}")
                if item["created"]:
                    metrics.RESCAN_ALERTS.labels(str(kev).lower()).inc()
                    alerts.append({"lead_id": row["lead_id"], "company": row["company_name"], "kind": "cve", "cve": cve, "kev": kev, "work_item": item["id"]})
        time.sleep(delay)
    return {"org_id": org_id, "scanned": scanned, "alerts": alerts, "skipped": skipped}


def run_if_due(now: Optional[float] = None, every_hours: int = EVERY_HOURS, **kw) -> Optional[List[Dict[str, Any]]]:
    """Runs the re-scan for every tenant at most once per `every_hours`. Returns None when it was not due."""
    now = now or time.time()
    with get_db() as db:
        row = db.execute("SELECT strftime('%s', last_run_at) AS ts FROM job_runs WHERE job = ? AND org_id = '*'", (JOB,)).fetchone()
        if row and row["ts"] and now - int(row["ts"]) < every_hours * 3600:
            return None
        db.execute("INSERT INTO job_runs (job, org_id, last_run_at) VALUES (?, '*', CURRENT_TIMESTAMP) "
                   "ON CONFLICT(job, org_id) DO UPDATE SET last_run_at = CURRENT_TIMESTAMP", (JOB,))
        db.commit()
        orgs = [r["org_id"] for r in db.execute("SELECT DISTINCT org_id FROM leads").fetchall()]
    results = [rescan_org(org, **kw) for org in orgs]
    for r in results:
        if r["alerts"]:
            _notify(r)
    return results


def _notify(result: Dict[str, Any]) -> None:
    """Best-effort Slack message and phone message; silently skipped when nothing is set up."""
    from config.honesty import NotConfiguredError
    from workflows.digest import send_to_slack
    lines = [f"• {a['company']}: {a['cve']}{' (exploited in the wild)' if a['kev'] else ''}" if a.get("kind", "cve") == "cve" else f"• {a['company']}: {a['what']}"
             for a in result["alerts"][:10]]
    text = f"*Changes worth a message ({result['org_id']})*\n" + "\n".join(lines)
    try:
        send_to_slack(text)
    except NotConfiguredError:
        pass
    except Exception:
        logger.exception("rescan notification failed")
    try:
        from alertdesk import engine as desk
        desk.tell(result["org_id"], f"{len(result['alerts'])} saved client(s) changed overnight:\n" + "\n".join(lines[:5]), "Client sites")
    except Exception:
        logger.exception("rescan phone notification failed")
