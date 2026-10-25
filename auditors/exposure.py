"""
Exposure auditor: what does the site volunteer to every visitor that an attacker would find useful?

Passive only: it reads the homepage response and two standard public files (robots.txt, security.txt). It never requests
guessed paths, never tries logins, never sends payloads. Absence of evidence is reported as unknown, never as clean.
"""

import re
from typing import List

from auditors.base import AuditFinding
from auditors.context import SiteContext

SENSITIVE_PATH = re.compile(r"/(?:admin|administrator|backup|backups|\.git|\.env|phpmyadmin|dbadmin|config|database|db|sql|dump|private|staging|test|old)\b", re.IGNORECASE)
VERSIONED = re.compile(r"\b[\w-]+/\d+(?:\.\d+)+")


class ExposureAuditor:
    @staticmethod
    def audit(ctx: SiteContext) -> List[AuditFinding]:
        f: List[AuditFinding] = []
        h = ctx.lower_headers

        # 1. software version disclosure
        for header in ("server", "x-powered-by", "x-aspnet-version"):
            value = h.get(header, "")
            if value and (VERSIONED.search(value) or header == "x-aspnet-version"):
                f.append(AuditFinding("security", "version_disclosure", "low",
                                      f"The {header} header reveals the exact software version ({value[:60]}).",
                                      "Hide version numbers in the web server and runtime configuration (e.g. ServerTokens Prod, expose_php=Off).",
                                      "Version details make it easier to look up known vulnerabilities for this server.",
                                      "security_hardening", f"{header}: {value[:80]}"))
                break

        # 2. no published security contact
        if ctx.security_txt is False:
            f.append(AuditFinding("security", "missing_security_txt", "info",
                                  "No security.txt: researchers have no published way to report a problem.",
                                  "Publish /.well-known/security.txt with a Contact line (RFC 9116).",
                                  "Reports of real problems may go unseen.", "security_hardening", "/.well-known/security.txt not found", 0.9))

        # 3. robots.txt advertising sensitive-looking paths
        if ctx.robots_txt:
            hits = sorted({m.group(0) for line in ctx.robots_txt.splitlines() if line.lower().startswith("disallow:")
                           for m in [SENSITIVE_PATH.search(line)] if m})
            if hits:
                f.append(AuditFinding("security", "robots_lists_sensitive_paths", "low",
                                      f"robots.txt names sensitive-looking paths ({', '.join(hits[:5])}), which tells everyone where to look.",
                                      "Protect those paths with authentication and remove them from robots.txt; robots.txt is not access control.",
                                      "Lists of hidden areas guide automated scanning.", "security_hardening",
                                      "Disallow: " + ", ".join(hits[:5])))

        # 4. open directory listing on the homepage
        title = (ctx.soup.title.string or "").strip().lower() if ctx.soup.title and ctx.soup.title.string else ""
        if title.startswith("index of /"):
            f.append(AuditFinding("security", "directory_listing", "high",
                                  "The homepage is an open directory listing: files on the server can be browsed.",
                                  "Disable directory indexing (Options -Indexes / autoindex off) and add a real index page.",
                                  "Exposed files may include backups, configuration or customer data.", "security_hardening", f"Page title: {title[:60]}"))

        # 5. cookie flags (first Set-Cookie only, as that is all a single response gives us)
        cookie = h.get("set-cookie", "")
        if cookie:
            low = cookie.lower()
            missing = [n for n, t in (("Secure", "secure"), ("HttpOnly", "httponly"), ("SameSite", "samesite")) if t not in low]
            if missing and ctx.scheme == "https":
                f.append(AuditFinding("security", "cookie_flags", "low",
                                      f"A cookie is set without: {', '.join(missing)}.",
                                      "Set Secure, HttpOnly and SameSite on session and tracking cookies.",
                                      "Cookies without these flags are easier to steal or misuse.", "security_hardening", f"Set-Cookie: {cookie[:80]}"))
        return f
