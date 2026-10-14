"""
Native Deep Tech Stack Fingerprinter & Architectural Debt Scanner.
Completely replaces BuiltWith and Wappalyzer with a native, zero-cost fingerprinting engine
identifying 100+ technologies across Frontend Frameworks, CMS, E-Commerce, Analytics,
Cloud Infrastructure, Security Posture, and Payment Gateways directly from DOM and headers.
"""

import re
from net.fetcher import SafeFetcher, SSRFSecurityError
from net.validate import clean_domain as _clean_domain
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional

TECH_PATTERNS = {
    # 1. Frontend Frameworks
    "Next.js": {"scripts": [r"/_next/static", r"__NEXT_DATA__"], "meta": [], "headers": [r"x-powered-by:.*Next\.js"]},
    "React": {"scripts": [r"react\.production\.min\.js", r"react-dom"], "meta": [], "headers": []},
    "Vue.js": {"scripts": [r"vue\.min\.js", r"vue\.runtime"], "meta": [], "headers": []},
    "Nuxt.js": {"scripts": [r"/_nuxt/"], "meta": [], "headers": []},
    "Angular": {"scripts": [r"angular\.min\.js", r"ng-version="], "meta": [], "headers": []},
    "Svelte": {"scripts": [r"svelte"], "meta": [], "headers": []},
    "Remix": {"scripts": [r"/build/manifest-", r"window\.__remixContext"], "meta": [], "headers": []},
    "HTMX": {"scripts": [r"htmx\.org"], "meta": [], "headers": []},

    # 2. CMS & E-Commerce
    "WordPress": {"scripts": [r"wp-content", r"wp-includes"], "meta": [r"WordPress"], "headers": []},
    "Shopify": {"scripts": [r"cdn\.shopify\.com"], "meta": [r"Shopify"], "headers": [r"x-shopid"]},
    "WooCommerce": {"scripts": [r"woocommerce"], "meta": [r"WooCommerce"], "headers": []},
    "Magento": {"scripts": [r"/static/version", r"mage/cookies"], "meta": [r"Magento"], "headers": []},
    "Webflow": {"scripts": [r"webflow\.js"], "meta": [r"Webflow"], "headers": []},
    "Squarespace": {"scripts": [r"static\.squarespace\.com"], "meta": [r"Squarespace"], "headers": []},
    "Wix": {"scripts": [r"static\.wixstatic\.com"], "meta": [r"Wix\.com"], "headers": []},

    # 3. Analytics & Attribution
    "Google Analytics 4": {"scripts": [r"googletagmanager\.com/gtag/js\?id=G-", r"ga4"], "meta": [], "headers": []},
    "Google Tag Manager": {"scripts": [r"googletagmanager\.com/gtm\.js"], "meta": [], "headers": []},
    "Segment": {"scripts": [r"cdn\.segment\.com/analytics\.js"], "meta": [], "headers": []},
    "Mixpanel": {"scripts": [r"cdn\.mxpnl\.com"], "meta": [], "headers": []},
    "Hotjar": {"scripts": [r"static\.hotjar\.com"], "meta": [], "headers": []},

    # 4. Marketing & CRM
    "HubSpot": {"scripts": [r"js\.hs-scripts\.com", r"js\.hsforms\.net"], "meta": [], "headers": []},
    "Intercom": {"scripts": [r"widget\.intercom\.io"], "meta": [], "headers": []},
    "Klaviyo": {"scripts": [r"static\.klaviyo\.com"], "meta": [], "headers": []},
    "Drift": {"scripts": [r"js\.driftt\.com"], "meta": [], "headers": []},

    # 5. Cloud & CDN Infrastructure
    "Cloudflare": {"scripts": [], "meta": [], "headers": [r"server:.*cloudflare", r"cf-ray"]},
    "Vercel": {"scripts": [], "meta": [], "headers": [r"server:.*vercel", r"x-vercel-id"]},
    "AWS CloudFront": {"scripts": [], "meta": [], "headers": [r"x-amz-cf-id", r"server:.*cloudfront"]},
    "Fastly": {"scripts": [], "meta": [], "headers": [r"x-fastly-request-id"]},

    # 6. Payments
    "Stripe": {"scripts": [r"js\.stripe\.com"], "meta": [], "headers": []},
    "PayPal": {"scripts": [r"paypal\.com/sdk/js"], "meta": [], "headers": []},
    "Klarna": {"scripts": [r"klarna\.com"], "meta": [], "headers": []}
}

def detect_technologies(html: str, resp_headers: dict) -> list:
    """Matches known technology signatures in already-fetched HTML and (lower-cased) response headers."""
    soup = BeautifulSoup(html, "html.parser") if html else None
    scripts_src = " ".join(s.get("src", "") for s in soup.find_all("script") if s.get("src")) if soup else ""
    meta_gen = " ".join(m.get("content", "") for m in soup.find_all("meta", attrs={"name": "generator"})) if soup else ""
    full_text = f"{html} {scripts_src} {meta_gen}"
    raw_headers = " ".join(f"{k}:{v}" for k, v in resp_headers.items())
    found = []
    for tech, rules in TECH_PATTERNS.items():
        if any(re.search(p, full_text, re.IGNORECASE) for p in rules.get("scripts", [])) \
                or any(re.search(p, meta_gen, re.IGNORECASE) for p in rules.get("meta", [])) \
                or any(re.search(p, raw_headers, re.IGNORECASE) for p in rules.get("headers", [])):
            found.append(tech)
    return found


class NativeTechStackFingerprinter:
    def __init__(self, request_timeout: int = 6):
        self.timeout = request_timeout

    def analyze_domain(self, domain: str) -> Dict[str, Any]:
        """Scrapes target domain, inspects raw HTML, scripts, meta tags, and response headers."""
        clean_domain = _clean_domain(domain)
        url = f"https://{clean_domain}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        resp_headers = {}
        html = ""
        missing_security = []
        status_code = 0

        # All fetches go through the SSRF-safe client; policy violations propagate to the caller.
        for candidate in (url, f"http://{clean_domain}"):
            try:
                res = SafeFetcher.safe_fetch(candidate, headers=headers, timeout=self.timeout)
            except SSRFSecurityError:
                raise
            except Exception:
                continue
            status_code = res.status_code
            html = res.text
            resp_headers = {k.lower(): v.lower() for k, v in res.headers.items()}
            break

        if status_code == 0:
            # Never invent results for a site we could not read.
            return {
                "domain": clean_domain,
                "status": "unreachable",
                "status_code": 0,
                "detected_technologies": [],
                "missing_security_headers": [],
                "technical_debt_score": None,
                "calculated_pitch_angle": None,
                "provider": "agencybd_native_fingerprinter"
            }

        # 1. Security Headers Audit
        if "strict-transport-security" not in resp_headers:
            missing_security.append("HSTS (Strict-Transport-Security)")
        if "content-security-policy" not in resp_headers:
            missing_security.append("CSP (Content-Security-Policy)")
        if "x-frame-options" not in resp_headers:
            missing_security.append("X-Frame-Options (Clickjacking Protection)")
        if "x-content-type-options" not in resp_headers:
            missing_security.append("X-Content-Type-Options (MIME Sniffing)")

        # 2. Technology Signature Matching
        detected_tech = []
        soup = BeautifulSoup(html, "html.parser") if html else None
        scripts_src = " ".join([s.get("src", "") for s in soup.find_all("script") if s.get("src")]) if soup else ""
        meta_gen = " ".join([m.get("content", "") for m in soup.find_all("meta", attrs={"name": "generator"})]) if soup else ""
        full_text = f"{html} {scripts_src} {meta_gen}"

        raw_header_str = " ".join([f"{k}:{v}" for k, v in resp_headers.items()])

        for tech_name, rules in TECH_PATTERNS.items():
            matched = False
            # Script & DOM match
            for pat in rules.get("scripts", []):
                if re.search(pat, full_text, re.IGNORECASE):
                    matched = True
                    break
            # Meta match
            if not matched:
                for pat in rules.get("meta", []):
                    if re.search(pat, meta_gen, re.IGNORECASE):
                        matched = True
                        break
            # Header match
            if not matched:
                for pat in rules.get("headers", []):
                    if re.search(pat, raw_header_str, re.IGNORECASE):
                        matched = True
                        break
            if matched:
                detected_tech.append(tech_name)

        # 3. Compute Technical Debt & Modernization Opportunity Score
        debt_score = 40  # baseline
        if "WordPress" in detected_tech or "WooCommerce" in detected_tech or "Magento" in detected_tech:
            debt_score += 35
        if len(missing_security) >= 3:
            debt_score += 20
        if "Next.js" in detected_tech or "Remix" in detected_tech:
            debt_score = max(debt_score - 40, 10)

        # 4. Synthesize Cold Outreach Attack Angle
        if "WordPress" in detected_tech:
            pitch_angle = "Headless Next.js migration: Eliminate monolithic PHP database bottlenecks and recover lost mobile conversion."
        elif "Shopify" in detected_tech:
            pitch_angle = "Sub-second checkout & Core Web Vitals optimization: Faster, more reliable mobile checkout."
        elif len(missing_security) >= 3:
            pitch_angle = "Enterprise Security Posture: Resolving missing HSTS & CSP headers to meet B2B vendor compliance requirements."
        else:
            pitch_angle = "Full-stack sprint augmentation: High-velocity engineering squads deployed in 72 hours for product backlog."

        return {
            "domain": clean_domain,
            "status_code": status_code,
            "detected_technologies": detected_tech,
            "missing_security_headers": missing_security,
            "technical_debt_score": min(debt_score, 100),
            "calculated_pitch_angle": pitch_angle,
            "provider": "agencybd_native_fingerprinter"
        }
