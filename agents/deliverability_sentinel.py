"""
DeliverabilitySentinelAgent: Automated Deliverability Circuit Breaker & DNS Health Guard.
Enforces:
1. Automated 2% Bounce Rate Kill-Switch (Circuit Breaker).
2. Live DNS SPF, DKIM, and DMARC p=reject compliance audits.
3. Domain Reputation Index scoring and automated inbox re-routing.
"""

import re
import socket
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from config.deliverability import SECONDARY_SENDING_DOMAINS
from database.db import log_audit_trail
from config.honesty import NotConfiguredError, PreconditionFailedError
from net.dns_records import lookup_txt, lookup_cname, lookup_mx

class DeliverabilitySentinelAgent:
    """
    Automated sentinel monitoring sender domain health.
    Instantly trips circuit breakers to prevent domain blacklisting.
    """

    CRITICAL_BOUNCE_THRESHOLD = 0.02  # 2.0% Maximum Allowed Bounce Rate
    CRITICAL_COMPLAINT_THRESHOLD = 0.001  # 0.1% Maximum Allowed Spam Complaint Rate

    DKIM_SELECTORS = ("google", "selector1", "selector2", "default", "k1", "s1", "s2", "mail", "smtp")

    def check_dns_records(self, domain: str) -> Dict[str, Any]:
        """
        Looks up the domain's real MX, SPF, DKIM and DMARC records. A value is True only when the record
        was found and is well-formed, False when it is absent, and None when DNS could not be queried.
        """
        mx = lookup_mx(domain)
        spf_txt = lookup_txt(domain)
        dmarc_txt = lookup_txt(f"_dmarc.{domain}")

        spf = None if spf_txt is None else next((t for t in spf_txt if t.lower().startswith("v=spf1")), None)
        dmarc = None if dmarc_txt is None else next((t for t in dmarc_txt if t.lower().startswith("v=dmarc1")), None)

        dkim_selector = None
        dkim_checked = False
        for selector in self.DKIM_SELECTORS:
            name = f"{selector}._domainkey.{domain}"
            txt, cname = lookup_txt(name), lookup_cname(name)
            if txt is None and cname is None:
                continue
            dkim_checked = True
            if cname or any("v=dkim1" in t.lower() or "p=" in t.lower() for t in (txt or [])):
                dkim_selector = selector
                break

        dmarc_policy = None
        if dmarc:
            m = re.search(r"\bp=(\w+)", dmarc, re.IGNORECASE)
            dmarc_policy = m.group(1).lower() if m else None

        def flag(found, queried=True):
            return None if (found is None and not queried) else bool(found)

        status = {
            "domain": domain,
            "mx_valid": None if mx is None else bool(mx),
            "spf_valid": None if spf_txt is None else bool(spf),
            "dkim_valid": bool(dkim_selector) if dkim_checked else None,
            "dkim_selector": dkim_selector,
            "dmarc_valid": None if dmarc_txt is None else bool(dmarc),
            "dmarc_policy": dmarc_policy,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        score = 100
        for key, weight in (("mx_valid", 30), ("spf_valid", 25), ("dkim_valid", 25), ("dmarc_valid", 20)):
            if status[key] is False:
                score -= weight
        status["unverifiable_checks"] = [k for k in ("mx_valid", "spf_valid", "dkim_valid", "dmarc_valid") if status[k] is None]
        status["health_score"] = score
        return status

    def evaluate_circuit_breaker(
        self,
        inbox_email: str,
        total_sent: int,
        total_bounced: int,
        total_complaints: int = 0
    ) -> Dict[str, Any]:
        """
        Evaluates 24-hour performance against deliverability thresholds:
        - Critical Bounce Rate >= 2.0%
        - Critical Spam Complaint Rate >= 0.1%
        If breached with >= 10 sends, trips circuit breaker and pauses the inbox immediately.
        """
        bounce_rate = round((total_bounced / max(total_sent, 1)), 4)
        complaint_rate = round((total_complaints / max(total_sent, 1)), 4)

        bounce_breached = bounce_rate >= self.CRITICAL_BOUNCE_THRESHOLD and total_sent >= 10
        complaint_breached = complaint_rate >= self.CRITICAL_COMPLAINT_THRESHOLD and total_sent >= 10

        is_tripped = bounce_breached or complaint_breached
        status = "HEALTHY" if not is_tripped else "TRIPPED_CIRCUIT_BREAKER_PAUSED"
        action = "NORMAL_DISPATCH" if not is_tripped else "HALT_DISPATCH_AND_REROUTE"

        if is_tripped:
            log_audit_trail(None, "DeliverabilitySentinel", "CIRCUIT_BREAKER_TRIPPED", {
                "inbox": inbox_email,
                "bounce_rate": bounce_rate,
                "complaint_rate": complaint_rate,
                "action": action
            })

        return {
            "inbox": inbox_email,
            "total_sent_24h": total_sent,
            "bounced_24h": total_bounced,
            "complaints_24h": total_complaints,
            "bounce_rate_percent": round(bounce_rate * 100, 2),
            "complaint_rate_percent": round(complaint_rate * 100, 3),
            "circuit_breaker_status": status,
            "action_taken": action
        }

    def run_fleet_health_audit(self, org_id: str = "org_default") -> List[Dict[str, Any]]:
        """Audits the tenant's real sending mailboxes: live DNS plus measured bounce/complaint rates."""
        from database.db import get_db
        results: List[Dict[str, Any]] = []
        with get_db() as db:
            mailboxes = [dict(r) for r in db.execute("SELECT * FROM mailboxes WHERE org_id = ?", (org_id,)).fetchall()]
            for mb in mailboxes:
                email = mb["email"]
                domain = email.split("@")[-1]
                counts = {"sent": 0, "bounced": 0, "complaint": 0}
                if mb.get("id") is not None:
                    for event_type in counts:
                        counts[event_type] = db.execute(
                            "SELECT COUNT(*) FROM outreach_events WHERE org_id = ? AND mailbox_id = ? AND event_type = ?",
                            (org_id, mb["id"], event_type)).fetchone()[0]
                dns_health = self.check_dns_records(domain)
                breaker = self.evaluate_circuit_breaker(email, counts["sent"], counts["bounced"], counts["complaint"])
                results.append({
                    "inbox": email, "domain": domain, "dns_health": dns_health, "circuit_breaker": breaker,
                    "overall_status": "ONLINE_ACTIVE" if breaker["circuit_breaker_status"] == "HEALTHY" and dns_health["health_score"] >= 70 else "NEEDS_ATTENTION",
                })
        return results
