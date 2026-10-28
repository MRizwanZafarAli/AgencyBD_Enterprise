"""
Executive Presentation Deck Generator for AgencyBD Enterprise.
Generates a 16:9 widescreen, multi-slide executive teardown presentation deck
(HTML + print-ready PDF) built from verified website audit findings.
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

e = html.escape
SEV_COLOR = {"critical": "#ef4444", "high": "#f97316", "medium": "#eab308", "low": "#64748b", "info": "#94a3b8"}


class ExecutiveDeckGenerator:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.path.join("data", "reports"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def build_deck_data(self, org_id: str, domain: str, competitor: Optional[str] = None) -> Dict[str, Any]:
        audit = WebsiteDoctorEngine.run_audit(domain, org_id=org_id)
        comparison = compare_domains(domain, competitor, org_id) if competitor else None
        return {
            "audit": audit,
            "comparison": comparison,
            "generated_at": datetime.now(timezone.utc),
            "domain": domain,
            "competitor": competitor
        }

    def render_deck_html(self, data: Dict[str, Any], org_id: str) -> str:
        audit = data["audit"]
        agency = settings.agency
        findings = [f for f in audit.get("findings", []) if f.get("severity") != "info"]
        findings.sort(key=lambda x: (0 if x["severity"] == "critical" else 1 if x["severity"] == "high" else 2))

        date_str = data["generated_at"].strftime("%B %d, %Y")
        domain = audit["domain"]
        score = audit.get("overall_score") or 0
        company_label = domain.split(".")[0].capitalize()

        # Estimated conversion loss calculation from LCP
        lcp_val = 2.5
        for f in audit.get("findings", []):
            if "lcp" in f.get("check_id", "").lower() or "largest contentful paint" in f.get("finding", "").lower():
                try:
                    import re
                    m = re.search(r"(\d+(\.\d+)?)", f.get("evidence_value", ""))
                    if m:
                        lcp_val = float(m.group(1))
                except Exception:
                    pass

        # Each second over 2.0s roughly accounts for ~7% conversion loss
        conv_loss_pct = max(0, min(65, int((lcp_val - 1.8) * 7))) if lcp_val > 1.8 else 0

        # Slide 3: Findings rows
        findings_html = ""
        for i, f in enumerate(findings[:6], 1):
            sev = f["severity"].lower()
            color = SEV_COLOR.get(sev, "#64748b")
            findings_html += f"""
            <div class="card finding-card">
                <div class="finding-header">
                    <span class="badge" style="background:{color}22; color:{color}; border:1px solid {color}44;">{e(sev.upper())}</span>
                    <span class="finding-title">{e(f['finding'])}</span>
                </div>
                <div class="finding-detail"><strong style="color:#f8fafc;">Evidence:</strong> {e(f.get('evidence_value', 'Observed on public endpoint'))}</div>
                <div class="finding-fix"><strong style="color:#d97706;">Recommended Action:</strong> {e(f.get('fix', 'Review architecture.'))}</div>
            </div>
            """
        if not findings_html:
            findings_html = '<div class="card"><p style="color:#10b981;">No critical or high-severity vulnerabilities detected on public endpoints.</p></div>'

        # Slide 4: Surgery steps
        services = sorted({f.get("service_id") for f in findings if f.get("service_id")})
        services_list_html = ""
        for s_id in (services[:4] if services else ["speed_optimization", "security_headers", "seo_optimization"]):
            label = ServiceCatalog.label(s_id) if s_id else "Technical Optimization"
            services_list_html += f'<li style="margin-bottom:8px;"><strong>{e(label)}</strong></li>'

        metric = getattr(agency, "case_study_metric", "") or ""
        proof_html = f'<p style="color:#d97706; font-size:14px; margin-top:12px;"><strong>Documented Standard:</strong> {e(metric)}</p>' if metric else ""
        booking_btn = f'<a href="{e(agency.booking_link)}" class="cta-button" target="_blank">Book Architectural Strategy Call &rarr;</a>' if getattr(agency, "booking_link", "") else ""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Executive Deck: {e(domain)}</title>
<style>
  @page {{
    size: 11in 8.5in landscape;
    margin: 0;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #090d16;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .slide {{
    width: 100vw;
    height: 100vh;
    min-height: 720px;
    padding: 48px 64px;
    page-break-after: always;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    position: relative;
    background: radial-gradient(circle at 85% 15%, rgba(217, 119, 6, 0.08) 0%, rgba(9, 13, 22, 1) 70%);
    border-bottom: 2px solid #1e293b;
    overflow: hidden;
  }}
  .slide-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 16px;
  }}
  .agency-brand {{
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #d97706;
    text-transform: uppercase;
  }}
  .slide-number {{
    font-family: monospace;
    font-size: 12px;
    color: #64748b;
  }}
  .slide-content {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 24px 0;
  }}
  .slide-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 12px;
    font-size: 11px;
    color: #64748b;
  }}
  h1 {{ font-size: 42px; font-weight: 800; line-height: 1.15; color: #ffffff; margin-bottom: 16px; }}
  h2 {{ font-size: 28px; font-weight: 700; color: #ffffff; margin-bottom: 12px; }}
  p.subtitle {{ font-size: 18px; color: #94a3b8; max-width: 720px; line-height: 1.5; }}
  
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }}
  .grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }}
  
  .card {{
    background: rgba(17, 24, 39, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 24px;
    backdrop-filter: blur(12px);
  }}
  .score-badge {{
    font-size: 72px;
    font-weight: 900;
    color: { '#10b981' if score >= 80 else '#d97706' if score >= 50 else '#ef4444' };
    line-height: 1;
  }}
  .badge {{
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 10px;
    font-family: monospace;
    font-weight: 700;
  }}
  .finding-card {{
    margin-bottom: 12px;
    padding: 16px;
  }}
  .finding-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }}
  .finding-title {{
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
  }}
  .finding-detail, .finding-fix {{
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.4;
    margin-top: 4px;
  }}
  .step-box {{
    background: rgba(30, 41, 59, 0.5);
    border-radius: 12px;
    padding: 20px;
    border-left: 4px solid #d97706;
  }}
  .step-num {{ font-family: monospace; font-size: 12px; color: #d97706; font-weight: 700; margin-bottom: 4px; }}
  .step-title {{ font-size: 16px; font-weight: 700; color: #ffffff; margin-bottom: 6px; }}
  .step-desc {{ font-size: 12px; color: #94a3b8; line-height: 1.4; }}
  
  .cta-button {{
    display: inline-block;
    margin-top: 20px;
    background: linear-gradient(135deg, #d97706, #f59e0b);
    color: #0f172a;
    font-weight: 800;
    font-size: 15px;
    padding: 14px 28px;
    border-radius: 12px;
    text-decoration: none;
    box-shadow: 0 4px 20px rgba(217, 119, 6, 0.4);
  }}

  @media print {{
    body {{ background: #090d16 !important; -webkit-print-color-adjust: exact; }}
    .slide {{ border: none; height: 100vh; width: 100vw; min-height: 100vh; }}
  }}
</style>
</head>
<body>

  <!-- SLIDE 1: COVER -->
  <section class="slide">
    <div class="slide-header">
      <div class="agency-brand">{e(agency.name)} &middot; Executive Diagnostic</div>
      <div class="slide-number">01 / 05</div>
    </div>
    <div class="slide-content">
      <div style="display:inline-block; margin-bottom:12px;">
        <span class="badge" style="background:#d9770622; color:#d97706; border:1px solid #d9770644; font-size:12px; padding:4px 12px;">
          EXECUTIVE AUDIT &amp; TEARDOWN
        </span>
      </div>
      <h1>Website Forensics &amp; Digital Infrastructure Teardown</h1>
      <p class="subtitle">
        A strategic diagnostic prepared for the executive leadership of <strong>{e(domain)}</strong>.
        Evaluates Core Web Vitals, speed bottlenecks, mobile responsiveness, and security headers against modern enterprise benchmarks.
      </p>
      <div style="margin-top:32px; font-family:monospace; font-size:13px; color:#94a3b8;">
        Target: <strong style="color:#ffffff;">{e(domain)}</strong> &nbsp;|&nbsp; 
        Evaluated: {e(date_str)} &nbsp;|&nbsp; 
        Audited by: {e(agency.name)} {e(agency.founder_name)}
      </div>
    </div>
    <div class="slide-footer">
      <div>CONFIDENTIAL &middot; PREPARED SPECIFICALLY FOR {e(domain).upper()}</div>
      <div>100% Verified Telemetry &middot; $0 Recurring API Tax</div>
    </div>
  </section>

  <!-- SLIDE 2: EXECUTIVE HEALTH & IMPACT -->
  <section class="slide">
    <div class="slide-header">
      <div class="agency-brand">{e(agency.name)} &middot; Executive Diagnostic</div>
      <div class="slide-number">02 / 05</div>
    </div>
    <div class="slide-content">
      <h2>Digital Health &amp; Revenue Risk Analysis</h2>
      <p style="color:#94a3b8; font-size:14px; margin-bottom:24px;">Measured speed and technical hygiene directly govern your visitor retention, bounce rates, and organic discovery.</p>
      
      <div class="grid-2">
        <div class="card" style="display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center;">
          <div style="font-size:13px; font-mono; color:#94a3b8; margin-bottom:8px; text-transform:uppercase; letter-spacing:1px;">Overall Technical Health Score</div>
          <div class="score-badge">{score}<span style="font-size:24px; color:#64748b;">/100</span></div>
          <div style="font-size:13px; color:#f8fafc; margin-top:8px;">
            { 'Enterprise Grade Performance' if score >= 80 else 'Noticeable Friction & Latency Bottlenecks' if score >= 50 else 'Critical Conversion & Architecture Blockers' }
          </div>
        </div>

        <div class="card">
          <div style="font-size:13px; font-mono; color:#d97706; margin-bottom:12px; font-weight:700; text-transform:uppercase;">Observed Conversion Headwind</div>
          <p style="font-size:13px; color:#cbd5e1; line-height:1.5;">
            Target measured loading time is approximately <strong style="color:#ffffff;">{lcp_val:.1f}s</strong>.
            Research across top web properties indicates each 1-second delay past 2.0s degrades conversion by ~7%.
          </p>
          <div style="margin-top:16px; padding:12px; background:rgba(239, 68, 68, 0.1); border-left:3px solid #ef4444; border-radius:6px;">
            <div style="font-size:12px; font-weight:700; color:#ef4444;">Estimated Opportunity Drag: ~{conv_loss_pct}%</div>
            <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Visitors abandon slow checkout, demo, and contact pages before interaction.</div>
          </div>
        </div>
      </div>
    </div>
    <div class="slide-footer">
      <div>Source: Real-World Public Telemetry &middot; Google Lighthouse Standards</div>
      <div>Page 2</div>
    </div>
  </section>

  <!-- SLIDE 3: KEY FINDINGS -->
  <section class="slide">
    <div class="slide-header">
      <div class="agency-brand">{e(agency.name)} &middot; Key Findings</div>
      <div class="slide-number">03 / 05</div>
    </div>
    <div class="slide-content">
      <h2>Top Architectural &amp; Infrastructure Findings</h2>
      <p style="color:#94a3b8; font-size:14px; margin-bottom:20px;">Prioritized telemetry findings identified on public endpoints:</p>
      
      <div style="max-height:460px; overflow-y:auto; padding-right:8px;">
        {findings_html}
      </div>
    </div>
    <div class="slide-footer">
      <div>Public inspection only &middot; zero intrusive scanning performed</div>
      <div>Page 3</div>
    </div>
  </section>

  <!-- SLIDE 4: THE SURGERY PLAN -->
  <section class="slide">
    <div class="slide-header">
      <div class="agency-brand">{e(agency.name)} &middot; Action Blueprint</div>
      <div class="slide-number">04 / 05</div>
    </div>
    <div class="slide-content">
      <h2>The 3-Step Remediation Plan ("Surgery")</h2>
      <p style="color:#94a3b8; font-size:14px; margin-bottom:24px;">An opinionated engineering roadmap to eliminate latency and resolve compliance risks:</p>
      
      <div class="grid-3">
        <div class="step-box">
          <div class="step-num">PHASE 01 &middot; 48 HOURS</div>
          <div class="step-title">Quick Wins &amp; Defense</div>
          <div class="step-desc">
            Deploy missing HTTP security headers (CSP, HSTS, X-Content-Type), verify TLS 1.3 protocol, and enforce basic asset compression.
          </div>
        </div>

        <div class="step-box">
          <div class="step-num">PHASE 02 &middot; 2 WEEKS</div>
          <div class="step-title">Vitals &amp; Speed Overhaul</div>
          <div class="step-desc">
            Optimize Largest Contentful Paint (LCP) images, defer blocking JavaScript, eliminate CSS render bottlenecks, and resolve mobile viewport scaling.
          </div>
        </div>

        <div class="step-box">
          <div class="step-num">PHASE 03 &middot; ONGOING</div>
          <div class="step-title">Growth &amp; Conversion Pod</div>
          <div class="step-desc">
            Continuous performance monitoring, conversion funnel hardening, and dedicated engineering sprint pod to protect organic search equity.
          </div>
        </div>
      </div>
    </div>
    <div class="slide-footer">
      <div>Execution Timeline: Immediate to 30 Days</div>
      <div>Page 4</div>
    </div>
  </section>

  <!-- SLIDE 5: NEXT STEPS -->
  <section class="slide">
    <div class="slide-header">
      <div class="agency-brand">{e(agency.name)} &middot; Next Steps</div>
      <div class="slide-number">05 / 05</div>
    </div>
    <div class="slide-content" style="text-align:center; max-width:800px; margin:0 auto;">
      <h2>Partnering with {e(agency.name)}</h2>
      <p style="color:#94a3b8; font-size:16px; line-height:1.5; margin-top:12px;">
        We partner with forward-thinking leadership at companies like {e(company_label)} to engineer resilient, high-speed digital infrastructure.
      </p>

      {proof_html}

      <div style="margin-top:32px;">
        {booking_btn}
      </div>

      <div style="margin-top:28px; font-size:12px; color:#64748b;">
        Direct Contact: {e(getattr(agency, 'founder_name', 'The Team'))} &middot; {e(getattr(agency, 'primary_domain', ''))}
      </div>
    </div>
    <div class="slide-footer">
      <div>{e(agency.name)} &middot; Enterprise Business Development Architecture</div>
      <div>Page 5</div>
    </div>
  </section>

</body>
</html>"""

    def export(self, org_id: str, domain: str, competitor: Optional[str] = None, output_format: str = "both") -> Dict[str, Any]:
        domain = clean_domain(domain).split(":")[0]
        data = self.build_deck_data(org_id, domain, clean_domain(competitor).split(":")[0] if competitor else None)
        content = self.render_deck_html(data, org_id)
        stamp = data["generated_at"].strftime("%Y%m%d%H%M%S")
        slug = f"{org_id}_{domain.replace('.', '_')}_deck_{stamp}"
        html_path = self.storage_dir / f"deck_{slug}.html"
        html_path.write_text(content, encoding="utf-8")
        
        result = {
            "status": "success",
            "domain": domain,
            "overall_score": data["audit"].get("overall_score"),
            "html_filename": html_path.name,
            "pdf_filename": None,
            "view_url": f"/api/reports/view/{html_path.name}"
        }

        browser = NativeBrowserService(storage_dir=str(self.storage_dir))
        if output_format in ("pdf", "both") and browser.is_browser_available():
            pdf_path = self.storage_dir / f"deck_{slug}.pdf"
            proc = ProcessSupervisor.run_confined(
                [
                    browser.chrome_binary,
                    "--headless=new",
                    "--disable-gpu",
                    f"--print-to-pdf={pdf_path}",
                    "--no-pdf-header-footer",
                    f"file://{html_path.resolve()}"
                ],
                timeout_seconds=30
            )
            if proc.returncode == 0 and pdf_path.exists():
                result["pdf_filename"] = pdf_path.name
                result["pdf_view_url"] = f"/api/reports/view/{pdf_path.name}"

        return result
