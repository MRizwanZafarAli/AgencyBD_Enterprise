"""
Sovereign Universal Scraper & Fit-Markdown Perception Engine for AgencyBD Enterprise.
Inspired by Crawl4AI and Firecrawl architectures.
Renders dynamic client-side SPAs using local Chromium, cleans DOM boilerplate, generates
token-efficient Fit-Markdown, extracts structured Pydantic entities, and triggers HITL on challenges.
"""

import re
import time
import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup, Comment
from pydantic import BaseModel, Field

from core.logger import get_enterprise_logger
from engines.native_browser_service import NativeBrowserService
from net.fetcher import SafeFetcher, SSRFSecurityError
from net.validate import clean_domain
from database.db import get_db

logger = get_enterprise_logger("UniversalScraper")

# Hook definitions for scraper lifecycle
HOOK_SCRAPE_REQUESTED = "on_scrape_requested"
HOOK_CHALLENGE_DETECTED = "on_challenge_detected"
HOOK_MARKDOWN_EXTRACTED = "on_markdown_extracted"
HOOK_STRUCTURED_DATA_PERSISTED = "on_structured_data_persisted"


class ScrapeResult(BaseModel):
    url: str
    domain: str
    title: str
    fit_markdown: str
    raw_html_length: int
    markdown_length: int
    compression_ratio: float
    challenge_detected: bool = False
    challenge_type: Optional[str] = None
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    developer_audit: Dict[str, Any] = Field(default_factory=dict)
    mode: str = "general"
    duration_ms: float = 0.0
    status: str = "success"


class UniversalScraperEngine:
    """
    Sovereign AI-First Universal Scraper.
    Zero external SaaS dependencies, $0 operating overhead, fully SSRF-protected.
    """

    CHALLENGE_SIGNATURES = {
        "cloudflare_turnstile": ["challenges.cloudflare.com/turnstile", "cf-turnstile", "cf-challenge"],
        "cloudflare_ray": ["cf-ray", "attention required! | cloudflare", "just a moment..."],
        "recaptcha": ["google.com/recaptcha", "g-recaptcha"],
        "hcaptcha": ["hcaptcha.com", "h-captcha"],
        "datadome": ["datadome", "geo.captcha-delivery.com"],
        "perimeterx": ["px-captcha", "perimeterx"],
        "login_wall": ["sign in to continue", "log in to continue", "please authenticate"],
    }

    BOILERPLATE_TAGS = {"script", "style", "noscript", "svg", "canvas", "iframe", "nav", "footer", "header"}
    BOILERPLATE_SELECTORS = [
        "[class*='cookie']", "[id*='cookie']",
        "[class*='consent']", "[id*='consent']",
        "[class*='banner']", "[id*='banner']",
        "[class*='popup']", "[id*='popup']",
        "[class*='modal']", "[id*='modal']",
        "[class*='advertisement']", "[class*='adsbygoogle']",
        "header", "footer", "nav",
    ]

    def __init__(self):
        self.browser_service = NativeBrowserService()

    def detect_challenges(self, html: str) -> Tuple[bool, Optional[str]]:
        """Detects whether target page presented an anti-bot challenge or login gate."""
        html_lower = html.lower()
        for challenge_type, patterns in self.CHALLENGE_SIGNATURES.items():
            if any(p in html_lower for p in patterns):
                return True, challenge_type
        return False, None

    def sanitize_html(self, html: str) -> BeautifulSoup:
        """Strips scripts, styles, tracking tags, and noise elements."""
        soup = BeautifulSoup(html, "html.parser")

        # 1. Strip raw boilerplate tags
        for tag in soup.find_all(self.BOILERPLATE_TAGS):
            tag.decompose()

        # 2. Strip comments
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()

        # 3. Strip layout and banner elements
        for selector in self.BOILERPLATE_SELECTORS:
            try:
                for el in soup.select(selector):
                    el.decompose()
            except Exception:
                continue

        return soup

    def html_to_markdown(self, soup: BeautifulSoup) -> str:
        """
        Converts sanitized DOM tree to clean, token-efficient GitHub Flavored Markdown.
        Inspired by Crawl4AI's Fit-Markdown generator.
        """
        lines: List[str] = []

        # Target primary content container if present, else body
        body = soup.find("main") or soup.find("article") or soup.find("body") or soup

        for el in body.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "table", "pre", "blockquote"]):
            tag = el.name
            text = el.get_text().strip()
            if not text:
                continue

            if tag == "h1":
                lines.append(f"\n# {text}\n")
            elif tag == "h2":
                lines.append(f"\n## {text}\n")
            elif tag == "h3":
                lines.append(f"\n### {text}\n")
            elif tag == "h4":
                lines.append(f"\n#### {text}\n")
            elif tag == "p":
                lines.append(f"{text}\n")
            elif tag in ("ul", "ol"):
                for li in el.find_all("li"):
                    li_text = li.get_text().strip()
                    if li_text:
                        lines.append(f"- {li_text}")
                lines.append("")
            elif tag == "pre":
                lines.append(f"```\n{text}\n```\n")
            elif tag == "blockquote":
                lines.append(f"> {text}\n")
            elif tag == "table":
                # Convert table rows to GFM table
                rows = el.find_all("tr")
                if rows:
                    for i, row in enumerate(rows):
                        cols = [c.get_text().strip() for c in row.find_all(["th", "td"])]
                        if cols:
                            lines.append("| " + " | ".join(cols) + " |")
                            if i == 0:
                                lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
                    lines.append("")

        md = "\n".join(lines)
        # Collapse multiple empty lines into at most 2
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        return md

    def filter_relevance(self, markdown: str, keywords: List[str]) -> str:
        """
        Filters markdown sections by BM25/keyword relevance.
        Preserves only sections matching target topics (e.g. pricing, leadership, team).
        """
        if not keywords:
            return markdown

        sections = markdown.split("\n\n")
        scored_sections = []
        kw_lower = [k.lower().strip() for k in keywords]

        for s in sections:
            s_lower = s.lower()
            score = sum(s_lower.count(k) for k in kw_lower)
            if score > 0 or s.startswith("#"):
                scored_sections.append(s)

        if not scored_sections:
            return markdown
        return "\n\n".join(scored_sections)

    def extract_structured_entities(self, soup: BeautifulSoup, html: str, md: str, domain: str) -> Dict[str, Any]:
        """Extracts high-value RevOps entities: leadership, emails, stack, pricing, and hiring signals."""
        from engines.native_browser_service import NativeBrowserService
        svc = self.browser_service

        dom_intel = svc._extract_dom_intelligence(html, domain, "universal_scraper")

        # 1. Leadership and Team Contacts
        team_members = []
        for match in re.finditer(r"(?:meet our team|leadership|executive team|about us)(.*?)(?=\n##|\Z)", md, re.I | re.S):
            snippet = match.group(1)
            # Find names and titles
            for line in snippet.split("\n"):
                line_clean = line.strip().lstrip("-*# ")
                if line_clean and len(line_clean) < 80 and not line_clean.startswith("http"):
                    if any(t in line_clean.lower() for t in ["ceo", "cto", "vp", "founder", "director", "head of", "engineer"]):
                        team_members.append(line_clean)

        # 2. Pricing Tiers Detection
        pricing_tiers = []
        for match in re.finditer(r"(?:pricing|starter|pro|enterprise|growth|tier|annual|monthly)(.*?)(?=\n##|\Z)", md, re.I | re.S):
            p_snippet = match.group(1)
            prices = re.findall(r"\$\d+(?:,\d+)*(?:\.\d+)?(?:\s*/\s*(?:mo|month|yr|year))?", p_snippet)
            if prices:
                pricing_tiers.extend(prices[:4])

        # 3. Hiring & Careers Signals
        hiring_roles = []
        for match in re.finditer(r"(?:open positions|careers|we're hiring|join us)(.*?)(?=\n##|\Z)", md, re.I | re.S):
            c_snippet = match.group(1)
            for line in c_snippet.split("\n"):
                l_clean = line.strip().lstrip("-*# ")
                if l_clean and any(role in l_clean.lower() for role in ["engineer", "developer", "designer", "product", "manager", "architect"]):
                    hiring_roles.append(l_clean)

        # 4. Expert Developer Technical Audit
        gaps = []
        has_title = bool(dom_intel.get("title"))
        has_desc = bool(dom_intel.get("meta_description"))
        has_og = bool(soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"}))
        has_viewport = bool(soup.find("meta", attrs={"name": "viewport"}))
        has_canonical = bool(soup.find("link", rel="canonical"))
        missing_alts = len(soup.find_all("img", alt="")) + len(soup.find_all("img", alt=False))

        if not has_desc:
            gaps.append("Missing meta description (hurts organic SEO click-through rate)")
        if not has_og:
            gaps.append("Missing OpenGraph preview image (poor link sharing previews)")
        if not has_viewport:
            gaps.append("Missing mobile viewport configuration tag")
        if missing_alts > 2:
            gaps.append(f"{missing_alts} image(s) missing accessibility alt attributes")
        if not dom_intel.get("emails") and not dom_intel.get("phones"):
            gaps.append("No direct public contact email or phone found on landing page")

        health_score = max(35, 100 - (len(gaps) * 15))

        dev_audit = {
            "health_score": health_score,
            "cms_frameworks": dom_intel.get("detected_stack", ["Modern Web Architecture"]),
            "seo_audit": {
                "has_title": has_title,
                "title_length": len(dom_intel.get("title", "")),
                "has_meta_description": has_desc,
                "has_og_image": has_og,
                "has_viewport": has_viewport,
                "has_canonical": has_canonical,
            },
            "technical_gaps": gaps,
            "recommended_hook": (
                f"We performed a technical scan of {domain} and noticed {gaps[0].lower()}."
                if gaps else f"We analyzed {domain}'s architecture ({', '.join(dom_intel.get('detected_stack', ['modern stack']))}) and identified high-impact scaling opportunities."
            ),
        }

        return {
            "title": dom_intel.get("title", ""),
            "meta_description": dom_intel.get("meta_description", ""),
            "emails": dom_intel.get("emails", []),
            "phones": dom_intel.get("phones", []),
            "linkedin_urls": dom_intel.get("linkedin_urls", []),
            "detected_stack": dom_intel.get("detected_stack", []),
            "leadership_mentions": team_members[:6],
            "pricing_signals": list(set(pricing_tiers)),
            "open_roles": hiring_roles[:8],
            "developer_audit": dev_audit,
        }

    def scrape_url(
        self,
        target: str,
        query_keywords: Optional[List[str]] = None,
        mode: str = "general",
        org_id: str = "org_default",
    ) -> ScrapeResult:
        """
        Executes sovereign scrape: SSRF validation -> headless render -> challenge check
        -> Fit-Markdown conversion -> entity extraction -> persistent database storage.
        Adapts extraction filtering and developer audit based on mode (client_audit, job_spec, local_audit).
        """
        start_time = time.time()
        clean_host = clean_domain(target)
        target_url = f"https://{clean_host}" if not target.startswith("http") else target
        
        # Mode-tailored keyword defaults if not explicitly provided
        if not query_keywords:
            if mode == "job_spec":
                query_keywords = ["requirements", "qualifications", "responsibilities", "skills", "tech stack", "budget", "salary", "experience", "role", "deliverables"]
            elif mode == "client_audit":
                query_keywords = ["technology", "stack", "services", "pricing", "leadership", "team", "security", "api", "about", "contact", "performance"]
            elif mode == "local_audit":
                query_keywords = ["services", "contact", "phone", "hours", "booking", "location", "pricing", "reviews"]
        
        # 1. Validate SSRF
        self.browser_service._validate_ssrf_for_url(target_url)

        # Emit hook
        try:
            from core.hooks import event_bus
            event_bus.emit(HOOK_SCRAPE_REQUESTED, {"url": target_url, "domain": clean_host, "org_id": org_id})
        except Exception:
            pass

        # 2. Render Virtual DOM
        dom_data = self.browser_service.render_spa_dom(target_url)
        if dom_data.get("status") == "unreachable":
            err_msg = dom_data.get("error", f"Unable to establish secure connection to {clean_host}.")
            return ScrapeResult(
                url=target_url,
                domain=clean_host,
                title=f"Unreachable: {clean_host}",
                fit_markdown=f"### Site Unreachable\n\n`{clean_host}` could not be scraped automatically.\n\n**Reason:** {err_msg}\n\nTry opening the site in the Native Chrome Popout Window to inspect whether it uses legacy TLS/SSL or blocks automated handshakes.",
                raw_html_length=0,
                markdown_length=0,
                compression_ratio=0.0,
                challenge_detected=False,
                challenge_type=None,
                extracted_data={"error": err_msg},
                developer_audit={
                    "health_score": 0,
                    "cms_frameworks": [],
                    "seo_audit": {"has_title": False, "has_meta_description": False, "has_og_image": False, "has_viewport": False},
                    "technical_gaps": [f"TLS / Network Handshake Failure: {err_msg}"],
                    "recommended_hook": f"Hi team — I tried reviewing {clean_host} and noticed an SSL/TLS handshake error preventing automated and modern client connections. Worth a quick check on your certificate/TLS config.",
                },
                mode=mode,
                duration_ms=round((time.time() - start_time) * 1000, 2),
                status="unreachable",
            )

        html = ""
        # If render_spa_dom returned, fetch full html via SafeFetcher for deep parsing
        try:
            fetch_res = SafeFetcher.safe_fetch(target_url, timeout=8)
            html = fetch_res.text
        except Exception:
            html = f"<html><head><title>{dom_data.get('title', clean_host)}</title></head><body><h1>{dom_data.get('title', clean_host)}</h1><p>{dom_data.get('meta_description', '')}</p></body></html>"

        # 3. Challenge Radar
        has_challenge, challenge_type = self.detect_challenges(html)
        if has_challenge:
            logger.warning(f"Anti-bot challenge detected on {clean_host}: {challenge_type}")
            try:
                from core.hooks import event_bus
                event_bus.emit(HOOK_CHALLENGE_DETECTED, {
                    "url": target_url,
                    "domain": clean_host,
                    "challenge_type": challenge_type,
                    "org_id": org_id,
                })
            except Exception:
                pass

        # 4. Generate Clean Fit-Markdown
        soup = self.sanitize_html(html)
        title = soup.title.string.strip() if soup.title and soup.title.string else dom_data.get("title", clean_host)
        markdown = self.html_to_markdown(soup)
        
        if query_keywords:
            markdown = self.filter_relevance(markdown, query_keywords)

        # 5. Extract Structured Entities
        entities = self.extract_structured_entities(soup, html, markdown, clean_host)

        duration_ms = (time.time() - start_time) * 1000.0
        raw_len = len(html)
        md_len = len(markdown)
        ratio = round((raw_len - md_len) / max(raw_len, 1) * 100, 1)

        result = ScrapeResult(
            url=target_url,
            domain=clean_host,
            title=title,
            fit_markdown=markdown,
            raw_html_length=raw_len,
            markdown_length=md_len,
            compression_ratio=ratio,
            challenge_detected=has_challenge,
            challenge_type=challenge_type,
            extracted_data=entities,
            developer_audit=entities.get("developer_audit", {}),
            mode=mode,
            duration_ms=duration_ms,
            status="challenge_blocked" if has_challenge else "success",
        )

        # 6. Persistent DB Storage
        self._persist_scraped_page(result, org_id)

        # 7. Emit Completion Hooks
        try:
            from core.hooks import event_bus
            event_bus.emit(HOOK_MARKDOWN_EXTRACTED, {
                "url": target_url,
                "domain": clean_host,
                "markdown_length": md_len,
                "compression_ratio": ratio,
                "org_id": org_id,
            })
            event_bus.emit(HOOK_STRUCTURED_DATA_PERSISTED, {
                "domain": clean_host,
                "entities_count": len(entities),
                "org_id": org_id,
            })
        except Exception:
            pass

        return result

    def _persist_scraped_page(self, res: ScrapeResult, org_id: str):
        try:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO scraped_pages (
                        org_id, url, domain, title, fit_markdown,
                        extracted_json, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(org_id, url) DO UPDATE SET
                        fit_markdown = excluded.fit_markdown,
                        extracted_json = excluded.extracted_json,
                        title = excluded.title,
                        status = excluded.status,
                        created_at = CURRENT_TIMESTAMP
                    """,
                    (
                        org_id,
                        res.url,
                        res.domain,
                        res.title,
                        res.fit_markdown,
                        json.dumps(res.extracted_data),
                        res.status,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not persist scraped page to DB: {e}")


# Global Singleton Instance
universal_scraper = UniversalScraperEngine()
