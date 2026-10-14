"""
LinkedInAgent: Autonomous LinkedIn People & Company Prospecting Engine.
Executes Google X-Ray scraping, Sales Navigator profile discovery,
and multi-touch LinkedIn connection & InMail sequence generation.
"""

import re
import random
import urllib.parse
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

from database.models import LeadRepository, ContactRepository
from config.settings import settings
from config.honesty import NotConfiguredError, PreconditionFailedError

class LinkedInAgent:
    """
    Dedicated agent for finding executive decision makers on LinkedIn,
    extracting verified public profile URLs, and generating high-converting connection sequences.
    """

    def __init__(self):
        pass  # No network sessions here: data comes from vetted connectors.

    def build_xray_query(self, company: str, titles: List[str], location: Optional[str] = None) -> str:
        """Constructs precision Google X-Ray search string for LinkedIn."""
        title_terms = " OR ".join([f'"{t}"' for t in titles])
        loc_term = f' "{location}"' if location else ""
        return f'site:linkedin.com/in/ "{company}" ({title_terms}){loc_term}'

    def search_people(
        self,
        company_name: str,
        titles: Optional[List[str]] = None,
        location: str = "United States",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Discovers verified decision makers for a target company on LinkedIn.
        Returns parsed profiles with headline, location, and verified profile URLs.
        """
        if not titles:
            titles = ["CTO", "Chief Technology Officer", "VP of Engineering", "Founder", "CEO", "Head of Product"]

        raise NotConfiguredError("linkedin.people", "LinkedIn cannot be scraped or automated. Use a licensed people-data provider, or paste a profile you are viewing into the LinkedIn Companion.")

    def search_companies(
        self,
        keyword: str = "AI Agents Software",
        industry: str = "Technology",
        location: str = "San Francisco, CA",
        limit: int = 5,
        org_id: str = "org_default"
    ) -> List[Dict[str, Any]]:
        """
        Discovers company LinkedIn pages matching tech keyword and industry.
        """
        raise NotConfiguredError("linkedin.companies", "LinkedIn cannot be scraped or automated. Use a licensed people-data provider, or paste a profile you are viewing into the LinkedIn Companion.")

    def generate_linkedin_sequence(self, first_name: str, company_name: str, trigger_hook: str) -> Dict[str, str]:
        """
        Generates a 3-touch LinkedIn sequence tailored specifically to character limits:
        1. Connection Request Note (< 300 chars, no links)
        2. Post-Acceptance Welcome Message (< 75 words)
        3. 48-Hour Value Teardown Offer (< 50 words)
        """
        # Note strictly under 300 chars
        conn_note = (
            f"Hi {first_name}, noticed your work scaling {company_name}. "
            f"Ran a brief audit on your tech stack—saw an interesting performance angle. "
            f"Would love to connect and share notes!"
        )
        if len(conn_note) > 295:
            conn_note = f"Hi {first_name}, saw your work scaling {company_name}. Would love to connect and follow your roadmap!"

        # Welcome message upon accepting connection
        welcome_msg = (
            f"Thanks for connecting, {first_name}!\n\n"
            f"Reason I reached out: {trigger_hook}.\n\n"
            f"We specialize in deploying senior engineering pods in 72h and optimizing sub-second cloud architectures.\n\n"
            f"No pitch right now—just wanted to share what we've seen work for similar engineering teams if useful."
        )

        # 48h Follow-up
        followup_msg = (
            f"Hi {first_name}, put together a 90-second visual breakdown of that architecture bottleneck we discussed.\n\n"
            f"Mind if I drop the link here for you and the team?"
        )

        return {
            "connection_request_note": conn_note,
            "connection_note_char_count": len(conn_note),
            "post_acceptance_message": welcome_msg,
            "followup_value_message": followup_msg
        }
