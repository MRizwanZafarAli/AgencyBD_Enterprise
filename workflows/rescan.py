"""
Nightly re-scan of saved clients: when a NEW vulnerability record starts matching software a prospect runs, tell a person.

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
        try:
            res = WebsiteDoctorEngine.run_audit(row["domain"], company_id=row["company_id"], org_id=org_id)
        except SSRFSecurityError:
            skipped.append({"domain": row["domain"], "reason": "blocked target"})
            continue
        scanned += 1
        if res["status"] != "completed":
            skipped.append({"domain": row["domain"], "reason": "refuses automated access this time" if res["status"] == "blocked" else "unreachable this time"})
            continue
        for f in res["findings"]:
            if f["check_id"].startswith("cve_") and f["check_id"] not in before:
                cve = f["check_id"].replace("cve_", "").upper()
                kev = "exploited in the wild" in f["estimated_impact"].lower()
                item = WorkItemRepository.add(
                    org_id, "new_cve", f"New vulnerability match for {row['company_name']}: {cve}",
                    f"{f['finding']} {f['estimated_impact']} This is a reason to get in touch; confirm the real patch level first.",
                    "lead", row["lead_id"], 90 if kev else 70, f"cve:{row['lead_id']}:{cve}")
                if item["created"]:
                    metrics.RESCAN_ALERTS.labels(str(kev).lower()).inc()
                    alerts.append({"lead_id": row["lead_id"], "company": row["company_name"], "cve": cve, "kev": kev, "work_item": item["id"]})
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
    """Best-effort Slack message; silently skipped when no webhook is configured."""
    from config.honesty import NotConfiguredError
    from workflows.digest import send_to_slack
    text = f"*New vulnerability matches ({result['org_id']})*\n" + "\n".join(
        f"• {a['company']}: {a['cve']}{' (exploited in the wild)' if a['kev'] else ''}" for a in result["alerts"][:10])
    try:
        send_to_slack(text)
    except NotConfiguredError:
        pass
    except Exception:
        logger.exception("rescan notification failed")
