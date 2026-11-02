"""Where saved searches look. Each source returns real items only: {key, title, detail, url, data}. Nothing is guessed or filled in."""

import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib.parse import quote, urlencode

from database.db import get_db
from database.models import OpportunityRepository
from net.fetcher import SafeFetcher

Hit = Dict[str, Any]


class NotConfigured(RuntimeError):
    """A key or setup step is missing; shown to the person as a plain instruction."""


# ------------------------------------------------------------------ what your own stored checks can say

SIGNALS: Dict[str, Dict[str, Any]] = {
    "certificate": {"label": "Certificate expiring or invalid", "checks": ["tls_certificate_expiring", "tls_certificate_invalid"]},
    "no_https": {"label": "Not served over HTTPS", "checks": ["no_https"]},
    "outdated_software": {"label": "Outdated software or known vulnerabilities", "checks": ["version_disclosure", "cve_%"]},
    "not_mobile": {"label": "No mobile layout", "checks": ["missing_viewport_tag"]},
    "slow": {"label": "Slow loading", "checks": ["slow_lcp", "low_lighthouse_score"]},
    "hidden_from_google": {"label": "Hidden from search engines", "checks": ["noindex_set", "robots_blocks_all", "missing_meta_title"]},
}


def _words(text: str) -> List[str]:
    return [w for w in re.split(r"[^\w+#.]+", text.lower()) if w]


def _matches(text: str, keywords: List[str]) -> bool:
    haystack = f" {' '.join(_words(text))} "
    return any(f" {' '.join(_words(k))} " in haystack for k in keywords if _words(k))


def clean_params(source: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validates and normalises the options of one source. Raises ValueError with a sentence a person can act on."""
    p = params or {}
    if source == "hiring":
        keywords = [str(k).strip()[:60] for k in (p.get("keywords") or []) if str(k).strip()][:12]
        if not keywords:
            raise ValueError("Add at least one word or phrase to look for, for example: react developer.")
        return {"keywords": keywords, "min_fit": max(0, min(100, int(p.get("min_fit") or 0)))}
    if source == "new_companies":
        days = int(p.get("days") or 7)
        if not 1 <= days <= 30:
            raise ValueError("Choose between 1 and 30 days.")
        sic = [str(c).strip() for c in (p.get("sic_codes") or []) if str(c).strip()][:10]
        if any(not re.fullmatch(r"\d{4,5}", c) for c in sic):
            raise ValueError("Business type codes (SIC) are 4 or 5 digits, for example 47910.")
        return {"days": days, "sic_codes": sic, "location": str(p.get("location") or "").strip()[:60]}
    if source == "new_companies_ie":
        days = int(p.get("days") or 7)
        if not 1 <= days <= 30:
            raise ValueError("Choose between 1 and 30 days.")
        codes = [str(c).strip() for c in (p.get("sic_codes") or []) if str(c).strip()][:10]
        if any(not re.fullmatch(r"\d{4}", c) for c in codes):
            raise ValueError("Irish business type codes (NACE) are 4 digits, for example 4791.")
        place = str(p.get("location") or "").strip()[:40]
        if place and not re.fullmatch(r"[A-Za-z0-9 \-]+", place):
            raise ValueError("The place can only use letters, numbers, spaces and hyphens.")
        return {"days": days, "sic_codes": codes, "location": place}
    if source == "site_signals":
        chosen = [s for s in (p.get("signals") or []) if s in SIGNALS]
        if not chosen:
            raise ValueError("Pick at least one thing to watch for.")
        return {"signals": chosen}
    raise ValueError("Unknown source.")


# ------------------------------------------------------------------ hiring: what the scans already collected

def hiring(org_id: str, params: Dict[str, Any]) -> List[Hit]:
    out = []
    for o in OpportunityRepository.list_opportunities(limit=200, org_id=org_id):
        text = f"{o['title']} {o.get('description') or ''}"
        if not _matches(text, params["keywords"]) or (o.get("fit_score") or 0) * 100 < params.get("min_fit", 0):
            continue
        out.append({"key": f"{o['source']}:{o.get('external_id') or o['id']}", "title": o["title"],
                    "detail": o["source"] + (f" · {o['company_name']}" if o.get("company_name") else ""),
                    "url": o.get("url"), "data": {"opportunity_id": o["id"], "source": o["source"], "company": o.get("company_name")}})
    return out


# ------------------------------------------------------------------ new_companies: UK Companies House (official, free key)

def companies_house(org_id: str, params: Dict[str, Any]) -> List[Hit]:
    key = (os.environ.get("COMPANIES_HOUSE_API_KEY") or "").strip()
    if not key:
        raise NotConfigured("Add a free Companies House key in Settings, Integrations and keys (Companies House).")
    today = datetime.now(timezone.utc).date()
    query = {"incorporated_from": (today - timedelta(days=params["days"])).isoformat(), "incorporated_to": today.isoformat(), "company_status": "active", "size": 100}
    if params.get("sic_codes"):
        query["sic_codes"] = ",".join(params["sic_codes"])
    if params.get("location"):
        query["location"] = params["location"]
    auth = base64.b64encode(f"{key}:".encode()).decode()
    r = SafeFetcher.safe_fetch(f"https://api.company-information.service.gov.uk/advanced-search/companies?{urlencode(query)}", timeout=30,
                               headers={"Authorization": f"Basic {auth}"}, max_bytes=3_000_000)
    if r.status_code in (401, 403):
        raise NotConfigured("Companies House rejected the key. Check it in Settings, Integrations and keys.")
    if r.status_code == 429:
        raise RuntimeError("Companies House asked us to slow down. It will be tried again at the next run.")
    if r.status_code != 200:
        raise RuntimeError(f"Companies House answered HTTP {r.status_code}.")
    out = []
    for c in (json.loads(r.text).get("items") or []):
        number, name = c.get("company_number"), c.get("company_name")
        if not number or not name:
            continue
        addr = c.get("registered_office_address") or {}
        place = ", ".join(x for x in (addr.get("locality"), addr.get("postal_code")) if x)
        out.append({"key": str(number), "title": name.title(), "url": f"https://find-and-update.company-information.service.gov.uk/company/{number}",
                    "detail": f"Registered {c.get('date_of_creation', 'recently')}" + (f" · {place}" if place else "") + " · no website or email is listed in the register",
                    "data": {"company_number": number, "created": c.get("date_of_creation"), "sic_codes": c.get("sic_codes") or [], "country": "GB"}})
    return out


# ------------------------------------------------------------------ new_companies_ie: Irish register open data (CC BY 4.0, no key)

CRO_RESOURCE = "3fef41bc-b8f4-4b10-8434-ce51c29b1bba"


def cro_ireland(org_id: str, params: Dict[str, Any]) -> List[Hit]:
    since = (datetime.now(timezone.utc).date() - timedelta(days=params["days"])).isoformat()
    where = [f"company_reg_date >= '{since}'", "company_status LIKE 'Normal%'"]       # every value below was validated: digits, or letters and spaces only
    if params.get("sic_codes"):
        where.append("nace_v2_code IN (" + ", ".join(f"'{c}'" for c in params["sic_codes"]) + ")")
    if params.get("location"):
        where.append("(" + " OR ".join(f"{col} ILIKE '%{params['location']}%'" for col in ("company_address_2", "company_address_3", "company_address_4")) + ")")
    sql = (f'SELECT company_num, company_name, company_type, company_reg_date, company_address_2, company_address_3, company_address_4, eircode, nace_v2_code '
           f'FROM "{CRO_RESOURCE}" WHERE {" AND ".join(where)} ORDER BY company_reg_date DESC LIMIT 100')
    r = SafeFetcher.safe_fetch(f"https://opendata.cro.ie/api/3/action/datastore_search_sql?{urlencode({'sql': sql})}", timeout=45, max_bytes=3_000_000,
                               headers={"User-Agent": "AgencyBD-LeadFinder/1.0 (open data reader)", "Accept": "application/json"})      # says plainly what it is
    if r.status_code != 200:
        raise RuntimeError(f"The Irish register answered HTTP {r.status_code}. It will be tried again at the next run.")
    body = json.loads(r.text)
    if not body.get("success"):
        raise RuntimeError("The Irish register could not answer that search. It will be tried again at the next run.")
    out = []
    for c in body["result"].get("records") or []:
        number, name = c.get("company_num"), re.sub(r"\s+", " ", c.get("company_name") or "").strip()
        if not number or not name:
            continue
        place = ", ".join(x.strip() for x in (c.get("company_address_2"), c.get("company_address_3"), c.get("company_address_4")) if x and x.strip())
        out.append({"key": f"IE:{number}", "title": name.title(), "url": None,
                    "detail": f"Registered {(c.get('company_reg_date') or 'recently')[:10]}" + (f" · {place}" if place else "") + (f" · {c['eircode']}" if c.get("eircode") else "")
                              + f" · CRO number {number} · no website or email is listed in the register",
                    "data": {"company_number": number, "created": c.get("company_reg_date"), "nace": c.get("nace_v2_code"), "country": "IE"}})
    return out


# ------------------------------------------------------------------ site_signals: your own saved website checks

def site_signals(org_id: str, params: Dict[str, Any]) -> List[Hit]:
    out = []
    with get_db() as db:
        for sig in params["signals"]:
            clauses, args = [], [org_id]
            for c in SIGNALS[sig]["checks"]:
                clauses.append("f.check_id LIKE ?" if "%" in c else "f.check_id = ?")
                args.append(c)
            rows = db.execute(
                f"""SELECT c.id AS company_id, c.name, c.domain, f.check_id, f.finding FROM audit_findings f
                    JOIN audit_runs r ON r.id = f.audit_run_id AND r.status = 'completed'
                    JOIN companies c ON c.id = r.company_id
                    WHERE c.org_id = ? AND ({' OR '.join(clauses)})
                      AND r.id = (SELECT MAX(id) FROM audit_runs WHERE company_id = c.id AND status = 'completed')
                    GROUP BY c.id""", args).fetchall()
            for row in rows:
                out.append({"key": f"{row['company_id']}:{sig}", "title": row["name"], "detail": f"{SIGNALS[sig]['label']}: {row['finding']}",
                            "url": f"https://{row['domain']}" if row["domain"] else None, "data": {"company_id": row["company_id"], "domain": row["domain"], "signal": sig, "check": row["check_id"]}})
    return out


SOURCES = {
    "hiring": {"label": "Jobs and projects", "run": hiring, "needs": None,
               "about": "Looks through the jobs, projects and hiring posts your scans have collected and keeps the ones that mention your words."},
    "new_companies": {"label": "Newly registered UK companies", "run": companies_house, "needs": "COMPANIES_HOUSE_API_KEY",
                      "about": "Companies registered in the last few days. They usually need a website, logo and email address soon. Free official register."},
    "new_companies_ie": {"label": "Newly registered Irish companies", "run": cro_ireland, "needs": None,
                         "about": "Companies registered in the last few days in Ireland. Free open data from the Companies Registration Office (licence CC BY 4.0). It lists name, address and business type only."},
    "site_signals": {"label": "Problems found on websites you checked", "run": site_signals, "needs": None,
                     "about": "Watches your saved website checks for problems you can fix, such as an expiring certificate or no mobile layout."},
}


# ------------------------------------------------------------------ LinkedIn-style search links (you click them; nothing is fetched)

def xray_links(role: str, industry: str = "", location: str = "") -> List[Dict[str, str]]:
    role, industry, location = role.strip()[:80], industry.strip()[:80], location.strip()[:80]
    if not role:
        raise ValueError("Say who you are looking for, for example: owner, marketing manager, founder.")
    extra = " ".join(f'"{x}"' for x in (industry, location) if x)
    people = f'site:linkedin.com/in "{role}" {extra}'.strip()
    companies = f'site:linkedin.com/company {extra}'.strip() if extra else ""
    links = [
        {"label": "People on LinkedIn (Google)", "url": f"https://www.google.com/search?q={quote(people)}", "note": "Public profiles that Google has indexed."},
        {"label": "People on LinkedIn (Bing)", "url": f"https://www.bing.com/search?q={quote(people)}", "note": "A second index; often shows different people."},
        {"label": "LinkedIn people search", "url": f"https://www.linkedin.com/search/results/people/?keywords={quote(' '.join([role, industry, location]).strip())}",
         "note": "Opens inside your own logged-in LinkedIn. Free accounts show a limited list."},
    ]
    if companies:
        links.append({"label": "Company pages (Google)", "url": f"https://www.google.com/search?q={quote(companies)}", "note": "Companies in that field and place."})
    links.append({"label": "Who is hiring for it (Google)", "url": f"https://www.google.com/search?q={quote(f'site:linkedin.com/jobs {role} {extra}'.strip())}", "note": "A company hiring for this role is spending on it."})
    return links


# ------------------------------------------------------------------ places to look that have no feed we may read: links you open yourself

LOOK_HERE = [
    {"region": "Pakistan", "label": "Federal public tenders (PPRA e-Pak)", "url": "https://epms.ppra.gov.pk",
     "note": "Look under the information technology sector. PPRA publishes no feed that we may read, so you search it by hand."},
    {"region": "Pakistan", "label": "Punjab public tenders (PPRA Punjab)", "url": "https://ppra.punjab.gov.pk", "note": "Provincial portals differ; Sindh and Khyber Pakhtunkhwa have their own."},
    {"region": "Pakistan", "label": "P@SHA member companies", "url": "https://pasha.org.pk", "note": "Software houses that sometimes need a partner or overflow help. Contact them as a partner, not as a customer."},
    {"region": "Pakistan", "label": "PSEB registered companies", "url": "https://pseb.org.pk", "note": "The same idea: possible white-label and partner work."},
    {"region": "Ireland", "label": "CRO weekly gazette of new companies", "url": "https://www.cro.ie", "note": "Lead Finder already reads the open data file; the gazette is a PDF you can skim."},
    {"region": "Everywhere", "label": "UN and NGO tenders (UNGM)", "url": "https://www.ungm.org", "note": "Registration is free. Slow, but large and often overlooked by small agencies."},
    {"region": "Everywhere", "label": "ReliefWeb jobs and tenders", "url": "https://reliefweb.int", "note": "NGOs sometimes need websites and tools built."},
]
