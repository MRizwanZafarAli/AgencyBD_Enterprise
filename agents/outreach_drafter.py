"""
Drafts a first-touch email from MEASURED findings only.

Every sentence about the prospect comes from a stored audit finding (with its measured value). If there are no findings of at
least medium severity there is nothing true and specific to say, so no draft is produced. The agency's own claims come only
from the identity you configured; nothing about past results is stated unless you set AGENCYBD_CASE_STUDY.
"""

import re
from typing import Any, Dict, List, Optional

from config.settings import settings

MAX_FINDINGS = 3
USABLE = ("critical", "high", "medium")


def _bullet(f: Dict[str, Any]) -> str:
    """Vulnerability findings are phrased as hedged observations; the public record text is not copied into outreach."""
    cve = re.search(r"CVE-\d{4}-\d+", str(f.get("measured", "")))
    product = re.match(r"^(.+?) \(seen in", f["finding"])
    if cve and product:
        return (f"- Your site appears to run {product.group(1)}, which is listed in public vulnerability records ({cve.group(0)}). "
                "It may already be patched by your host; worth confirming the patch level.")
    return f"- {f['finding'].rstrip('.')}. ({str(f['measured'])[:140]})"


def draft_from_brief(brief: Dict[str, Any], contact_first_name: str, domain: str) -> Optional[Dict[str, Any]]:
    health = brief.get("digital_health") or {}
    findings: List[Dict[str, Any]] = [f for f in health.get("top_findings", []) if f.get("severity") in USABLE and f.get("measured")][:MAX_FINDINGS]
    if not findings:
        return None
    agency = settings.agency
    lines = [f"Hi {contact_first_name},", "",
             f"I ran a public, non-intrusive check of {domain} and noticed {'a few things' if len(findings) > 1 else 'something'} worth a look:", ""]
    for f in findings:
        lines.append(_bullet(f))
    lines += ["", "Each of these is quick to fix. " + (f"{agency.case_study_metric}. " if agency.case_study_metric else "")
              + "Happy to send the full list, no obligation."]
    if agency.booking_link:
        lines += ["", f"If it is easier to talk, here is my calendar: {agency.booking_link}"]
    lines += ["", f"{agency.founder_name}", agency.name]
    return {"subject": f"{domain}: {findings[0]['finding'].rstrip('.')[:70]}", "body": "\n".join(lines),
            "evidence_ids": sorted({i for f in findings for i in f.get("evidence_ids", [])})}
