"""
NativeBrowserService: Sovereign Headless Chrome & Browser Automation Engine.

Renders full virtual DOM of JavaScript Single Page Apps (React, Next.js, Vue),
captures high-fidelity screenshots (desktop & mobile) for proposal teardowns,
extracts obfuscated emails/phones, and performs real client-side tech fingerprinting.
Enforces strict SSRF protection before any browser navigation.
"""

import base64
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from bs4 import BeautifulSoup
from net.fetcher import _check_ip, SafeFetcher, SSRFSecurityError
from net.egress_proxy import EgressProxy
from net.process_supervisor import ProcessSupervisor
from net.validate import clean_domain, is_valid_hostname


class NativeBrowserService:
    """
    Sovereign browser engine utilizing local headless Chromium/Chrome
    to inspect and audit dynamic client-side web applications.
    """

    CHROME_CANDIDATE_PATHS = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ]

    EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    OBFUSCATED_AT_REGEX = re.compile(
        r'([a-zA-Z0-9_.+-]+)\s*(?:\[at\]|\(at\)|\s+at\s+)\s*([a-zA-Z0-9-]+)\s*(?:\[dot\]|\(dot\)|\s+dot\s+)\s*([a-zA-Z0-9-.]+)',
        re.IGNORECASE
    )
    PHONE_REGEX = re.compile(r'(?:\+?1[-. ]?)?\(?[0-9]{3}\)?[-. ]?[0-9]{3}[-. ]?[0-9]{4}')
    LINKEDIN_REGEX = re.compile(r'https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_.-]+')

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.path.join("data", "screenshots"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.chrome_binary = self._resolve_chrome_binary()

    def _resolve_chrome_binary(self) -> Optional[str]:
        for candidate in self.CHROME_CANDIDATE_PATHS:
            if candidate.startswith("/"):
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    return candidate
            else:
                found = shutil.which(candidate)
                if found:
                    return found
        return None

    @staticmethod
    def _sandbox_flags() -> list:
        """Chrome's sandbox stays ON. It can only be disabled explicitly (needed when running as root in a container)."""
        import os as _os
        root = hasattr(_os, "geteuid") and _os.geteuid() == 0
        return ["--no-sandbox"] if (root or _os.getenv("AGENCYBD_BROWSER_NO_SANDBOX", "off").lower() in ("on", "true", "1")) else []

    @staticmethod
    def _proxy_flags(proxy: "EgressProxy") -> list:
        # All traffic, including redirects and sub-resources, goes through the filtering proxy; loopback is NOT bypassed.
        return [f"--proxy-server={proxy.url}", "--proxy-bypass-list=<-loopback>"]

    def is_browser_available(self) -> bool:
        return self.chrome_binary is not None

    def _validate_ssrf_for_url(self, target_url: str) -> str:
        """
        Validates hostname against SSRF policy prior to browser invocation.
        Returns the sanitized URL.
        """
        parsed = urllib.parse.urlparse(target_url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise SSRFSecurityError(f"Unsupported scheme '{scheme}' for browser navigation")

        host = parsed.hostname
        if not host:
            raise SSRFSecurityError("Missing hostname in target URL")

        # Resolve IP and verify it is a globally routable public address
        try:
            addr_infos = socket.getaddrinfo(host, parsed.port or (443 if scheme == "https" else 80), socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not addr_infos:
                raise SSRFSecurityError(f"Could not resolve host {host}")
            for family, socktype, proto, _canon, sockaddr in addr_infos:
                ip_str = sockaddr[0]
                _check_ip(ip_str)
        except (socket.gaierror, socket.herror) as e:
            raise SSRFSecurityError(f"DNS resolution failed for {host}: {e}")

        return target_url

    def render_spa_dom(self, domain_or_url: str, timeout_seconds: int = 8) -> Dict[str, Any]:
        """
        Navigates headless Chrome to the target URL, executes JavaScript (virtual-time-budget),
        and returns the fully rendered virtual DOM with extracted intelligence.
        Falls back to SafeFetcher if Chrome is unavailable.
        """
        clean_host = clean_domain(domain_or_url)
        target_url = f"https://{clean_host}" if not domain_or_url.startswith("http") else domain_or_url
        self._validate_ssrf_for_url(target_url)

        html = ""
        rendered_by = "native_chrome"

        if self.chrome_binary:
            try:
                with EgressProxy() as proxy:
                    cmd = [self.chrome_binary, "--headless=new", "--disable-gpu", *self._sandbox_flags(), "--disable-dev-shm-usage",
                           *self._proxy_flags(proxy), "--virtual-time-budget=4000", "--timeout=8000", "--dump-dom", target_url]
                    res = ProcessSupervisor.run_confined(cmd, timeout_seconds=timeout_seconds)
                if res.returncode == 0 and len(res.stdout) > 200:
                    html = res.stdout
                else:
                    html = SafeFetcher.safe_fetch(target_url, timeout=5).text
                    rendered_by = "safe_fetcher_fallback"
            except SSRFSecurityError:
                raise
            except Exception:
                html = SafeFetcher.safe_fetch(target_url, timeout=5).text
                rendered_by = "safe_fetcher_fallback"
        else:
            html = SafeFetcher.safe_fetch(target_url, timeout=5).text
            rendered_by = "safe_fetcher_direct"

        return self._extract_dom_intelligence(html, clean_host, rendered_by)

    def capture_screenshot(
        self,
        domain_or_url: str,
        viewport: str = "desktop",
        timeout_seconds: int = 10
    ) -> Dict[str, Any]:
        """
        Captures a high-resolution screenshot of the target URL.
        Viewports: 'desktop' (1440x900) or 'mobile' (375x812).
        Returns disk file path and base64 data URI for instant web display.
        """
        clean_host = clean_domain(domain_or_url)
        target_url = f"https://{clean_host}" if not domain_or_url.startswith("http") else domain_or_url
        self._validate_ssrf_for_url(target_url)

        viewport_dims = "375,812" if viewport == "mobile" else "1440,900"
        filename = f"{clean_host.replace('.', '_')}_{viewport}.png"
        out_path = self.storage_dir / filename

        if not self.chrome_binary:
            return {
                "status": "unavailable",
                "message": "Headless Chrome binary not found on host system",
                "file_path": None,
                "data_uri": None
            }

        with EgressProxy() as proxy:
            cmd = [self.chrome_binary, "--headless=new", "--disable-gpu", *self._sandbox_flags(), "--disable-dev-shm-usage",
                   *self._proxy_flags(proxy), f"--window-size={viewport_dims}", f"--screenshot={out_path}", "--virtual-time-budget=3000", target_url]
            res = ProcessSupervisor.run_confined(cmd, timeout_seconds=timeout_seconds)
        if out_path.exists() and out_path.stat().st_size > 1000:
            with open(out_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
            return {
                "status": "success",
                "domain": clean_host,
                "viewport": viewport,
                "file_path": str(out_path),
                "file_size_bytes": out_path.stat().st_size,
                "data_uri": f"data:image/png;base64,{b64_data}"
            }
        elif res.timed_out:
            return {
                "status": "timeout",
                "error": f"Screenshot timed out after {timeout_seconds}s",
                "file_path": None,
                "data_uri": None
            }
        else:
            return {
                "status": "failed",
                "error": res.stderr if res.stderr else "Unknown screenshot error",
                "file_path": None,
                "data_uri": None
            }

    def _extract_dom_intelligence(self, html: str, host: str, rendered_by: str) -> Dict[str, Any]:
        """Extracts structured contact info, metadata, and detected stack from rendered DOM."""
        soup = BeautifulSoup(html, "html.parser")

        # 1. Email Extraction (mailto + regex + obfuscated [at])
        emails: Set[str] = set()
        for a in soup.select('a[href^="mailto:"]'):
            href = a.get("href", "")
            raw = href.replace("mailto:", "").split("?")[0].strip().lower()
            if raw and "@" in raw:
                emails.add(raw)

        for match in self.EMAIL_REGEX.findall(html):
            clean = match.strip().lower()
            if not clean.endswith((".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp")):
                emails.add(clean)

        for match in self.OBFUSCATED_AT_REGEX.findall(html):
            reassembled = f"{match[0]}@{match[1]}.{match[2]}".lower().strip()
            emails.add(reassembled)

        # 2. Phone Extraction
        phones: Set[str] = set()
        for a in soup.select('a[href^="tel:"]'):
            tel = a.get("href", "").replace("tel:", "").strip()
            if tel:
                phones.add(tel)
        for match in self.PHONE_REGEX.findall(html):
            phones.add(match.strip())

        # 3. Social & LinkedIn Links
        linkedin_urls: Set[str] = set()
        for match in self.LINKEDIN_REGEX.findall(html):
            linkedin_urls.add(match)

        # 4. Tech Stack Signatures
        detected_stack: List[str] = []
        html_lower = html.lower()
        signatures = {
            "Next.js": ["__next", "next/dist", "_next/static"],
            "React": ["react", "data-reactroot"],
            "Vue.js": ["data-v-", "__vue__"],
            "Nuxt.js": ["__nuxt"],
            "Angular": ["ng-version", "_nghost"],
            "WordPress": ["wp-content", "wp-includes"],
            "Shopify": ["cdn.shopify.com", "myshopify.com"],
            "Webflow": ["assets.website-files.com", "w-nav"],
            "Tailwind CSS": ["tailwindcss", "class=\"tw-"],
            "Google Tag Manager": ["googletagmanager.com/gtm.js"],
            "HubSpot": ["js.hs-scripts.com", "hs-analytics"],
            "Stripe": ["js.stripe.com"],
            "Intercom": ["widget.intercom.io"]
        }
        for tech, patterns in signatures.items():
            if any(p in html_lower for p in patterns):
                detected_stack.append(tech)

        # 5. Page Title and Meta Description
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"].strip()

        # 6. Primary Headings
        headings = [h.get_text().strip() for h in soup.find_all(["h1", "h2"]) if h.get_text().strip()][:5]

        return {
            "status": "success",
            "domain": host,
            "rendered_by": rendered_by,
            "html_length": len(html),
            "title": title,
            "meta_description": meta_desc,
            "headings": headings,
            "emails": sorted(list(emails)),
            "phones": sorted(list(phones)),
            "linkedin_urls": sorted(list(linkedin_urls)),
            "detected_stack": detected_stack,
            "has_react": "React" in detected_stack or "Next.js" in detected_stack,
            "has_contact_form": bool(soup.find("form")),
        }
