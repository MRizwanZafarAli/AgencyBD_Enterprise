"""
Company identity resolver.

Turns a company name (or a domain the user already knows) into a verified website, or says it could not.

* A name is expanded into plausible domains; each is fetched through the SSRF-safe client and scored by whether the
  homepage itself (title, og:site_name, h1, copyright, structured data) names the company.
* Parked/for-sale pages are rejected. Two close matches are reported as AMBIGUOUS, never silently picked.
* Statuses: resolved | ambiguous | unresolved | domain_unreachable | domain_parked. Nothing is guessed.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from database.db import get_db
from database.models import CompanyRepository, EvidenceRepository
from intel.search import candidate_domains as search_candidates, search_configured
from intel.site_profile import extract_profile
from net.fetcher import SafeFetcher, SSRFSecurityError, HostUnreachableError
from net.validate import clean_domain

LEGAL_WORDS = {"inc", "llc", "ltd", "limited", "corp", "corporation", "co", "company", "gmbh", "plc", "llp", "pty", "sa", "bv", "ag",
               "holdings", "group", "the", "and", "of", "services", "solutions"}
TLDS = ("com", "io", "co", "ai", "net", "org", "app", "dev")
RESOLVE_THRESHOLD = 0.8
AMBIGUITY_MARGIN = 0.15


def name_tokens(name: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", name.lower())
    tokens = [w for w in words if w not in LEGAL_WORDS and len(w) >= 2]
    return tokens or [w for w in words if len(w) >= 2]


def candidate_domains(name: str) -> List[str]:
    toks = name_tokens(name)
    if not toks:
        return []
    bases = ["".join(toks)]
    if len(toks) > 1:
        bases += ["-".join(toks), toks[0] + toks[1]]
    else:
        bases += ["get" + toks[0], "use" + toks[0], "try" + toks[0]]
    out: List[str] = []
    for base in bases:
        for tld in TLDS:
            d = f"{base}.{tld}"
            if d not in out:
                out.append(d)
    return out[:14]


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def score_homepage(tokens: List[str], domain: str, profile: Dict[str, Any]) -> float:
    """Fraction of the company's name tokens that the page itself uses to identify the business (0..1)."""
    hay = _squash(" ".join([profile["title"], profile["og_site_name"], " ".join(profile["h1"]), profile["copyright_holder"],
                            str(profile["org_jsonld"].get("name", ""))]))
    if not tokens or not hay:
        return 0.0
    score = sum(1 for t in tokens if _squash(t) in hay) / len(tokens)
    return round(score * (0.2 if profile["is_parked"] else 1.0), 3)


def probe(domain: str, tokens: List[str]) -> Optional[Dict[str, Any]]:
    """Fetches a candidate homepage. None when it cannot be reached; SSRF-blocked targets raise."""
    try:
        res = SafeFetcher.safe_fetch(f"https://{domain}", timeout=6)
    except SSRFSecurityError:
        raise
    except Exception:
        try:
            res = SafeFetcher.safe_fetch(f"http://{domain}", timeout=6)
        except SSRFSecurityError:
            raise
        except Exception:
            return None
    if res.status_code >= 400:
        return None
    profile = extract_profile(res.text, res.final_url)
    return {"domain": domain, "final_url": res.final_url, "status_code": res.status_code, "profile": profile,
            "score": score_homepage(tokens, domain, profile), "parked": profile["is_parked"], "html": res.text}


def _find_company(name: str, org_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as db:
        row = db.execute("SELECT * FROM companies WHERE org_id = ? AND LOWER(name) = LOWER(?) ORDER BY id LIMIT 1", (org_id, name)).fetchone()
    return dict(row) if row else None


def _save(company_name: str, domain: Optional[str], org_id: str) -> Dict[str, Any]:
    existing = _find_company(company_name, org_id)
    if existing:
        if domain and existing.get("domain") != domain:
            with get_db() as db:
                db.execute("UPDATE companies SET domain = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND org_id = ?", (domain, existing["id"], org_id))
                db.commit()
            existing["domain"] = domain
        return existing
    return CompanyRepository.create_or_get(name=company_name, domain=domain, org_id=org_id)


class CompanyResolver:
    @staticmethod
    def resolve_domain_from_name(company_name: str, hint_domain: Optional[str] = None, org_id: str = "org_default") -> Dict[str, Any]:
        name = (company_name or "").strip()
        if len(name) < 2 or len(name) > 120:
            raise ValueError("company_name must be 2-120 characters.")
        tokens = name_tokens(name)
        looks_like_domain = "." in name and " " not in name
        given = hint_domain or (name if looks_like_domain else None)

        # ---- the user supplied the domain: verify it, don't search
        if given:
            domain = clean_domain(given).split(":")[0]
            result = probe(domain, tokens)
            if result is None:
                status, chosen, candidates = "domain_unreachable", None, []
            elif result["parked"]:
                status, chosen, candidates = "domain_parked", None, [result]
            else:
                status, chosen, candidates = "resolved", result, [result]
            confidence = 0.0 if not chosen else max(0.85, chosen["score"])
        else:
            # ---- name only: generate + (optionally) search candidates, then verify every one
            domains = candidate_domains(name)
            if search_configured():
                try:
                    domains = list(dict.fromkeys(search_candidates(name) + domains))[:18]
                except Exception:
                    pass  # search is a bonus; guessing + verification still works
            with ThreadPoolExecutor(max_workers=6) as pool:
                probed = [r for r in pool.map(lambda d: _safe_probe(d, tokens), domains) if r]
            probed.sort(key=lambda r: r["score"], reverse=True)
            candidates = probed[:5]
            good = [r for r in probed if r["score"] >= RESOLVE_THRESHOLD and not r["parked"]]
            if not good:
                status, chosen = "unresolved", None
            elif len(good) > 1 and (good[0]["score"] - good[1]["score"]) < AMBIGUITY_MARGIN and \
                    _root(good[0]["final_url"]) != _root(good[1]["final_url"]):
                status, chosen = "ambiguous", None
            else:
                status, chosen = "resolved", good[0]
            confidence = chosen["score"] if chosen else 0.0

        company = _save(name, chosen["domain"] if chosen else None, org_id)
        evidence_ids: List[int] = []
        if chosen:
            p = chosen["profile"]
            ev = EvidenceRepository.record_evidence(
                entity_type="company", entity_id=company["id"], org_id=org_id, method="resolver.homepage",
                claim=f"{chosen['domain']} identifies itself as '{p['og_site_name'] or p['title'] or p['copyright_holder']}'",
                value=f"title={p['title']!r}; h1={p['h1']!r}; copyright={p['copyright_holder']!r}; match={chosen['score']}",
                source_url=chosen["final_url"], confidence=min(1.0, confidence))
            evidence_ids.append(ev["id"])

        return {
            "company_id": company["id"], "name": company["name"], "domain": chosen["domain"] if chosen else None,
            "status": status, "confidence": round(confidence, 3), "evidence_ids": evidence_ids,
            "candidates": [{"domain": c["domain"], "score": c["score"], "title": c["profile"]["title"], "parked": c["parked"]}
                           for c in candidates],
            "note": None if status == "resolved" else _NOTES[status],
        }


_NOTES = {
    "unresolved": "No website that clearly belongs to this company was found. The business may have no site; confirm by other means before claiming so.",
    "ambiguous": "Several different websites match this name equally well. Re-run with the correct domain as hint_domain.",
    "domain_unreachable": "The domain you gave could not be reached from our servers.",
    "domain_parked": "That domain is parked or for sale, not a live business site.",
}


def _safe_probe(domain: str, tokens: List[str]) -> Optional[Dict[str, Any]]:
    try:
        return probe(domain, tokens)
    except SSRFSecurityError:
        return None


def _root(url: str) -> str:
    host = re.sub(r"^https?://", "", url).split("/")[0].removeprefix("www.")
    return ".".join(host.split(".")[-2:])
