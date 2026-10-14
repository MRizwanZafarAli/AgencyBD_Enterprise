"""
AgencyBD_Enterprise: Ultra-Luxury Streamlit Command Center.
Autonomous Multi-Agent Business Development & Lead Intelligence Swarm for Software Agencies.
"""

import os
import streamlit as st
import pandas as pd
import json
import time

from orchestrator.swarm_engine import SwarmEngine
from database.models import (
    LeadRepository, AuditRepository, ContactRepository,
    OutreachRepository, ReplyRepository, BookingRepository
)
from database.security_vault import SecurityVault
from database.db import (
    create_api_key_record, list_api_keys, revoke_api_key_record,
    add_entity_to_suppression, is_entity_suppressed
)
from config.deliverability import SECONDARY_SENDING_DOMAINS, analyze_spam_friction
from config.settings import settings
from data.geo_database import GeoDatabase
from agents.market_intelligence_agent import MarketIntelligenceAgent
from analytics.financial_ledger import FinancialLedger
from analytics.ab_testing_cohorts import SpintaxABOptimizer
from tasks.task_queue import TaskQueueEngine
from core.metrics import MetricsManager
from agents.inbound_webhook_router import InboundWebhookRouter
from adapters.vendor_connectors import VendorConnectors
from config.dns_fleet_configurator import DNSFleetConfigurator
from engines.native_smtp_verifier import NativeSMTPVerifier
from engines.native_tech_stack_fingerprinter import NativeTechStackFingerprinter
from engines.native_visitor_deanonymizer import NativeVisitorDeanonymizer
from engines.native_warmup_engine import NativeWarmupEngine
from engines.native_sales_intelligence import NativeSalesIntelligence
from engines.native_multimodal_generator import NativeMultimodalGenerator
from engines.native_copy_coach import NativeCopyCoach
from engines.native_waterfall_orchestrator import NativeWaterfallOrchestrator
from engines.native_smartlead_router import NativeSmartleadRouter

# Page Configuration
st.set_page_config(
    page_title="ApexCore | Autonomous BD Swarm",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-End Styling
st.markdown("""
<style>
    .reportview-container { background: #0B0F19; }
    .main { background-color: #0B0F19; }
    h1, h2, h3, h4, h5, h6 { color: #F3F4F6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .metric-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
    }
    .badge-success { background: #065F46; color: #34D399; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 12px; }
    .badge-warning { background: #78350F; color: #FBBF24; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 12px; }
    .badge-danger { background: #7F1D1D; color: #F87171; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 12px; }
    .stButton>button {
        background: linear-gradient(90deg, #2563EB 0%, #1D4ED8 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 10px 24px;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #1D4ED8 0%, #1E40AF 100%);
        box-shadow: 0 0 15px rgba(37, 99, 235, 0.5);
    }
</style>
""", unsafe_allow_html=True)

# Authentication gate (must run before any data is rendered)
from security.dashboard_gate import require_dashboard_login
require_dashboard_login(st)

# Initialize Engine
@st.cache_resource
def get_engine():
    return SwarmEngine()

engine = get_engine()

# --- TOP NAVIGATION & HEADER ---
st.title("⚡ ApexCore Autonomous BD Swarm")
st.markdown("### *Enterprise Lead Intelligence & Autonomous Technical Sourcing Engine*")

# Live KPI Metric Strip
metrics = engine.get_pipeline_metrics()
c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    st.markdown("""
    <div class="metric-card">
        <p style="color: #9CA3AF; margin: 0; font-size: 13px;">Total Prospects</p>
        <h2 style="margin: 4px 0 0 0; color: #60A5FA;">{}</h2>
    </div>
    """.format(metrics["total_leads"]), unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="metric-card">
        <p style="color: #9CA3AF; margin: 0; font-size: 13px;">Technical Audits</p>
        <h2 style="margin: 4px 0 0 0; color: #34D399;">{}</h2>
    </div>
    """.format(metrics["total_audited"]), unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div class="metric-card">
        <p style="color: #9CA3AF; margin: 0; font-size: 13px;">Verified DMs (0% Bounce)</p>
        <h2 style="margin: 4px 0 0 0; color: #A78BFA;">{}</h2>
    </div>
    """.format(metrics["total_verified_emails"]), unsafe_allow_html=True)

with c4:
    st.markdown("""
    <div class="metric-card">
        <p style="color: #9CA3AF; margin: 0; font-size: 13px;">Sequences Sent</p>
        <h2 style="margin: 4px 0 0 0; color: #FBBF24;">{}</h2>
    </div>
    """.format(metrics["total_sent"]), unsafe_allow_html=True)

with c5:
    st.markdown("""
    <div class="metric-card">
        <p style="color: #9CA3AF; margin: 0; font-size: 13px;">Reply Rate</p>
        <h2 style="margin: 4px 0 0 0; color: #F472B6;">{}%</h2>
    </div>
    """.format(metrics["reply_rate_percent"]), unsafe_allow_html=True)

with c6:
    st.markdown("""
    <div class="metric-card">
        <p style="color: #9CA3AF; margin: 0; font-size: 13px;">Pipeline Value</p>
        <h2 style="margin: 4px 0 0 0; color: #10B981;">${:,.0f}</h2>
    </div>
    """.format(metrics["estimated_pipeline_value_usd"]), unsafe_allow_html=True)

st.write("")

# Main Interface Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13, tab14, tab15 = st.tabs([
    "🛰️ Sourcing Radar",
    "👔 LinkedIn People Radar",
    "🕷️ Website Contact Crawler",
    "🔬 Technical Audit Lab",
    "✍️ Sequence Studio",
    "🛡️ Objection Triage Desk",
    "📅 Discovery Calls & Briefs",
    "🌐 Deliverability & Inboxes",
    "🚀 Next-Gen & Future GTM Lab",
    "🔒 Cryptographic Vault & Suppression",
    "⚡ Circuit Breaker, CRM & HITL Gate",
    "🌍 Global Geo & AI Market Recommender",
    "📊 Prometheus Telemetry & DLQ Queue",
    "🔐 Zero-Trust Keys & Inbound Webhooks",
    "🛠️ BD Tool Matrix & Vendor Hub"
])

# ==========================================
# TAB 1: SOURCING RADAR
# ==========================================
with tab1:
    st.subheader("Autonomous Multi-Channel Lead Ingestion")
    st.markdown("Harvest high-ticket accounts from Google Maps, Tech Hiring Signals, and Venture capital announcements.")
    
    col_s1, col_s2, col_s3, col_s4 = st.columns([2, 2, 1, 1])
    with col_s1:
        s_channel = st.selectbox("Ingestion Pipeline", ["google_maps", "hiring_intent", "venture_database"], format_func=lambda x: {
            "google_maps": "📍 Google Maps (High-Ticket Local B2B)",
            "hiring_intent": "💼 Hiring Signals (JobSpy / Open Roles)",
            "venture_database": "🚀 Venture Database (Seed & Series A)"
        }[x])
    with col_s2:
        default_q = "Commercial Roofing" if s_channel == "google_maps" else ("Senior React Engineer" if s_channel == "hiring_intent" else "Series A")
        s_query = st.text_input("Target Query / Role Keyword", value=default_q)
    with col_s3:
        s_loc = st.text_input("Location / Metro", value="Austin, TX" if s_channel == "google_maps" else "United States / Remote")
    with col_s4:
        s_limit = st.number_input("Ingest Limit", min_value=1, max_value=25, value=5)

    if st.button("🚀 Execute Autonomous Sourcing", use_container_width=True):
        with st.spinner("SourcingAgent actively crawling and extracting decision entities..."):
            sourced = engine.source_leads(channel=s_channel, query=s_query, location=s_loc, limit=s_limit)
            st.success(f"Successfully ingested {len(sourced)} target accounts into the pipeline!")

    # Display Leads Table
    leads = LeadRepository.list_leads(limit=100)
    if leads:
        df_leads = pd.DataFrame(leads)[["id", "company_name", "domain", "source_channel", "rating", "reviews_count", "status", "created_at"]]
        st.dataframe(df_leads, use_container_width=True)
    else:
        st.info("No leads ingested yet. Run the Sourcing Agent above to populate.")

# ==========================================
# TAB 2: LINKEDIN PEOPLE & COMPANY RADAR
# ==========================================
with tab2:
    st.subheader("👔 Dedicated LinkedIn Prospecting & Executive Discovery")
    st.markdown("Execute precision Google X-Ray searches, uncover verified CTO/Founder LinkedIn profiles, and draft instant InMail & Connection requests.")

    li_mode = st.radio("LinkedIn Sourcing Mode", ["Search Decision Makers by Company", "Search Companies & Startups on LinkedIn"], horizontal=True)

    if li_mode == "Search Decision Makers by Company":
        col_li1, col_li2, col_li3 = st.columns([2, 2, 1])
        with col_li1:
            leads = LeadRepository.list_leads(limit=100)
            comp_suggestions = [l["company_name"] for l in leads] if leads else ["OmniStream Analytics", "Stripe", "Lone Star Luxury Renovations"]
            li_company = st.selectbox("Target Company", comp_suggestions)
        with col_li2:
            li_titles = st.multiselect("Target Leadership Titles", ["CTO", "Chief Technology Officer", "VP of Engineering", "Founder", "CEO", "Head of Product", "Chief AI Officer"], default=["CTO", "VP of Engineering", "Founder"])
        with col_li3:
            li_limit = st.number_input("Results Limit", min_value=1, max_value=10, value=3, key="li_lim")

        if st.button("🔍 Search & Extract LinkedIn Profiles", use_container_width=True):
            with st.spinner(f"Executing Google X-Ray query on LinkedIn for {li_company}..."):
                people = engine.source_linkedin_people(company_name=li_company, titles=li_titles, limit=li_limit)
                st.session_state["discovered_li_people"] = people
                st.success(f"Found {len(people)} verified executive profiles!")

        if "discovered_li_people" in st.session_state:
            st.write("---")
            st.markdown("#### 👤 Discovered Leadership Profiles")
            for p in st.session_state["discovered_li_people"]:
                with st.container():
                    st.markdown(f"""
                    <div class="metric-card" style="margin-bottom: 12px;">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div>
                                <h3 style="margin:0; color:#60A5FA;">{p['first_name']} {p['last_name']}</h3>
                                <p style="margin:2px 0 6px 0; color:#F3F4F6; font-weight:600;">{p['title']}</p>
                                <p style="margin:0; color:#9CA3AF; font-size:13px;">{p['headline']}</p>
                                <p style="margin:4px 0 0 0; color:#D1D5DB; font-size:12px;">📍 {p['location']} | Degree: <span class="badge-success">{p['connection_degree']} Connection</span></p>
                            </div>
                            <div>
                                <a href="{p['linkedin_url']}" target="_blank" style="background:#0A66C2; color:white; padding:8px 14px; border-radius:6px; text-decoration:none; font-weight:600; font-size:13px;">🔗 Open LinkedIn</a>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Generate tailored LinkedIn message
                    seq = engine.generate_linkedin_outreach(p["first_name"], p["company"], "noticed your team scaling core architecture")
                    st.markdown(f"**Personalized Connection Request Note ({seq['connection_note_char_count']}/300 chars):**")
                    st.code(seq["connection_request_note"], language="text")

    else:
        # Search Companies on LinkedIn
        col_lic1, col_lic2, col_lic3 = st.columns([2, 1, 1])
        with col_lic1:
            lic_keyword = st.text_input("Tech Keyword", value="AI Multi-Agent Systems")
        with col_lic2:
            lic_loc = st.text_input("Location", value="San Francisco, CA")
        with col_lic3:
            lic_limit = st.number_input("Limit", min_value=1, max_value=10, value=3, key="lic_lim")

        if st.button("🏢 Prospect Companies on LinkedIn", use_container_width=True):
            with st.spinner("Extracting tech companies from LinkedIn directory..."):
                comps = engine.source_leads(channel="linkedin_company_search", query=lic_keyword, location=lic_loc, limit=lic_limit)
                st.success(f"Discovered {len(comps)} companies on LinkedIn and added them to pipeline!")
                df_lic = pd.DataFrame(comps)[["company_name", "domain", "address", "rating", "notes"]]
                st.dataframe(df_lic, use_container_width=True)

# ==========================================
# TAB 3: WEBSITE CONTACT CRAWLER
# ==========================================
with tab3:
    st.subheader("🕷️ Deep Website & Leadership Scraper")
    st.markdown("Directly crawls `/`, `/about`, `/team`, and `/contact` to extract unmasked `mailto:` emails, phone numbers, and leadership names.")

    crawl_domain_input = st.text_input("Target Domain to Crawl", value="lonestarluxuryremodel.com")
    
    if st.button("🕷️ Execute Deep Website Crawl", use_container_width=True):
        with st.spinner(f"Crawling {crawl_domain_input} for direct emails, phone numbers, and social links..."):
            crawl_data = engine.crawl_website_for_contacts(crawl_domain_input)
            st.session_state["crawl_data"] = crawl_data
            st.success("Website Crawl Finished!")

    if "crawl_data" in st.session_state:
        cd = st.session_state["crawl_data"]
        st.write("---")
        cw1, cw2, cw3 = st.columns(3)
        with cw1:
            st.markdown("#### ✉️ Discovered Direct Emails")
            for em in cd["verified_emails"]:
                st.markdown(f"- `{em}`")
        with cw2:
            st.markdown("#### 📞 Telephone Numbers")
            for ph in cd["phone_numbers"]:
                st.markdown(f"- `{ph}`")
            if not cd["phone_numbers"]:
                st.info("No raw phone numbers embedded in HTML.")
        with cw3:
            st.markdown("#### 👥 Leadership / Team Members")
            for leader in cd["discovered_leaders"]:
                st.markdown(f"- 👤 **{leader}**")
            if not cd["discovered_leaders"]:
                st.info("Founders list in /about page parsed.")

# ==========================================
# TAB 4: TECHNICAL AUDIT LAB
# ==========================================
with tab4:
    st.subheader("Automated Technical Audit & Architecture Inspector")
    st.markdown("Headless web auditor testing Core Web Vitals, detecting legacy tech stacks, and generating conversion-focused pitching ammo.")

    leads = LeadRepository.list_leads(limit=100)
    if not leads:
        st.warning("Please source leads first in the Sourcing Radar tab.")
    else:
        lead_options = {f"#{l['id']} - {l['company_name']} ({l['domain']})": l["id"] for l in leads}
        selected_label = st.selectbox("Select Target Company", list(lead_options.keys()))
        selected_lead_id = lead_options[selected_label]

        col_a1, col_a2 = st.columns([1, 1])
        with col_a1:
            if st.button("🔬 Run Headless Tech Audit", use_container_width=True):
                with st.spinner("Analyzing TTFB, Lighthouse LCP, DOM structure, and security headers..."):
                    audit_res = engine.audit_lead(selected_lead_id)
                    st.success("Technical Audit Completed & Saved!")

        with col_a2:
            if st.button("⚡ Run Full Autonomous Pipeline (Audit -> Enrich -> Copywrite -> Send)", use_container_width=True):
                with st.spinner("Executing full 8-agent swarm workflow..."):
                    full_res = engine.run_autonomous_pipeline(selected_lead_id)
                    st.success(f"Pipeline executed! Sequence dispatched from {full_res['dispatch']['dispatched_from_inbox']}")

        # Show Audit Details
        audit = AuditRepository.get_audit_by_lead(selected_lead_id)
        if audit:
            st.write("---")
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                lcp = audit["lcp_score"]
                color = "#34D399" if lcp <= 2.5 else "#F87171"
                st.markdown(f"**Largest Contentful Paint (LCP)**<br><h3 style='color:{color};'>{lcp}s</h3><span style='font-size:12px; color:#9CA3AF;'>Threshold: 2.5s</span>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"**Total Page Latency**<br><h3 style='color:#60A5FA;'>{audit['load_time_ms']} ms</h3><span style='font-size:12px; color:#9CA3AF;'>TTFB: {audit['ttfb_ms']} ms</span>", unsafe_allow_html=True)
            with m3:
                resp_text = "✅ Responsive" if audit["mobile_responsive"] else "❌ Viewport Missing"
                st.markdown(f"**Mobile UX Layout**<br><h3 style='color:#A78BFA;'>{resp_text}</h3>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"**Identified Vulnerabilities**<br><h3 style='color:#FBBF24;'>{len(audit['missing_headers'])} Missing</h3><span style='font-size:12px; color:#9CA3AF;'>Headers / Security</span>", unsafe_allow_html=True)

            col_detail1, col_detail2 = st.columns(2)
            with col_detail1:
                st.markdown("#### 🧩 Detected Tech Stack & CMS")
                for tech in audit["tech_stack"]:
                    st.markdown(f"- 🏷️ `{tech}`")
                st.markdown("#### 🔒 Missing Security Headers")
                for h in audit["missing_headers"]:
                    st.markdown(f"- ⚠️ `{h}`")

            with col_detail2:
                st.markdown("#### 🎯 Formulated Pitch Angle")
                st.info(audit["calculated_pitch_angle"])
                st.markdown("#### 📋 Executive Audit Summary")
                st.write(audit["audit_summary"])

# ==========================================
# TAB 5: SEQUENCE STUDIO
# ==========================================
with tab5:
    st.subheader("Trigger-Based 3-Step Outreach Studio & Deliverability Guard")
    st.markdown("Hyper-personalized cold outreach engineered under 80 words with zero spam trigger words.")

    leads = LeadRepository.list_leads(limit=100)
    if leads:
        lead_options = {f"#{l['id']} - {l['company_name']} ({l['domain']})": l["id"] for l in leads}
        selected_label = st.selectbox("Select Account for Outreach", list(lead_options.keys()), key="seq_lead_select")
        selected_lead_id = lead_options[selected_label]

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("👥 Step 1: Enrich Executive Decision Maker", use_container_width=True):
                with st.spinner("Finding CTO / Founder & verifying SMTP deliverability..."):
                    dm = engine.enrich_lead(selected_lead_id)
                    st.success(f"Enriched: {dm['first_name']} {dm['last_name']} ({dm['title']}) - {dm['email']}")

        with col_c2:
            if st.button("✍️ Step 2: Generate 3-Step Sequence", use_container_width=True):
                with st.spinner("Crafting trigger-based copy & auditing spam scores..."):
                    seq = engine.generate_copywriting(selected_lead_id)
                    st.success("High-Converting Sequences Generated!")

        # Display Contacts & Sequences
        contacts = ContactRepository.get_contacts_by_lead(selected_lead_id)
        sequences = OutreachRepository.get_sequences_by_lead(selected_lead_id)

        if contacts:
            c = contacts[0]
            st.markdown(f"""
            **Target Decision Maker:** `{c['first_name']} {c['last_name']}` | **Title:** `{c['title']}` | **Email:** `{c['email']}`  
            *Verification Status:* <span class="badge-success">{c['verification_status'].upper()}</span> &nbsp;
            *SMTP Status:* `{c['smtp_handshake_status']}`
            """, unsafe_allow_html=True)

        if sequences:
            st.write("---")
            seq_col1, seq_col2, seq_col3 = st.columns(3)
            for s in sequences:
                box = seq_col1 if s["step_number"] == 1 else (seq_col2 if s["step_number"] == 2 else seq_col3)
                with box:
                    st.markdown(f"### Step {s['step_number']} Email")
                    st.markdown(f"**Subject:** `{s['subject']}`")
                    st.text_area(f"Body (Step {s['step_number']})", value=s["body"], height=160, key=f"step_{s['id']}")
                    
                    spam_score, flagged, rating = analyze_spam_friction(s["subject"], s["body"])
                    st.markdown(f"**Spam Score:** `{spam_score}` ({rating})")
                    if flagged:
                        st.warning(f"Flagged terms: {', '.join(flagged)}")

            st.write("")
            if st.button("📤 Dispatch Sequence to Sending Queue", use_container_width=True):
                with st.spinner("Rotated to secondary sending inbox with human-paced delay..."):
                    disp = engine.dispatch_lead(selected_lead_id)
                    st.success(f"Email dispatched from inbox: {disp['dispatched_from_inbox']} (Domain: {disp['sending_domain']})")

# ==========================================
# TAB 6: OBJECTION TRIAGE DESK
# ==========================================
with tab6:
    st.subheader("Autonomous Inbound Objection Triage Desk")
    st.markdown("Paste incoming prospect email responses. The AI classifies sentiment and drafts winning senior rebuttals.")

    leads = LeadRepository.list_leads(limit=100)
    if leads:
        lead_options = {f"#{l['id']} - {l['company_name']}": l["id"] for l in leads}
        obj_lead_id = st.selectbox("Prospect Replying", list(lead_options.keys()), key="obj_lead_sel")
        
        # Sample quick test templates
        sample_choice = st.selectbox("Quick-Load Objection Scenario", [
            "We already have an in-house engineering team handling this.",
            "We don't have budget for any external agencies this quarter.",
            "Sounds interesting, mind sending over more information?",
            "Yes, Thursday at 2pm works for a quick walkthrough.",
            "Please unsubscribe and remove me from your mailing list."
        ])
        
        reply_input = st.text_area("Inbound Reply Text", value=sample_choice, height=90)
        
        if st.button("🧠 Classify Reply & Draft Rebuttal", use_container_width=True):
            with st.spinner("Triaging sentiment and crafting rebuttal..."):
                triage_res = engine.triage_reply(lead_id=obj_lead_id, reply_text=reply_input)
                
                st.write("---")
                o_c1, o_c2 = st.columns([1, 2])
                with o_c1:
                    st.markdown("#### 📊 Triage Breakdown")
                    st.markdown(f"**Sentiment:** `{triage_res['sentiment'].upper()}`")
                    st.markdown(f"**Category:** `{triage_res['objection_category'].replace('_', ' ').title()}`")
                    st.markdown(f"**Strategy:** {triage_res['rebuttal_strategy']}")
                with o_c2:
                    st.markdown("#### ✉️ Suggested Senior Rebuttal")
                    st.text_area("Auto-Drafted Response", value=triage_res["auto_rebuttal_draft"], height=180)

# ==========================================
# TAB 7: DISCOVERY CALLS & BRIEFS
# ==========================================
with tab7:
    st.subheader("Founder Discovery Call Briefing Packs & Bookings")
    st.markdown("Executive 1-page dossiers prepared for agency partners to close contracts on discovery calls.")

    leads = LeadRepository.list_leads(limit=100)
    if leads:
        lead_options = {f"#{l['id']} - {l['company_name']}": l["id"] for l in leads}
        book_lead_id = st.selectbox("Convert Account to Booking", list(lead_options.keys()), key="book_lead_sel")
        b_time = st.text_input("Meeting Slot", value="Thursday, Oct 16th @ 2:00 PM EST")

        if st.button("📅 Confirm Discovery Call Booking", use_container_width=True):
            b_res = engine.book_meeting(lead_id=book_lead_id, booking_time=b_time)
            st.success(f"Meeting booked for {b_res['company_name']}! Executive brief generated.")

    # Show Bookings Table
    bookings = BookingRepository.list_bookings()
    if bookings:
        for b in bookings:
            st.write("---")
            st.markdown(f"### 🤝 Discovery Call #{b['id']}")
            st.markdown(f"**Meeting Time:** `{b['booking_time']}` | **Calendar URL:** [{b['cal_link']}]({b['cal_link']})")
            st.text_area("Executive Founder Prep Brief", value=b["founder_prep_brief"], height=200, key=f"brief_{b['id']}")
    else:
        st.info("No discovery calls booked yet.")

# ==========================================
# TAB 8: DELIVERABILITY & INBOXES
# ==========================================
with tab8:
    st.subheader("Secondary Sending Domain Pool & Deliverability Guard")
    st.markdown("Multi-domain rotation protecting primary agency reputation with SPF, DKIM, and DMARC enforcement.")

    for domain_info in SECONDARY_SENDING_DOMAINS:
        with st.container():
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom: 12px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <h4 style="margin:0; color:#F3F4F6;">📫 {domain_info['inbox']}</h4>
                        <span style="color:#9CA3AF; font-size:12px;">Domain: {domain_info['domain']} | Warmup Age: {domain_info['warmup_days']} days</span>
                    </div>
                    <div>
                        <span class="badge-success">SPF VALID</span> &nbsp;
                        <span class="badge-success">DKIM 2048-BIT</span> &nbsp;
                        <span class="badge-success">DMARC p=reject</span>
                    </div>
                </div>
                <div style="margin-top: 12px;">
                    <p style="margin:0 0 4px 0; font-size:12px; color:#9CA3AF;">Daily Volume: {domain_info['sent_today']} / {domain_info['daily_limit']} sent today</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.progress(min(domain_info["sent_today"] / domain_info["daily_limit"], 1.0))

# ==========================================
# TAB 9: NEXT-GEN & FUTURE GTM LAB (2026-2027)
# ==========================================
with tab9:
    st.subheader("🚀 Next-Generation & Future GTM Lab")
    st.markdown("Explore autonomous B2B technologies shaping 2026 and 2027: **RB2B Visitor De-anonymization**, **Retell AI / Bland AI Conversational Calling**, and **Tavus / HeyGen Dynamic Video Cloning**.")

    fg_mode = st.radio("Next-Gen Tooling Simulation", [
        "1. RB2B / Warmly Website Visitor De-anonymization",
        "2. Retell AI / Bland AI Autonomous Voice SDR Pathway",
        "3. Tavus / HeyGen 1-to-1 Dynamic Video Generation"
    ])

    if "1. RB2B" in fg_mode:
        st.markdown("#### 🕵️ RB2B / Warmly Real-Time IP Reverse-Identity Engine")
        st.markdown("Detect high-intent decision makers browsing your pricing or agency case studies before they fill out a form.")

        fg_col1, fg_col2 = st.columns([1, 2])
        with fg_col1:
            ip_in = st.text_input("Simulated Visitor IP", value="198.51.100.42")
            path_in = st.text_input("Page Visited", value="/pricing-and-ai-agent-sprints")
            if st.button("⚡ Detect & De-anonymize Visitor", use_container_width=True):
                with st.spinner("Resolving IP, social graph, and LinkedIn identity..."):
                    deanon = engine.deanonymize_visitor(ip_address=ip_in, visited_path=path_in)
                    st.session_state["deanon_res"] = deanon
                    st.success("Visitor De-anonymized!")

        with fg_col2:
            if "deanon_res" in st.session_state:
                dr = st.session_state["deanon_res"]
                st.markdown(f"""
                <div class="metric-card">
                    <h3 style="color:#60A5FA; margin:0;">🎯 Identified: {dr['identified_person']}</h3>
                    <p style="color:#F3F4F6; margin:2px 0 6px 0; font-weight:600;">{dr['title']} @ {dr['identified_company']}</p>
                    <p style="color:#D1D5DB; margin:0; font-size:13px;">🔗 <a href="{dr['linkedin_url']}" target="_blank" style="color:#60A5FA;">{dr['linkedin_url']}</a></p>
                    <div style="margin-top:10px;">
                        <span class="badge-danger">{dr['intent_score']}</span>
                    </div>
                    <p style="color:#9CA3AF; margin-top:8px; font-size:13px;"><b>Automated Swarm Action:</b> {dr['automation_action']}</p>
                </div>
                """, unsafe_allow_html=True)

    elif "2. Retell AI" in fg_mode:
        st.markdown("#### 📞 Retell AI / Bland AI Sub-Second Conversational Voice SDR")
        st.markdown("Deploy sub-500ms voice agents that call prospects, qualify technical requirements, and book calendar appointments in a natural human voice.")

        leads = LeadRepository.list_leads(limit=100)
        if leads:
            lead_options = {f"#{l['id']} - {l['company_name']}": l["id"] for l in leads}
            v_lead_id = st.selectbox("Target Account for Voice Outreach", list(lead_options.keys()), key="v_lead_sel")

            if st.button("🎙️ Generate Conversational Call Tree", use_container_width=True):
                with st.spinner("Compiling conversational branching tree..."):
                    voice_res = engine.generate_voice_call_pathway(v_lead_id)
                    st.session_state["voice_res"] = voice_res
                    st.success("Voice Calling Pathway Ready!")

            if "voice_res" in st.session_state:
                vr = st.session_state["voice_res"]
                st.write("---")
                st.markdown(f"**Engine:** `{vr['agent_provider']}` | **Latency Target:** `450ms sub-second`")
                tree = vr["conversational_tree"]
                st.markdown("##### 1. Natural Opening Hook:")
                st.info(tree["step_1_opener"])
                st.markdown("##### 2. Positive Response Pathway:")
                st.write(tree["branch_positive"])
                st.markdown("##### 3. In-House Objection Rebuttal:")
                st.warning(tree["branch_in_house_objection"])
                st.markdown("##### 4. Live Appointment Confirmation:")
                st.success(tree["branch_closing_booking"])

    else:
        st.markdown("#### 🎬 Tavus / HeyGen Dynamic 1-to-1 Video Generation Engine")
        st.markdown("Generate thousands of personalized video teardowns where the founder's AI avatar pitches each prospect by name with their audited website on screen.")

        leads = LeadRepository.list_leads(limit=100)
        if leads:
            lead_options = {f"#{l['id']} - {l['company_name']}": l["id"] for l in leads}
            vid_lead_id = st.selectbox("Target Account for Video Pitch", list(lead_options.keys()), key="vid_lead_sel")

            if st.button("🎥 Generate Dynamic Video Pitch Spec", use_container_width=True):
                with st.spinner("Rendering lip-sync parameters and dynamic background URL..."):
                    video_res = engine.generate_video_pitch_spec(vid_lead_id)
                    st.session_state["video_res"] = video_res
                    st.success("Tavus Dynamic Video Spec Generated!")

            if "video_res" in st.session_state:
                vdr = st.session_state["video_res"]
                st.write("---")
                st.markdown(f"**Provider:** `{vdr['provider']}` | **Duration:** `{vdr['video_duration_seconds']}s`")
                st.markdown(f"**Dynamic Background (Prospect URL):** `{vdr['dynamic_background_url']}`")
                st.markdown("##### 📝 Spoken Lip-Sync Script:")
                st.text_area("Avatar Spoken Audio", value=vdr["spoken_script"], height=120)
                st.markdown(f"**Direct Video Call-to-Action:** [{vdr['video_cta_link']}]({vdr['video_cta_link']})")

# ==========================================
# TAB 10: CRYPTOGRAPHIC VAULT & SUPPRESSION
# ==========================================
with tab10:
    st.subheader("🔒 Cryptographic Security Vault & CAN-SPAM Suppression Engine")
    st.markdown("Tamper-proof digital signatures (HMAC-SHA256) on lead records and constant-time SHA-256 suppression vaults ensuring unhackable integrity and GDPR compliance.")

    col_v1, col_v2 = st.columns(2)
    with col_v1:
        st.markdown("#### 🛡️ Database Record Tamper-Detection Check")
        leads = LeadRepository.list_leads(limit=20)
        if leads:
            tamper_lead_id = st.selectbox("Select Record to Verify Cryptographic Signature", [f"#{l['id']} - {l['company_name']}" for l in leads], key="tamper_sel")
            target_id = int(tamper_lead_id.split(" - ")[0].replace("#", ""))
            target_lead = LeadRepository.get_lead(target_id)
            
            sig = target_lead.get("record_hash")
            st.markdown(f"**Stored HMAC-SHA256 Signature:**")
            st.code(sig or "UNSIGNED_LEGACY_RECORD", language="text")

            if st.button("🔐 Verify HMAC Signature Integrity", use_container_width=True):
                payload = {
                    "company_name": target_lead["company_name"],
                    "domain": target_lead["domain"],
                    "phone": target_lead["phone"],
                    "rating": target_lead["rating"],
                    "source_channel": target_lead["source_channel"]
                }
                is_valid = SecurityVault.verify_record_signature("lead", target_id, payload, sig) if sig else False
                if is_valid:
                    st.success("✅ Signature Verified! Record has NOT been tampered with outside the application.")
                else:
                    st.warning("⚠️ Signature mismatch or unsigned legacy record.")

    with col_v2:
        st.markdown("#### ⛔ Global CAN-SPAM / GDPR Universal Suppression Vault")
        st.markdown("One-click permanent opt-out. Entities are stored as irreversible cryptographic SHA-256 hashes.")
        
        supp_input = st.text_input("Enter Email or Domain to Suppress", value="optout@competitor.com")
        supp_type = st.radio("Entity Type", ["email", "domain"], horizontal=True)

        if st.button("🚫 Enforce Permanent Suppression", use_container_width=True):
            add_entity_to_suppression(supp_input, supp_type, "manual_admin_suppression")
            target_hash = SecurityVault.generate_sha256_hash(supp_input)
            st.success(f"Entity suppressed! Stored Hash: {target_hash[:24]}...")

        st.markdown("##### 🔍 Check Suppression Status")
        check_val = st.text_input("Verify Email/Domain Status", value=supp_input, key="check_supp_in")
        is_sup = is_entity_suppressed(check_val)
        if is_sup:
            st.error(f"⛔ {check_val} is SUPPRESSED. Outbound sequences will be blocked at driver level.")
        else:
            st.success(f"✅ {check_val} is CLEAN (Eligible for outreach).")

# ==========================================
# TAB 11: CIRCUIT BREAKER, CRM & HITL GATE
# ==========================================
with tab11:
    st.subheader("⚡ Automated Circuit Breaker, HubSpot Sync & HITL Approval Desk")
    st.markdown("Enterprise deliverability kill-switches, bi-directional CRM integration, and Tier-1 Human-in-the-Loop executive review.")

    c_mode = st.radio("Enterprise Control Module", [
        "1. Automated 2% Bounce Rate Circuit Breaker",
        "2. Bi-Directional CRM & Rich Slack Alert Relay",
        "3. Tier-1 Human-in-the-Loop (HITL) Executive Approval Desk"
    ], horizontal=True)

    if "1. Automated 2%" in c_mode:
        st.markdown("#### ⚡ 2% Bounce Rate Automated Kill-Switch")
        st.markdown("Simulate daily sending volume and test whether domain reputation circuit breakers trigger automatically.")
        
        cb_c1, cb_c2, cb_c3 = st.columns(3)
        with cb_c1:
            sim_inbox = st.selectbox("Sender Inbox", [d["inbox"] for d in SECONDARY_SENDING_DOMAINS])
        with cb_c2:
            sim_sent = st.number_input("Simulated Sent in 24h", value=100, min_value=10, max_value=500)
        with cb_c3:
            sim_bounced = st.number_input("Simulated Bounces", value=3, min_value=0, max_value=20)

        if st.button("🧪 Test Circuit Breaker Evaluation", use_container_width=True):
            cb_res = engine.test_circuit_breaker(sim_inbox, sim_sent, sim_bounced)
            st.write("---")
            if "TRIPPED" in cb_res["circuit_breaker_status"]:
                st.error(f"🚨 CIRCUIT BREAKER TRIPPED! Bounce rate: {cb_res['bounce_rate_percent']}% exceeds 2.0% limit.")
                st.warning(f"Action Taken: {cb_res['action_taken']}. Sending paused on this inbox.")
            else:
                st.success(f"✅ Status: HEALTHY. Bounce rate: {cb_res['bounce_rate_percent']}%. Outbound continues normally.")

    elif "2. Bi-Directional CRM" in c_mode:
        st.markdown("#### 🤝 HubSpot Deal Sync & Interactive Slack Webhook Cards")
        leads = LeadRepository.list_leads(limit=20)
        if leads:
            crm_lead_sel = st.selectbox("Select Account for CRM Push", [f"#{l['id']} - {l['company_name']}" for l in leads], key="crm_sel")
            crm_target_id = int(crm_lead_sel.split(" - ")[0].replace("#", ""))

            col_crm1, col_crm2 = st.columns(2)
            with col_crm1:
                if st.button("📊 Sync Deal to HubSpot", use_container_width=True):
                    h_res = engine.sync_crm(crm_target_id, stage="meeting_scheduled", amount=35000.0)
                    st.success(f"HubSpot Deal Created! ID: {h_res['deal_id']} | Amount: ${h_res['amount']:,.0f}")
            with col_crm2:
                if st.button("💬 Dispatch Interactive Slack Card", use_container_width=True):
                    s_res = engine.send_slack_notification("High-Value Discovery Booked", {
                        "company": crm_lead_sel.split(" - ")[1],
                        "domain": "target.io",
                        "value": 35000.0,
                        "lead_id": crm_target_id
                    })
                    st.success(f"Slack webhook card dispatched with 1-click action buttons!")

    else:
        st.markdown("#### 👤 Tiered Human-in-the-Loop (HITL) Executive Approval Gate")
        st.markdown("Hold high-value deals ($50k+) in a review queue. The agency founder can review and grant 1-click sign-off.")

        leads = LeadRepository.list_leads(limit=20)
        if leads:
            hitl_lead_sel = st.selectbox("Select Account for Governance Evaluation", [f"#{l['id']} - {l['company_name']} ({l['source_channel']})" for l in leads], key="hitl_sel")
            hitl_id = int(hitl_lead_sel.split(" - ")[0].replace("#", ""))
            
            deal_val = st.number_input("Estimated Contract Value ($)", value=75000.0, step=5000.0)

            col_h1, col_h2 = st.columns(2)
            with col_h1:
                if st.button("⚖️ Route Governance Tier", use_container_width=True):
                    gov_res = engine.route_governance_tier(hitl_id, deal_val)
                    st.write("---")
                    st.markdown(f"**Governance Tier:** `{gov_res['governance_tier']}`")
                    st.markdown(f"**Dispatch Status:** `{gov_res['dispatch_status']}`")
                    if gov_res["requires_human_signoff"]:
                        st.warning("⚠️ Deal value >= $50,000. Sequence held in founder review bucket.")
                    else:
                        st.success("✅ Deal eligible for 100% autonomous dispatch.")

            with col_h2:
                if st.button("✅ Grant Founder 1-Click Approval", use_container_width=True):
                    app_res = engine.approve_held_lead(hitl_id)
                    st.success(f"Approval granted by {app_res['approver']}! Lead queued for immediate dispatch.")

# ==========================================
# TAB 12: GLOBAL GEO & AI MARKET RECOMMENDER
# ==========================================
with tab12:
    st.subheader("🌍 Global Geographic Intelligence & AI Market Sourcing Recommender")
    st.markdown("Precision territory targeting covering worldwide countries, provinces/states, and tech clusters powered by 2025/2026 enterprise market research.")

    sub_geo1, sub_geo2 = st.tabs(["🤖 AI Project Demand Recommender", "🌐 Global Country, State & City Explorer"])

    with sub_geo1:
        st.markdown("#### 🎯 Synthesize Project Demand & Identify High-Converting Territories")
        st.markdown("Enter your agency's service offering, core tech stack, and contract size. The AI analyzes real-time enterprise budgets and capital flows to recommend optimal geographic clusters.")

        demand_input = st.text_area(
            "Agency Project Demand & Service Offering",
            value="We build custom autonomous LLM multi-agent swarms, enterprise RAG architectures, and high-performance Next.js full-stack applications.",
            height=100
        )
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            ticket_size_sel = st.selectbox("Target Contract Value / Ticket Size", ["$10k-$25k (SME Sprint)", "$25k-$75k (Growth Tier)", "$75k-$200k+ (Enterprise Overhaul)"], index=1)
        with col_d2:
            market_agent = MarketIntelligenceAgent()
            avail_countries = GeoDatabase.get_all_countries()
            focus_countries = st.multiselect("Optional Country Filter (Leave empty for Global)", avail_countries, default=["United States", "United Kingdom", "Germany", "United Arab Emirates"])

        if st.button("🚀 Analyze Project Demand & Recommend Top Geos", use_container_width=True):
            with st.spinner("Synthesizing enterprise research vectors, capital flows, and tech modernization cycles..."):
                intel_res = market_agent.analyze_demand(
                    project_demand=demand_input,
                    ticket_size=ticket_size_sel,
                    target_countries=focus_countries if focus_countries else None
                )

                st.success(f"Market analysis complete! Identified Sector: **{intel_res['detected_market_sector']}**")

                prim = intel_res["primary_target"]
                st.markdown(f"""
                <div class="metric-card" style="border-left: 4px solid #10B981;">
                    <h3 style="margin: 0; color: #34D399;">🏆 Top Recommended Territory: {prim['city']}, {prim['state_province']} ({prim['country']})</h3>
                    <p style="color: #FBBF24; font-size: 16px; margin: 4px 0;">Opportunity Score: <b>{prim['opportunity_score']}/100</b> | Buying Power: <b>Tier-1 Enterprise</b></p>
                    <p style="color: #E5E7EB; margin: 0;"><b>Strategic Rationale:</b> {prim['strategic_rationale']}</p>
                </div>
                """, unsafe_allow_html=True)

                st.write("")
                st.markdown("#### ⚡ Ready-to-Execute Outbound Sourcing Queries")
                q_col1, q_col2 = st.columns(2)
                with q_col1:
                    st.code(f"# Google Maps Sourcing Query:\n{intel_res['operational_search_queries']['google_maps_query']}", language="bash")
                    st.code(f"# JobSpy Hiring Trigger Query:\n{intel_res['operational_search_queries']['jobspy_hiring_trigger']}", language="bash")
                with q_col2:
                    st.code(f"# LinkedIn Boolean X-Ray String:\n{intel_res['operational_search_queries']['linkedin_xray_boolean']}", language="bash")
                    st.markdown(f"**Target Decision Maker Titles:** {', '.join(intel_res['operational_search_queries']['recommended_titles'])}")

                st.markdown("#### 🛡️ High-Friction Regulatory & Technical Pitch Angles")
                for hook in intel_res["regulatory_attack_angles"]:
                    st.markdown(f"• **{hook}**")

                st.write("---")
                st.markdown("#### 🗺️ All Ranked Global Geographic Targets for this Offering")
                ranked_df = pd.DataFrame([
                    {
                        "Rank": idx + 1,
                        "Country": g["country"],
                        "State / Province": g["state"],
                        "Commercial Hubs": ", ".join(g["cities"]),
                        "Opportunity Score": f"{g['score']}/100",
                        "Market Thesis": g["rationale"]
                    }
                    for idx, g in enumerate(intel_res["top_recommended_geos"])
                ])
                st.dataframe(ranked_df, use_container_width=True)

    with sub_geo2:
        st.markdown("#### 🌐 Global Territory & City Hierarchy Explorer")
        st.markdown("Explore countries, states, provinces, and specific commercial tech hubs with purchasing power indicators.")

        c_col1, c_col2, c_col3 = st.columns(3)
        all_countries = GeoDatabase.get_all_countries()
        with c_col1:
            sel_country = st.selectbox("Select Country", all_countries, index=all_countries.index("United States") if "United States" in all_countries else 0)
        
        states = GeoDatabase.get_states_provinces(sel_country)
        with c_col2:
            sel_state = st.selectbox("Select State / Province", states if states else ["N/A"])
        
        cities = GeoDatabase.get_cities(sel_country, sel_state)
        with c_col3:
            sel_city = st.selectbox("Select City / Tech Hub", cities if cities else ["N/A"])

        country_info = GeoDatabase.get_country_info(sel_country)
        if country_info:
            tech_tags = GeoDatabase.get_tech_tags(sel_country, sel_state)
            st.markdown(f"""
            <div class="metric-card">
                <h4>📍 {sel_city}, {sel_state} ({sel_country})</h4>
                <p><b>Global Region:</b> {country_info.get('region')} | <b>Currency:</b> {country_info.get('currency')} | <b>Purchasing Power:</b> {country_info.get('purchasing_power_tier')}</p>
                <p><b>Primary Tech Hub Clusters:</b> {', '.join(tech_tags) if tech_tags else 'General Commercial Enterprise'}</p>
            </div>
            """, unsafe_allow_html=True)

        st.write("")
        st.markdown("#### 🔍 Search Cities Globally")
        search_query = st.text_input("Search city, state, or country worldwide", placeholder="e.g. Zurich, Austin, Munich, Dubai, Singapore")
        if search_query:
            results = GeoDatabase.search_cities_globally(search_query)
            if results:
                st.dataframe(pd.DataFrame(results), use_container_width=True)
            else:
                st.info("No matching locations found.")

# ==========================================
# TAB 13: PROMETHEUS TELEMETRY & DLQ QUEUE
# ==========================================
with tab13:
    st.subheader("📊 Enterprise Observability, Unit Economics & Dead-Letter Queue (DLQ)")
    st.markdown("Prometheus telemetry scrape integration, SDR unit economics ledger, and fault-tolerant background queue recovery.")

    econ = FinancialLedger.get_unit_economics(org_id="org_default", pipeline_deal_size=35000.0)
    e1, e2, e3, e4, e5, e6 = st.columns(6)
    with e1:
        st.metric("Total SDR Spend", f"${econ['total_agent_cost_usd']:,.2f}")
    with e2:
        st.metric("Total Prospects", econ['total_leads_sourced'])
    with e3:
        st.metric("Meetings Booked", econ['total_meetings_booked'])
    with e4:
        st.metric("Cost / Qual. Lead", f"${econ['cost_per_qualified_lead_usd']:,.2f}")
    with e5:
        st.metric("Cost / Meeting", f"${econ['cost_per_booked_meeting_usd']:,.2f}")
    with e6:
        st.metric("Agent ROI Multiple", f"{econ['sdr_roi_multiple']}x")

    st.write("---")
    col_tele1, col_tele2 = st.columns(2)

    with col_tele1:
        st.markdown("#### 🎯 Spintax A/B Cohort Conversion Leaderboard")
        cohort_report = SpintaxABOptimizer.get_cohort_report(org_id="org_default")
        if cohort_report:
            st.dataframe(pd.DataFrame(cohort_report), use_container_width=True)
        else:
            st.info("No A/B variant dispatches recorded yet. Variants will automatically populate upon campaign dispatch.")

    with col_tele2:
        st.markdown("#### ☠️ Dead-Letter Queue (DLQ) Incident Monitor")
        st.markdown("Failed background tasks that exceeded retry limits (3 attempts) are quarantined here for root-cause triage.")
        dlq_tasks = TaskQueueEngine.list_dead_letters(org_id="org_default")
        if dlq_tasks:
            st.warning(f"⚠️ {len(dlq_tasks)} tasks trapped in Dead Letter Queue!")
            for t in dlq_tasks:
                st.markdown(f"**Task ID:** `{t['id']}` | **Task Name:** `{t['task_name']}` | **Retries:** `{t['retries']}`")
                st.error(f"Error: {t['error_message']}")
                if st.button(f"🔄 Re-queue {t['id']}", key=f"requeue_{t['id']}"):
                    TaskQueueEngine.retry_dead_letter(t['id'])
                    st.success(f"Task {t['id']} reset to pending status!")
                    st.rerun()
        else:
            st.success("✅ Zero Dead-Letter Queue failures. All background workers running cleanly.")

    st.write("")
    st.markdown("#### 📈 Live Prometheus Metrics Scrape Endpoint")
    st.markdown("Scraped by Prometheus server every 15s at `/metrics`:")
    prom_sample = MetricsManager.export_prometheus_metrics().decode("utf-8")
    st.code(prom_sample[:1200] + "\n...", language="text")

# ==========================================
# TAB 14: ZERO-TRUST KEYS & INBOUND WEBHOOKS
# ==========================================
with tab14:
    st.subheader("🔐 Zero-Trust Security, API Key Vault & Live Inbound Webhooks")
    st.markdown("Manage enterprise API keys with constant-time verification and simulate incoming prospect reply webhooks.")

    col_sec1, col_sec2 = st.columns(2)

    with col_sec1:
        st.markdown("#### 🔑 Generate Enterprise API Key")
        key_name = st.text_input("Key Label / Service Name", value="Growth SDR Outbound Automation", key="k_name")
        key_user = st.text_input("User ID / Owner", value="founder_alex", key="k_user")
        key_role = st.selectbox("RBAC Role Scope", ["growth_lead", "sdr_rep", "auditor", "super_admin"], key="k_role")
        key_org = st.text_input("Tenant Org ID", value="org_default", key="k_org")

        if st.button("🛡️ Generate Cryptographic Key", use_container_width=True):
            new_key = create_api_key_record(name=key_name, user_id=key_user, role=key_role, org_id=key_org)
            st.success("Enterprise API Key Generated Successfully!")
            st.code(new_key, language="text")
            st.caption("🔒 Warning: Copy this key now. It is stored as an irreversible SHA-256 hash.")

        st.write("---")
        st.markdown("#### 📋 Registered API Keys")
        active_keys = list_api_keys(org_id=key_org)
        if active_keys:
            for k in active_keys:
                status_color = "red" if k["revoked"] else "green"
                status_text = "REVOKED" if k["revoked"] else "ACTIVE"
                col_k1, col_k2 = st.columns([3, 1])
                with col_k1:
                    st.markdown(f"**{k['name']}** (`{k['prefix']}`) | Role: `{k['role']}` | Status: <span style='color:{status_color}; font-weight:bold;'>{status_text}</span>", unsafe_allow_html=True)
                with col_k2:
                    if not k["revoked"]:
                        if st.button("Revoke", key=f"rev_{k['id']}"):
                            revoke_api_key_record(k["id"], org_id=key_org)
                            st.warning("Key revoked instantly!")
                            st.rerun()

    with col_sec2:
        st.markdown("#### 📬 Live Inbound Webhook Simulator")
        st.markdown("Simulate incoming replies from Sendgrid, Resend, or Instantly to test quote stripping, sentiment classification, and auto-suppression.")

        esp_provider = st.selectbox("ESP Provider Payload Format", ["resend", "sendgrid", "generic_email"], index=0)
        sender_in = st.text_input("Prospect Sender Email", value="mark.spencer@targetcorp.com")
        subject_in = st.text_input("Email Subject", value="Re: Architectural teardown")
        body_in = st.text_area(
            "Prospect Email Body (with reply thread history)",
            value="Hi Alex,\nYes, we are definitely interested in discussing the Next.js migration. Are you free Thursday at 2pm?\n\nOn Mon, Oct 12, 2026 at 10:14 AM Alex <alex@apexcore.ai> wrote:\n> Noticed your current setup on TargetCorp is running an older stack...\n-- \nMark Spencer\nVP Engineering | TargetCorp",
            height=130
        )

        if st.button("⚡ Simulate Webhook Ingress", use_container_width=True):
            hook_router = InboundWebhookRouter()
            sim_payload = {
                "from": sender_in,
                "subject": subject_in,
                "text": body_in
            }
            with st.spinner("Processing inbound reply..."):
                hook_res = hook_router.process_inbound_reply(sim_payload)

                st.success("Inbound Webhook Processed Successfully!")
                st.markdown(f"**Cleaned Response (Quotes Stripped):** `{hook_res['clean_body']}`")
                st.markdown(f"**Sentiment Detected:** `{hook_res['sentiment']}` | **Category:** `{hook_res['objection_category']}`")
                if hook_res["auto_suppressed"]:
                    st.error("🚫 Opt-Out Detected: Domain permanently added to CAN-SPAM Suppression Vault!")
                else:
                    st.info("✅ Valid Prospect Response: Generating Automated Rebuttal / Booking Slot.")

                st.markdown("#### 📝 Auto-Generated Rebuttal / Walkthrough Proposal:")
                st.text_area("Rebuttal Draft", value=hook_res["auto_rebuttal"], height=100)

# ==========================================
# TAB 15: BD TOOL MATRIX & VENDOR HUB
# ==========================================
with tab15:
    st.subheader("🛠️ Enterprise BD Software Ecosystem & Automated DNS Fleet Studio")
    st.markdown("Comprehensive breakdown of every modern & future BD tool, automated DNS deliverability generator, and live vendor connector hub.")

    sub_tool1, sub_tool2, sub_tool3, sub_tool4 = st.tabs([
        "📚 Full Modern BD Software Matrix",
        "⚡ Self-Hosted Replacement Engines (Zero API Cost)",
        "🌐 DNS Record Fleet Configurator & Warmup",
        "🔌 Vendor Connectors & API Health Matrix"
    ])

    with sub_tool1:
        st.markdown("#### 🗺️ The Complete Modern & Future Business Development (BD/SDR) Tech Stack")
        st.markdown("How top-performing B2B enterprise SDR teams operate in 2025/2026—and how **AgencyBD_Enterprise** natively unifies them:")

        bd_stack_data = [
            {"Category": "1. Lead Sourcing & Databases", "Industry Standard Tools": "Apollo.io, ZoomInfo, Clay.com, LinkedIn Sales Navigator, Crunchbase, BuiltWith, JobSpy", "AgencyBD Native Equivalent": "Autonomous Maps, Hiring Trigger & Venture Sourcing Swarm"},
            {"Category": "2. Waterfall Email Enrichment", "Industry Standard Tools": "Dropcontact, Hunter.io, Findymail, Prospeo, Datagma, Clearbit", "AgencyBD Native Equivalent": "Multi-Vendor Sequential Waterfall + Socket SMTP MX Handshake"},
            {"Category": "3. Email Verification & Scrubbing", "Industry Standard Tools": "ZeroBounce, NeverBounce, MillionVerifier, Bouncer", "AgencyBD Native Equivalent": "Automated ZeroBounce Gate + DNS Sentry (0.0% Bounce Guarantee)"},
            {"Category": "4. Cold Outreach & Sequencers", "Industry Standard Tools": "Instantly.ai, Smartlead.ai, Lemlist, Outreach.io, Salesloft", "AgencyBD Native Equivalent": "Fleet Domain Rotator + Anti-Clustering Spintax Studio"},
            {"Category": "5. Deliverability & Warmup", "Industry Standard Tools": "Warmy.io, Mailreach, GlockApps, MXToolbox, Mailforge", "AgencyBD Native Equivalent": "2.0% Circuit Breaker Killswitch + Automated DNS Fleet Studio"},
            {"Category": "6. Website Visitor Deanonymization", "Industry Standard Tools": "RB2B, Factors.ai, 6sense, Demandbase, Snitcher, Warmly.ai", "AgencyBD Native Equivalent": "RB2B Reverse-IP & B2B Cookie Deanonymizer Agent"},
            {"Category": "7. Multimodal AI Personalization", "Industry Standard Tools": "Claygent, Lavender.ai, Tavus, HeyGen, Retell AI, Bland.ai", "AgencyBD Native Equivalent": "Lighthouse Performance Teardowns, Tavus Dynamic Video & Retell Voice SDR"},
            {"Category": "8. CRM & Revenue Sync", "Industry Standard Tools": "HubSpot Enterprise, Salesforce, Attio, Close CRM, Pipedrive", "AgencyBD Native Equivalent": "HubSpot Deal Pipeline Relay & Slack Interactive Cards"},
            {"Category": "9. Meeting Scheduling", "Industry Standard Tools": "Cal.com, Calendly, Chili Piper, HubSpot Meetings", "AgencyBD Native Equivalent": "Cal.com Webhook Sync + Founder 1-Page Briefing Dossier"},
            {"Category": "10. Objection Handling & Inbound", "Industry Standard Tools": "Gong.io, Chorus.ai, Fathom AI, Lavender Reply Assistant", "AgencyBD Native Equivalent": "5-Vector Objection Classifier & Auto-Rebuttal Router"}
        ]
        st.dataframe(pd.DataFrame(bd_stack_data), use_container_width=True)

    with sub_tool2:
        st.markdown("#### ⚡ Self-Hosted Replacement Engines: 100% Free of Third-Party API Keys")
        st.markdown(r"Directly beat $50k–$100k/year commercial vendors with our built-in enterprise engines running locally.")

        eng_p1, eng_p2, eng_p3, eng_p4, eng_p5, eng_p6, eng_p7, eng_p8 = st.tabs([
            "🔬 Deep SMTP Verifier (vs ZeroBounce)",
            "🔍 Tech Fingerprinter (vs BuiltWith)",
            "🌊 Waterfall Lead Enrichment (vs Clay)",
            "🪶 Real-Time Copy Coach (vs Lavender)",
            "🚀 Deliverability & Spintax Router (vs Smartlead)",
            "🕵️ Visitor Deanonymizer (vs RB2B)",
            "📈 Call Intelligence (vs Gong)",
            "🎬 Video Storyboard & Voice SDR (vs Tavus/Retell)"
        ])

        with eng_p1:
            st.markdown("##### 🔬 Native Deep Socket SMTP Handshake & Deliverability Verifier")
            st.markdown("RFC 5322 syntax validation, 1,000+ disposable domain blocking, role-account filter, and port 25 MX socket handshake.")
            v_email_in = st.text_input("Enter Email to Verify", value="bu@resend.com", key="v_email_in")
            if st.button("🧪 Execute Deep SMTP Handshake", use_container_width=True):
                with st.spinner("Executing non-intrusive socket handshake..."):
                    verifier_engine = NativeSMTPVerifier()
                    res_ver = verifier_engine.verify_email(v_email_in)
                    c_col1, c_col2 = st.columns(2)
                    with c_col1:
                        st.metric("Deliverability Score", f"{res_ver['confidence_score']}/100")
                        st.markdown(f"**Mailbox Status:** `{res_ver['status']}`")
                        st.markdown(f"**Recommendation:** `{res_ver['recommendation']}`")
                    with c_col2:
                        st.markdown(f"• Catch-All Server: `{'⚠️ Yes' if res_ver['is_catch_all'] else '✅ No'}`")
                        st.markdown(f"• Shared Role Account: `{'⚠️ Yes' if res_ver['is_role_account'] else '✅ No (Personal DM)'}`")
                        st.markdown(f"• Primary MX Host: `{res_ver.get('primary_mx')}`")
                        st.markdown(f"• SMTP Protocol Status: `{res_ver.get('smtp_response')}`")

        with eng_p2:
            st.markdown("##### 🔍 Native 100+ Technology Stack Fingerprinter & Debt Scanner")
            st.markdown("Deep DOM parser detecting Next.js, React, Vue, WordPress, Shopify, GA4, Missing HSTS/CSP headers.")
            fp_domain_in = st.text_input("Enter Domain to Fingerprint", value="resend.com", key="fp_domain_in")
            if st.button("🔎 Scan DOM & Response Headers", use_container_width=True):
                with st.spinner("Scraping DOM and parsing 100+ technology signatures..."):
                    fp_engine = NativeTechStackFingerprinter()
                    res_fp = fp_engine.analyze_domain(fp_domain_in)
                    st.markdown(f"**Detected Technologies:** {', '.join(res_fp['detected_technologies'])}")
                    st.markdown(f"**Technical Debt Score:** `{res_fp['technical_debt_score']}/100`")
                    st.markdown(f"**Calculated Cold Outreach Angle:** `{res_fp['calculated_pitch_angle']}`")
                    if res_fp['missing_security_headers']:
                        st.warning(f"⚠️ Missing Security Headers: {', '.join(res_fp['missing_security_headers'])}")
                    else:
                        st.success("✅ Full enterprise security headers active (HSTS, CSP, X-Frame-Options).")

        with eng_p3:
            st.markdown("##### 🌊 Native 5-Tier Waterfall Lead Enrichment & Claygent Research Studio")
            st.markdown("Chains DNS MX discovery, permutation matrices, SMTP socket probes, and autonomous AI research formulas without paid Clay credits.")
            w_col1, w_col2 = st.columns(2)
            with w_col1:
                w_fn = st.text_input("First Name", value="Alex", key="w_fn")
                w_ln = st.text_input("Last Name", value="Bouaziz", key="w_ln")
            with w_col2:
                w_comp = st.text_input("Company Name", value="Deel", key="w_comp")
                w_dom = st.text_input("Company Domain", value="deel.com", key="w_dom")

            if st.button("⚡ Execute Native Waterfall Enrichment", use_container_width=True):
                with st.spinner("Running 5-tier waterfall sequence..."):
                    waterfall_engine = NativeWaterfallOrchestrator()
                    res_wf = waterfall_engine.run_waterfall_enrichment(w_fn, w_ln, w_comp, w_dom, "CEO & Founder")
                    
                    wf_c1, wf_c2, wf_c3 = st.columns(3)
                    with wf_c1:
                        st.metric("Enriched Email", res_wf["resolved_email"])
                    with wf_c2:
                        st.metric("Confidence Score", f"{res_wf['confidence_score']}/100")
                    with wf_c3:
                        st.metric("SaaS Credits Saved", f"${res_wf['estimated_commercial_dollars_saved']}")
                    
                    st.markdown(f"**Target ESP Infrastructure:** `{res_wf['esp_provider']}` | **Verdict:** `{res_wf['verdict']}`")
                    st.markdown("**Executed Waterfall Steps:**")
                    for s in res_wf["waterfall_steps_executed"]:
                        st.markdown(f"  • {s}")
                    st.markdown("##### 🤖 Claygent Autonomous Research Intelligence Dossier:")
                    st.json(res_wf["autonomous_research_dossier"])

        with eng_p4:
            st.markdown("##### 🪶 Native AI Cold Email Copy Coach & Readability Analyzer")
            st.markdown("Flesch-Kincaid 5th-8th grade scoring, 100+ spam word filter, paragraph density, and low-friction CTA classifier inspired by Lavender.ai.")
            cc_sub = st.text_input("Cold Email Subject Line", value="quick question regarding deel's engineering roadmap", key="cc_sub")
            cc_body = st.text_area(
                "Cold Email Body Draft",
                value="Hi Alex,\n\nNoticed Deel is expanding full-stack engineering sprints. We ran an architectural performance teardown on your customer portal this morning.\n\nOur senior squads plug in to eliminate sprint backlog without the 3-month agency procurement cycle.\n\nWorth exploring a brief look at the teardown notes?",
                height=150,
                key="cc_body"
            )
            if st.button("📊 Audit Cold Email Copy (0-100 Lavender Score)", use_container_width=True):
                res_coach = NativeCopyCoach.score_draft(cc_sub, cc_body)
                c_sc1, c_sc2, c_sc3 = st.columns(3)
                with c_sc1:
                    st.metric("Overall Copy Score", f"{res_coach['overall_score']}/100")
                with c_sc2:
                    st.metric("Word Count", f"{res_coach['word_count']} words")
                with c_sc3:
                    st.metric("Reading Grade Level", f"Grade {res_coach['reading_grade_level']}")
                
                if res_coach["strengths"]:
                    st.success("**Copy Strengths:**\n" + "\n".join([f"• {s}" for s in res_coach["strengths"]]))
                if res_coach["penalties"]:
                    st.warning("**Areas for Optimization:**\n" + "\n".join([f"• {p}" for p in res_coach["penalties"]]))
                
                st.markdown("##### ✍️ Automated 1-Click Lavender-Optimized Refactor:")
                st.text_input("Refactored Subject", value=res_coach["suggested_refactor"]["optimized_subject"], key="ref_sub")
                st.text_area("Refactored Body", value=res_coach["suggested_refactor"]["optimized_body"], height=120, key="ref_body")

        with eng_p5:
            st.markdown("##### 🚀 Native Deliverability Router, ESP-Matcher & Recursive Spintax Engine")
            st.markdown("Smartlead & Instantly replacement: Matches sender ESP to recipient ESP and recursively expands spintax to prevent email hash clustering.")
            s_col1, s_col2 = st.columns(2)
            with s_col1:
                st.markdown("###### 🔄 Smartlead ESP-Matching Dispatch Router")
                mx_target = st.text_input("Target MX Host", value="aspmx.l.google.com", key="mx_target")
                if st.button("🎯 Calculate Optimal Sender Inbox", use_container_width=True):
                    sample_inboxes = [
                        {"email": "alex@apexcore-labs.com", "provider": "Google Workspace"},
                        {"email": "growth@apexcore-hq.io", "provider": "Microsoft 365"}
                    ]
                    route_res = NativeSmartleadRouter.match_esp_sender(mx_target, sample_inboxes)
                    st.success(f"Selected Sender: **{route_res['selected_sender']['email']}** ({route_res['target_esp']})")
                    st.info(route_res["deliverability_boost_rationale"])
            with s_col2:
                st.markdown("###### 🎲 Recursive Anti-Clustering Spintax Studio")
                spin_input = st.text_area(
                    "Spintax Template",
                    value="{Hi|Hello|Hey} {{first_name}}, {noticed|saw|came across} your work at {{company}}. {Open to taking|Worth exploring} a quick peek?",
                    height=90,
                    key="spin_in"
                )
                if st.button("🎲 Generate Unique Email Variant", use_container_width=True):
                    variant = NativeSmartleadRouter.parse_spintax(spin_input)
                    st.markdown(f"**Randomized Generated Variant:**\n> {variant}")

        with eng_p6:
            st.markdown("##### 🕵️ Native B2B Reverse-IP & Corporate Deanonymizer")
            st.markdown("Translates anonymous website visitor IP addresses into corporate accounts and auto-discovers decision makers.")
            ip_in = st.text_input("Enter Visitor IP Address", value="199.16.156.1", key="ip_in")
            if st.button("🌐 Deanonymize Visiting Enterprise", use_container_width=True):
                with st.spinner("Resolving PTR DNS and querying corporate subnet..."):
                    deanonym_engine = NativeVisitorDeanonymizer()
                    res_ip = deanonym_engine.resolve_ip(ip_in)
                    if res_ip["is_corporate"]:
                        st.success(f"🏢 Corporate Visitor Identified: **{res_ip['company_name']}** ({res_ip['domain']})")
                        st.markdown(f"**Industry:** {res_ip['industry']} | **Hostname:** `{res_ip['hostname']}`")
                        st.markdown("##### 👥 Auto-Discovered Decision Makers at Visiting Enterprise:")
                        st.dataframe(pd.DataFrame(res_ip["identified_decision_makers"]), use_container_width=True)
                    else:
                        st.info(f"ℹ️ {res_ip['message']}")

        with eng_p7:
            st.markdown("##### 📈 Native Sales Call & Conversation Intelligence")
            st.markdown("Analyzes discovery call transcripts: talk-to-listen ratios, question rates, competitor battlecards, and Gong-calibrated deal health.")
            transcript_in = st.text_area(
                "Paste Meeting Transcript",
                value="Alex: Hi Mark, great to connect. Tell me a bit about your current mobile conversion bottleneck.\nMark: Thanks Alex. Our site on WordPress is extremely slow and TTFB is over 1 second. We have a dev shortage and are behind schedule.\nAlex: Completely understand. How long has that backlog been impacting your quarterly releases?\nMark: At least three months. We considered Toptal, but their rates were too high and open-ended. Can you send over a proposal by Friday?\nAlex: Absolutely, will send the SOW tomorrow.",
                height=120,
                key="call_trans_in"
            )
            if st.button("📊 Evaluate Call Transcript", use_container_width=True):
                call_intel = NativeSalesIntelligence()
                res_call = call_intel.analyze_transcript(transcript_in)
                c_t1, c_t2, c_t3 = st.columns(3)
                with c_t1:
                    st.metric("Founder Speaking Ratio", f"{res_call['founder_talk_percent']}%")
                with c_t2:
                    st.metric("Prospect Speaking Ratio", f"{res_call['prospect_talk_percent']}%")
                with c_t3:
                    st.metric("Estimated Win Probability", f"{res_call['estimated_deal_win_probability_pct']}%")
                st.markdown(f"**Gong Ratio Assessment:** `{res_call['talk_ratio_grade']}`")
                st.markdown(f"**Discovery Question Rate:** `{res_call['question_rate_assessment']}`")
                if res_call["competitor_battlecards"]:
                    st.markdown("##### ⚔️ Active Competitor Battlecards:")
                    for bc in res_call["competitor_battlecards"]:
                        st.info(f"**{bc['competitor'].upper()}**: {bc['battlecard_strategy']}")
                st.markdown(f"• Validated Customer Pain Points: `{', '.join(res_call['validated_customer_pain_points'])}`")
                st.markdown("• Extracted Next-Step Action Items:")
                for itm in res_call["extracted_action_items"]:
                    st.markdown(f"  - {itm}")

        with eng_p8:
            st.markdown("##### 🎬 Native Multimodal Video Storyboard & Conversational Voice SDR")
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.markdown("###### 🎥 45-Second Personalized Video Pitch Storyboard")
                p_name_v = st.text_input("Prospect Name", value="Bu Kinoshita", key="p_name_v")
                c_name_v = st.text_input("Company Name", value="Resend", key="c_name_v")
                if st.button("🎬 Generate Video Storyboard Spec", use_container_width=True):
                    story = NativeMultimodalGenerator.generate_video_pitch_storyboard(p_name_v, c_name_v, f"{c_name_v.lower()}.com", 1.4)
                    for scn in story["storyboard_scenes"]:
                        st.markdown(f"**Scene {scn['scene_number']} ({scn['duration_seconds']}s):** {scn['visual_overlay']}")
                        st.info(f"🗣️ Script: \"{scn['audio_script']}\"")
            with m_col2:
                st.markdown("###### 🎙️ Interactive Conversational Voice SDR Calling Tree")
                if st.button("📞 Generate Voice SDR State Machine", use_container_width=True):
                    v_tree = NativeMultimodalGenerator.generate_voice_sdr_call_tree(p_name_v, c_name_v)
                    st.markdown(f"**Target Latency:** `{v_tree['latency_target_ms']}ms` | **VAD Barge-In Mode:** `{v_tree['vad_interruption_spec']['interruption_mode']}`")
                    for n_name, n_data in v_tree["call_nodes"].items():
                        st.markdown(f"• **Node `{n_name}`** ({n_data['intent']}):")
                        st.code(n_data["ssml_text"], language="xml")

    with sub_tool3:
        st.markdown("#### 🛡️ Secondary Sending Domain DNS Configurator")
        st.markdown("Generate 10/10 deliverability DNS records for any domain to ensure primary domain immunity.")

        col_cfg1, col_cfg2 = st.columns(2)
        with col_cfg1:
            cfg_domain = st.text_input("Secondary Domain Name", value="apexcore-labs.com", key="cfg_dom")
            cfg_esp = st.selectbox("Mail Infrastructure Provider", ["google_workspace", "microsoft_365"], index=0, key="cfg_esp")
            
            if st.button("⚡ Generate Production DNS Records", use_container_width=True):
                records = DNSFleetConfigurator.generate_dns_records(cfg_domain, cfg_esp)
                st.session_state["dns_records"] = records
                st.success(f"Records generated for {cfg_domain}!")

        with col_cfg2:
            st.markdown("#### 🔍 Live DNS Resolution Audit")
            test_dom = st.text_input("Domain to Audit", value=cfg_domain, key="audit_dom")
            if st.button("🧪 Conduct Live DNS Socket Audit", use_container_width=True):
                with st.spinner("Querying live MX, SPF, and DMARC records..."):
                    audit_res = DNSFleetConfigurator.audit_live_dns(test_dom)
                    st.markdown(f"**Domain Health Score:** `{audit_res['health_score_pct']}%`")
                    st.markdown(f"• MX Mail Exchange Active: `{'✅ Yes' if audit_res['mx_active'] else '❌ No'}`")
                    st.markdown(f"• SPF TXT Active: `{'✅ Yes' if audit_res['spf_active'] else '❌ No'}`")
                    st.markdown(f"• DMARC Policy Active: `{'✅ Yes' if audit_res['dmarc_active'] else '❌ No'}`")
                    if audit_res["ready_for_outreach"]:
                        st.success("✅ Domain is healthy and ready for cold outreach dispatch.")
                    else:
                        st.warning("⚠️ Domain requires DNS propagation before launching campaigns.")

        if "dns_records" in st.session_state:
            recs = st.session_state["dns_records"]
            st.write("---")
            st.markdown(f"### 📋 DNS Records for `{recs['domain']}` (Copy into Cloudflare / DNS Host)")
            
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                st.markdown("**1. SPF Record (TXT)**")
                st.code(f"Host: {recs['spf']['host']}\nValue: {recs['spf']['value']}", language="text")

                st.markdown("**2. DMARC Enforcement (TXT)**")
                st.code(f"Host: {recs['dmarc']['host']}\nValue: {recs['dmarc']['value']}", language="text")

                st.markdown("**3. BIMI Brand Indicator (TXT)**")
                st.code(f"Host: {recs['bimi']['host']}\nValue: {recs['bimi']['value']}", language="text")

            with d_col2:
                st.markdown("**4. DKIM Authentication**")
                st.code(f"Host: {recs['dkim']['host']}\nValue: {recs['dkim']['value']}", language="text")

                st.markdown("**5. MX Mail Exchanger Records**")
                mx_str = "\n".join([f"Priority {m['priority']}: {m['value']}" for m in recs["mx"]])
                st.code(mx_str, language="text")

                st.markdown("**6. Custom Tracking Domain (CNAME)**")
                st.code(f"Host: {recs['custom_tracking_cname']['host']}\nValue: {recs['custom_tracking_cname']['value']}", language="text")

            st.write("")
            st.markdown("#### 📈 Recommended 21-Day Volume Ramp-up Curve")
            warmup_df = pd.DataFrame(DNSFleetConfigurator.generate_21_day_warmup_curve(40))
            st.dataframe(warmup_df, use_container_width=True)

    with sub_tool4:
        st.markdown("#### 🔌 Commercial Vendor Integration Hub & Live Ping Tester")
        st.markdown("Test live connectivity to commercial APIs or rely on AgencyBD's autonomous scraping fallback engine.")

        v_col1, v_col2 = st.columns(2)
        with v_col1:
            st.markdown("**Vendor Credentials Health Matrix:**")
            st.markdown(f"• **Apollo.io API:** `{'🟢 Configured' if os.getenv('APOLLO_API_KEY') else '🟡 Autonomous Fallback'}`")
            st.markdown(f"• **Hunter.io API:** `{'🟢 Configured' if os.getenv('HUNTER_API_KEY') else '🟡 Autonomous Fallback'}`")
            st.markdown(f"• **ZeroBounce API:** `{'🟢 Configured' if os.getenv('ZEROBOUNCE_API_KEY') else '🟡 Autonomous Fallback'}`")
            st.markdown(f"• **Resend Outbound API:** `{'🟢 Configured' if os.getenv('RESEND_API_KEY') else '🟡 Autonomous Simulation'}`")
            st.markdown(f"• **HubSpot CRM Token:** `{'🟢 Configured' if os.getenv('HUBSPOT_ACCESS_TOKEN') else '🟡 Local Database Sync'}`")
            st.markdown(f"• **Slack Webhook URL:** `{'🟢 Configured' if os.getenv('SLACK_WEBHOOK_URL') else '🟡 Local Dispatch Logger'}`")

        with v_col2:
            st.markdown("**Live Vendor Ping Tool:**")
            ping_target = st.text_input("Test Target Domain", value="resend.com", key="ping_tgt")
            if st.button("🚀 Test Vendor Discovery & Fallback Pipeline", use_container_width=True):
                with st.spinner("Pinging vendor connectors..."):
                    p_res = VendorConnectors.apollo_search_people(ping_target, ["CTO", "CEO"])
                    h_res = VendorConnectors.hunter_verify_email(f"contact@{ping_target}")
                    st.success("Vendor pipeline tested successfully!")
                    st.json({"discovery_sample": p_res, "verification_sample": h_res})




