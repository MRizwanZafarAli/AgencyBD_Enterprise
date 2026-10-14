"""
Company Briefing Engine.

A one-screen brief a non-expert can use on a call. Every statement is built from stored evidence (a measurement or a
quote with its source URL and timestamp). Statements without evidence are dropped, not softened. Anything we could not
establish is reported as unknown. Prices come only from the agency's own service catalog.

* ``generate_brief(..., refresh=True)`` fetches the homepage, runs the Website Doctor and stores new evidence.
* ``generate_brief(..., refresh=False)`` is read-only and uses what is already stored.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.db import get_db
from database.models import AuditRunRepository, CompanyRepository, EvidenceRepository
from intel.services import ServiceCatalog
from intel.site_profile import extract_profile
from net.fetcher import SafeFetcher

SEVERITY_WEIGHT = {"critical": 5, "high": 3, "medium": 2, "low": 1, "info": 0}


def _record(org_id: str, company_id: int, claim: str, value: str, method: str, url: str, confidence: float = 1.0) -> int:
    return EvidenceRepository.record_evidence(entity_type="company", entity_id=company_id, claim=claim, value=value,
                                              method=method, source_url=url, confidence=confidence, org_id=org_id)["id"]


def _latest(evidence: List[Dict[str, Any]], method: str) -> Optional[Dict[str, Any]]:
    rows = [e for e in evidence if e["method"] == method]
    return rows[-1] if rows else None


def _store_profile(org_id: str, company_id: int, domain: str) -> Optional[str]:
    """Fetches the homepage and stores each extracted fact as evidence. Returns an error string or None."""
    try:
        res = SafeFetcher.safe_fetch(f"https://{domain}", timeout=10)
    except Exception as exc:
        return str(exc)[:160]
    p = extract_profile(res.text, res.final_url)
    url = res.final_url
    if p["is_parked"]:
        _record(org_id, company_id, f"{domain} looks parked or nearly empty", f"words={p['word_count']}", "profile.parked", url)
        return None
    description = p["org_jsonld"].get("description") or p["meta_description"] or p["og_description"]
    if description:
        _record(org_id, company_id, f"{domain} describes itself as: \"{description[:240]}\"", description[:500], "profile.description", url)
    elif p["h1"]:
        _record(org_id, company_id, f"The main headline on {domain} reads: \"{p['h1'][0][:160]}\"", p["h1"][0], "profile.headline", url)
    if p["copyright_holder"]:
        _record(org_id, company_id, f"The site footer credits '{p['copyright_holder'][:80]}'", p["copyright_holder"], "profile.copyright", url)
    if p["org_jsonld"]:
        _record(org_id, company_id, "The site publishes structured business data (schema.org)",
                str(p["org_jsonld"])[:500], "profile.structured_data", url)
    if p["social_profiles"]:
        _record(org_id, company_id, f"The site links to {len(p['social_profiles'])} social profile(s)", ", ".join(p["social_profiles"])[:500], "profile.social", url)
    try:
        from engines.native_tech_stack_fingerprinter import detect_technologies
        tech = detect_technologies(res.text, {k.lower(): v.lower() for k, v in res.headers.items()})
    except Exception:
        tech = []
    if tech:
        _record(org_id, company_id, f"Detected technologies: {', '.join(tech)}", ", ".join(tech), "profile.stack", url, confidence=0.8)
    return None


class CompanyBriefEngine:
    @classmethod
    def generate_brief(cls, company_id: int, org_id: str, refresh: bool = False) -> Dict[str, Any]:
        company = CompanyRepository.get_by_id(company_id, org_id=org_id)
        if not company:
            raise LookupError("Company not found")
        domain = company.get("domain")
        base = {"company_id": company_id, "company_name": company["name"], "domain": domain,
                "generated_at": datetime.now(timezone.utc).isoformat(), "refreshed": False}

        if not domain:
            return {**base, "status": "no_domain", "what_they_do": None, "digital_health": None, "tech_stack": None,
                    "signals": cls._signals(company["name"], org_id), "pitch_kit": None, "evidence_count": 0, "evidence": [],
                    "next_steps": ["No verified website. Resolve the company with a domain, or use Presence Rescue to check whether the business has any web presence."]}

        fetch_error = None
        audit = AuditRunRepository.latest_for_company(company_id, org_id)
        if refresh:
            fetch_error = _store_profile(org_id, company_id, domain)
            from auditors.engine import WebsiteDoctorEngine
            WebsiteDoctorEngine.run_audit(domain, company_id=company_id, org_id=org_id)
            audit = AuditRunRepository.latest_for_company(company_id, org_id)
            base["refreshed"] = True

        evidence = EvidenceRepository.get_for_entity("company", company_id, org_id=org_id)
        if not audit and not any(e["method"].startswith("profile.") for e in evidence):
            return {**base, "status": "needs_refresh", "what_they_do": None, "digital_health": None, "tech_stack": None,
                    "signals": cls._signals(company["name"], org_id), "pitch_kit": None, "evidence_count": 0, "evidence": [],
                    "next_steps": ["Nothing has been collected for this company yet. Run the brief with refresh to fetch and audit the site."]}

        sections: Dict[str, Any] = {}
        desc = _latest(evidence, "profile.description") or _latest(evidence, "profile.headline")
        sections["what_they_do"] = {"text": desc["claim"], "evidence_ids": [desc["id"]]} if desc else None
        stack = _latest(evidence, "profile.stack")
        sections["tech_stack"] = {"technologies": [t.strip() for t in stack["value"].split(",")], "evidence_ids": [stack["id"]]} if stack else None

        health, kit = cls._health_and_pitch(audit, org_id)
        sections["digital_health"], sections["pitch_kit"] = health, kit
        sections["social_presence"] = ({"text": _latest(evidence, "profile.social")["claim"], "profiles": _latest(evidence, "profile.social")["value"].split(", "),
                                        "evidence_ids": [_latest(evidence, "profile.social")["id"]]} if _latest(evidence, "profile.social") else None)
        sections["identity"] = ({"text": _latest(evidence, "profile.copyright")["claim"], "evidence_ids": [_latest(evidence, "profile.copyright")["id"]]}
                                if _latest(evidence, "profile.copyright") else None)

        out = {**base, "status": "unreachable" if (audit and audit["status"] == "unreachable") else "ok", **sections,
               "signals": cls._signals(company["name"], org_id)}
        if fetch_error:
            out["fetch_error"] = fetch_error
        out = cls.enforce_grounding(out)
        used = cls._collect_evidence_ids(out)
        out["evidence"] = list(EvidenceRepository.get_by_ids(sorted(used), org_id).values())
        out["evidence_count"] = len(out["evidence"])
        out["unknown"] = [label for label, key in (("What the company does", "what_they_do"), ("Technology stack", "tech_stack"),
                                                   ("Company size and revenue", None), ("Funding", None), ("Decision makers", None))
                          if key is None or not out.get(key)]
        return out

    # ------------------------------------------------------------------ pieces

    @staticmethod
    def _health_and_pitch(audit: Optional[Dict[str, Any]], org_id: str):
        if not audit:
            return None, None
        findings = AuditRunRepository.get_findings(audit["id"], org_id=org_id)
        findings.sort(key=lambda f: SEVERITY_WEIGHT.get(f["severity"], 0), reverse=True)
        ev = EvidenceRepository.get_by_ids([f["evidence_id"] for f in findings if f.get("evidence_id")], org_id)
        counts: Dict[str, int] = {}
        for f in findings:
            counts[f["category"]] = counts.get(f["category"], 0) + 1
        top = [{"finding": f["finding"], "severity": f["severity"], "category": f["category"], "service": f["service_id"],
                "fix": f["fix"], "measured": (ev.get(f["evidence_id"]) or {}).get("value"), "evidence_ids": [f["evidence_id"]]}
               for f in findings[:5] if f.get("evidence_id")]
        health = {"score": audit["overall_score"], "status": audit["status"], "audit_id": audit["id"], "audited_at": audit["created_at"],
                  "findings_total": len(findings), "findings_by_category": counts, "top_findings": top}
        if audit["status"] == "unreachable":
            return health, None

        weights: Dict[str, int] = {}
        for f in findings:
            if f["service_id"]:
                weights[f["service_id"]] = weights.get(f["service_id"], 0) + SEVERITY_WEIGHT.get(f["severity"], 0)
        best = max(weights, key=weights.get) if weights and max(weights.values()) > 0 else None
        service = ServiceCatalog.get(org_id, best) if best else None
        talking = [{"text": f"{t['finding']} (measured: {t['measured']})", "evidence_ids": t["evidence_ids"]} for t in top[:3]]
        kit = {
            "recommended_service": {"key": best, "label": ServiceCatalog.label(best), "offer": service["offer"] if service else None} if best else None,
            "angle": ({"text": f"Lead with {ServiceCatalog.label(best).lower()}: {weights[best]} severity points across the audit, most serious: {top[0]['finding']}",
                       "evidence_ids": top[0]["evidence_ids"]} if best and top else None),
            "talking_points": talking,
            "price_band": service["price_band"] if service and service.get("price_band") else None,
            "price_band_note": None if (service and service.get("price_band")) else "No price band set for this service. Add one under Services.",
            "objections_to_prepare_for": {"generic": True, "items": (service or {}).get("objections") or
                                          ["They already have an in-house team.", "No budget this quarter.", "Send me something by email."]},
        }
        return health, kit

    @staticmethod
    def _signals(company_name: str, org_id: str) -> List[Dict[str, Any]]:
        """Radar items that name the company (e.g. it posted a job or project). Real ingested rows only."""
        with get_db() as db:
            rows = db.execute("SELECT id, source, title, posted_at, created_at FROM opportunities WHERE org_id = ? "
                              "AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ?) ORDER BY id DESC LIMIT 5",
                              (org_id, f"%{company_name.lower()}%", f"%{company_name.lower()}%")).fetchall()
        return [{"text": f"Radar item from {r['source']}: {r['title']}", "source": r["source"], "opportunity_id": r["id"],
                 "seen_at": r["created_at"]} for r in rows]

    @staticmethod
    def enforce_grounding(brief: Dict[str, Any]) -> Dict[str, Any]:
        """Removes any statement that does not point at stored evidence."""
        def grounded(item) -> bool:
            return bool(item) and bool(item.get("evidence_ids"))
        for key in ("what_they_do", "identity", "social_presence", "tech_stack"):
            if not grounded(brief.get(key)):
                brief[key] = None
        health = brief.get("digital_health")
        if health:
            health["top_findings"] = [t for t in health["top_findings"] if grounded(t)]
        kit = brief.get("pitch_kit")
        if kit:
            kit["talking_points"] = [t for t in kit["talking_points"] if grounded(t)]
            if kit.get("angle") and not grounded(kit["angle"]):
                kit["angle"] = None
        return brief

    @staticmethod
    def _collect_evidence_ids(brief: Dict[str, Any]) -> set:
        ids: set = set()

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == "evidence_ids" and isinstance(v, list):
                        ids.update(i for i in v if isinstance(i, int))
                    else:
                        walk(v)
            elif isinstance(node, list):
                for x in node:
                    walk(x)
        walk(brief)
        return ids
