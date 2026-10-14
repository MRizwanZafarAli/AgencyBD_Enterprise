"""
DNS setup guidance and live verification for sending domains.

What it generates is what you can actually publish. Where a value cannot be known in advance (the DKIM public key is
created by your mail provider for your domain) it says so and tells you where to get it, instead of printing a
placeholder that looks real. DMARC starts in monitor mode (p=none): moving straight to p=reject on a new domain can bounce
your own legitimate mail until SPF/DKIM alignment is confirmed.
"""

from typing import Any, Dict, List, Optional

from agents.deliverability_sentinel import DeliverabilitySentinelAgent
from net.validate import clean_domain
from outbound.providers.registry import RAMP_SCHEDULE

GOOGLE_MX = [(1, "ASPMX.L.GOOGLE.COM."), (5, "ALT1.ASPMX.L.GOOGLE.COM."), (5, "ALT2.ASPMX.L.GOOGLE.COM."),
             (10, "ALT3.ASPMX.L.GOOGLE.COM."), (10, "ALT4.ASPMX.L.GOOGLE.COM.")]


class DNSFleetConfigurator:
    @staticmethod
    def generate_dns_records(domain: str, esp_provider: str = "google_workspace", dmarc_policy: str = "none",
                             dmarc_report_mailbox: Optional[str] = None) -> Dict[str, Any]:
        d = clean_domain(domain).split(":")[0]
        if dmarc_policy not in ("none", "quarantine", "reject"):
            raise ValueError("dmarc_policy must be none, quarantine or reject")
        report_to = dmarc_report_mailbox or f"dmarc-reports@{d}"

        if esp_provider == "google_workspace":
            spf = "v=spf1 include:_spf.google.com ~all"
            mx = [{"priority": p, "host": "@", "value": v} for p, v in GOOGLE_MX]
            dkim = {"type": "TXT", "host": f"google._domainkey.{d}", "value": None,
                    "how_to_get_value": "Google Admin console > Apps > Google Workspace > Gmail > Authenticate email > Generate new record. Publish the TXT value Google shows, then click Start authentication."}
        elif esp_provider == "microsoft_365":
            spf = "v=spf1 include:spf.protection.outlook.com ~all"
            mx = [{"priority": 0, "host": "@", "value": f"{d.replace('.', '-')}.mail.protection.outlook.com."}]
            dkim = {"type": "CNAME", "host": f"selector1._domainkey.{d}", "value": f"selector1-{d.replace('.', '-')}._domainkey.<your-tenant>.onmicrosoft.com",
                    "how_to_get_value": "Microsoft 365 Defender > Email & collaboration > Policies > DKIM. Use the exact CNAME targets shown for your tenant (selector1 and selector2) and enable signing."}
        else:
            raise ValueError("esp_provider must be google_workspace or microsoft_365")

        return {
            "domain": d, "esp_provider": esp_provider,
            "spf": {"type": "TXT", "host": "@", "value": spf},
            "dkim": dkim,
            "dmarc": {"type": "TXT", "host": f"_dmarc.{d}", "value": f"v=DMARC1; p={dmarc_policy}; rua=mailto:{report_to}; adkim=r; aspf=r; pct=100"},
            "mx": mx,
            "notes": [
                "Create the mailbox that receives DMARC reports (" + report_to + ") or point rua= at one you read.",
                "Run in p=none for 2-4 weeks, read the reports, then move to p=quarantine and finally p=reject.",
                "Only one SPF record is allowed per domain: merge includes if you already have one.",
                "Use a SECONDARY domain for cold outreach so a reputation problem never touches your main domain.",
            ],
        }

    @staticmethod
    def audit_live_dns(domain: str) -> Dict[str, Any]:
        """Real MX/SPF/DKIM/DMARC lookups. Checks that could not be performed are None, never guessed."""
        d = clean_domain(domain).split(":")[0]
        health = DeliverabilitySentinelAgent().check_dns_records(d)
        return {
            "domain": d, "mx_active": health["mx_valid"], "spf_active": health["spf_valid"], "dkim_active": health["dkim_valid"],
            "dkim_selector": health["dkim_selector"], "dmarc_active": health["dmarc_valid"], "dmarc_policy": health["dmarc_policy"],
            "health_score_pct": health["health_score"], "unverifiable_checks": health["unverifiable_checks"],
            "ready_for_outreach": all(health[k] is True for k in ("mx_valid", "spf_valid", "dkim_valid", "dmarc_valid")),
            "checked_at": health["checked_at"],
        }

    @staticmethod
    def generate_21_day_warmup_curve(daily_target_cap: int = 40) -> List[Dict[str, Any]]:
        """The organic ramp the mailbox registry enforces (sends per day by mailbox age). No fake engagement is generated."""
        days, previous = [], 0
        for limit, cap in RAMP_SCHEDULE:
            for day in range(previous + 1, limit + 1):
                days.append({"day": day, "send_volume": min(cap, daily_target_cap)})
            previous = limit
        days.append({"day": previous + 1, "send_volume": daily_target_cap, "note": "full configured cap from here on"})
        return days
