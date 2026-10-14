"""
SiteCrawlerAgent: Deep Website & Leadership Extraction Engine.
Crawls homepage, /about, /team, and /contact pages to discover direct emails,
phone numbers, leadership names, and embedded LinkedIn profiles.
"""

import re
import urllib.parse
from typing import Dict, Any, List, Set
from net.fetcher import SafeFetcher, SSRFSecurityError
from net.validate import clean_domain as _clean_domain
from bs4 import BeautifulSoup
from config.honesty import NotConfiguredError, PreconditionFailedError

class SiteCrawlerAgent:
    """
    Crawls target company domains to extract real emails, phone numbers,
    team member names, and LinkedIn URLs directly from their website DOM.
    """

    EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    PHONE_REGEX = re.compile(r'\(?\b[0-9]{3}\)?[-. ]?[0-9]{3}[-. ]?[0-9]{4}\b')
    LINKEDIN_REGEX = re.compile(r'https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_-]+')

    def __init__(self):
        pass  # network access goes through net.fetcher.SafeFetcher

    def crawl_domain(self, domain: str) -> Dict[str, Any]:
        """
        Crawls the domain and key pages to extract contact details and team info.
        """
        clean_domain = _clean_domain(domain)
        base_url = f"https://{clean_domain}"

        found_emails: Set[str] = set()
        found_phones: Set[str] = set()
        found_linkedin_urls: Set[str] = set()
        leadership_candidates: List[str] = []

        subpaths = ["", "/about", "/team", "/contact", "/leadership"]

        for path in subpaths:
            target_url = f"{base_url}{path}"
            try:
                resp = SafeFetcher.safe_fetch(target_url, timeout=4)
                if resp.status_code != 200:
                    continue

                html = resp.text
                soup = BeautifulSoup(html, "html.parser")

                # 1. Extract mailto: links
                for mailto in soup.select('a[href^="mailto:"]'):
                    href = mailto.get("href", "")
                    clean_email = href.replace("mailto:", "").split("?")[0].strip().lower()
                    if clean_email and clean_domain in clean_email:
                        found_emails.add(clean_email)

                # 2. Extract regex emails
                for match in self.EMAIL_REGEX.findall(html):
                    clean_match = match.strip().lower()
                    # Skip common static assets like image@2x.png or fonts
                    if not clean_match.endswith((".png", ".jpg", ".svg", ".js", ".css")) and clean_domain in clean_match:
                        found_emails.add(clean_match)

                # 3. Extract tel: links and phones
                for tel in soup.select('a[href^="tel:"]'):
                    p = tel.get("href", "").replace("tel:", "").strip()
                    if len(p) >= 10:
                        found_phones.add(p)

                for phone_match in self.PHONE_REGEX.findall(html):
                    found_phones.add(phone_match.strip())

                # 4. Extract LinkedIn URLs
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    if "linkedin.com" in href:
                        found_linkedin_urls.add(href.strip())

                # 5. Extract team/leadership names from h3, h4 with titles
                for heading in soup.find_all(["h2", "h3", "h4"]):
                    text = heading.get_text().strip()
                    if len(text.split()) in [2, 3] and not any(k in text.lower() for k in ["about", "contact", "services", "menu", "blog", "home"]):
                        # Check if parent or sibling has title like "CEO", "Founder", "CTO"
                        parent_text = heading.parent.get_text().lower() if heading.parent else ""
                        if any(t in parent_text for t in ["cto", "ceo", "founder", "president", "partner", "director", "head of"]):
                            leadership_candidates.append(text)

            except SSRFSecurityError:
                raise
            except Exception:
                continue

        # Only emails actually found on the site are reported.

        return {
            "domain": clean_domain,
            "crawled_urls": [f"{base_url}{p}" for p in subpaths],
            "verified_emails": list(found_emails),
            "phone_numbers": list(found_phones),
            "linkedin_urls": list(found_linkedin_urls),
            "discovered_leaders": list(set(leadership_candidates))[:5]
        }
