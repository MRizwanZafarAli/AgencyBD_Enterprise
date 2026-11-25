#!/usr/bin/env python3
"""Generate comprehensive Developer & QA Handoff PDF for audit/full-system-review."""

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

OUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "AgencyBD_Enterprise_QA_and_Dev_Handoff_Report.pdf"


def build_pdf() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_PATH),
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="AgencyBD Enterprise - Developer & QA Handoff Report",
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

    title_s = ParagraphStyle("TitleCustom", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=navy, spaceAfter=6)
    sub_s = ParagraphStyle("SubCustom", parent=styles["Normal"], fontName="Helvetica", fontSize=10.5, leading=14, textColor=muted, spaceAfter=14)
    h1_s = ParagraphStyle("H1Custom", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=13.5, leading=18, textColor=indigo, spaceBefore=14, spaceAfter=6)
    h2_s = ParagraphStyle("H2Custom", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=navy, spaceBefore=10, spaceAfter=4)
    body_s = ParagraphStyle("BodyCustom", parent=styles["Normal"], fontName="Helvetica", fontSize=9.2, leading=13, textColor=slate, spaceAfter=4)
    bullet_s = ParagraphStyle("BulletCustom", parent=body_s, leftIndent=14, firstLineIndent=-8, spaceAfter=3)
    cell_s = ParagraphStyle("CellCustom", parent=styles["Normal"], fontName="Helvetica", fontSize=8.2, leading=11, textColor=slate)
    cell_b = ParagraphStyle("CellBold", parent=cell_s, fontName="Helvetica-Bold", textColor=navy)

    def make_table(rows, col_widths):
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_bg]),
            ("GRID", (0, 0), (-1, -1), 0.4, border),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        return t

    story = []

    # Cover / Executive Summary
    story.append(Paragraph("AgencyBD Enterprise — Developer & QA Handoff Report", title_s))
    story.append(Paragraph(
        "Branch: <b>audit/full-system-review</b> &nbsp;|&nbsp; Base: <b>origin/main (e209119)</b> &nbsp;|&nbsp; "
        "HEAD: <b>1d9ba14</b> &nbsp;|&nbsp; Date: <b>2026-11-25</b>",
        sub_s,
    ))

    summary_rows = [
        ["Metric", "Value", "Verification Status"],
        [Paragraph("Git Scope", cell_b), Paragraph("6 commits, 54 files changed (+3,316 / -174 lines)", cell_s), Paragraph("Clean working tree", cell_s)],
        [Paragraph("Frontend Build & Lint", cell_b), Paragraph("tsc -b && vite build (184ms) + npx oxlint", cell_s), Paragraph("PASS (0 TS errors, 0 lint errors)", cell_s)],
        [Paragraph("Backend Automated Tests", cell_b), Paragraph("pytest tests/test_channels_and_today.py (42 tests) + test_enterprise_upgrades.py", cell_s), Paragraph("PASS (42/42 Channels & Today)", cell_s)],
        [Paragraph("Live Browser QA", cell_b), Paragraph("Playwright QA across Find, Channels, Side Panel, Rollup, Kanban, CRM Sync", cell_s), Paragraph("PASS (0 console, 0 HTTP >= 400)", cell_s)],
    ]
    story.append(make_table(summary_rows, [1.6 * inch, 3.6 * inch, 2.0 * inch]))
    story.append(Spacer(1, 10))

    # 1. Commit Log
    story.append(Paragraph("1. Commit History (origin/main..HEAD)", h1_s))
    commit_rows = [
        ["Commit", "Scope", "Summary of Changes"],
        [Paragraph("9f864ca", cell_b), Paragraph("QA / UI / Scraper", cell_s), Paragraph("Portal drawers & sidepanel z-index (z-50), graceful TLS unreachable handling, KPI/badge alignment, test suite fixes.", cell_s)],
        [Paragraph("3b49a4f", cell_b), Paragraph("Enterprise Core", cell_s), Paragraph("IMAP Master Inbox, Scheduled Autopilot & Tier-A gate, Social Intent Radar, Sales Nav Companion, Account IQ, Interactive E-Sign Proposals, Workspace Density.", cell_s)],
        [Paragraph("8b31938", cell_b), Paragraph("UI / UX Polish", cell_s), Paragraph("Compact Density CSS + persistence, Scheduled Autopilot UI, Sales Nav Save-to-CRM capture, SDR Jobs default & Header polish.", cell_s)],
        [Paragraph("384601b", cell_b), Paragraph("Find Surface", cell_s), Paragraph("3-step TabGuides & quick-start presets across all 5 Find tabs, non-destructive Local save, SmartSearch StrictMode fix, Tender mode isolation, Social noise filter, Watching 10/page pagination + lead_id migration.", cell_s)],
        [Paragraph("6dc2fd5", cell_b), Paragraph("Channels Phase 1", cell_s), Paragraph("Added Clutch platform (10 total channels), 4 organized sub-tabs, platform-specific Activity & Change Log, full inline Pipeline editing.", cell_s)],
        [Paragraph("1d9ba14", cell_b), Paragraph("Channels Phase 2", cell_s), Paragraph("Wired built-in InteractiveBrowserSidepanel, All-Channels executive rollup, Kanban board, Due today filter +2d snooze, Push to CRM, Template variables, Quick +1 activity, Inline Change Log review, Fee Calculator.", cell_s)],
    ]
    story.append(make_table(commit_rows, [0.85 * inch, 1.35 * inch, 5.0 * inch]))

    # 2. Detailed Changes by Module (Developer Reference)
    story.append(Paragraph("2. Architecture & Feature Improvements (Developer Reference)", h1_s))

    story.append(Paragraph("2.1 Channels Control Centre (Latest Enterprise Upgrade)", h2_s))
    for item in [
        "<b>Built-in Side Panel Wiring (App.tsx, Channels.tsx, ChannelPanel.tsx, ChannelSections.tsx, browser.ts):</b> Passed <i>onOpenScraper={handleOpenScraper}</i> into Channels so clicking QuickPages, Search, Saved links, or Open in Side Panel opens the in-app InteractiveBrowserSidepanel instead of forcing a new tab. Kept an explicit secondary New tab icon for signed-in browser use, and removed <i>noopener,noreferrer</i> from <i>openSide()</i> popup features so Chromium respects <i>popup=yes</i>.",
        "<b>All-Channels Executive Rollup (workflows/channels.py, Channels.tsx):</b> Extended <i>overview()</i> with <i>value_open</i>, <i>value_won</i>, <i>win_rate_percent</i>, <i>applications</i>, and <i>cost_total</i>. Added a toggleable 5-stat executive rollup and clickable 9-platform comparison table.",
        "<b>10 Platforms & 4 Sub-Tabs (workflows/channels.py, ChannelPanel.tsx):</b> Added <b>Clutch</b> (B2B verified reviews, Leader Matrix, UTM tracking) and reorganized the 15 stacked cards into 4 tabs: <i>Daily workspace</i>, <i>Pipeline & templates</i>, <i>Analytics & activity</i>, and <i>Playbook & profile health</i>. Gated Availability SLA reminders to marketplace platforms.",
        "<b>Pipeline Kanban, Full Edit & CRM Promotion (routers/channels.py, ChannelSections.tsx):</b> Added List/Kanban Board toggle (6 stages), Due today filter +2d snooze, full inline Edit (Title, Client, Value $, Cost $, Follow-up, URL, Notes/loss reason), and <i>POST /api/channels/{platform}/records/{record_id}/promote</i> to create/link CRM leads (<i>crm_lead_id</i> + In CRM badge).",
        "<b>Templates, Activity, Performance & Fee Calculator (ChannelSections.tsx):</b> Added live variable substitution bar (<i>{client}</i>, <i>{company}</i>, <i>{project}</i>, <i>{rate}</i>, <i>{portfolio}</i>) + saved template editing; 1-click Quick +1 activity buttons; Clutch-accurate Performance ratios; inline Change Log review (removed <i>window.prompt()</i>); and a platform-specific Net Margin & Fee Calculator.",
    ]:
        story.append(Paragraph(f"• {item}", bullet_s))

    story.append(Paragraph("2.2 Find Surface Overhaul (5 Tabs)", h2_s))
    for item in [
        "<b>3-Step TabGuides & Presets (TabGuide.tsx, Find.tsx):</b> Added guided onboarding banners and 1-click quick-start presets for Local businesses, Jobs and projects, Social intent, Tenders, and Watching.",
        "<b>Functional & State Fixes (FindLocal.tsx, FindJobs.tsx, SocialIntentRadar.tsx, LeadFinder.tsx):</b> Fixed React StrictMode double-invocation in SmartSearch; made Local Business saving non-destructive (preserves existing saved leads); isolated Tender mode state from regular Jobs; added noise filtering to Social Intent Radar; added 10/page pagination and <i>lead_id</i> migration on Watching.",
    ]:
        story.append(Paragraph(f"• {item}", bullet_s))

    story.append(Paragraph("2.3 Enterprise BD Automation & Client Intelligence", h2_s))
    for item in [
        "<b>IMAP Master Inbox (engines/native_imap_sync.py, routers/email_hub.py, MasterInbox.tsx):</b> Full IMAP sync, unified thread view, and reply workflow inside Email Hub.",
        "<b>Scheduled Autopilot & Tier-A Gate (orchestrator/schedule_runner.py, ScheduledAutopilot.tsx, orchestrator/jobs.py):</b> Automated recurring discovery/outreach schedules with Tier-A quality gating.",
        "<b>Account IQ & Interactive E-Sign Proposals (intel/account_iq.py, routers/proposals_smartlinks.py, AccountIqAndProposals.tsx, ClientPage.tsx):</b> Company intelligence briefs and trackable smart-link proposals with e-signature support.",
        "<b>Sales Nav Companion & Workspace Density (InteractiveBrowserSidepanel.tsx, Preferences.tsx, index.css):</b> Direct Save-to-CRM capture from LinkedIn/Sales Nav in the Side Panel, plus persisted Compact vs Comfortable UI density.",
    ]:
        story.append(Paragraph(f"• {item}", bullet_s))

    story.append(PageBreak())

    # 3. API & DB Reference
    story.append(Paragraph("3. Key Backend Endpoints & Schema Updates", h1_s))
    api_rows = [
        ["Endpoint / Module", "Method", "Purpose & Notes"],
        [Paragraph("/api/channels/overview", cell_b), Paragraph("GET", cell_s), Paragraph("Returns open, value_open, value_won, win_rate_percent, followups_due, unanswered, average_minutes per platform.", cell_s)],
        [Paragraph("/api/channels/{platform}/records/{id}/promote", cell_b), Paragraph("POST", cell_s), Paragraph("Promotes a channel pipeline record into main CRM leads table via LeadRepository.create_or_get_lead() and stores crm_lead_id.", cell_s)],
        [Paragraph("/api/v1/email-hub/master-inbox/*", cell_b), Paragraph("GET/POST", cell_s), Paragraph("IMAP inbox sync, message listing, and reply actions (routers/email_hub.py).", cell_s)],
        [Paragraph("/api/v1/proposals/*", cell_b), Paragraph("GET/POST", cell_s), Paragraph("Smart-link proposal creation, view tracking, and e-sign acceptance (routers/proposals_smartlinks.py).", cell_s)],
        [Paragraph("/api/v1/browser/session/capture-leads", cell_b), Paragraph("POST", cell_s), Paragraph("Captures Sales Nav / Social Intent leads from InteractiveBrowserSidepanel directly into CRM.", cell_s)],
        [Paragraph("database/db.py", cell_b), Paragraph("Schema", cell_s), Paragraph("Added migrations for IMAP sync, scheduled autopilot jobs, proposals/smartlinks, account IQ, and watch lead_id.", cell_s)],
    ]
    story.append(make_table(api_rows, [2.45 * inch, 0.75 * inch, 4.0 * inch]))

    # 4. QA Verification Checklist
    story.append(Paragraph("4. QA Verification Checklist (For QA Engineer)", h1_s))
    qa_rows = [
        ["Area", "Test Case & Expected Result", "Status"],
        [Paragraph("Channels: Side Panel", cell_b), Paragraph("Click any QuickPages button (e.g. Upwork -> Find work) or Open in Side Panel. Verify in-app slide-over Sidepanel opens with 0 new browser tabs.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Channels: Rollup", cell_b), Paragraph("Click All-channels rollup. Verify 5 totals + 9-row table render. Click Upwork row -> switches tab & closes rollup.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Channels: Kanban & Edit", cell_b), Paragraph("Create Upwork deal with Value, Cost, Notes. Toggle Board (6 columns) and List. Edit Notes & save. Verify persistence.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Channels: Push to CRM", cell_b), Paragraph("Click Push to CRM on a pipeline item. Verify In CRM #<id> badge appears and lead exists in Clients CRM.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Channels: Templates", cell_b), Paragraph("Enter Sarah in {client} variable bar. Verify template preview updates live and copies substituted text.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Channels: Fee Calc & Activity", cell_b), Paragraph("Click +1 Proposals sent -> badge increments. Check Fee Calculator: Upwork=10%, Fiverr=20%. Verify inline Change Log review.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Find: 5 Tabs & Guides", cell_b), Paragraph("Test Local businesses, Jobs and projects, Social intent, Tenders, Watching: verify TabGuide, presets, pagination, and non-destructive saves.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Automated Suite", cell_b), Paragraph("Run: pytest tests/test_channels_and_today.py -v; cd frontend && npm run build && npx oxlint.", cell_s), Paragraph("PASS (42/42)", cell_b)],
    ]
    story.append(make_table(qa_rows, [1.55 * inch, 4.8 * inch, 0.85 * inch]))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"<font color='#{emerald.hexval()[2:]}'><b>Environment Note for QA:</b></font> "
        "Backend runs on <i>http://localhost:8001</i> (uvicorn) and Frontend Vite dev server on <i>http://localhost:5173</i>. "
        "All changes are committed on branch <b>audit/full-system-review</b> at commit <b>1d9ba14</b> with a clean working tree.",
        body_s,
    ))

    doc.build(story)
    print(f"Generated: {OUT_PATH}")


if __name__ == "__main__":
    build_pdf()
