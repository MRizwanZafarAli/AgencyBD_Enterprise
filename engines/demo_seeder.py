"""
DemoSeeder: Populates realistic enterprise pipeline, won deals, meetings, and evidence.
Used to give users an immediate, fully functional experience without empty dashes or skeletons.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from database.db import get_db


class DemoSeeder:
    @staticmethod
    def seed_demo_data(org_id: str = "org_default") -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()

            # 0. Ensure Base Demo Leads & Decision Makers exist
            demo_companies = [
                ("Apex Labs", "apexlabs.io", "Alex", "Vance", "VP Engineering", "alex@apexlabs.io"),
                ("FinVenture", "finventure.co", "Elena", "Rostova", "Lead Architect", "elena@finventure.co"),
                ("CloudScale", "cloudscale.io", "Marcus", "Brody", "Head of Infra", "marcus@cloudscale.io"),
            ]

            lead_dm_map = []
            for comp_name, domain, fn, ln, title, email in demo_companies:
                cursor.execute("SELECT id FROM leads WHERE domain = ?", (domain,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("""
                        INSERT INTO leads (company_name, domain, source_channel, status)
                        VALUES (?, ?, 'venture_database', 'qualified')
                    """, (comp_name, domain))
                    lid = cursor.lastrowid
                else:
                    lid = row[0]

                cursor.execute("SELECT id FROM decision_makers WHERE lead_id = ? AND email = ?", (lid, email))
                dm_row = cursor.fetchone()
                if not dm_row:
                    cursor.execute("""
                        INSERT INTO decision_makers (lead_id, first_name, last_name, title, email)
                        VALUES (?, ?, ?, ?, ?)
                    """, (lid, fn, ln, title, email))
                    dmid = cursor.lastrowid
                else:
                    dmid = dm_row[0]

                lead_dm_map.append((lid, dmid, comp_name, domain, f"{fn} {ln} ({title})"))

            # 1. Opportunities & Won Proposals
            sample_opps = [
                ("Apex Labs Next.js Edge Migration", "Full architecture overhaul from legacy monolithic React to Next.js App Router.", 48000.0, "USD", "https://apexlabs.io"),
                ("FinVenture Core Web Vitals Rescue", "Recapturing $14k/mo in bounce leakage via sub-1.5s LCP optimization.", 32500.0, "USD", "https://finventure.co"),
                ("CloudScale Distributed Swarm Pods", "Deploying dedicated automated lead generation and scraping pods.", 62000.0, "USD", "https://cloudscale.io"),
            ]

            opp_ids = []
            for title, desc, budget, curr, url in sample_opps:
                cursor.execute("""
                    INSERT INTO opportunities (
                        org_id, type, source, external_id, title, description,
                        budget_min, budget_max, currency, status, fit_score, url
                    ) VALUES (?, 'enterprise', 'direct_inbound', ?, ?, ?, ?, ?, ?, 'qualified', 0.94, ?)
                """, (org_id, f"demo_{abs(hash(title)) % 100000}", title, desc, budget, budget, curr, url))
                opp_ids.append(cursor.lastrowid)

            # 2. Won Proposals (linking to opps)
            cursor.execute("DELETE FROM proposals WHERE org_id = ? AND body LIKE '%[DEMO]%'", (org_id,))
            for i, opp_id in enumerate(opp_ids):
                cursor.execute("""
                    INSERT INTO proposals (
                        org_id, opportunity_id, variant, body, status, model,
                        prompt_version, outcome_reason, verification_json, cited_assets_json
                    ) VALUES (?, ?, 'A', ?, 'won', 'claude-sonnet-5-5', 'v1', 'Client signed contract', ?, '[]')
                """, (
                    org_id, opp_id,
                    f"[DEMO] Enterprise Architecture Proposal #{i+1} for deal execution.",
                    json.dumps({"verified": True, "score": 98, "proofs": 4})
                ))

            # 3. Booked Discovery Meetings (meeting_bookings)
            now = datetime.now(timezone.utc)
            cursor.execute("DELETE FROM meeting_bookings WHERE founder_prep_brief LIKE '%[DEMO]%'")
            meetings_data = [
                (lead_dm_map[0][0], lead_dm_map[0][1], lead_dm_map[0][4], now + timedelta(days=1, hours=2), "https://cal.com/agencybd/apex-discovery"),
                (lead_dm_map[1][0], lead_dm_map[1][1], lead_dm_map[1][4], now + timedelta(days=2, hours=4), "https://cal.com/agencybd/finventure-brief"),
                (lead_dm_map[2][0], lead_dm_map[2][1], lead_dm_map[2][4], now + timedelta(days=3, hours=1), "https://cal.com/agencybd/cloudscale-sow"),
                (lead_dm_map[0][0], lead_dm_map[0][1], lead_dm_map[0][4], now + timedelta(days=4, hours=3), "https://cal.com/agencybd/apex-deepdive"),
            ]

            for lid, dmid, contact, dt, link in meetings_data:
                cursor.execute("""
                    INSERT INTO meeting_bookings (
                        lead_id, decision_maker_id, booking_time, cal_link, founder_prep_brief, crm_synced
                    ) VALUES (?, ?, ?, ?, ?, 1)
                """, (lid, dmid, dt.isoformat(), link, f"[DEMO] Discovery Call with {contact}. Prep: Review LCP and hydration gap."))

            # 4. Verified Evidence Records (evidence)
            cursor.execute("DELETE FROM evidence WHERE org_id = ? AND claim LIKE '%[DEMO]%'", (org_id,))
            evidence_data = [
                ("website", lead_dm_map[0][0], "[DEMO] Measured LCP", "4.12s", "https://apexlabs.io", "native_chromium_audit", 0.98),
                ("website", lead_dm_map[1][0], "[DEMO] TTFB Bottleneck", "1.24s", "https://finventure.co", "tls_traceroute", 0.95),
                ("website", lead_dm_map[2][0], "[DEMO] Monolithic JS Bundle", "2.8 MiB uncompressed", "https://cloudscale.io", "bundle_analyzer", 0.92),
                ("website", lead_dm_map[0][0], "[DEMO] Conversion Loss Drag", "$14,200 / month", "https://apexlabs.io", "akamai_delay_formula", 0.96),
                ("website", lead_dm_map[1][0], "[DEMO] Benchmark Peer LCP", "1.38s", "https://finventure.co", "native_chromium_audit", 0.99),
                ("company", lead_dm_map[2][0], "[DEMO] Form D Financing", "$8.5M Series A Filed", "https://sec.gov", "sec_edgar_crawler", 1.0),
            ]

            for etype, eid, claim, val, surl, method, conf in evidence_data:
                cursor.execute("""
                    INSERT INTO evidence (
                        org_id, entity_type, entity_id, claim, value, source_url, method, observed_at, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (org_id, etype, eid, claim, val, surl, method, now.isoformat(), conf))

            # 5. Financial Ledger & Outbound Events
            cursor.execute("DELETE FROM financial_ledger WHERE org_id = ? AND metadata_json LIKE '%[DEMO]%'", (org_id,))
            cursor.execute("""
                INSERT INTO financial_ledger (org_id, lead_id, expense_type, amount_usd, metadata_json)
                VALUES
                    (?, 1, 'infra_proxy', 8.50, '{"note": "[DEMO] Residential proxy residential band"}'),
                    (?, 1, 'llm_tokens', 14.20, '{"note": "[DEMO] Deep reasoning cognitive tokens"}')
            """, (org_id, org_id))

            cursor.execute("DELETE FROM outreach_events WHERE org_id = ? AND payload_json LIKE '%[DEMO]%'", (org_id,))
            for i in range(45):
                cursor.execute("""
                    INSERT INTO outreach_events (org_id, recipient_email, event_type, payload_json)
                    VALUES (?, ?, 'sent', '{"note": "[DEMO]"}')
                """, (org_id, f"demo_target_{i}@example.com"))
            for i in range(8):
                cursor.execute("""
                    INSERT INTO outreach_events (org_id, recipient_email, event_type, payload_json)
                    VALUES (?, ?, 'replied', '{"note": "[DEMO]"}')
                """, (org_id, f"demo_target_{i}@example.com"))

            conn.commit()

        return {
            "status": "success",
            "message": "Enterprise demo pipeline seeded successfully with won deals, meetings, evidence, and leads!",
            "proposals_won": 3,
            "pipeline_won_usd": 142500.0,
            "meetings_booked": 4,
            "evidence_records": 6,
            "opportunities_created": 3
        }
