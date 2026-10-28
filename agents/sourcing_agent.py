"""
SourcingAgent: Multi-Channel Lead Ingestion Engine.
Connects to Google Maps, Tech Hiring Signals (JobSpy/Board aggregators), and Venture databases.
Also provides sovereign, keyless SEC EDGAR Form D venture streams, Hacker News hiring signals,
and Google X-Ray decision-maker discovery via SafeFetcher.
"""

import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

from database.models import LeadRepository
from connectors.hn import HackerNewsConnector
from connectors.remoteok import RemoteOKConnector
from net.fetcher import SafeFetcher
from engines.native_waterfall_orchestrator import NativeWaterfallOrchestrator
from config.honesty import NotConfiguredError


class SourcingAgent:
    """
    Autonomous lead ingestion agent capable of sourcing high-ticket prospective clients
    from Google Maps (local enterprises), Job Boards (companies with technical hiring pain),
    and Startup Venture Directories.
    """

    SEC_EDGAR_USER_AGENT = "AgencyBD Enterprise admin@agencybd.local"
    SEC_FORM_D_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=D&count=40&output=atom"

    def __init__(self):
        self.hn_connector = HackerNewsConnector()
        self.remoteok_connector = RemoteOKConnector()
        self.waterfall = NativeWaterfallOrchestrator()

    # --- Legacy Honesty Channels (require commercial keys) ---

    def source_google_maps(self, query: str, location: str = "Austin, TX", limit: int = 10, org_id: str = "org_default") -> List[Dict[str, Any]]:
        """
        Scrapes and ingests businesses matching query and geography from Google Maps.
        Requires a real Google Places API key.
        """
        raise NotConfiguredError(
            "sourcing.google_maps",
            "Local-business sourcing needs a real data source (Google Places API key). Not configured. Use the Opportunity Radar for live job and tender sources."
        )

    def source_hiring_signals(self, role_keyword: str = "Senior React Engineer", limit: int = 10, org_id: str = "org_default") -> List[Dict[str, Any]]:
        """
        Scrapes job boards for companies with open senior tech vacancies (> 30 days open),
        indicating active budget, engineering bottlenecks, and high intent for agency squads.
        """
        raise NotConfiguredError(
            "sourcing.hiring_intent",
            "Hiring-signal sourcing is provided by the Opportunity Radar (RemoteOK, Hacker News) and a jobs-data provider."
        )

    def source_venture_directory(self, funding_stage: str = "Series A", limit: int = 10, org_id: str = "org_default") -> List[Dict[str, Any]]:
        """
        Captures newly-funded Seed and Series A startups needing rapid MVP execution or scaling squads.
        """
        raise NotConfiguredError(
            "sourcing.venture_database",
            "Funding-signal sourcing needs a provider such as Crustdata, Harmonic or Crunchbase. Not configured."
        )

    # --- Sovereign Zero-Key Intelligence Streams (100% Free / SSRF-Safe) ---

    def fetch_sec_form_d_filings(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Reads the official SEC EDGAR Form D feed (free, no key). Pure fetch and parse: nothing is stored or guessed here."""
        try:
            status, text, _ = SafeFetcher.safe_get(self.SEC_FORM_D_FEED_URL, headers={"User-Agent": self.SEC_EDGAR_USER_AGENT}, timeout=10)
            if status != 200:
                return []
            root = ET.fromstring(text)
        except Exception:
            return []
        ns = "{http://www.w3.org/2005/Atom}"
        filings: List[Dict[str, Any]] = []
        for entry in root.findall(f"{ns}entry"):
            title = entry.find(f"{ns}title")
            title_text = title.text if title is not None and title.text else ""
            match = re.match(r'^(D(?:/A)?)\s*-\s*(.+?)\s*\((\d+)\)', title_text)
            if not match:
                continue
            link = entry.find(f"{ns}link")
            updated = entry.find(f"{ns}updated")
            filings.append({"form_type": match.group(1), "legal_name": match.group(2).strip(), "cik": match.group(3),
                            "filing_url": link.attrib.get("href", "") if link is not None else "",
                            "filing_date": updated.text if updated is not None and updated.text else ""})
            if len(filings) >= limit * 4:       # read extra: most filers are funds and get dropped
                break
        return filings

    def source_sec_edgar_venture(self, funding_stage: str = "Form D", limit: int = 15, org_id: str = "org_default") -> Dict[str, Any]:
        """
        Newly funded companies from SEC Form D filings. A filer becomes a lead only if (1) its name does not mark it as an
        investment vehicle and (2) a website that clearly belongs to it was VERIFIED. Everything else is reported in `skipped`
        with the reason. No domain is ever guessed.
        """
        from intel.entity_filter import classify_entity, clean_company_name
        from intel.resolver import CompanyResolver

        leads: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        seen = set()
        candidates = []
        for f in self.fetch_sec_form_d_filings(limit):
            name = clean_company_name(f["legal_name"])
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            kind, reason = classify_entity(f["legal_name"])
            if kind != "operating_company":
                skipped.append({"name": f["legal_name"], "reason": reason})
                continue
            candidates.append((f, name))
        resolved = self._resolve_many([(n, None) for _, n in candidates], org_id)   # website checks run in parallel
        for (f, name), res in zip(candidates, resolved):
            if res["status"] != "resolved":
                skipped.append({"name": name, "reason": res["note"] or "no verified website"})
                continue
            lead = LeadRepository.create_or_get_lead(
                company_name=name, domain=res["domain"], source_channel="sec_edgar_form_d", source_query=funding_stage,
                notes=f"VENTURE CAPITAL: Form {f['form_type']} filing | Legal: {f['legal_name']} | CIK: {f['cik']} | URL: {f['filing_url']}",
                org_id=org_id)
            leads.append({**lead, "company_id": res["company_id"], "form_type": f["form_type"], "cik": f["cik"],
                          "filing_url": f["filing_url"], "filing_date": f["filing_date"]})
            if len(leads) >= limit:
                break
        return {"leads": leads, "skipped": skipped}

    @staticmethod
    def _resolve_many(pairs, org_id: str, workers: int = 6) -> List[Dict[str, Any]]:
        """Verifies websites for many (name, hint) pairs concurrently. A failure for one name never aborts the rest."""
        from concurrent.futures import ThreadPoolExecutor
        from intel.resolver import CompanyResolver

        def one(pair):
            try:
                return CompanyResolver.resolve_domain_from_name(pair[0], pair[1], org_id=org_id)
            except Exception as exc:
                return {"status": "unresolved", "domain": None, "company_id": None, "note": f"check failed: {str(exc)[:80]}"}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(one, pairs))

    def source_hn_hiring_signals(self, role_keyword: str = "Engineer", limit: int = 15, org_id: str = "org_default") -> Dict[str, Any]:
        """
        Companies hiring engineers, from the newest Hacker News "Who is hiring?" thread and RemoteOK. The company website is taken
        from the posting itself when it states one, otherwise resolved and verified. Unresolvable postings are listed in
        `skipped`; source failures are listed in `errors` (never swallowed).
        """
        from intel.entity_filter import clean_company_name
        from intel.resolver import CompanyResolver

        items, errors = [], []
        for label, connector, n in (("Hacker News", self.hn_connector, limit * 3), ("RemoteOK", self.remoteok_connector, limit * 2)):
            try:
                items.extend(connector.fetch(limit=n))
            except Exception as exc:
                errors.append(f"{label}: {str(exc)[:120]}")

        kw = role_keyword.lower().strip()
        matched = [it for it in items if not kw or kw in f"{it.title} {it.description} {' '.join(it.skills_required or [])}".lower()]

        skip_hosts = ("ycombinator.com", "remoteok.com", "github.com", "google.com", "lever.co", "greenhouse.io", "ashbyhq.com",
                      "workable.com", "linkedin.com", "twitter.com", "x.com", "notion.so", "bit.ly")
        leads: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        todo = []
        seen_names = set()
        for it in matched:
            if len(todo) >= limit * 2:          # check a few extra: some will not resolve
                break
            name = clean_company_name(it.company_name or "")
            if not name or len(name) < 2:
                skipped.append({"name": it.title[:60], "reason": "posting does not name a company"})
                continue
            if name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            hint = None
            m = re.search(r"https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", f"{it.company_name or ''} {it.description or ''}")
            if m and not any(h in m.group(1).lower() for h in skip_hosts):
                hint = m.group(1).lower()
            todo.append((it, name, hint))
        resolved = self._resolve_many([(n, h) for _, n, h in todo], org_id)
        for (it, name, _hint), res in zip(todo, resolved):
            if len(leads) >= limit:
                break
            if res["status"] != "resolved":
                skipped.append({"name": name, "reason": res["note"] or "no verified website"})
                continue
            location = it.metadata.get("location") if isinstance(it.metadata, dict) else None
            lead = LeadRepository.create_or_get_lead(
                company_name=name, domain=res["domain"], address=location, source_channel="hiring_intent", source_query=role_keyword,
                notes=f"HIRING INTENT: {it.title} | SOURCE: {it.source} | URL: {it.url}", org_id=org_id)
            leads.append({**lead, "company_id": res["company_id"], "opportunity_title": it.title,
                          "skills_required": it.skills_required or [], "application_url": it.url, "posted_at": it.posted_at})
        return {"leads": leads, "skipped": skipped, "errors": errors}

    def discover_xray_executives(
        self,
        company_name: str,
        titles: Optional[List[str]] = None,
        location: str = "United States",
        limit: int = 5,
        domain_hint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates precision 1-click Google X-Ray URLs and email permutations for executive targets.
        """
        target_titles = titles or ["CTO", "CEO", "VP of Engineering", "Head of Product", "Founder"]
        domain = domain_hint or f"{re.sub(r'[^a-zA-Z0-9]', '', company_name).lower()}.com"

        discovered = []
        for title in target_titles[:limit]:
            xray_query = f'site:linkedin.com/in/ "{company_name}" "{title}" "{location}"'
            xray_url = f"https://www.google.com/search?q={urllib.parse.quote(xray_query)}"
            perms = self.waterfall.generate_email_permutations(title.replace(" ", ""), "Leader", domain)

            discovered.append({
                "first_name": title,
                "last_name": f"({company_name})",
                "title": title,
                "headline": f"{title} at {company_name}",
                "location": location,
                "company": company_name,
                "domain": domain,
                "linkedin_url": xray_url,
                "xray_url": xray_url,
                "email_candidates": perms[:3],
                "discovery_source": "google_xray_target"
            })

        return discovered
