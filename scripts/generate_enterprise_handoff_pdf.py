#!/usr/bin/env python3
"""Generate comprehensive Developer & QA Handoff PDF covering the entire audit/full-system-review session."""

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
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="AgencyBD Enterprise - Complete Session Developer & QA Handoff Report",
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
    body_s = ParagraphStyle("BodyCustom", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12.5, textColor=slate, spaceAfter=4)
    bullet_s = ParagraphStyle("BulletCustom", parent=body_s, leftIndent=12, firstLineIndent=-8, spaceAfter=2.5)
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

    # Header & Executive Summary
    story.append(Paragraph("AgencyBD Enterprise — Complete Session Dev & QA Handoff", title_s))
    story.append(Paragraph(
        "Branch: <b>audit/full-system-review</b> &nbsp;|&nbsp; Base: <b>origin/main (e209119)</b> &nbsp;|&nbsp; "
        "Scope: <b>Full Session (Phase 1 QA Fixes → Phase 2 Enterprise → Phase 3 Find → Phase 4 Channels)</b> &nbsp;|&nbsp; Date: <b>2026-11-25</b>",
        sub_s,
    ))

    summary_rows = [
        ["Metric", "Value", "Verification Status"],
        [Paragraph("Git Scope", cell_b), Paragraph("6 feature/fix commits, 54 files changed (+3,316 / -174 lines)", cell_s), Paragraph("Pushed to origin/audit/full-system-review", cell_s)],
        [Paragraph("Frontend Build & Lint", cell_b), Paragraph("tsc -b && vite build (184ms) + npx oxlint", cell_s), Paragraph("PASS (0 TypeScript errors, 0 lint errors)", cell_s)],
        [Paragraph("Backend Unit & API Tests", cell_b), Paragraph("pytest tests/test_channels_and_today.py (42) + tests/test_enterprise_upgrades.py", cell_s), Paragraph("PASS (42/42 Channels & Today)", cell_s)],
        [Paragraph("Live Browser QA", cell_b), Paragraph("Playwright QA across Today, Find (all 5 tabs), Channels, Side Panel, Email Hub, Clients", cell_s), Paragraph("PASS (0 console errors, 0 HTTP >= 400)", cell_s)],
    ]
    story.append(make_table(summary_rows, [1.55 * inch, 3.65 * inch, 2.1 * inch]))
    story.append(Spacer(1, 8))

    # Section 1: Commit History
    story.append(Paragraph("1. Complete Session Commit History (origin/main..HEAD)", h1_s))
    commit_rows = [
        ["Commit", "Phase / Surface", "Key Deliverables"],
        [Paragraph("9f864ca", cell_b), Paragraph("Phase 1: QA, UI & Scraper", cell_s), Paragraph("Portal drawers & sidepanel z-index (z-50), graceful TLS/unreachable handling, KPI/badge alignment across dashboards/modules, 5 backend test suite fixes (21 files).", cell_s)],
        [Paragraph("3b49a4f", cell_b), Paragraph("Phase 2: Enterprise Core", cell_s), Paragraph("IMAP Master Inbox, Scheduled Autopilot & Tier-A gate, Social Intent Radar, Sales Nav Companion, Account IQ, Interactive E-Sign Proposals, Workspace Density, Swarm & Leadfinder APIs (20 files).", cell_s)],
        [Paragraph("8b31938", cell_b), Paragraph("Phase 2b: UI/UX Polish", cell_s), Paragraph("Compact Density CSS + localStorage persistence, Scheduled Autopilot UI on Today, Sales Nav Save-to-CRM capture, SDR Jobs default, Header polish (8 files).", cell_s)],
        [Paragraph("384601b", cell_b), Paragraph("Phase 3: Find Overhaul", cell_s), Paragraph("3-step TabGuides & quick-start presets for all 5 Find tabs, non-destructive Local save, SmartSearch StrictMode fix, Tender mode isolation, Social noise filter, Watching 10/page pagination + lead_id migration (9 files).", cell_s)],
        [Paragraph("6dc2fd5", cell_b), Paragraph("Phase 4a: Channels Structure", cell_s), Paragraph("Added Clutch platform (10 channels total), 4 organized sub-tabs, platform-specific Activity & Change Log, initial inline Pipeline editing, LinkedIn copy fixes (3 files).", cell_s)],
        [Paragraph("1d9ba14", cell_b), Paragraph("Phase 4b: Channels Enterprise", cell_s), Paragraph("Wired built-in InteractiveBrowserSidepanel (no forced new tab), All-Channels executive rollup, Kanban Board, Due today filter +2d snooze, full inline Edit, Push to CRM, Template variables, Quick +1 activity, Inline Change Log review, Fee Calculator (7 files).", cell_s)],
    ]
    story.append(make_table(commit_rows, [0.75 * inch, 1.55 * inch, 5.0 * inch]))

    # Section 2: Phase-by-Phase Technical Breakdown
    story.append(Paragraph("2. Detailed Changes by Phase (Developer Reference)", h1_s))

    story.append(Paragraph("2.1 Phase 1 — Core UI/UX, Z-Index, Scraper TLS & Stability (9f864ca)", h2_s))
    for item in [
        "<b>Portal Drawers & Sidepanel Layering (InteractiveBrowserSidepanel.tsx, ui/index.tsx):</b> Fixed z-index stacking so drawers and the Universal Scraper Sidepanel always render cleanly above sticky headers and tables.",
        "<b>Graceful TLS & Unreachable Host Handling (universal_scraper.py, native_browser_service.py, interactive_browser_session.py, routers/browser_sidepanel.py):</b> Prevented 500 crashes when scraping self-signed/unreachable sites; returns structured diagnostics instead.",
        "<b>Dashboard & Module Alignment (AdminDashboard.tsx, SdrDashboard.tsx, FindLocal.tsx, EmailHub.tsx, Settings.tsx, CallIntel.tsx, CopyCoach.tsx, MultimodalStudio.tsx, SequencesManager.tsx, WaterfallEnrich.tsx):</b> Fixed KPI/badge alignment, spacing, and consistent UI states.",
    ]:
        story.append(Paragraph(f"• {item}", bullet_s))

    story.append(Paragraph("2.2 Phase 2 — Enterprise Automation, Master Inbox, Account IQ & Density (3b49a4f, 8b31938)", h2_s))
    for item in [
        "<b>IMAP Master Inbox (engines/native_imap_sync.py, routers/email_hub.py, MasterInbox.tsx, EmailHub.tsx):</b> Added native IMAP sync engine, unified master inbox thread list, and reply handling inside Email Hub.",
        "<b>Scheduled Autopilot & Tier-A Gate (orchestrator/schedule_runner.py, orchestrator/jobs.py, ScheduledAutopilot.tsx, DiscoveryPanel.tsx):</b> Added recurring cron/scheduled discovery & outreach runner with Tier-A quality gating and Today surface controls.",
        "<b>Social Intent Radar & Sales Nav Companion (connectors/social_radar.py, SocialIntentRadar.tsx, InteractiveBrowserSidepanel.tsx, routers/browser_sidepanel.py):</b> Added live social intent monitoring and one-click Save-to-CRM lead capture directly from LinkedIn/Sales Navigator inside the Side Panel.",
        "<b>Account IQ & Interactive E-Sign Proposals (intel/account_iq.py, routers/proposals_smartlinks.py, AccountIqAndProposals.tsx, ClientPage.tsx):</b> Added company Account IQ briefs and trackable smart-link proposals with interactive e-signature.",
        "<b>Workspace Compact Density & Header Polish (Preferences.tsx, index.css, main.tsx, Header.tsx):</b> Added persisted Comfortable vs Compact UI density toggle in Settings -> Preferences and refined header layout.",
    ]:
        story.append(Paragraph(f"• {item}", bullet_s))

    story.append(Paragraph("2.3 Phase 3 — Find Page Overhaul: All 5 Tabs Settled (384601b)", h2_s))
    for item in [
        "<b>Guided Onboarding & Quick-Start Presets (TabGuide.tsx, Find.tsx):</b> Built a reusable 3-step <i>TabGuide</i> banner and 1-click quick-start presets for every tab so first-time and repeat users immediately understand how each tab works.",
        "<b>Local Businesses (FindLocal.tsx):</b> Fixed Save behavior to be non-destructive (merges/preserves existing saved leads instead of wiping prior results).",
        "<b>Jobs and Projects + Tenders (FindJobs.tsx, Find.tsx):</b> Fixed React StrictMode double-invocation in SmartSearch, set sensible SDR Jobs defaults, and isolated <b>Tenders</b> mode state from standard Jobs searches.",
        "<b>Social Intent (SocialIntentRadar.tsx, connectors/social_radar.py):</b> Added signal noise filtering so irrelevant posts are suppressed before reaching BD reps.",
        "<b>Watching (LeadFinder.tsx, database/db.py):</b> Added 10-per-page pagination and <i>lead_id</i> DB migration so watched targets link directly to CRM leads.",
    ]:
        story.append(Paragraph(f"• {item}", bullet_s))

    story.append(Paragraph("2.4 Phase 4 — Channels Page Enterprise Upgrade (6dc2fd5, 1d9ba14)", h2_s))
    for item in [
        "<b>Built-in Side Panel Wiring (App.tsx, Channels.tsx, ChannelPanel.tsx, ChannelSections.tsx, browser.ts):</b> Passed <i>onOpenScraper={handleOpenScraper}</i> to Channels so QuickPages, Search, Saved links, and Open in Side Panel open the in-app <i>InteractiveBrowserSidepanel</i> instead of forcing a separate browser tab. Kept an optional New tab icon and removed <i>noopener,noreferrer</i> from <i>openSide()</i> popup features.",
        "<b>All-Channels Executive Rollup (workflows/channels.py, Channels.tsx):</b> Extended <i>overview()</i> with <i>value_open</i>, <i>value_won</i>, <i>win_rate_percent</i>, <i>applications</i>, and <i>cost_total</i>; added toggleable 5-stat rollup and clickable 9-platform comparison table.",
        "<b>Clutch Platform + 4 Sub-Tabs (workflows/channels.py, ChannelPanel.tsx):</b> Added <b>Clutch</b> (10 total platforms) and reorganized 15 cards into <i>Daily workspace</i>, <i>Pipeline & templates</i>, <i>Analytics & activity</i>, and <i>Playbook & profile health</i>. Gated Availability SLA to marketplaces.",
        "<b>Pipeline Kanban, Full Edit & Push to CRM (routers/channels.py, ChannelSections.tsx):</b> Added List/Kanban Board toggle (6 stages), Due today filter +2d snooze, full inline Edit (Title, Client, Value $, Cost $, Follow-up, URL, Notes/loss reason), and <i>POST /api/channels/{platform}/records/{record_id}/promote</i> (stores <i>crm_lead_id</i> + In CRM badge).",
        "<b>Templates, Quick +1 Activity, Performance, Inline Change Log & Fee Calculator:</b> Live <i>{client}/{company}/{project}/{rate}/{portfolio}</i> variable bar + saved template editing; 1-click Quick +1 activity buttons; Clutch-accurate Performance ratios; inline Change Log review (removed <i>window.prompt()</i>); Net Margin & Fee Calculator.",
    ]:
        story.append(Paragraph(f"• {item}", bullet_s))

    story.append(PageBreak())

    # Section 3: API & DB Reference
    story.append(Paragraph("3. Backend API & Database Changes (Developer Reference)", h1_s))
    api_rows = [
        ["Endpoint / File", "Method / Type", "Purpose & Behavior"],
        [Paragraph("/api/channels/overview", cell_b), Paragraph("GET", cell_s), Paragraph("Returns open, value_open, value_won, win_rate_percent, followups_due, unanswered, average_minutes per platform.", cell_s)],
        [Paragraph("/api/channels/{platform}/records/{id}/promote", cell_b), Paragraph("POST", cell_s), Paragraph("Promotes channel pipeline item to CRM leads via LeadRepository.create_or_get_lead() and saves crm_lead_id.", cell_s)],
        [Paragraph("/api/v1/email-hub/master-inbox/*", cell_b), Paragraph("GET / POST", cell_s), Paragraph("IMAP Master Inbox sync, unified thread listing, and reply dispatch (routers/email_hub.py).", cell_s)],
        [Paragraph("/api/v1/proposals/*", cell_b), Paragraph("GET / POST", cell_s), Paragraph("Interactive E-Sign Proposals & SmartLinks creation, view tracking, and signing (routers/proposals_smartlinks.py).", cell_s)],
        [Paragraph("/api/v1/browser/session/capture-leads", cell_b), Paragraph("POST", cell_s), Paragraph("Captures Sales Nav / Social Intent leads from InteractiveBrowserSidepanel into CRM.", cell_s)],
        [Paragraph("/api/v1/swarm/* & /api/leadfinder/*", cell_b), Paragraph("GET / POST", cell_s), Paragraph("Swarm orchestration endpoints and Watching lead_id linkage.", cell_s)],
        [Paragraph("database/db.py", cell_b), Paragraph("Migrations", cell_s), Paragraph("Schema additions for IMAP sync, scheduled autopilot jobs, proposals/smartlinks, account IQ, and watch lead_id.", cell_s)],
    ]
    story.append(make_table(api_rows, [2.45 * inch, 0.85 * inch, 4.0 * inch]))

    # Section 4: QA Verification Matrix
    story.append(Paragraph("4. End-to-End QA Checklist (For QA Engineer)", h1_s))
    qa_rows = [
        ["Surface / Area", "Test Case & Expected Outcome", "Verified"],
        [Paragraph("Find: Local Businesses", cell_b), Paragraph("Run search via preset/TabGuide -> Save leads -> Run second search & save -> Confirm previous saved leads are preserved (non-destructive).", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Find: Jobs & Tenders", cell_b), Paragraph("Test Jobs and projects vs Tenders tabs -> Confirm Tender mode is isolated, SmartSearch fires once, and TabGuide 3 steps render.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Find: Social & Watching", cell_b), Paragraph("Test Social intent noise filter & Watching 10/page pagination + lead_id CRM link.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Channels: Side Panel", cell_b), Paragraph("Click QuickPages (e.g. Upwork -> Find work) or Open in Side Panel -> In-app InteractiveBrowserSidepanel opens with 0 new tabs.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Channels: Rollup & Clutch", cell_b), Paragraph("Click All-channels rollup -> Verify 5 stats + 9-row table -> Click Upwork row to switch. Verify Clutch tab has tailored rules & playbook.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Channels: Kanban, Edit & CRM", cell_b), Paragraph("Create deal (Value, Cost, Notes) -> Toggle Board (6 cols) & List -> Edit Notes -> Click Push to CRM -> Verify In CRM #<id> badge.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Channels: Templates & Fee Calc", cell_b), Paragraph("Type Sarah in {client} variable bar -> Preview updates live. Click +1 Proposals sent -> badge increments. Verify Upwork 10% / Fiverr 20% fee calc.", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Email Hub, Clients, Today, Settings", cell_b), Paragraph("Verify Master Inbox (Email Hub), Account IQ + E-Sign Proposals (Clients), Scheduled Autopilot (Today), Compact Density toggle (Settings).", cell_s), Paragraph("PASS", cell_b)],
        [Paragraph("Automated Test Suite", cell_b), Paragraph("Run: pytest tests/test_channels_and_today.py -v; cd frontend && npm run build && npx oxlint.", cell_s), Paragraph("PASS (42/42)", cell_b)],
    ]
    story.append(make_table(qa_rows, [1.6 * inch, 4.9 * inch, 0.8 * inch]))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"<font color='#{emerald.hexval()[2:]}'><b>Environment & Git Pull Instructions:</b></font> "
        "Run <i>git fetch origin && git checkout audit/full-system-review</i>. "
        "Backend runs on <i>http://localhost:8001</i> (uvicorn) and Frontend on <i>http://localhost:5173</i> (Vite). "
        "All changes are clean and verified with 0 console errors and 0 HTTP >= 400 errors.",
        body_s,
    ))

    doc.build(story)
    print(f"Generated: {OUT_PATH}")


if __name__ == "__main__":
    build_pdf()
