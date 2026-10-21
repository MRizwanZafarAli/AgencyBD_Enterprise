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

    def source_sec_edgar_venture(
        self,
        funding_stage: str = "Form D",
        limit: int = 15,
        org_id: str = "org_default"
    ) -> List[Dict[str, Any]]:
        """
        Ingests newly funded startups and venture rounds directly from the official SEC EDGAR
        Form D live feed (100% free, updated continuously, zero API keys required).
        Uses SafeFetcher for strict SSRF protection.
        """
        status, text, _ = SafeFetcher.safe_get(
            self.SEC_FORM_D_FEED_URL,
            headers={"User-Agent": self.SEC_EDGAR_USER_AGENT},
            timeout=10
        )
        if status != 200:
            return []

        root = ET.fromstring(text)
        ns = "{http://www.w3.org/2005/Atom}"
        parsed_entries = []

        for entry in root.findall(f"{ns}entry"):
            title = entry.find(f"{ns}title")
            title_text = title.text if title is not None and title.text else ""
            if not (title_text.startswith("D ") or title_text.startswith("D/A ")):
                continue

            match = re.match(r'^(D(?:/A)?)\s*-\s*(.+?)\s*\((\d+)\)', title_text)
            comp_name = match.group(2).strip() if match else title_text.replace("D -", "").replace("D/A -", "").strip()
            cik = match.group(3) if match else ""
            form_type = match.group(1) if match else "D"

            link_elem = entry.find(f"{ns}link")
            filing_url = link_elem.attrib.get("href", "") if link_elem is not None else ""

            updated_elem = entry.find(f"{ns}updated")
            updated_date = updated_elem.text if updated_elem is not None and updated_elem.text else ""

            # Clean legal entity noise from company name to get real trading identity
            clean_name = re.sub(r'\b(Inc\.?|LLC|LP|Ltd\.?|Corp\.?|Holdings|Series of.*)\b', '', comp_name, flags=re.I).strip()
            slug = re.sub(r'[^a-zA-Z0-9]', '', clean_name or comp_name).lower()
            domain = f"{slug}.com" if slug else "company.com"

            lead = LeadRepository.create_or_get_lead(
                company_name=clean_name or comp_name,
                domain=domain,
                phone=None,
                address=None,
                rating=5.0,
                reviews_count=0,
                source_channel="sec_edgar_form_d",
                source_query=funding_stage,
                notes=f"VENTURE CAPITAL: Form {form_type} Filing | Legal: {comp_name} | CIK: {cik} | URL: {filing_url}",
                org_id=org_id
            )
            parsed_entries.append({
                **lead,
                "form_type": form_type,
                "cik": cik,
                "filing_url": filing_url,
                "filing_date": updated_date
            })
            if len(parsed_entries) >= limit:
                break

        return parsed_entries

    def source_hn_hiring_signals(
        self,
        role_keyword: str = "Engineer",
        limit: int = 15,
        org_id: str = "org_default"
    ) -> List[Dict[str, Any]]:
        """
        Ingests companies with active, senior technical hiring pain from live Hacker News
        'Who is hiring?' threads and RemoteOK engineering feeds (100% free with zero keys).
        """
        all_opportunities = []
        try:
            hn_items = self.hn_connector.fetch(limit=limit * 2)
            all_opportunities.extend(hn_items)
        except Exception:
            pass

        try:
            remote_items = self.remoteok_connector.fetch(limit=limit)
            all_opportunities.extend(remote_items)
        except Exception:
            pass

        kw_lower = role_keyword.lower().strip()
        matched_items = []
        for it in all_opportunities:
            text = f"{it.title} {it.description} {' '.join(it.skills_required or [])}".lower()
            if not kw_lower or kw_lower in text:
                matched_items.append(it)

        if not matched_items and all_opportunities:
            matched_items = all_opportunities

        leads = []
        for it in matched_items[:limit]:
            comp_name = it.company_name or "Tech Employer"
            # Strip URLs embedded in name e.g. "Snout https://snout.com/"
            clean_name = re.sub(r'https?://[^\s]+', '', comp_name).strip() or comp_name
            slug = re.sub(r'[^a-zA-Z0-9]', '', clean_name).lower()

            # Attempt to extract real domain from company name or description
            domain = f"{slug}.com" if slug else "company.com"
            raw_text = f"{it.company_name} {it.description or ''}"
            url_match = re.search(r'https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', raw_text)
            if url_match:
                cand = url_match.group(1).lower()
                if not any(skip in cand for skip in ["ycombinator.com", "remoteok.com", "github.com", "google.com", "lever.co", "greenhouse.io", "ashbyhq.com", "workable.com"]):
                    domain = cand
            elif it.url:
                match = re.search(r'https?://(?:www\.)?([^/]+)', it.url)
                if match and "ycombinator" not in match.group(1) and "remoteok" not in match.group(1):
                    domain = match.group(1)

            notes = f"HIRING INTENT: {it.title} | SOURCE: {it.source} | URL: {it.url}"
            lead = LeadRepository.create_or_get_lead(
                company_name=clean_name,
                domain=domain,
                phone=None,
                address=it.metadata.get("location") if isinstance(it.metadata, dict) else None,
                rating=5.0,
                reviews_count=1,
                source_channel="hiring_intent",
                source_query=role_keyword,
                notes=notes,
                org_id=org_id
            )
            leads.append({
                **lead,
                "opportunity_title": it.title,
                "skills_required": it.skills_required or [],
                "application_url": it.url,
                "posted_at": it.posted_at
            })

        return leads

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
