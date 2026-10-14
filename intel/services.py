"""Service catalog: what the agency sells, with the agency's OWN price bands.

Price bands are never invented. If a service has no band configured, callers show "not set" and the brief says so."""

import json
from typing import Any, Dict, List, Optional

from database.db import get_db

# Keys emitted by the Website Doctor auditors (finding.service_id)
KNOWN_SERVICE_KEYS = {
    "performance_engineering": "Performance engineering",
    "seo_optimization": "SEO optimization",
    "security_hardening": "Security hardening",
    "a11y_compliance": "Accessibility compliance",
    "geo_ai_readiness": "AI-search readiness (GEO)",
    "mobile_optimization": "Mobile optimization",
    "devops_sre": "DevOps / SRE",
    "presence_rescue": "Digital presence build (site + Google profile)",
}


class ServiceCatalog:
    @staticmethod
    def upsert(org_id: str, service_key: str, name: str, offer: str, price_band: Optional[str] = None,
               objections: Optional[List[str]] = None) -> Dict[str, Any]:
        if not service_key.strip() or not name.strip() or not offer.strip():
            raise ValueError("service_key, name and offer are required.")
        with get_db() as db:
            row = db.execute("SELECT id FROM services WHERE org_id = ? AND service_key = ?", (org_id, service_key)).fetchone()
            if row:
                db.execute("UPDATE services SET name = ?, offer = ?, price_band = ?, objections_json = ? WHERE id = ?",
                           (name, offer, price_band, json.dumps(objections or []), row["id"]))
                sid = row["id"]
            else:
                sid = db.execute("INSERT INTO services (org_id, service_key, name, offer, price_band, objections_json) VALUES (?,?,?,?,?,?)",
                                 (org_id, service_key, name, offer, price_band, json.dumps(objections or []))).lastrowid
            db.commit()
        return ServiceCatalog.get(org_id, service_key)

    @staticmethod
    def get(org_id: str, service_key: str) -> Optional[Dict[str, Any]]:
        with get_db() as db:
            r = db.execute("SELECT * FROM services WHERE org_id = ? AND service_key = ?", (org_id, service_key)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["objections"] = json.loads(d.pop("objections_json", None) or "[]")
        return d

    @staticmethod
    def list(org_id: str) -> List[Dict[str, Any]]:
        with get_db() as db:
            rows = db.execute("SELECT service_key FROM services WHERE org_id = ? AND service_key IS NOT NULL ORDER BY id", (org_id,)).fetchall()
        return [ServiceCatalog.get(org_id, r["service_key"]) for r in rows]

    @staticmethod
    def delete(org_id: str, service_key: str) -> bool:
        with get_db() as db:
            cur = db.execute("DELETE FROM services WHERE org_id = ? AND service_key = ?", (org_id, service_key))
            db.commit()
            return cur.rowcount > 0

    @staticmethod
    def label(service_key: str) -> str:
        return KNOWN_SERVICE_KEYS.get(service_key, service_key.replace("_", " ").title())
