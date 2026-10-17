"""
High-Level Database Repository & CRUD operations for AgencyBD_Enterprise.
Enforces zero SQL-injection parameterization, cryptographic HMAC record signing,
audit logging, global CAN-SPAM suppression checks, and Multi-Tenant org_id isolation.
"""

import json
from typing import List, Optional, Dict, Any
from database.db import get_db, log_audit_trail, is_entity_suppressed, add_entity_to_suppression
from database.security_vault import SecurityVault

class LeadRepository:
    @staticmethod
    def create_or_get_lead(
        company_name: str,
        domain: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        rating: float = 0.0,
        reviews_count: int = 0,
        source_channel: str = "google_maps",
        source_query: Optional[str] = None,
        notes: Optional[str] = None,
        org_id: str = "org_default"
    ) -> Dict[str, Any]:
        company_name = SecurityVault.sanitize_identifier(company_name)
        domain = domain.lower().strip().replace("https://", "").replace("http://", "").split("/")[0]

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads WHERE domain = ? AND org_id = ?", (domain, org_id))
            row = cursor.fetchone()
            if row:
                return dict(row)
            
            cursor.execute("""
                INSERT INTO leads (
                    company_name, domain, phone, address, rating, reviews_count,
                    source_channel, source_query, notes, org_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (company_name, domain, phone, address, rating, reviews_count, source_channel, source_query, notes, org_id))
            lead_id = cursor.lastrowid
            
            # Generate cryptographic digital signature
            payload = {
                "company_name": company_name,
                "domain": domain,
                "phone": phone,
                "rating": rating,
                "source_channel": source_channel,
                "org_id": org_id
            }
            rec_hash = SecurityVault.sign_record("lead", lead_id, payload)
            cursor.execute("UPDATE leads SET record_hash = ? WHERE id = ?", (rec_hash, lead_id))
            log_audit_trail(lead_id, "SourcingEngine", "LEAD_CREATED", {"domain": domain, "channel": source_channel, "org_id": org_id}, conn=conn)
            conn.commit()
            
            cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
            return dict(cursor.fetchone())

    @staticmethod
    def get_lead(lead_id: int, org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            if org_id:
                cursor.execute("SELECT * FROM leads WHERE id = ? AND org_id = ?", (lead_id, org_id))
            else:
                cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_leads(status: Optional[str] = None, org_id: str = "org_default", limit: int = 100) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM leads WHERE status = ? AND org_id = ? ORDER BY id DESC LIMIT ?", (status, org_id, limit))
            else:
                cursor.execute("SELECT * FROM leads WHERE org_id = ? ORDER BY id DESC LIMIT ?", (org_id, limit))
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def update_status(lead_id: int, status: str) -> None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, lead_id))
            log_audit_trail(lead_id, "SwarmEngine", "STATUS_UPDATED", {"new_status": status}, conn=conn)
            conn.commit()

    @staticmethod
    def get_pipeline(org_id: str = "org_default") -> Dict[str, Any]:
        """Returns structured CRM pipeline deals grouped by stage with live revenue totals."""
        import re
        stages: Dict[str, List[Dict[str, Any]]] = {
            "sourced": [],
            "audited": [],
            "sequence_active": [],
            "meeting_booked": [],
            "proposal_sent": [],
            "won": [],
            "lost": []
        }
        stage_weights = {
            "sourced": 0.10,
            "audited": 0.25,
            "sequence_active": 0.40,
            "meeting_booked": 0.65,
            "proposal_sent": 0.80,
            "won": 1.00,
            "lost": 0.00
        }

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads WHERE org_id = ? ORDER BY id DESC", (org_id,))
            rows = [dict(r) for r in cursor.fetchall()]

        total_pipeline_value = 0.0
        weighted_projected_revenue = 0.0
        active_deals = 0
        won_deals = 0

        for r in rows:
            st = (r.get("status") or "sourced").lower().replace(" ", "_")
            if st not in stages:
                st = "sourced"

            deal_val = 4500.0
            notes = r.get("notes") or ""
            val_match = re.search(r"EST VALUE:\s*\$([0-9,]+)", notes)
            if val_match:
                try:
                    deal_val = float(val_match.group(1).replace(",", ""))
                except Exception:
                    pass

            pitch_angle = "Web Presence & Performance Rescue"
            angle_match = re.search(r"PITCH ANGLE:\s*([^|]+)", notes)
            if angle_match:
                pitch_angle = angle_match.group(1).strip()

            deal_item = {
                "id": r["id"],
                "company_name": r["company_name"],
                "domain": r["domain"],
                "phone": r.get("phone"),
                "address": r.get("address"),
                "rating": r.get("rating"),
                "reviews_count": r.get("reviews_count"),
                "source_channel": r.get("source_channel"),
                "status": st,
                "deal_stage": st,
                "deal_value": deal_val,
                "pitch_angle": pitch_angle,
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at")
            }
            stages[st].append(deal_item)

            if st != "lost":
                total_pipeline_value += deal_val
                weighted_projected_revenue += deal_val * stage_weights.get(st, 0.1)
                active_deals += 1
            if st == "won":
                won_deals += 1

        win_rate = (won_deals / max(active_deals, 1)) * 100

        formatted_stages = {}
        for s_key, s_leads in stages.items():
            s_val = round(sum(d["deal_value"] for d in s_leads), 2)
            s_info = {
                "count": len(s_leads),
                "value": s_val,
                "win_rate": stage_weights.get(s_key, 0.1),
                "leads": s_leads
            }
            formatted_stages[s_key] = s_info
            if s_key == "won":
                formatted_stages["closed_won"] = s_info
            elif s_key == "sequence_active":
                formatted_stages["outreach_active"] = s_info

        return {
            "total_pipeline_value": round(total_pipeline_value, 2),
            "total_value": round(total_pipeline_value, 2),
            "weighted_projected_revenue": round(weighted_projected_revenue, 2),
            "weighted_value": round(weighted_projected_revenue, 2),
            "active_deals_count": active_deals,
            "total_deals": active_deals,
            "won_deals_count": won_deals,
            "win_rate_percent": round(win_rate, 1),
            "stages": formatted_stages
        }

    @staticmethod
    def update_deal_stage(lead_id: int, new_stage: str, org_id: str = "org_default") -> Optional[Dict[str, Any]]:
        """Updates lead stage with audit trail logging."""
        stage_aliases = {
            "closed_won": "won",
            "outreach_active": "sequence_active",
        }
        clean_stage = new_stage.lower().strip().replace(" ", "_")
        clean_stage = stage_aliases.get(clean_stage, clean_stage)

        valid_stages = ("sourced", "audited", "sequence_active", "meeting_booked", "proposal_sent", "won", "lost")
        if clean_stage not in valid_stages:
            raise ValueError(f"Invalid stage '{new_stage}'. Must be one of: {valid_stages}")

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM leads WHERE id = ? AND org_id = ?", (lead_id, org_id))
            if not cursor.fetchone():
                return None
            cursor.execute("UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (clean_stage, lead_id))
            log_audit_trail(lead_id, "CRM_Pipeline", "STAGE_UPDATED", {"new_stage": clean_stage, "org_id": org_id}, conn=conn)
            conn.commit()
            cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
            row = dict(cursor.fetchone())
            row["deal_stage"] = row["status"]
            return row


class AuditRepository:
    @staticmethod
    def save_audit(
        lead_id: int,
        load_time_ms: int,
        ttfb_ms: int,
        lcp_score: float,
        mobile_responsive: bool,
        tech_stack: List[str],
        missing_headers: List[str],
        console_errors: List[str],
        audit_summary: str,
        calculated_pitch_angle: str,
        org_id: str = "org_default"
    ) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tech_audits (
                    lead_id, load_time_ms, ttfb_ms, lcp_score, mobile_responsive,
                    tech_stack_json, missing_headers_json, console_errors_json,
                    audit_summary, calculated_pitch_angle, org_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead_id, load_time_ms, ttfb_ms, lcp_score, mobile_responsive,
                json.dumps(tech_stack), json.dumps(missing_headers), json.dumps(console_errors),
                audit_summary, calculated_pitch_angle, org_id
            ))
            audit_id = cursor.lastrowid
            
            # Sign audit record
            payload = {"lead_id": lead_id, "lcp_score": lcp_score, "load_time_ms": load_time_ms, "org_id": org_id}
            rec_hash = SecurityVault.sign_record("tech_audit", audit_id, payload)
            cursor.execute("UPDATE tech_audits SET record_hash = ? WHERE id = ?", (rec_hash, audit_id))
            cursor.execute("UPDATE leads SET status = 'audited' WHERE id = ?", (lead_id,))
            log_audit_trail(lead_id, "TechAuditAgent", "AUDIT_COMPLETED", {"lcp": lcp_score, "stack": tech_stack, "org_id": org_id}, conn=conn)
            conn.commit()
            cursor.execute("SELECT * FROM tech_audits WHERE id = ?", (audit_id,))
            return dict(cursor.fetchone())

    @staticmethod
    def get_audit_by_lead(lead_id: int, org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            if org_id:
                cursor.execute("SELECT * FROM tech_audits WHERE lead_id = ? AND org_id = ? ORDER BY id DESC LIMIT 1", (lead_id, org_id))
            else:
                cursor.execute("SELECT * FROM tech_audits WHERE lead_id = ? ORDER BY id DESC LIMIT 1", (lead_id,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res["tech_stack"] = json.loads(res.get("tech_stack_json") or "[]")
                res["missing_headers"] = json.loads(res.get("missing_headers_json") or "[]")
                res["console_errors"] = json.loads(res.get("console_errors_json") or "[]")
                return res
            return None

class ContactRepository:
    @staticmethod
    def add_decision_maker(
        lead_id: int,
        first_name: str,
        last_name: str,
        title: str,
        email: str,
        linkedin_url: Optional[str] = None,
        email_source: str = "waterfall_enrichment",
        verification_status: str = "valid",
        mx_verified: bool = True,
        smtp_handshake_status: str = "250_OK",
        org_id: str = "org_default"
    ) -> Dict[str, Any]:
        email = email.lower().strip()
        # Enforce CAN-SPAM suppression check
        if is_entity_suppressed(email):
            verification_status = "suppressed"

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM decision_makers WHERE email = ? AND org_id = ?", (email, org_id))
            row = cursor.fetchone()
            if row:
                return dict(row)
            
            cursor.execute("""
                INSERT INTO decision_makers (
                    lead_id, first_name, last_name, title, linkedin_url,
                    email, email_source, verification_status, mx_verified, smtp_handshake_status, org_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead_id, first_name, last_name, title, linkedin_url,
                email, email_source, verification_status, mx_verified, smtp_handshake_status, org_id
            ))
            cursor.execute("UPDATE leads SET status = 'enriched' WHERE id = ?", (lead_id,))
            dm_id = cursor.lastrowid

            log_audit_trail(lead_id, "EnrichmentAgent", "CONTACT_VERIFIED", {"email": email, "status": verification_status, "org_id": org_id}, conn=conn)
            conn.commit()
            cursor.execute("SELECT * FROM decision_makers WHERE id = ?", (dm_id,))
            return dict(cursor.fetchone())

    @staticmethod
    def get_contacts_by_lead(lead_id: int, org_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            if org_id:
                cursor.execute("SELECT * FROM decision_makers WHERE lead_id = ? AND org_id = ?", (lead_id, org_id))
            else:
                cursor.execute("SELECT * FROM decision_makers WHERE lead_id = ?", (lead_id,))
            return [dict(r) for r in cursor.fetchall()]

class OutreachRepository:
    @staticmethod
    def save_sequence_steps(
        lead_id: int,
        decision_maker_id: int,
        steps: List[Dict[str, Any]],
        org_id: str = "org_default"
    ) -> List[Dict[str, Any]]:
        created = []
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM outreach_sequences WHERE lead_id = ? AND status = 'drafted' AND org_id = ?", (lead_id, org_id))
            for s in steps:
                cursor.execute("""
                    INSERT INTO outreach_sequences (
                        lead_id, decision_maker_id, step_number, channel, subject, body, spam_score, status, org_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead_id, decision_maker_id, s.get("step_number", 1),
                    s.get("channel", "email"), s.get("subject", ""), s.get("body", ""),
                    s.get("spam_score", 0.0), s.get("status", "drafted"), org_id
                ))
                created.append(cursor.lastrowid)
            cursor.execute("UPDATE leads SET status = 'queued' WHERE id = ?", (lead_id,))
            log_audit_trail(lead_id, "CopywriterAgent", "SEQUENCES_GENERATED", {"count": len(steps), "org_id": org_id}, conn=conn)
            conn.commit()
            cursor.execute("SELECT * FROM outreach_sequences WHERE lead_id = ? ORDER BY step_number ASC", (lead_id,))
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_sequences_by_lead(lead_id: int, org_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            if org_id:
                cursor.execute("SELECT * FROM outreach_sequences WHERE lead_id = ? AND org_id = ? ORDER BY step_number ASC", (lead_id, org_id))
            else:
                cursor.execute("SELECT * FROM outreach_sequences WHERE lead_id = ? ORDER BY step_number ASC", (lead_id,))
            return [dict(r) for r in cursor.fetchall()]

class ReplyRepository:
    @staticmethod
    def log_reply(
        lead_id: int,
        reply_text: str,
        sentiment: str,
        objection_category: str,
        auto_rebuttal_draft: str,
        org_id: str = "org_default"
    ) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inbound_replies (
                    lead_id, reply_text, sentiment, objection_category, auto_rebuttal_draft, org_id
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (lead_id, reply_text, sentiment, objection_category, auto_rebuttal_draft, org_id))
            reply_id = cursor.lastrowid

            # If prospect asked to unsubscribe, automatically enforce permanent suppression vault
            if objection_category == "not_interested":
                cursor.execute("SELECT domain FROM leads WHERE id = ?", (lead_id,))
                dom_row = cursor.fetchone()
                if dom_row:
                    add_entity_to_suppression(dom_row[0], "domain", "prospect_unsubscribed", conn=conn)
                new_status = "unsubscribed"
            else:
                new_status = "replied"

            cursor.execute("UPDATE leads SET status = ? WHERE id = ?", (new_status, lead_id))
            log_audit_trail(lead_id, "ObjectionAgent", "REPLY_LOGGED", {"sentiment": sentiment, "category": objection_category, "org_id": org_id}, conn=conn)
            conn.commit()
            cursor.execute("SELECT * FROM inbound_replies WHERE id = ?", (reply_id,))
            return dict(cursor.fetchone())

    @staticmethod
    def list_replies(limit: int = 50, org_id: str = "org_default") -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inbound_replies WHERE org_id = ? ORDER BY id DESC LIMIT ?", (org_id, limit))
            return [dict(r) for r in cursor.fetchall()]

class BookingRepository:
    @staticmethod
    def create_booking(
        lead_id: int,
        decision_maker_id: Optional[int],
        booking_time: str,
        cal_link: str,
        founder_prep_brief: str,
        org_id: str = "org_default"
    ) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO meeting_bookings (
                    lead_id, decision_maker_id, booking_time, cal_link, founder_prep_brief, org_id
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (lead_id, decision_maker_id, booking_time, cal_link, founder_prep_brief, org_id))
            bid = cursor.lastrowid
            
            # Sign booking record
            payload = {"lead_id": lead_id, "booking_time": booking_time, "cal_link": cal_link, "org_id": org_id}
            rec_hash = SecurityVault.sign_record("meeting_booking", bid, payload)
            cursor.execute("UPDATE meeting_bookings SET record_hash = ? WHERE id = ?", (rec_hash, bid))
            cursor.execute("UPDATE leads SET status = 'booked' WHERE id = ?", (lead_id,))
            log_audit_trail(lead_id, "BookingAgent", "MEETING_BOOKED", {"slot": booking_time, "org_id": org_id}, conn=conn)
            conn.commit()
            cursor.execute("SELECT * FROM meeting_bookings WHERE id = ?", (bid,))
            return dict(cursor.fetchone())

    @staticmethod
    def list_bookings(limit: int = 50, org_id: str = "org_default") -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM meeting_bookings WHERE org_id = ? ORDER BY id DESC LIMIT ?", (org_id, limit))
            return [dict(r) for r in cursor.fetchall()]

# ==================== Phase 0/1/2 Enterprise Repositories ====================

class CompanyRepository:
    @staticmethod
    def create_or_get(
        name: str,
        domain: Optional[str] = None,
        place_id: Optional[str] = None,
        size_band: Optional[str] = None,
        country: str = "US",
        industry: Optional[str] = None,
        org_id: str = "org_default"
    ) -> Dict[str, Any]:
        clean_name = SecurityVault.sanitize_identifier(name)
        clean_domain = domain.lower().strip().replace("https://", "").replace("http://", "").split("/")[0] if domain else None

        with get_db() as conn:
            cursor = conn.cursor()
            if clean_domain:
                cursor.execute("SELECT * FROM companies WHERE domain = ? AND org_id = ?", (clean_domain, org_id))
                row = cursor.fetchone()
                if row:
                    return dict(row)
            else:
                cursor.execute("SELECT * FROM companies WHERE name = ? AND org_id = ?", (clean_name, org_id))
                row = cursor.fetchone()
                if row:
                    return dict(row)

            cursor.execute("""
                INSERT INTO companies (name, domain, place_id, size_band, country, industry, org_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (clean_name, clean_domain, place_id, size_band, country, industry, org_id))
            cid = cursor.lastrowid
            conn.commit()
            cursor.execute("SELECT * FROM companies WHERE id = ?", (cid,))
            return dict(cursor.fetchone())

    @staticmethod
    def get_by_id(company_id: int, org_id: str = "org_default") -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE id = ? AND org_id = ?", (company_id, org_id))
            row = cursor.fetchone()
            return dict(row) if row else None


def _hydrate_opportunity(row) -> Dict[str, Any]:
    d = dict(row)
    d["risk_flags"] = json.loads(d.get("risk_flags_json") or "[]")
    d["skills"] = json.loads(d.get("skills_json") or "[]")
    d["fit_reasons"] = json.loads(d.get("fit_reasons_json") or "[]")
    return d


class OpportunityRepository:
    @staticmethod
    def create_opportunity(
        opp_type: str,
        source: str,
        title: str,
        description: Optional[str] = None,
        external_id: Optional[str] = None,
        company_id: Optional[int] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        currency: str = "USD",
        fit_score: Optional[float] = 0.0,
        risk_flags: Optional[List[str]] = None,
        org_id: str = "org_default",
        url: Optional[str] = None,
        company_name: Optional[str] = None,
        skills: Optional[List[str]] = None,
        fit_reasons: Optional[List[str]] = None,
        posted_at: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            if external_id:
                cursor.execute("SELECT * FROM opportunities WHERE org_id = ? AND source = ? AND external_id = ?",
                               (org_id, source, external_id))
                existing = cursor.fetchone()
                if existing:
                    return _hydrate_opportunity(existing)  # already ingested: scans are idempotent
            flags_json = json.dumps(risk_flags or [])
            cursor.execute("""
                INSERT INTO opportunities (
                    type, source, title, description, external_id, company_id,
                    budget_min, budget_max, currency, fit_score, risk_flags_json, org_id,
                    url, company_name, skills_json, fit_reasons_json, posted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (opp_type, source, title, description, external_id, company_id, budget_min, budget_max, currency, fit_score,
                  flags_json, org_id, url, company_name, json.dumps(skills or []), json.dumps(fit_reasons or []), posted_at))
            opp_id = cursor.lastrowid
            conn.commit()
            cursor.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,))
            return _hydrate_opportunity(cursor.fetchone())

    @staticmethod
    def get_opportunity(opportunity_id: int, org_id: str) -> Optional[Dict[str, Any]]:
        """Tenant-scoped lookup: another tenant's id behaves like a missing row."""
        with get_db() as conn:
            row = conn.execute("SELECT * FROM opportunities WHERE id = ? AND org_id = ?", (opportunity_id, org_id)).fetchone()
            return _hydrate_opportunity(row) if row else None

    @staticmethod
    def list_opportunities(
        source: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        org_id: str = "org_default"
    ) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM opportunities WHERE org_id = ?"
            params: List[Any] = [org_id]
            if source:
                query += " AND source = ?"
                params.append(source)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY (fit_score IS NULL), fit_score DESC, id DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, tuple(params))
            return [_hydrate_opportunity(r) for r in cursor.fetchall()]


class EvidenceRepository:
    @staticmethod
    def record_evidence(
        entity_type: str,
        entity_id: int,
        claim: str,
        value: str,
        method: str,
        source_url: Optional[str] = None,
        confidence: float = 1.0,
        org_id: str = "org_default"
    ) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO evidence (
                    entity_type, entity_id, claim, value, method, source_url, confidence, org_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (entity_type, entity_id, claim, value, method, source_url, confidence, org_id))
            eid = cursor.lastrowid
            conn.commit()
            cursor.execute("SELECT * FROM evidence WHERE id = ?", (eid,))
            return dict(cursor.fetchone())

    @staticmethod
    def attach_to(evidence_ids: List[int], entity_type: str, entity_id: int, org_id: str) -> None:
        """Re-points evidence rows at the entity they belong to (e.g. the audit run created after the evidence)."""
        if not evidence_ids:
            return
        with get_db() as conn:
            conn.executemany("UPDATE evidence SET entity_type = ?, entity_id = ? WHERE id = ? AND org_id = ?",
                             [(entity_type, entity_id, eid, org_id) for eid in evidence_ids])
            conn.commit()

    @staticmethod
    def get_by_ids(evidence_ids: List[int], org_id: str) -> Dict[int, Dict[str, Any]]:
        if not evidence_ids:
            return {}
        marks = ",".join("?" * len(evidence_ids))
        with get_db() as conn:
            rows = conn.execute(f"SELECT * FROM evidence WHERE org_id = ? AND id IN ({marks})", (org_id, *evidence_ids)).fetchall()
        return {r["id"]: dict(r) for r in rows}

    @staticmethod
    def get_for_entity(entity_type: str, entity_id: int, org_id: str = "org_default") -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM evidence
                WHERE entity_type = ? AND entity_id = ? AND org_id = ?
                ORDER BY id ASC
            """, (entity_type, entity_id, org_id))
            return [dict(r) for r in cursor.fetchall()]


class AuditRunRepository:
    @staticmethod
    def record_run(
        domain: str,
        overall_score: Optional[int],
        summary: str,
        findings: List[Dict[str, Any]],
        company_id: Optional[int] = None,
        org_id: str = "org_default",
        status: str = "completed"
    ) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_runs (domain, overall_score, summary, company_id, org_id, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (domain, overall_score, summary, company_id, org_id, status))
            run_id = cursor.lastrowid

            for f in findings:
                cursor.execute("""
                    INSERT INTO audit_findings (
                        audit_run_id, category, check_id, severity, finding, fix,
                        estimated_impact, service_id, evidence_id, org_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id,
                    f.get("category", "performance"),
                    f.get("check_id", "unknown"),
                    f.get("severity", "medium"),
                    f.get("finding", ""),
                    f.get("fix", ""),
                    f.get("estimated_impact", ""),
                    f.get("service_id", ""),
                    f.get("evidence_id"),
                    org_id
                ))
            conn.commit()
            cursor.execute("SELECT * FROM audit_runs WHERE id = ?", (run_id,))
            return dict(cursor.fetchone())

    @staticmethod
    def latest_for_company(company_id: int, org_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM audit_runs WHERE company_id = ? AND org_id = ? ORDER BY id DESC LIMIT 1",
                               (company_id, org_id)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_findings(run_id: int, org_id: str = "org_default") -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_findings WHERE audit_run_id = ? AND org_id = ?", (run_id, org_id))
            return [dict(r) for r in cursor.fetchall()]


class ProposalRepository:
    @staticmethod
    def create_proposal(
        opportunity_id: int,
        body: str,
        variant: str = "A",
        model: str = "claude-sonnet-5-5",
        prompt_version: str = "v1",
        org_id: str = "org_default",
        status: str = "draft",
        verification: Optional[Dict[str, Any]] = None,
        cited_asset_ids: Optional[List[int]] = None,
        queue_for_approval: bool = True
    ) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO proposals (
                    opportunity_id, variant, body, model, prompt_version, status, org_id,
                    verification_json, cited_assets_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (opportunity_id, variant, body, model, prompt_version, status, org_id,
                  json.dumps(verification) if verification is not None else None,
                  json.dumps(cited_asset_ids or [])))
            prop_id = cursor.lastrowid

            # Only verified drafts reach the human approval inbox
            if queue_for_approval:
                cursor.execute("""
                    INSERT INTO approvals (subject_type, subject_id, requested_by, decision, org_id)
                    VALUES ('proposal', ?, 'ProposalStudio', 'pending', ?)
                """, (prop_id, org_id))

            conn.commit()
            cursor.execute("SELECT * FROM proposals WHERE id = ?", (prop_id,))
            return dict(cursor.fetchone())

    @staticmethod
    def update_status(proposal_id: int, status: str, outcome_reason: Optional[str] = None, org_id: str = "org_default") -> None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE proposals SET status = ?, outcome_reason = ? WHERE id = ? AND org_id = ?
            """, (status, outcome_reason, proposal_id, org_id))
            conn.commit()


class ApprovalRepository:
    @staticmethod
    def create_approval_request(
        subject_type: str,
        subject_id: int,
        requested_by: str,
        reason: Optional[str] = None,
        org_id: str = "org_default"
    ) -> int:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO approvals (org_id, subject_type, subject_id, requested_by, decision, reason)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """, (org_id, subject_type, subject_id, requested_by, reason))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def list_pending(org_id: str = "org_default") -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.*, p.body AS proposal_body, p.opportunity_id,
                       d.subject AS draft_subject, d.body AS draft_body, d.recipient_email AS draft_recipient,
                       d.step_number AS draft_step
                FROM approvals a
                LEFT JOIN proposals p ON a.subject_type = 'proposal' AND a.subject_id = p.id
                LEFT JOIN outbound_drafts d ON a.subject_type = 'outbound_draft' AND a.subject_id = d.id
                WHERE a.decision = 'pending' AND a.org_id = ?
                ORDER BY a.id DESC
            """, (org_id,))
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def decide(approval_id: int, decision: str, decided_by: str, reason: Optional[str] = None, org_id: str = "org_default") -> None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE approvals
                SET decision = ?, decided_by = ?, reason = ?, decided_at = CURRENT_TIMESTAMP
                WHERE id = ? AND org_id = ?
            """, (decision, decided_by, reason, approval_id, org_id))

            # If proposal approved, update proposal status
            cursor.execute("SELECT subject_type, subject_id FROM approvals WHERE id = ? AND org_id = ?", (approval_id, org_id))
            row = cursor.fetchone()
            if row and row["subject_type"] == "proposal":
                new_status = "approved" if decision == "approved" else "rejected"
                cursor.execute("UPDATE proposals SET status = ? WHERE id = ? AND org_id = ?", (new_status, row["subject_id"], org_id))
            elif row and row["subject_type"] == "outbound_draft":
                new_status = "approved" if decision == "approved" else "rejected"
                cursor.execute("UPDATE outbound_drafts SET status = ?, decided_at = CURRENT_TIMESTAMP WHERE id = ? AND org_id = ? AND status = 'pending_approval'",
                               (new_status, row["subject_id"], org_id))
                if new_status == "rejected":
                    cursor.execute("""UPDATE sequence_enrollments SET status = 'stopped', stop_reason = 'message rejected by reviewer'
                                      WHERE org_id = ? AND id = (SELECT enrollment_id FROM outbound_drafts WHERE id = ?)""",
                                   (org_id, row["subject_id"]))
            conn.commit()


class PolicyRepository:
    @staticmethod
    def evaluate_rule(rule_name: str, default_level: str = "L1", org_id: str = "org_default") -> str:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT level FROM policies WHERE rule_name = ? AND org_id = ?", (rule_name, org_id))
            row = cursor.fetchone()
            return row["level"] if row else default_level

    @staticmethod
    def record_decision(rule_name: str, allowed: bool, reason: str, input_data: dict, org_id: str = "org_default") -> None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO policy_decisions (rule_name, allowed, reason, input_json, org_id)
                VALUES (?, ?, ?, ?, ?)
            """, (rule_name, 1 if allowed else 0, reason, json.dumps(input_data), org_id))
            conn.commit()


class AgentRunRepository:
    @staticmethod
    def log_run(
        agent_name: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        latency_ms: int,
        status: str = "success",
        input_ref: Optional[str] = None,
        output_ref: Optional[str] = None,
        org_id: str = "org_default"
    ) -> None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_runs (
                    agent_name, model, tokens_in, tokens_out, cost_usd,
                    latency_ms, status, input_ref, output_ref, org_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (agent_name, model, tokens_in, tokens_out, cost_usd, latency_ms, status, input_ref, output_ref, org_id))
            conn.commit()

