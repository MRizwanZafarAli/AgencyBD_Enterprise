"""
Public vulnerability data, read-only and cached 24 hours in the database:

  NVD   services.nvd.nist.gov   CVEs affecting a product version (CPE match; NVD_API_KEY optional, raises the rate limit)
  OSV   api.osv.dev             advisories for open-source packages (npm)
  KEV   www.cisa.gov            CVEs CISA says are exploited in the wild

Every fetch goes through the SSRF-safe client to these three fixed hosts. A failure returns None ("unknown"), never an empty
list, so callers can tell "no vulnerabilities" from "could not check".
"""

import json
import os
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

from database.db import get_db
from net.fetcher import SafeFetcher

TTL_SECONDS = 24 * 3600
ALLOWED_HOSTS = ("services.nvd.nist.gov", "api.osv.dev", "www.cisa.gov")
UA = {"User-Agent": "AgencyBD-Enterprise/1.0 (vulnerability lookup; read-only)"}


def _cached(key: str) -> Optional[Any]:
    with get_db() as db:
        row = db.execute("SELECT payload_json, strftime('%s', fetched_at) AS ts FROM vuln_cache WHERE cache_key = ?", (key,)).fetchone()
    if row and time.time() - int(row["ts"]) < TTL_SECONDS:
        return json.loads(row["payload_json"])
    return None


def _store(key: str, payload: Any) -> None:
    with get_db() as db:
        db.execute("INSERT INTO vuln_cache (cache_key, payload_json, fetched_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                   "ON CONFLICT(cache_key) DO UPDATE SET payload_json = excluded.payload_json, fetched_at = CURRENT_TIMESTAMP",
                   (key, json.dumps(payload)))
        db.commit()


def _get_json(url: str, key: str, method: str = "GET", body: Optional[dict] = None, headers: Optional[dict] = None,
              max_bytes: int = 6_000_000) -> Optional[Any]:
    host = url.split("/")[2]
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"Host not allowed for vulnerability lookups: {host}")
    hit = _cached(key)
    if hit is not None:
        return hit
    try:
        res = SafeFetcher.safe_fetch(url, timeout=20, max_bytes=max_bytes, method=method, json_body=body, headers={**UA, **(headers or {})})
        if res.status_code != 200:
            return None
        data = json.loads(res.text)
    except Exception:
        return None
    _store(key, data)
    return data


def nvd_cves(vendor: str, product: str, version: str) -> Optional[List[Dict[str, Any]]]:
    """CVEs NVD lists as affecting exactly this version. None = could not check."""
    cpe = f"cpe:2.3:a:{vendor}:{product}:{version}:*:*:*:*:*:*:*"
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cpeName={quote(cpe, safe=':*')}&isVulnerable&resultsPerPage=100"
    headers = {"apiKey": os.environ["NVD_API_KEY"]} if os.getenv("NVD_API_KEY") else None
    data = _get_json(url, f"nvd:{cpe}", headers=headers)
    if data is None:
        return None
    out = []
    for v in data.get("vulnerabilities", []):
        c = v["cve"]
        score, label = None, None
        for k in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if c.get("metrics", {}).get(k):
                m = c["metrics"][k][0]["cvssData"]
                score, label = m.get("baseScore"), m.get("baseSeverity")
                break
        desc = next((d["value"] for d in c.get("descriptions", []) if d.get("lang") == "en"), "")
        out.append({"cve_id": c["id"], "summary": desc, "cvss": score, "severity": (label or "").lower() or None,
                    "published": c.get("published", "")[:10], "url": f"https://nvd.nist.gov/vuln/detail/{c['id']}"})
    return out


def osv_vulns(ecosystem: str, package: str, version: str) -> Optional[List[Dict[str, Any]]]:
    data = _get_json("https://api.osv.dev/v1/query", f"osv:{ecosystem}:{package}:{version}", method="POST",
                     body={"package": {"name": package, "ecosystem": ecosystem}, "version": version})
    if data is None:
        return None
    sev_map = {"CRITICAL": 9.5, "HIGH": 8.0, "MODERATE": 5.5, "MEDIUM": 5.5, "LOW": 3.0}
    out = []
    for v in data.get("vulns", []):
        cve = next((a for a in v.get("aliases", []) if a.startswith("CVE-")), v["id"])
        label = (v.get("database_specific", {}) or {}).get("severity", "")
        out.append({"cve_id": cve, "summary": v.get("summary") or v.get("details", "")[:200], "cvss": sev_map.get(label.upper()),
                    "severity": label.lower() or None, "published": (v.get("published") or "")[:10], "url": f"https://osv.dev/vulnerability/{v['id']}"})
    return out


def kev_ids() -> Optional[Set[str]]:
    """CVE ids on the CISA Known Exploited Vulnerabilities list. None = could not load it."""
    data = _get_json("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", "kev", max_bytes=8_000_000)
    return {v["cveID"] for v in data.get("vulnerabilities", [])} if data else None
