"""
Match fingerprinted software to known vulnerabilities, and say honestly what that does and does not prove.

"Potentially affected" means: the version this site advertises appears in the public vulnerability record. It does not prove the
site is vulnerable (distributions backport fixes without changing the version string; headers can be hidden or spoofed). Only
CVEs that are on the CISA exploited list or score CVSS >= 7.0 are reported, ranked by exploitation first, then score.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from intel.vuln import sources
from intel.vuln.fingerprint import PRODUCTS, Tech

MIN_CVSS = 7.0
MAX_PER_PRODUCT = 3


@dataclass
class VulnMatch:
    cve_id: str
    summary: str
    cvss: Optional[float]
    kev: bool
    product: str
    version: str
    signal: str
    confidence: float
    backport_risk: bool
    url: str
    published: str

    def severity(self) -> str:
        """Never 'critical': a version match alone cannot confirm exposure."""
        if self.kev or (self.cvss or 0) >= 9.0:
            level = "high"
        elif (self.cvss or 0) >= MIN_CVSS:
            level = "medium"
        else:
            level = "low"
        return {"high": "medium", "medium": "low"}.get(level, level) if self.confidence < 0.5 else level

    def as_dict(self) -> Dict[str, Any]:
        return {"cve_id": self.cve_id, "summary": self.summary, "cvss": self.cvss, "kev": self.kev, "product": self.product,
                "version": self.version, "signal": self.signal, "confidence": self.confidence, "severity": self.severity(),
                "backport_risk": self.backport_risk, "url": self.url, "published": self.published}


def match(techs: List[Tech]) -> Dict[str, Any]:
    """Returns {"matches": [...], "unchecked": [labels we could not look up]}; `unchecked` keeps unknown separate from clean."""
    kev = sources.kev_ids()
    matches: List[VulnMatch] = []
    unchecked: List[str] = []
    for t in techs:
        spec = PRODUCTS[t.product]
        found: Optional[List[Dict[str, Any]]] = None
        if "cpe" in spec:
            parts = [sources.nvd_cves(v, p, t.version) for v, p in spec["cpe"]]
            if any(p is not None for p in parts):
                found = [c for p in parts if p for c in p]
        elif "osv" in spec:
            found = sources.osv_vulns(spec["osv"][0], spec["osv"][1], t.version)
        if found is None:
            unchecked.append(f"{t.label} {t.version}")
            continue
        seen, rows = set(), []
        for c in found:
            if c["cve_id"] in seen:
                continue
            seen.add(c["cve_id"])
            is_kev = bool(kev and c["cve_id"] in kev)
            if is_kev or (c["cvss"] or 0) >= MIN_CVSS:
                rows.append((is_kev, c["cvss"] or 0, c))
        for is_kev, _, c in sorted(rows, key=lambda r: (r[0], r[1]), reverse=True)[:MAX_PER_PRODUCT]:
            matches.append(VulnMatch(c["cve_id"], c["summary"], c["cvss"], is_kev, t.label, t.version, t.signal, t.confidence,
                                     t.backport_risk, c["url"], c["published"]))
    if kev is None and techs:
        unchecked.append("CISA exploited-vulnerability list (could not load)")
    return {"matches": matches, "unchecked": unchecked}
