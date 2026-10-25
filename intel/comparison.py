"""
Side-by-side comparison of two sites using the same real audits (Website Doctor) for both.

Only measured differences are reported: issues one site has and the other does not, with the evidence value for each.
There is no estimated revenue, and no performance number unless PageSpeed measured it (PAGESPEED_API_KEY).
"""

from typing import Any, Dict, List

from auditors.engine import WebsiteDoctorEngine, SEVERITY_DEDUCTION

CATEGORIES = ("performance", "security", "seo", "geo", "a11y", "dns")
SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _category_scores(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    return {c: max(15, 100 - sum(SEVERITY_DEDUCTION.get(f["severity"], 0) for f in findings if f["category"] == c)) for c in CATEGORIES}


def compare_domains(target: str, competitor: str, org_id: str) -> Dict[str, Any]:
    a = WebsiteDoctorEngine.run_audit(target, org_id=org_id)
    b = WebsiteDoctorEngine.run_audit(competitor, org_id=org_id)
    out: Dict[str, Any] = {"target": {"domain": a["domain"], "audit_id": a["audit_id"], "status": a["status"], "overall_score": a["overall_score"]},
                           "competitor": {"domain": b["domain"], "audit_id": b["audit_id"], "status": b["status"], "overall_score": b["overall_score"]}}
    if a["status"] != "completed" or b["status"] != "completed":
        down = [x["domain"] for x in (a, b) if x["status"] == "unreachable"]
        blocked = [x["domain"] for x in (a, b) if x["status"] == "blocked"]
        why = " and ".join(filter(None, [f"could not reach {', '.join(down)} from our servers" if down else "", f"{', '.join(blocked)} refuses automated access" if blocked else ""]))
        out.update(comparable=False, note=f"No comparison was made: {why}.",
                   target_only_issues=[], competitor_only_issues=[], category_scores=None, hook=None)
        return out

    ids_a = {f["check_id"]: f for f in a["findings"]}
    ids_b = {f["check_id"]: f for f in b["findings"]}

    def pick(src: Dict[str, Any], other: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = [{"check_id": k, "category": f["category"], "severity": f["severity"], "finding": f["finding"], "fix": f["fix"],
                 "measured": f["evidence_value"], "evidence_id": f.get("evidence_id")} for k, f in src.items()
                if k not in other and f["severity"] in ("critical", "high", "medium", "low")]
        return sorted(rows, key=lambda r: -SEVERITY_ORDER[r["severity"]])

    target_only, competitor_only = pick(ids_a, ids_b), pick(ids_b, ids_a)
    out.update(comparable=True, target_only_issues=target_only, competitor_only_issues=competitor_only,
               category_scores={"target": _category_scores(a["findings"]), "competitor": _category_scores(b["findings"])},
               checks_skipped=sorted(set(a["checks_skipped"]) | set(b["checks_skipped"])), note=None)
    top = next((r for r in target_only if r["severity"] in ("critical", "high", "medium")), None)
    out["hook"] = (f"{b['domain']} does not have this issue and {a['domain']} does: {top['finding']} (measured: {top['measured']})." if top else None)
    return out
