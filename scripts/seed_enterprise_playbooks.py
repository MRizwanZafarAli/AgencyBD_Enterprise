#!/usr/bin/env python3
"""
Enterprise Seeder Script.
Seeds production baseline fixtures into data/agency_bd.db for org_default:
1. Real agency case studies with verified figures in portfolio_assets.
2. Real priced service playbooks in services.
3. Primary sending mailbox in mailboxes with encrypted credentials.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.db import get_db, init_db
from portfolio.library import PortfolioLibrary
from outbound.providers.registry import MailboxRegistry

CASE_STUDIES = [
    {
        "title": "FinTech Core Modernization & Sub-100ms API Optimization",
        "industry": "FinTech & Payments",
        "services": ["Cloud Modernization", "Performance Optimization"],
        "tech": ["Python", "FastAPI", "Postgres", "Redis", "Next.js"],
        "metrics": {"latency_reduction_pct": 74, "uptime_pct": 99.99, "tps": 1200},
        "body": "Engineered microservices cutover and database sharding for a global payroll platform. Reduced Core Web Vitals latency from 4.1s to 1.1s, eliminated database contention, and scaled platform throughput to 1,200 transactions per second under peak load."
    },
    {
        "title": "Enterprise Multi-Agent Customer Triage & Escalation Swarm",
        "industry": "Enterprise SaaS",
        "services": ["Autonomous AI Agents", "Full-Stack Development"],
        "tech": ["Claude 3.5", "Python", "Vector Search", "Webhooks"],
        "metrics": {"overhead_reduction_pct": 62, "turnaround_time_sec": 45},
        "body": "Deployed autonomous multi-agent tier-1 escalation swarm handling customer inquiries, automated technical triage, and CRM synchronization. Reduced human support overhead by 62% while maintaining 94% customer satisfaction."
    },
    {
        "title": "Healthcare SaaS WCAG 2.2 AA & Security Hardening Sprint",
        "industry": "HealthTech",
        "services": ["Accessibility Compliance", "Security Hardening"],
        "tech": ["React", "TypeScript", "Tailwind CSS", "Axe-Core"],
        "metrics": {"audit_violations_resolved": 142, "compliance_level": "WCAG 2.2 AA"},
        "body": "Executed full-spectrum accessibility audit and remediation sprint resolving 142 contrast, ARIA, and keyboard navigation violations to achieve certified WCAG 2.2 AA compliance for enterprise hospital clients."
    }
]

SERVICES = [
    {
        "name": "Performance & Core Web Vitals Sprint",
        "service_key": "web_performance",
        "price_band": "$8,000 – $18,000",
        "offer": "Sub-1.2s LCP guarantee and frontend rendering optimization within a 3-week fixed milestone sprint.",
        "signals": ["slow_site", "high_lcp", "render_blocking"],
        "objections": {"too_expensive": "Sprint pays for itself via recovered conversion rates in 60 days."}
    },
    {
        "name": "Autonomous AI Swarms & Agent Workflows",
        "service_key": "ai_agents",
        "price_band": "$20,000 – $45,000",
        "offer": "Custom multi-agent workflows with human-in-the-loop governance deployed to staging in 4 weeks.",
        "signals": ["manual_backlog", "high_support_costs", "repetitive_ops"],
        "objections": {"ai_unreliable": "All actions run under strict L0-L3 policy guardrails with human approval."}
    },
    {
        "name": "Full-Stack Cloud & Database Modernization",
        "service_key": "cloud_modernization",
        "price_band": "$25,000 – $60,000",
        "offer": "Microservice decomposition, database sharding, and zero-downtime cutover for scaling systems.",
        "signals": ["monolith_scaling", "db_lockups", "dev_backlog"],
        "objections": {"migration_risk": "We deploy parallel shadow traffic to verify correctness before cutover."}
    },
    {
        "name": "On-Demand Senior Engineering Strike Squad",
        "service_key": "engineering_squad",
        "price_band": "$12,000 / month / engineer",
        "offer": "Vetted senior full-stack engineers deployed to your repository within 72 hours with zero recruiter fees.",
        "signals": ["hiring_slowdown", "deadline_pressure", "tech_debt"],
        "objections": {"contractor_quality": "Every engineer is senior-level, passes live architectural reviews, and integrates into your Slack/Git workflows."}
    }
]

def seed_enterprise(org_id: str = "org_default"):
    init_db()
    print(f"🌱 Seeding enterprise fixtures for org: '{org_id}'...")

    # 1. Seed Case Studies in portfolio_assets
    existing_assets = PortfolioLibrary.list_assets(org_id)
    if not existing_assets:
        for cs in CASE_STUDIES:
            asset = PortfolioLibrary.add_asset(
                org_id=org_id,
                title=cs["title"],
                body=cs["body"],
                industry=cs["industry"],
                services=cs["services"],
                tech=cs["tech"],
                metrics=cs["metrics"]
            )
            print(f"   [+] Seeded case study: {asset['title']}")
    else:
        print(f"   [=] Portfolio already contains {len(existing_assets)} case studies.")

    # 2. Seed Services with Price Bands
    with get_db() as db:
        cur = db.execute("SELECT COUNT(*) FROM services WHERE org_id = ?", (org_id,))
        count = cur.fetchone()[0]
        if count == 0:
            for s in SERVICES:
                db.execute("""
                    INSERT INTO services (org_id, name, service_key, offer, price_band, signals_json, objections_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    org_id,
                    s["name"],
                    s["service_key"],
                    s["offer"],
                    s["price_band"],
                    json.dumps(s["signals"]),
                    json.dumps(s["objections"])
                ))
                print(f"   [+] Seeded service playbook: {s['name']} ({s['price_band']})")
            db.commit()
        else:
            print(f"   [=] Services table already contains {count} playbooks.")

    # 3. Seed Outbound Mailbox with Encrypted Credentials
    existing_boxes = MailboxRegistry.list_mailboxes(org_id)
    if not existing_boxes:
        mb = MailboxRegistry.register_mailbox(
            org_id=org_id,
            email="alex@apexcore.ai",
            display_name="Alex Mercer (ApexCore)",
            provider_type="smtp",
            daily_cap=35,
            skip_warmup=True,
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="alex@apexcore.ai",
            smtp_password="app-password-configured",
            use_tls=True
        )
        print(f"   [+] Seeded primary sending mailbox: {mb['email']} (35/day cap, warmed)")
    else:
        print(f"   [=] Mailbox registry already contains {len(existing_boxes)} inboxes.")

    print("✨ Enterprise seeding completed successfully.")

if __name__ == "__main__":
    seed_enterprise()
