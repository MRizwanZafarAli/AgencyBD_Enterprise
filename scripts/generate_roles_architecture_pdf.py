#!/usr/bin/env python3
"""Generate comprehensive Enterprise Roles & User Access Architecture PDF."""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "AgencyBD_Enterprise_Roles_and_Access_Architecture.pdf"


def build_pdf() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_PATH),
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="AgencyBD Enterprise - Roles & User Access Architecture",
        author="AgencyBD Engineering",
    )

    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0F172A")
    indigo = colors.HexColor("#4F46E5")
    slate = colors.HexColor("#334155")
    muted = colors.HexColor("#64748B")
    light_bg = colors.HexColor("#F8FAFC")
    border = colors.HexColor("#CBD5E1")
    emerald = colors.HexColor("#047857")

    title_s = ParagraphStyle("TitleCustom", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=navy, spaceAfter=5)
    sub_s = ParagraphStyle("SubCustom", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=13.5, textColor=muted, spaceAfter=12)
    h1_s = ParagraphStyle("H1Custom", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=indigo, spaceBefore=12, spaceAfter=5)
    h2_s = ParagraphStyle("H2Custom", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=navy, spaceBefore=9, spaceAfter=3)
    body_s = ParagraphStyle("BodyCustom", parent=styles["Normal"], fontName="Helvetica", fontSize=9.2, leading=13, textColor=slate, spaceAfter=4)
    bullet_s = ParagraphStyle("BulletCustom", parent=body_s, leftIndent=12, firstLineIndent=-8, spaceAfter=3)
    cell_s = ParagraphStyle("CellCustom", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10.5, textColor=slate)
    cell_b = ParagraphStyle("CellBold", parent=cell_s, fontName="Helvetica-Bold", textColor=navy)

    def make_table(rows, col_widths):
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8.2),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_bg]),
            ("GRID", (0, 0), (-1, -1), 0.4, border),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5.5),
        ]))
        return t

    story = []

    # Cover / Executive Summary
    story.append(Paragraph("AgencyBD Enterprise — Roles & User Access Architecture", title_s))
    story.append(Paragraph(
        "Future-Proof RBAC & Workspace Design for a 10+ Person Agency and Multi-Tenant SaaS &nbsp;|&nbsp; Date: <b>2026-11-26</b>",
        sub_s,
    ))

    story.append(Paragraph("1. Executive Verdict: Are 4 Roles Enough?", h1_s))
    story.append(Paragraph(
        "<b>Short Answer:</b> For a small 1–4 person internal team today, the existing 4 roles "
        "(<i>super_admin</i>, <i>growth_lead</i>, <i>sdr_rep</i>, <i>auditor</i>) cover basic operations. "
        "However, for a <b>10+ person agency</b> or a <b>multi-tenant SaaS product</b>, 4 shared tier-password roles "
        "are <b>not sufficient</b> and introduce accountability, security, and UI permission gaps.",
        body_s,
    ))

    story.append(Paragraph("Why the Current 4-Tier Model Hits a Ceiling", h2_s))
    for item in [
        "<b>Shared Tier Passwords Instead of Individual Users:</b> Today, <i>security/auth.py</i> authenticates by tier password rather than individual user accounts (email + password). If 5 BD reps share one <i>sdr_rep</i> login, the system cannot track who owns a deal, who sent a proposal, or each rep's win rate.",
        "<b>Missing Agency Owner Role (org_admin):</b> Only <i>super_admin</i> can access Settings. In a SaaS product, paying agency owners need to manage their own team seats, billing, integrations, and templates without holding cross-tenant <i>super_admin</i> privileges.",
        "<b>UI vs Backend Permission Drift:</b> <i>growth_lead</i> has backend permissions for <i>webhooks:manage</i> and <i>portfolio:manage</i>, yet <i>App.tsx</i> blocks <i>growth_lead</i> from opening the Settings surface.",
        "<b>Pure Read-Only Auditor vs Real Agency Pre-Sales:</b> In real agencies, technical staff run <i>Site Clinic</i> audits, <i>Account IQ</i> briefs, and <i>Call Notes to SOW</i>. A purely passive read-only <i>auditor</i> rarely reflects how a 10-person team operates.",
    ]:
        story.append(Paragraph(f"• {item}", bullet_s))

    # Section 2: Recommended 6-Role Architecture
    story.append(Paragraph("2. Recommended Enterprise Model: 6 Roles (5 Internal + 1 External)", h1_s))
    story.append(Paragraph(
        "Six roles is the enterprise SaaS sweet spot (similar to HubSpot, Apollo, and Salesforce): "
        "it provides strict separation of duties without creating bloated menus or confusing permissions.",
        body_s,
    ))

    role_rows = [
        ["Role", "Who It Is", "Allowed Access & Capabilities", "Restricted / Excluded"],
        [
            Paragraph("1. super_admin<br/>(Platform Owner)", cell_b),
            Paragraph("SaaS / System Owner", cell_s),
            Paragraph("All 7 surfaces across all tenants/orgs, global outbound kill-switch, DNS/SMTP infra, security, billing, API/system health.", cell_s),
            Paragraph("None (full platform control).", cell_s),
        ],
        [
            Paragraph("2. org_admin<br/>(Agency Owner — New)", cell_b),
            Paragraph("Head of a client agency or internal ops admin", cell_s),
            Paragraph("All 7 surfaces scoped strictly to <b>their own org_id</b>: manage team seats, agency profile, API keys, webhooks, templates, and workspace billing.", cell_s),
            Paragraph("Other tenants/orgs, platform-wide infrastructure, cross-org telemetry.", cell_s),
        ],
        [
            Paragraph("3. growth_lead<br/>(BD Manager)", cell_b),
            Paragraph("Head of Sales / BD Director", cell_s),
            Paragraph("Today, Find, Clients, Channels, Email Hub, Tools + <b>Workspace Settings</b> (Services & Proof, Alerts, Webhooks, Preferences). Approves Tier-A HITL outreach; views team ROI & rep leaderboards.", cell_s),
            Paragraph("Security/RBAC, DNS/SMTP infra, global kill-switch, org billing.", cell_s),
        ],
        [
            Paragraph("4. bd_rep<br/>(Evolves sdr_rep)", cell_b),
            Paragraph("Upwork/LinkedIn Bidder, SDR, Account Executive", cell_s),
            Paragraph("Today, Find, Clients, Channels, Email Hub, Tools — scoped to <b>their own assigned deals</b>, daily routines, outreach drafts/sends, and personal quotas.", cell_s),
            Paragraph("Admin settings, billing, global outbound halt, deleting other reps' deals.", cell_s),
        ],
        [
            Paragraph("5. specialist<br/>(Upgrades auditor)", cell_b),
            Paragraph("Solutions Engineer, SEO/Tech Auditor, Pre-Sales", cell_s),
            Paragraph("Today (audit queue), Clients (Technical Audits, Account IQ, Proposals), Tools (Site Clinic, Compare Sites, Client Report, Call Notes to SOW).", cell_s),
            Paragraph("Cold email blasts, mailbox fleet config, deal margin/pricing edits, Settings.", cell_s),
        ],
        [
            Paragraph("6. client_viewer<br/>(External — Future)", cell_b),
            Paragraph("Prospect or External Client", cell_s),
            Paragraph("Branded Smart-Link Deal Room (/p/{token}): view interactive proposal, e-sign acceptance, and download website health report.", cell_s),
            Paragraph("All internal surfaces (Today, Find, Clients CRM, Channels, Email Hub, Tools, Settings).", cell_s),
        ],
    ]
    story.append(make_table(role_rows, [1.2 * inch, 1.25 * inch, 2.7 * inch, 2.15 * inch]))

    story.append(PageBreak())

    # Section 3: Surface Matrix
    story.append(Paragraph("3. Role-to-UI Surface Access Matrix", h1_s))
    matrix_rows = [
        ["Surface / Area", "super_admin", "org_admin", "growth_lead", "bd_rep", "specialist", "client_viewer"],
        [Paragraph("Today (Role Dashboard)", cell_b), Paragraph("All Orgs", cell_s), Paragraph("Org Overview", cell_s), Paragraph("Team + Rep KPIs", cell_s), Paragraph("My Quota & Tasks", cell_s), Paragraph("Audit Queue", cell_s), Paragraph("No", cell_s)],
        [Paragraph("Find (Hunt & Radar)", cell_b), Paragraph("Full", cell_s), Paragraph("Full", cell_s), Paragraph("Full", cell_s), Paragraph("Full", cell_s), Paragraph("No", cell_s), Paragraph("No", cell_s)],
        [Paragraph("Clients (CRM & IQ)", cell_b), Paragraph("Full", cell_s), Paragraph("Full (Org)", cell_s), Paragraph("Full (Team)", cell_s), Paragraph("My Deals / Assigned", cell_s), Paragraph("Audits & IQ Only", cell_s), Paragraph("No", cell_s)],
        [Paragraph("Channels (10 Sites)", cell_b), Paragraph("Full", cell_s), Paragraph("Full (Org)", cell_s), Paragraph("Team Rollup + All", cell_s), Paragraph("My Pipeline & Routine", cell_s), Paragraph("No", cell_s), Paragraph("No", cell_s)],
        [Paragraph("Email Hub (Inbox/Send)", cell_b), Paragraph("Full", cell_s), Paragraph("Full (Org)", cell_s), Paragraph("Full + Approvals", cell_s), Paragraph("Compose & My Inbox", cell_s), Paragraph("No", cell_s), Paragraph("No", cell_s)],
        [Paragraph("Tools (Clinic/Coach)", cell_b), Paragraph("All Tools", cell_s), Paragraph("All Tools", cell_s), Paragraph("All Tools", cell_s), Paragraph("Outreach & Research", cell_s), Paragraph("Clinic, Report, SOW", cell_s), Paragraph("No", cell_s)],
        [Paragraph("Settings", cell_b), Paragraph("All Sections", cell_s), Paragraph("Org Sections", cell_s), Paragraph("Workspace & Alerts", cell_s), Paragraph("Preferences Only", cell_s), Paragraph("Preferences Only", cell_s), Paragraph("No", cell_s)],
        [Paragraph("Deal Room (/p/{token})", cell_b), Paragraph("Manage", cell_s), Paragraph("Manage", cell_s), Paragraph("Manage", cell_s), Paragraph("Share Link", cell_s), Paragraph("Preview", cell_s), Paragraph("View & E-Sign", cell_s)],
    ]
    story.append(make_table(matrix_rows, [1.5 * inch, 0.95 * inch, 0.95 * inch, 1.05 * inch, 1.05 * inch, 0.95 * inch, 0.85 * inch]))

    # Section 4: Implementation Roadmap
    story.append(Paragraph("4. Implementation Roadmap & Architecture Upgrades", h1_s))
    for item in [
        "<b>Phase A — Individual User Accounts & Deal Ownership:</b> Replace shared tier passwords in <i>security/auth.py</i> with a <i>users</i> table (id, org_id, email, password_hash, role, display_name, is_active). Add <i>owner_user_id</i> to <i>leads</i> and <i>channel_records</i> so <b>My Deals vs Team Deals</b> filters and <b>Rep Leaderboards</b> work cleanly across Today, Channels, and Clients.",
        "<b>Phase B — Scoped Settings & Unified UI/API Policy:</b> Allow <i>growth_lead</i> and <i>org_admin</i> into scoped Settings sections (Agency Profile, Services & Proof, Alerts, Webhooks, Preferences) while locking Security/DNS/RBAC. Consolidate <i>Sidebar.tsx</i> and <i>App.tsx</i> to read from one shared <i>ROLE_UI_POLICY</i> so frontend navigation and backend RBAC never drift.",
        "<b>Phase C — External Client Portal (client_viewer):</b> Extend <i>proposals_smartlinks.py</i> (/p/{token}) with optional client comments and downloadable Site Clinic PDF teardowns, giving prospects a clean deal room with zero internal CRM exposure.",
    ]:
        story.append(Paragraph(f"• {item}", bullet_s))

    # Section 5: Stakeholder Discussion Questions
    story.append(Paragraph("5. Decisions Needed From Team & Stakeholders", h1_s))
    q_rows = [
        ["#", "Decision Topic", "Options to Align On"],
        [Paragraph("1", cell_b), Paragraph("6-Role Structure", cell_s), Paragraph("Confirm whether the 6 roles (super_admin, org_admin, growth_lead, bd_rep, specialist, client_viewer) match our agency + SaaS roadmap.", cell_s)],
        [Paragraph("2", cell_b), Paragraph("Lead Visibility for bd_rep", cell_s), Paragraph("Should a bd_rep see all team leads in Clients (read-only) to prevent duplicate outreach, or only their own assigned deals?", cell_s)],
        [Paragraph("3", cell_b), Paragraph("Tool & Margin Boundaries", cell_s), Paragraph("Confirm if specialists should view deal values/margins or only technical audits, Account IQ, and SOW generation.", cell_s)],
    ]
    story.append(make_table(q_rows, [0.4 * inch, 1.8 * inch, 5.1 * inch]))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"<font color='#{emerald.hexval()[2:]}'><b>Reference Files:</b></font> "
        "<i>security/auth.py</i> (ROLE_PERMISSIONS), <i>frontend/src/App.tsx</i> (ALLOWED_SURFACES), "
        "<i>frontend/src/components/layout/Sidebar.tsx</i>, and <i>routers/proposals_smartlinks.py</i>.",
        body_s,
    ))

    doc.build(story)
    print(f"Generated: {OUT_PATH}")


if __name__ == "__main__":
    build_pdf()
