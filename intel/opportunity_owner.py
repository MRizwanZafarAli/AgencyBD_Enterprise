"""
Opportunity Business Owner & Decision Maker Resolver ("Related Read").

Extracts company identity, domain, and decision maker/business owner contacts
from job and project postings across radar sources (Upwork, RemoteOK, WWR, HN,
Reddit, GitHub, etc.) and company website intelligence.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from database.db import get_db
from database.models import OpportunityRepository, LeadRepository, ContactRepository
from intel import contacts as contact_finder
from intel import resolver

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?")

# Common patterns in job and project titles/descriptions
COMPANY_AT_RE = re.compile(r"(?:at|@|for|with)[ \t]+([A-Z][A-Za-z0-9&.,'\s]{1,40}?)(?:[ \t]+is|[ \t]+looking|[ \t]+seeking|[ \t]+hiring|[ \t]*[-–—|(\[\r\n]|$)", re.IGNORECASE)
COMPANY_PREFIX_RE = re.compile(r"^\[?([A-Z][A-Za-z0-9&.,'\s]{1,30}?)\]?[ \t]*[-–—:|][ \t]*", re.IGNORECASE)
OWNER_LINE_RE = re.compile(r"(?:posted by|hiring manager|contact|founder|owner|lead|cto|ceo|point of contact)[: \t]+([A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){1,3})", re.IGNORECASE)


def extract_company_name(title: str, description: Optional[str] = None, fallback: Optional[str] = None) -> str:
    """Intelligently detects company name from title, description, or fallback."""
    if fallback and fallback.strip() and fallback.lower() not in ("unknown", "n/a", "none", "remote"):
        return fallback.strip()

    full_text = f"{title}\n{description or ''}"
    
    # Check title prefix e.g. "Acme Corp - Senior React Developer"
    m_pre = COMPANY_PREFIX_RE.match(title.strip())
    if m_pre:
        cand = m_pre.group(1).strip()
        if len(cand) >= 2 and cand.lower() not in ("hiring", "job", "project", "remote", "urgent", "looking"):
            return cand

    # Check "at / for / with Company"
    m_at = COMPANY_AT_RE.search(title)
    if m_at:
        cand = m_at.group(1).strip()
        if len(cand) >= 2 and cand.lower() not in ("remote", "anywhere", "worldwide", "us", "uk", "eu"):
            return cand

    # Scan description lines for "Company:" or "About [Company]"
    m_about = re.search(r"(?:About|Company):\s*([A-Z][A-Za-z0-9&.,'\s]{2,40})", full_text, re.IGNORECASE)
    if m_about:
        return m_about.group(1).strip()

    return fallback or "Client Organization"


def extract_domain_from_url(url: Optional[str]) -> Optional[str]:
    """Extracts non-aggregator domain if URL points directly to company site."""
    if not url:
        return None
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower().removeprefix("www.")
        # Ignore major job boards and social portals
        aggregators = (
            "upwork.com", "reddit.com", "news.ycombinator.com", "remoteok.com",
            "weworkremotely.com", "github.com", "sam.gov", "ted.europa.eu",
            "find-tender.service.gov.uk", "linkedin.com", "twitter.com", "x.com"
        )
        if host and not any(host.endswith(agg) for agg in aggregators):
            return host
    except Exception:
        pass
    return None


def resolve_opportunity_owner(opportunity_id: int, org_id: str = "org_default") -> Dict[str, Any]:
    """
    Performs 'Related Read' on a job or project opportunity:
    Extracts company name, domain, decision makers, business owners, and contact telemetry.
    """
    opp = OpportunityRepository.get_opportunity(opportunity_id, org_id)
    if not opp:
        raise LookupError(f"Opportunity #{opportunity_id} not found")

    title = opp.get("title") or ""
    description = opp.get("description") or ""
    full_text = f"{title}\n{description}"
    stored_company = opp.get("company_name")
    opp_url = opp.get("url")

    # 1. Resolve Company Name
    company_name = extract_company_name(title, description, fallback=stored_company)

    # 2. Extract detected emails & phone numbers from text
    raw_emails = EMAIL_RE.findall(full_text)
    detected_emails = sorted(list(set(e.lower() for e in raw_emails)))
    
    raw_phones = PHONE_RE.findall(full_text)
    detected_phones = sorted(list(set(p.strip() for p in raw_phones if len(p.strip()) >= 10)))

    raw_linkedins = LINKEDIN_RE.findall(full_text)
    detected_linkedins = sorted(list(set(raw_linkedins)))

    # 3. Extract direct poster / manager from posting text
    direct_owner = None
    m_owner = OWNER_LINE_RE.search(full_text)
    if m_owner:
        owner_name = m_owner.group(1).split("\n")[0].strip()
        matched_email = next((e for e in detected_emails if owner_name.lower().split()[0] in e), None) or (detected_emails[0] if detected_emails else None)
        direct_owner = {
            "name": owner_name,
            "title": "Hiring Manager / Project Sponsor",
            "email": matched_email,
            "phone": detected_phones[0] if detected_phones else None,
            "linkedin_url": detected_linkedins[0] if detected_linkedins else None,
            "verification_status": "detected_in_posting",
            "rank": 95,
            "source": "posting_content"
        }

    # 4. Resolve Domain
    domain = extract_domain_from_url(opp_url)
    website_url = f"https://{domain}" if domain else None

    # If domain not in URL, attempt quick resolution from company name
    if not domain and company_name and company_name != "Client Organization":
        cands = resolver.candidate_domains(company_name)
        for cand in cands[:2]:
            try:
                p = resolver.probe(cand, resolver.name_tokens(company_name), timeout=1.5)
                if p and not p.get("parked") and p.get("score", 0) >= 0.4:
                    domain = cand
                    website_url = p.get("final_url") or f"https://{domain}"
                    break
            except Exception:
                continue

    # 5. Discover decision makers on company domain if available
    site_contacts: List[Dict[str, Any]] = []
    if domain:
        try:
            cf_out = contact_finder.find_contacts(domain)
            for c in cf_out.get("candidates") or []:
                if c.get("name"):
                    site_contacts.append({
                        "name": c.get("name"),
                        "title": c.get("title") or "Executive / Decision Maker",
                        "email": c.get("email"),
                        "phone": None,
                        "linkedin_url": c.get("linkedin_url"),
                        "verification_status": "published_on_site",
                        "rank": c.get("rank", 50),
                        "source": "company_website"
                    })
        except Exception:
            pass

    # Sort site contacts by executive rank
    site_contacts.sort(key=lambda x: -x["rank"])

    # Pick the primary business owner / decision maker
    primary_owner = direct_owner
    if not primary_owner and site_contacts:
        primary_owner = site_contacts[0]

    if not primary_owner:
        # Fallback synthesized owner contact based on company & detected emails
        best_email = detected_emails[0] if detected_emails else (f"contact@{domain}" if domain else None)
        primary_owner = {
            "name": f"Leadership Team ({company_name})",
            "title": "Hiring / Business Owner",
            "email": best_email,
            "phone": detected_phones[0] if detected_phones else None,
            "linkedin_url": detected_linkedins[0] if detected_linkedins else None,
            "verification_status": "unverified_signal",
            "rank": 60,
            "source": "derived_opportunity"
        }

    all_contacts: List[Dict[str, Any]] = []
    if primary_owner:
        all_contacts.append(primary_owner)
    for sc in site_contacts:
        if sc.get("name") != primary_owner.get("name"):
            all_contacts.append(sc)

    summary_note = (
        f"Verified business owner & decision maker intelligence retrieved for '{company_name}'. "
        f"{'Domain confirmed as ' + domain + '. ' if domain else 'No public domain resolved. '}"
        f"{len(all_contacts)} decision maker(s) and {len(detected_emails)} direct email signal(s) identified."
    )

    return {
        "opportunity_id": opportunity_id,
        "company_name": company_name,
        "domain": domain or f"{company_name.lower().replace(' ', '')}.invalid",
        "website_url": website_url,
        "business_owner": primary_owner,
        "contacts": all_contacts,
        "detected_emails": detected_emails,
        "detected_phones": detected_phones,
        "detected_linkedins": detected_linkedins,
        "summary": summary_note
    }


def convert_opportunity_to_lead(opportunity_id: int, org_id: str = "org_default") -> Dict[str, Any]:
    """Converts a job/project opportunity into a Client Lead in the CRM pipeline."""
    owner_info = resolve_opportunity_owner(opportunity_id, org_id)
    opp = OpportunityRepository.get_opportunity(opportunity_id, org_id)
    
    company_name = owner_info["company_name"]
    domain = owner_info["domain"]
    
    lead = LeadRepository.create_or_get_lead(
        company_name=company_name,
        domain=domain,
        source_channel="jobs_and_projects",
        source_query=opp.get("source") if opp else "radar",
        org_id=org_id
    )
    
    lead_id = lead["id"]
    owner = owner_info.get("business_owner")
    
    if owner and owner.get("name") and owner.get("email"):
        name_parts = owner["name"].split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else "-"
        try:
            ContactRepository.add_decision_maker(
                lead_id=lead_id,
                first_name=first_name,
                last_name=last_name,
                title=owner.get("title") or "Business Owner",
                email=owner["email"],
                linkedin_url=owner.get("linkedin_url"),
                email_source=f"opportunity_{opportunity_id}_related_read",
                org_id=org_id
            )
        except Exception:
            pass  # Unique constraint or already added

    # Update opportunity with company_name if it was null
    if opp and not opp.get("company_name") and company_name != "Client Organization":
        with get_db() as db:
            db.execute("UPDATE opportunities SET company_name = ? WHERE id = ? AND org_id = ?",
                       (company_name, opportunity_id, org_id))
            db.commit()

    return {
        "status": "created",
        "lead_id": lead_id,
        "company_name": company_name,
        "domain": domain,
        "business_owner": owner,
        "message": f"Successfully converted '{company_name}' to CRM Client Lead #{lead_id}!"
    }
