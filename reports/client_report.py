"""
Client Health Report: a one-page-per-topic, printable report built ONLY from stored audit evidence.

Sections: health score, what we found (measured value + fix + the service that addresses it), optional competitor comparison,
optional security watch, next steps, and what was and was not checked. All dynamic text is HTML-escaped and the page carries a
Content-Security-Policy that forbids scripts, because finding text can originate from the audited site.
"""

import html
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from auditors.engine import WebsiteDoctorEngine
from config.settings import settings
from engines.native_browser_service import NativeBrowserService
from intel.comparison import compare_domains
from intel.services import ServiceCatalog
from net.process_supervisor import ProcessSupervisor
from net.validate import clean_domain

SEV_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
SEV_COLOR = {"critical": "#b91c1c", "high": "#c2410c", "medium": "#a16207", "low": "#475569", "info": "#64748b"}
e = html.escape


def _h(text: Any) -> str:
    return e(str(text if text is not None else ""))


class ClientReport:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.path.join("data", "reports"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def build(self, org_id: str, domain: str, competitor: Optional[str] = None, vulnerabilities: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        audit = WebsiteDoctorEngine.run_audit(domain, org_id=org_id)
        comparison = compare_domains(domain, competitor, org_id) if competitor else None
        if vulnerabilities is None:
            vulnerabilities = [{"cve_id": f["check_id"].replace("cve_", "").upper(), "severity": f["severity"], "summary": f["finding"], "signal": f["evidence_value"]}
                               for f in audit["findings"] if f["check_id"].startswith("cve_")]
        return {"audit": audit, "comparison": comparison, "vulnerabilities": vulnerabilities, "generated_at": datetime.now(timezone.utc)}

    def render_html(self, data: Dict[str, Any], org_id: str) -> str:
        audit, comp, vulns = data["audit"], data["comparison"], data["vulnerabilities"]
        agency = settings.agency
        findings = sorted([f for f in audit["findings"] if f["severity"] != "info"], key=lambda f: -SEV_RANK[f["severity"]])
        parts: List[str] = []

        if audit["status"] != "completed":
            parts.append(f'<section><h2>We could not reach {_h(audit["domain"])}</h2><p>{_h(audit["summary"])} '
                         "One failed check is not proof the site is down for visitors.</p></section>")
        else:
            parts.append(f'<section class="score"><div class="big">{_h(audit["overall_score"])}<small>/100</small></div>'
                         f'<p>{_h(len(findings))} issue(s) found by {_h(len(audit["checks_run"]))} check groups on {_h(audit["domain"])}.</p></section>')
            rows = []
            for f in findings[:12]:
                svc = ServiceCatalog.label(f["service_id"]) if f.get("service_id") else ""
                rows.append(f'<tr><td><span class="sev" style="background:{SEV_COLOR[f["severity"]]}">{_h(f["severity"])}</span></td>'
                            f'<td><strong>{_h(f["finding"])}</strong><br><span class="m">Measured: {_h(f["evidence_value"])}</span></td>'
                            f'<td>{_h(f["fix"])}</td><td>{_h(svc)}</td></tr>')
            parts.append('<section><h2>What we found</h2><table><tr><th>Priority</th><th>Finding</th><th>Recommended fix</th><th>Service</th></tr>'
                         + "".join(rows) + "</table></section>")

        if comp:
            if not comp["comparable"]:
                parts.append(f'<section><h2>Comparison</h2><p>{_h(comp["note"])}</p></section>')
            else:
                lis = "".join(f'<li>{_h(r["finding"])} <span class="m">({_h(r["measured"])})</span></li>' for r in comp["target_only_issues"][:8])
                parts.append(f'<section><h2>Compared with {_h(comp["competitor"]["domain"])}</h2>'
                             f'<p>Health score: {_h(comp["target"]["overall_score"])} vs {_h(comp["competitor"]["overall_score"])}. '
                             f'Issues {_h(comp["target"]["domain"])} has that {_h(comp["competitor"]["domain"])} does not:</p><ul>{lis or "<li>None found.</li>"}</ul></section>')

        if vulns:
            lis = "".join(f'<li><strong>{_h(v["cve_id"])}</strong> ({_h(v.get("severity", "unknown"))}): {_h(v["summary"])} '
                          f'<span class="m">Signal: {_h(v["signal"])}. Potentially affected, not confirmed.</span></li>' for v in vulns[:10])
            parts.append(f'<section><h2>Security watch</h2><ul>{lis}</ul>'
                         '<p class="m">Based on software versions visible from outside. Confirm the exact version before acting.</p></section>')

        services = sorted({f["service_id"] for f in findings if f.get("service_id")})
        if services:
            lis = []
            for key in services:
                svc = ServiceCatalog.get(org_id, key)
                price = f' <span class="m">({_h(svc["price_band"])})</span>' if svc and svc.get("price_band") else ""
                lis.append(f"<li>{_h(ServiceCatalog.label(key))}{price}</li>")
            parts.append('<section><h2>Suggested next steps</h2><ul>' + "".join(lis) + "</ul></section>")

        limits = "".join(f"<li>{_h(s)}</li>" for s in audit.get("checks_skipped", []))
        parts.append('<section class="m"><h2>How this was produced</h2><p>Public pages and standard requests only; nothing was tested '
                     "intrusively. Checks run: " + _h(", ".join(audit["checks_run"]) or "none") + f".</p>{'<p>Not checked:</p><ul>' + limits + '</ul>' if limits else ''}</section>")

        cta = f'<p>Questions? <a href="{_h(agency.booking_link)}">Book a call</a>.</p>' if agency.booking_link else ""
        return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
<title>Health report: {_h(audit["domain"])}</title><style>
body{{font:14px/1.5 -apple-system,Segoe UI,Inter,sans-serif;color:#0f172a;max-width:860px;margin:0 auto;padding:32px}}
h1{{font-size:24px;margin:0}} h2{{font-size:16px;border-bottom:1px solid #e2e8f0;padding-bottom:4px;margin-top:28px}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid #e2e8f0;font-size:13px}}
.sev{{color:#fff;border-radius:4px;padding:1px 6px;font-size:11px;text-transform:uppercase}} .m{{color:#64748b;font-size:12px}}
.big{{font-size:48px;font-weight:700}} .big small{{font-size:16px;color:#64748b}} section{{break-inside:avoid}}
@media print{{body{{padding:0}}}}</style></head><body>
<header><h1>Website health report</h1><p class="m">{_h(audit["domain"])} &middot; {data["generated_at"].strftime("%Y-%m-%d")} &middot; prepared by {_h(agency.name)}</p></header>
{"".join(parts)}<footer class="m">{cta}<p>{_h(agency.name)} {_h(agency.founder_name)}</p></footer></body></html>"""

    def export(self, org_id: str, domain: str, competitor: Optional[str] = None, output_format: str = "both",
               vulnerabilities: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        domain = clean_domain(domain).split(":")[0]
        data = self.build(org_id, domain, clean_domain(competitor).split(":")[0] if competitor else None, vulnerabilities)
        content = self.render_html(data, org_id)
        stamp = data["generated_at"].strftime("%Y%m%d%H%M%S")
        slug = f"{org_id}_{domain.replace('.', '_')}_{stamp}"
        html_path = self.storage_dir / f"report_{slug}.html"
        html_path.write_text(content, encoding="utf-8")
        result = {"status": "success", "domain": domain, "audit_id": data["audit"]["audit_id"], "html_filename": html_path.name,
                  "pdf_filename": None, "overall_score": data["audit"]["overall_score"]}
        browser = NativeBrowserService(storage_dir=str(self.storage_dir))
        if output_format in ("pdf", "both") and browser.is_browser_available():
            pdf_path = self.storage_dir / f"report_{slug}.pdf"
            proc = ProcessSupervisor.run_confined([browser.chrome_binary, "--headless=new", "--disable-gpu", f"--print-to-pdf={pdf_path}",
                                                   "--no-pdf-header-footer", f"file://{html_path.resolve()}"], timeout_seconds=30)
            if proc.returncode == 0 and pdf_path.exists():
                result["pdf_filename"] = pdf_path.name
        return result
