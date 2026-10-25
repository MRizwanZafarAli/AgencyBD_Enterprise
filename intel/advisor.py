"""
Business Advisor: what should this client do, and which of YOUR services addresses it?

recommendations()   deterministic. Groups the latest audit's findings by the service that fixes them, ranks by severity, and
                    cites the evidence ids. Works with no AI key.
advise()            optional. A language model turns those same findings into 3-5 plain-language recommendations. Each one must
                    cite evidence ids that exist for this company and name a service from your catalog; anything else is dropped.
"""

from typing import Any, Dict, List

from config.honesty import PreconditionFailedError
from database.models import AuditRunRepository, CompanyRepository
from intel.services import KNOWN_SERVICE_KEYS, ServiceCatalog
from llm.client import LLMGateway

POINTS = {"critical": 12, "high": 8, "medium": 4, "low": 1, "info": 0}


def _latest_findings(company_id: int, org_id: str):
    audit = AuditRunRepository.latest_for_company(company_id, org_id)
    if not audit or audit["status"] != "completed":
        raise PreconditionFailedError("audit_required", "Audit this company first (Clients > Run audit); advice is built only from measured findings.")
    return audit, [f for f in AuditRunRepository.get_findings(audit["id"], org_id=org_id) if f["severity"] != "info" and f.get("evidence_id")]


def recommendations(company_id: int, org_id: str) -> Dict[str, Any]:
    audit, findings = _latest_findings(company_id, org_id)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for f in findings:
        groups.setdefault(f.get("service_id") or "other", []).append(f)
    out = []
    for key, items in groups.items():
        items.sort(key=lambda f: -POINTS.get(f["severity"], 0))
        score = sum(POINTS.get(f["severity"], 0) for f in items)
        svc = ServiceCatalog.get(org_id, key)
        out.append({"service_key": key, "service": ServiceCatalog.label(key), "offer": svc["offer"] if svc else None,
                    "price_band": svc["price_band"] if svc else None, "priority": "high" if score >= 15 else "medium" if score >= 6 else "low",
                    "score": score, "summary": f"{len(items)} finding(s); most important: {items[0]['finding'].rstrip('.')}",
                    "findings": [{"finding": f["finding"], "severity": f["severity"], "fix": f["fix"], "evidence_id": f["evidence_id"]} for f in items[:6]],
                    "evidence_ids": [f["evidence_id"] for f in items]})
    out.sort(key=lambda r: -r["score"])
    return {"audit_id": audit["id"], "audited_at": audit["created_at"], "recommendations": out,
            "note": "Built only from stored audit findings. Prices appear only where you set a price band in Settings > Services."}


ADVISOR_SYSTEM = (
    "You advise a software agency on what to recommend to a prospective client. Use ONLY the findings listed. Give 3 to 5 "
    "recommendations in plain language for a non-technical owner. Each recommendation must list the evidence ids it rests on "
    "and one service_key from the allowed list. Never invent numbers, revenue effects, competitors or facts about the business."
)


def advise(company_id: int, org_id: str) -> Dict[str, Any]:
    base = recommendations(company_id, org_id)
    company = CompanyRepository.get_by_id(company_id, org_id)
    allowed = sorted(set(KNOWN_SERVICE_KEYS) | {s["service_key"] for s in ServiceCatalog.list(org_id)})
    valid_ids = {i for r in base["recommendations"] for i in r["evidence_ids"]}
    lines = "\n".join(f"[{f['evidence_id']}] ({f['severity']}) {f['finding']} | fix: {f['fix']}" for r in base["recommendations"] for f in r["findings"])
    prompt = (f"Company: {(company or {}).get('name', 'the prospect')}\nAllowed service_key values: {', '.join(allowed)}\nFINDINGS:\n{lines}\n\n"
              'Return JSON: {"recommendations": [{"title": str, "why_it_matters": str, "evidence_ids": [int], "service_key": str}]}')
    out = LLMGateway.complete_json(prompt, system=ADVISOR_SYSTEM, agent_name="BusinessAdvisor", org_id=org_id, max_tokens=900)
    kept, dropped = [], 0
    for r in out["data"].get("recommendations") or []:
        ids = [i for i in r.get("evidence_ids", []) if i in valid_ids]
        if ids and r.get("service_key") in allowed and str(r.get("title", "")).strip() and str(r.get("why_it_matters", "")).strip():
            kept.append({"title": str(r["title"]).strip(), "why_it_matters": str(r["why_it_matters"]).strip(), "evidence_ids": ids,
                         "service_key": r["service_key"], "service": ServiceCatalog.label(r["service_key"])})
        else:
            dropped += 1
    return {**base, "ai_recommendations": kept, "ai_dropped": dropped, "model": out.get("model"),
            "ai_note": "Each AI recommendation cites evidence ids from this company's audit; uncited or off-catalog items were removed."}
