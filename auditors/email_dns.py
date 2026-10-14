"""
Email & DNS health from real lookups (MX, SPF, DMARC). A record we could not look up is skipped, not reported missing.
"""

from typing import List

from auditors.base import AuditFinding
from net.dns_records import lookup_mx, lookup_txt


class EmailDNSAuditor:
    @staticmethod
    def audit(domain: str) -> List[AuditFinding]:
        f: List[AuditFinding] = []
        mx, spf_txt, dmarc_txt = lookup_mx(domain), lookup_txt(domain), lookup_txt(f"_dmarc.{domain}")

        def add(check, severity, finding, fix, impact, evidence):
            f.append(AuditFinding("dns", check, severity, finding, fix, impact, "devops_sre", evidence))

        if mx is None:
            return f  # DNS unavailable: say nothing rather than guess
        if not mx:
            add("no_mx_records", "info", "The domain has no MX records, so it cannot receive email.",
                "Ignore if the business uses a different domain for email; otherwise add MX records for your mail provider.",
                "Messages sent to addresses on this domain bounce.", "MX lookup returned no records.")
            return f
        if spf_txt is not None and not any(t.lower().startswith("v=spf1") for t in spf_txt):
            add("missing_spf", "medium", "No SPF record: nothing says which servers may send email for this domain.",
                "Publish an SPF TXT record for your mail provider.", "Mail from the domain is more likely to be flagged as spam or spoofed.",
                f"TXT records at the apex: {len(spf_txt)}, none start with v=spf1.")
        if dmarc_txt is not None:
            record = next((t for t in dmarc_txt if t.lower().startswith("v=dmarc1")), None)
            if record is None:
                add("missing_dmarc", "medium", "No DMARC record.", "Publish a DMARC record, starting with p=none and reporting.",
                    "Gmail and Yahoo expect DMARC from bulk senders; without it spoofing is easy.", "No v=DMARC1 TXT at _dmarc.<domain>.")
            elif "p=none" in record.replace(" ", "").lower():
                add("dmarc_monitor_only", "low", "DMARC is in monitor-only mode (p=none).", "After reviewing reports, move to p=quarantine then p=reject.",
                    "Spoofed mail is reported but not blocked.", f"DMARC record: {record[:120]}")
        return f
