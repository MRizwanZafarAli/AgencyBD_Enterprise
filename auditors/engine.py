"""
Website Doctor engine.

1. Fetch the site and its supporting files ONCE (auditors/context.py), through the SSRF-safe client.
2. Run every auditor against that shared evidence. One auditor failing never aborts the audit; it is listed under
   `checks_failed`, and checks that could not run (e.g. PageSpeed without a key) are listed under `checks_skipped`.
3. Store each finding with its measured value, source URL and timestamp, and link the evidence to the audit run.

No metric is ever estimated. An unreachable site gets status 'unreachable' and no score.
"""

import time
from typing import Any, Dict, List, Optional

from auditors import pagespeed
from auditors.a11y import A11yAuditor
from auditors.base import AuditFinding
from auditors.context import SiteContext, fetch_site
from auditors.email_dns import EmailDNSAuditor
from auditors.geo import GEOAuditor
from auditors.performance import PerformanceAuditor
from auditors.security import SecurityAuditor
from auditors.seo import SEOAuditor
from database.models import AuditRunRepository, EvidenceRepository
from net.fetcher import SSRFSecurityError
from net.validate import clean_domain

SEVERITY_DEDUCTION = {"critical": 25, "high": 15, "medium": 8, "low": 3, "info": 0}

PAGE_AUDITORS = [("performance", PerformanceAuditor.audit), ("security", SecurityAuditor.audit), ("seo", SEOAuditor.audit),
                 ("geo", GEOAuditor.audit), ("a11y", A11yAuditor.audit)]


class WebsiteDoctorEngine:
    @classmethod
    def run_audit(cls, domain: str, company_id: Optional[int] = None, org_id: str = "org_default") -> Dict[str, Any]:
        clean = clean_domain(domain).split(":")[0]
        started = time.time()
        findings: List[AuditFinding] = []
        ran: List[str] = []
        skipped: List[str] = []
        failed: List[Dict[str, str]] = []
        ctx: Optional[SiteContext] = None
        error_msg: Optional[str] = None

        try:
            ctx = fetch_site(clean)
        except SSRFSecurityError:
            raise  # a blocked target is a bad request, not a finding about the prospect's site
        except Exception as exc:
            error_msg = str(exc)[:200]

        if ctx is None:
            findings.append(AuditFinding(
                "performance", "site_unreachable", "high",
                f"Could not reach {clean} from our servers at {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. "
                f"The site may be down, may not exist, or may block automated requests.",
                "Re-test later and confirm the domain. If the business has no website, use Presence Rescue.",
                "Unknown. One failed check is not proof the site is down for visitors.", "presence_rescue",
                f"Error: {error_msg}", confidence=0.4))
            score: Optional[int] = None
            target_url = f"https://{clean}"
            ttfb = 0
        else:
            target_url, ttfb = ctx.url, ctx.ttfb_ms
            for name, fn in PAGE_AUDITORS:
                try:
                    findings.extend(fn(ctx))
                    ran.append(name)
                except Exception as exc:
                    failed.append({"check": name, "error": str(exc)[:120]})
            try:
                findings.extend(EmailDNSAuditor.audit(clean))
                ran.append("email_dns")
            except Exception as exc:
                failed.append({"check": "email_dns", "error": str(exc)[:120]})
            if pagespeed.configured():
                try:
                    findings.extend(pagespeed.PageSpeedAuditor.audit(ctx.url))
                    ran.append("pagespeed")
                except Exception as exc:
                    failed.append({"check": "pagespeed", "error": str(exc)[:120]})
            else:
                skipped.append("pagespeed (set PAGESPEED_API_KEY for Core Web Vitals and the browser-based accessibility audit)")
            if ctx.tls is None and ctx.scheme == "https":
                skipped.append("tls (inspection failed)")
            skipped += [f"{label} (could not be fetched)" for label, val in
                        (("robots.txt", ctx.robots_txt), ("llms.txt", ctx.llms_txt), ("sitemap", ctx.sitemap_found)) if val is None]
            score = max(15, 100 - sum(SEVERITY_DEDUCTION.get(f.severity, 0) for f in findings))

        saved: List[Dict[str, Any]] = []
        for f in findings:
            ev = EvidenceRepository.record_evidence(
                entity_type="audit", entity_id=company_id or 0, claim=f.finding, value=f.evidence_value,
                method=f"auditors.{f.category}", source_url=target_url, confidence=f.confidence, org_id=org_id)
            d = f.to_dict()
            d["evidence_id"] = ev["id"]
            saved.append(d)

        summary = (f"Website Doctor could not reach {clean}; no health score was computed." if ctx is None else
                   f"Website Doctor audit of {clean}: health score {score}/100, {len(findings)} finding(s) from {len(ran)} check group(s)"
                   f"{'; ' + str(len(skipped)) + ' check(s) skipped' if skipped else ''}.")
        status = "unreachable" if ctx is None else "completed"
        record = AuditRunRepository.record_run(domain=clean, overall_score=score, summary=summary, findings=saved,
                                               company_id=company_id, org_id=org_id, status=status)
        EvidenceRepository.attach_to([x["evidence_id"] for x in saved], "audit_run", record["id"], org_id)

        return {
            "audit_id": record["id"], "domain": clean, "overall_score": score, "status": status,
            "response_time_ms": ttfb, "findings_count": len(findings), "findings": saved, "summary": summary,
            "checks_run": ran, "checks_skipped": skipped, "checks_failed": failed,
            "duration_ms": int((time.time() - started) * 1000),
        }
