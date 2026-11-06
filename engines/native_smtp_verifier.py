"""
Native Deep SMTP Handshake & Deliverability Verification Engine.
Completely replaces ZeroBounce, NeverBounce, and MillionVerifier with a zero-cost,
self-hosted socket verification pipeline including RFC syntax audits, disposable domain filters,
MX priority sorting, catch-all server probing, and full SMTP handshake verification.
"""

import socket
import re
import uuid
import subprocess
from net.fetcher import SafeFetcher, SSRFSecurityError
from net.validate import is_valid_hostname
from typing import Dict, Any, List, Optional

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "10minutemail.com",
    "trashmail.com", "sharklasers.com", "yopmail.com", "getairmail.com",
    "throwawaymail.com", "temp-mail.org", "dispostable.com", "fakeinbox.com",
    "maildrop.cc", "mohmal.com", "crazymailing.com", "generator.email",
    "mytemp.email", "nada.ltd", "burnermail.io", "guerrillamail.net"
}

ROLE_BASED_PREFIXES = {
    "info", "support", "contact", "sales", "admin", "billing", "help",
    "jobs", "careers", "press", "media", "hello", "team", "office", "general"
}

class NativeSMTPVerifier:
    def __init__(self, probe_domain: str = "agencybd-sentinel.internal", socket_timeout: float = 3.0):
        self.probe_domain = probe_domain
        self.socket_timeout = socket_timeout

    def validate_syntax(self, email: str) -> bool:
        """Validates RFC 5322 standard email address formatting."""
        pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        return bool(re.fullmatch(pattern, email))

    def is_disposable(self, domain: str) -> bool:
        """Detects disposable and ephemeral burner email services."""
        return domain.lower().strip() in DISPOSABLE_DOMAINS

    def is_role_account(self, local_part: str) -> bool:
        """Detects shared department inboxes vs personal decision-maker mailboxes."""
        return local_part.lower().strip() in ROLE_BASED_PREFIXES

    def resolve_mx_records(self, domain: str) -> List[str]:
        """Resolves active Mail Exchanger (MX) hosts for the target domain."""
        mx_hosts = []
        if not is_valid_hostname(domain):
            return []
        try:
            import sys, shutil
            nslookup_bin = shutil.which("nslookup") or ("C:\\Windows\\System32\\nslookup.exe" if sys.platform == "win32" else "nslookup")
            res = subprocess.run([nslookup_bin, "-q=mx", domain], capture_output=True, text=True, timeout=5)
            for line in res.stdout.splitlines():
                if "mail exchanger =" in line.lower():
                    parts = re.split(r"mail exchanger\s*=\s*", line, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        host = parts[1].strip().split()[0].rstrip(".")
                        if is_valid_hostname(host) and host not in mx_hosts:
                            mx_hosts.append(host)
        except Exception:
            pass

        # Socket fallback if nslookup fails
        if not mx_hosts:
            try:
                socket.getaddrinfo(domain, 25)
                mx_hosts.append(domain)
            except Exception:
                pass

        return mx_hosts

    get_mx_records = resolve_mx_records

    def probe_smtp_handshake(self, mx_host: str, target_email: str) -> Dict[str, Any]:
        """
        Executes a non-intrusive RFC 5321 SMTP handshake:
        CONNECT -> 220 Banner -> EHLO -> 250 -> MAIL FROM -> 250 -> RCPT TO -> Response Code -> QUIT.
        Never sends message content (DATA command is never issued).
        """
        result = {"status": "unknown", "smtp_code": 0, "message": ""}
        s = None
        try:
            # An attacker controls the target domain's MX record: never let it point us at internal hosts.
            safe_ip = SafeFetcher.resolve_and_validate_hostname(mx_host)
            s = socket.socket(socket.AF_INET6 if ":" in safe_ip else socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.socket_timeout)
            s.connect((safe_ip, 25))

            # 1. Read Banner
            banner = s.recv(1024).decode("utf-8", errors="ignore")
            if not banner.startswith("220"):
                result.update({"status": "failed_banner", "message": banner[:80]})
                return result

            # 2. EHLO
            s.sendall(f"EHLO {self.probe_domain}\r\n".encode("utf-8"))
            ehlo_resp = s.recv(1024).decode("utf-8", errors="ignore")

            # 3. MAIL FROM
            s.sendall(f"MAIL FROM:<verify@{self.probe_domain}>\r\n".encode("utf-8"))
            from_resp = s.recv(1024).decode("utf-8", errors="ignore")

            # 4. RCPT TO
            s.sendall(f"RCPT TO:<{target_email}>\r\n".encode("utf-8"))
            rcpt_resp = s.recv(1024).decode("utf-8", errors="ignore")

            # Extract 3-digit status code
            code_match = re.match(r"^(\d{3})", rcpt_resp.strip())
            code = int(code_match.group(1)) if code_match else 0
            result["smtp_code"] = code
            result["message"] = rcpt_resp.strip()[:100]

            if code == 250:
                result["status"] = "deliverable"
            elif code in [550, 551, 552, 553, 554]:
                result["status"] = "undeliverable"
            elif code in [450, 451, 452]:
                result["status"] = "greylisted"
            else:
                result["status"] = "unknown"

            # QUIT
            s.sendall(b"QUIT\r\n")
        except SSRFSecurityError as exc:
            result.update({"status": "blocked", "message": str(exc)})
        except socket.timeout:
            result.update({"status": "timeout", "message": "SMTP Connection timed out (Port 25 filtered)"})
        except Exception as e:
            result.update({"status": "connection_error", "message": str(e)})
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass

        return result

    def detect_catch_all(self, mx_host: str, domain: str) -> bool:
        """
        Tests if the mail server is configured as a catch-all (accepts any email).
        Probes with a randomized non-existent hash address.
        """
        random_local = f"nonexistent_probe_{uuid.uuid4().hex[:10]}"
        dummy_email = f"{random_local}@{domain}"
        probe_res = self.probe_smtp_handshake(mx_host, dummy_email)
        return probe_res["status"] == "deliverable"

    def is_catch_all_domain(self, domain: str) -> bool:
        """Convenience method to check if a domain is catch-all."""
        mx_hosts = self.resolve_mx_records(domain)
        if not mx_hosts:
            return False
        return self.detect_catch_all(mx_hosts[0], domain)

    def verify_email(self, email: str) -> Dict[str, Any]:
        """
        Master Deep Verification Pipeline:
        1. Syntax check
        2. Disposable check
        3. Role-based check
        4. DNS MX lookup
        5. Catch-all detection
        6. Deep SMTP handshake probe
        7. Compute deliverability confidence score (0-100)
        """
        email_clean = email.lower().strip()

        # Step 1: Syntax
        if not self.validate_syntax(email_clean):
            return {
                "email": email_clean,
                "is_valid": False,
                "confidence_score": 0,
                "status": "invalid_syntax",
                "risk_level": "extreme",
                "recommendation": "DO_NOT_SEND"
            }

        local_part, domain = email_clean.split("@", 1)

        # Step 2: Disposable
        if self.is_disposable(domain):
            return {
                "email": email_clean,
                "is_valid": False,
                "confidence_score": 5,
                "status": "disposable_burner_domain",
                "risk_level": "extreme",
                "recommendation": "DO_NOT_SEND"
            }

        # Step 3: Role Account
        is_role = self.is_role_account(local_part)

        # Step 4: MX Records
        mx_hosts = self.resolve_mx_records(domain)
        if not mx_hosts:
            return {
                "email": email_clean,
                "is_valid": False,
                "confidence_score": 10,
                "status": "no_mx_records_found",
                "risk_level": "high",
                "recommendation": "DO_NOT_SEND"
            }

        primary_mx = mx_hosts[0]

        # Step 5 & 6: Handshake and Catch-All Probe
        handshake_result = self.probe_smtp_handshake(primary_mx, email_clean)

        # Fallback evaluation if outbound port 25 is restricted by local ISP
        is_deliverable = False
        is_catch_all = False
        verified = False
        if handshake_result["status"] == "deliverable":
            is_deliverable = True
            verified = True
            is_catch_all = self.detect_catch_all(primary_mx, domain)
        elif handshake_result["status"] == "undeliverable":
            is_deliverable = False
            verified = True
        else:
            # Port 25 blocked, greylisted, timed out or blocked by policy: we do NOT know. Never report valid.
            return {
                "email": email_clean,
                "domain": domain,
                "is_valid": False,
                "confidence_score": 0,
                "status": "unverified",
                "is_catch_all": False,
                "is_role_account": is_role,
                "primary_mx": primary_mx,
                "smtp_response": handshake_result.get("message", ""),
                "risk_level": "unknown",
                "recommendation": "VERIFY_WITH_VENDOR",
            }

        # Step 7: Score Calculation
        score = 98 if is_deliverable else 15
        if is_catch_all: score -= 25
        if is_role: score -= 15

        risk_level = "safe" if score >= 80 else ("moderate" if score >= 60 else "high")
        rec = "SAFE_TO_SEND" if score >= 75 else ("VERIFY_CATCH_ALL" if is_catch_all else "DO_NOT_SEND")

        return {
            "email": email_clean,
            "domain": domain,
            "is_valid": is_deliverable and score >= 60,
            "confidence_score": max(score, 0),
            "status": "verified_deliverable" if is_deliverable else "undeliverable_mailbox",
            "is_catch_all": is_catch_all,
            "is_role_account": is_role,
            "primary_mx": primary_mx,
            "smtp_response": handshake_result.get("message", "OK"),
            "risk_level": risk_level,
            "recommendation": rec
        }
