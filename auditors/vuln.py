"""Vulnerability Watch auditor: software versions this site reveals, matched against public vulnerability records."""

from typing import List

from auditors.base import AuditFinding
from auditors.context import SiteContext
from intel.vuln.fingerprint import fingerprint
from intel.vuln.matcher import match


class VulnAuditor:
    @staticmethod
    def audit(ctx: SiteContext) -> List[AuditFinding]:
        techs = fingerprint(ctx.headers, ctx.html)
        if not techs:
            return []
        result = match(techs)
        findings: List[AuditFinding] = []
        for m in result["matches"]:
            note = " Distribution builds often backport fixes, so the real exposure may be lower." if m.backport_risk else ""
            findings.append(AuditFinding(
                category="security", check_id=f"cve_{m.cve_id.lower()}", severity=m.severity(),
                finding=f"{m.product} {m.version} (seen in {m.signal}) is listed as affected by {m.cve_id}: {m.summary[:140].rstrip('.')}.",
                fix="Confirm the real patch level, then update to the latest supported release or confirm the fix was backported by your host." + note,
                estimated_impact=("Listed by CISA as exploited in the wild. " if m.kev else "") +
                                 (f"CVSS {m.cvss}. " if m.cvss else "") + "Potentially affected, based on the visible version only.",
                service_id="security_hardening",
                evidence_value=f"{m.signal} | {m.cve_id} ({m.url}) | published {m.published}", confidence=m.confidence))
        for label in result["unchecked"]:
            findings.append(AuditFinding("security", "vuln_lookup_unavailable", "info",
                                         f"Could not check {label} against vulnerability databases.", "Re-run later.",
                                         "Unknown; this is not a clean result.", "security_hardening", "lookup failed", 0.3))
        return findings
