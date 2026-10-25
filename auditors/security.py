"""
Security-posture auditor. Passive only: it reads what the server sends to any visitor (headers, TLS handshake, page
markup). It never probes paths, submits forms or attempts exploitation.
"""

import re
from typing import Any, Dict, List

from auditors.base import AuditFinding
from auditors.context import SiteContext


def _php_version(text: str):
    m = re.search(r"PHP/(\d+)\.(\d+)", text or "", re.IGNORECASE)
    return (int(m.group(1)), int(m.group(2))) if m else None


def certificate_findings(tls: Dict[str, Any]) -> List[AuditFinding]:
    """Findings from a TLS inspection alone. Usable even when the site's pages cannot be read."""
    f: List[AuditFinding] = []
    if tls.get("valid") is False:
        f.append(AuditFinding("security", "tls_certificate_invalid", "critical",
                              f"The HTTPS certificate fails validation: {tls.get('error')}.",
                              "Reissue a valid certificate for this hostname and install the full chain.",
                              "Browsers show a full-page security warning to visitors.", "security_hardening",
                              f"TLS verification error: {tls.get('error')} (code {tls.get('verify_code')})."))
    elif tls.get("valid"):
        days = tls["days_remaining"]
        if days < 30:
            f.append(AuditFinding("security", "tls_certificate_expiring", "high" if days < 14 else "medium",
                                  f"The HTTPS certificate expires in {days} days ({tls['not_after']}).",
                                  "Renew the certificate and automate renewal (certbot/ACME).",
                                  "An expired certificate takes the site offline for most visitors.", "security_hardening",
                                  f"Certificate notAfter: {tls['not_after']}; issuer: {tls.get('issuer')}."))
    return f


class SecurityAuditor:
    @staticmethod
    def audit(ctx: SiteContext) -> List[AuditFinding]:
        f: List[AuditFinding] = []
        h = ctx.lower_headers
        https = ctx.scheme == "https"

        if not https:
            f.append(AuditFinding("security", "no_https", "critical", "The site is served over plain HTTP, not HTTPS.",
                                  "Install a TLS certificate (free via Let's Encrypt) and redirect all traffic to HTTPS.",
                                  "Browsers label the site 'Not secure'; anything visitors type can be read in transit.",
                                  "security_hardening", f"Final URL: {ctx.url}"))
        else:
            if ctx.http_to_https is False:
                f.append(AuditFinding("security", "no_https_redirect", "medium", "http:// does not redirect to https://.",
                                      "Redirect all HTTP requests to HTTPS with a 301.", "Visitors who type the bare address stay on an insecure connection.",
                                      "security_hardening", "GET http://<domain>/ ended on an http:// URL."))
            f.extend(certificate_findings(ctx.tls or {}))
            if "strict-transport-security" not in h:
                f.append(AuditFinding("security", "missing_hsts", "medium", "No HSTS header (Strict-Transport-Security).",
                                      "Send Strict-Transport-Security: max-age=31536000; includeSubDomains once HTTPS works everywhere.",
                                      "Browsers will not force HTTPS on return visits, leaving a window for downgrade attacks.",
                                      "security_hardening", "Header 'Strict-Transport-Security' not present."))
            mixed = [t for t in ctx.soup.find_all(["script", "link", "iframe", "img"])
                     if str(t.get("src") or t.get("href") or "").startswith("http://")]
            active = [t for t in mixed if t.name in ("script", "iframe") or (t.name == "link" and "stylesheet" in (t.get("rel") or []))]
            if mixed:
                f.append(AuditFinding("security", "mixed_content", "high" if active else "medium",
                                      f"The HTTPS page loads {len(mixed)} resource(s) over insecure HTTP ({len(active)} scripts/styles/frames).",
                                      "Change those URLs to https:// or relative paths.",
                                      "Browsers may block them (breaking features) and the page loses its secure indicator.",
                                      "security_hardening", "; ".join(str(t.get('src') or t.get('href')) for t in mixed[:3])))

        if "content-security-policy" not in h:
            f.append(AuditFinding("security", "missing_csp", "medium", "No Content-Security-Policy header.",
                                  "Add a CSP, starting in report-only mode, to restrict where scripts can load from.",
                                  "Reduces the damage if an attacker manages to inject script (XSS).", "security_hardening",
                                  "Header 'Content-Security-Policy' not present."))
        if "x-frame-options" not in h and "frame-ancestors" not in h.get("content-security-policy", ""):
            f.append(AuditFinding("security", "missing_x_frame_options", "low", "Pages can be embedded in other sites' frames (no clickjacking protection).",
                                  "Send X-Frame-Options: SAMEORIGIN or CSP frame-ancestors 'self'.",
                                  "Another site could overlay your page in a hidden frame to trick clicks.", "security_hardening",
                                  "Neither X-Frame-Options nor CSP frame-ancestors present."))
        if "x-content-type-options" not in h:
            f.append(AuditFinding("security", "missing_content_type_options", "low", "No X-Content-Type-Options: nosniff header.",
                                  "Send X-Content-Type-Options: nosniff.", "Browsers may second-guess declared file types.",
                                  "security_hardening", "Header 'X-Content-Type-Options' not present."))
        if "referrer-policy" not in h:
            f.append(AuditFinding("security", "missing_referrer_policy", "info", "No Referrer-Policy header.",
                                  "Send Referrer-Policy: strict-origin-when-cross-origin.", "Full page URLs may leak to other sites via the Referer header.",
                                  "security_hardening", "Header 'Referrer-Policy' not present.", confidence=0.9))
        php = _php_version(h.get("x-powered-by", "") + " " + h.get("server", ""))
        if php and php < (8, 2):
            f.append(AuditFinding("security", "end_of_life_php", "high", f"The server advertises PHP {php[0]}.{php[1]}, which no longer receives security fixes.",
                                  "Upgrade to a supported PHP release (see php.net/supported-versions.php) and hide version banners.",
                                  "Known vulnerabilities in old PHP versions stay unpatched.", "security_hardening",
                                  f"X-Powered-By/Server: {h.get('x-powered-by') or h.get('server')}"))
        return f
