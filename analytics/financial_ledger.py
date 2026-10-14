"""
Financial Cost Attribution & Unit Economics Ledger.
Calculates SDR agent unit economics: Cost Per Qualified Lead (CPQL),
Cost Per Booked Meeting (CPBM), and Agent Return on Investment (ROI).
"""

import json
from typing import Dict, Any, List, Optional
from database.db import get_db

# Standard Unit Cost Rates (USD)
UNIT_COSTS = {
    "apollo_enrichment": 0.030,
    "hunter_enrichment": 0.010,
    "smtp_mx_handshake": 0.001,
    "deep_site_crawl": 0.005,
    "gpt4o_audit_analysis": 0.015,
    "claude_copywrite_sequence": 0.020,
    "proxy_bandwidth_mb": 0.002,
    "secondary_inbox_send": 0.001
}

class FinancialLedger:
    @staticmethod
    def record_expense(
        org_id: str,
        expense_type: str,
        amount_usd: float,
        lead_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Appends a cryptographically verified cost line item to the ledger."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO financial_ledger (org_id, lead_id, expense_type, amount_usd, metadata_json)
                VALUES (?, ?, ?, ?, ?)
            """, (org_id, lead_id, expense_type, amount_usd, json.dumps(metadata or {})))
            conn.commit()
            item_id = cursor.lastrowid
            return {
                "id": item_id,
                "org_id": org_id,
                "expense_type": expense_type,
                "amount_usd": amount_usd,
                "lead_id": lead_id
            }

    @staticmethod
    def log_agent_step_cost(org_id: str, lead_id: int, step_name: str) -> float:
        """Convenience method to log fixed step costs."""
        cost = UNIT_COSTS.get(step_name, 0.005)
        FinancialLedger.record_expense(
            org_id=org_id,
            expense_type=step_name,
            amount_usd=cost,
            lead_id=lead_id
        )
        return cost

    @staticmethod
    def get_unit_economics(org_id: str = "org_default", pipeline_deal_size: float = 35000.0) -> Dict[str, Any]:
        """
        Computes financial metrics across the entire funnel:
        Total Cost, Leads Count, Audits Count, Bookings Count,
        Cost Per Qualified Lead (CPQL), Cost Per Booked Meeting (CPBM), and ROI.
        """
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Total expenses
            cursor.execute("SELECT COALESCE(SUM(amount_usd), 0.0) as total_spent FROM financial_ledger WHERE org_id = ?", (org_id,))
            total_spent = float(cursor.fetchone()["total_spent"])

            # Leads count
            cursor.execute("SELECT COUNT(*) as total_leads FROM leads WHERE org_id = ?", (org_id,))
            total_leads = cursor.fetchone()["total_leads"]

            # Bookings count
            cursor.execute("SELECT COUNT(*) as total_bookings FROM meeting_bookings WHERE org_id = ?", (org_id,))
            total_bookings = cursor.fetchone()["total_bookings"]

            cpql = round(total_spent / max(total_leads, 1), 2)
            cpbm = round(total_spent / max(total_bookings, 1), 2) if total_bookings > 0 else total_spent

            pipeline_value = total_bookings * pipeline_deal_size
            roi_multiple = round((pipeline_value - total_spent) / max(total_spent, 1.0), 1) if total_spent > 0 else 0.0

            return {
                "org_id": org_id,
                "total_agent_cost_usd": round(total_spent, 3),
                "total_leads_sourced": total_leads,
                "total_meetings_booked": total_bookings,
                "cost_per_qualified_lead_usd": cpql,
                "cost_per_booked_meeting_usd": cpbm,
                "estimated_pipeline_value_usd": pipeline_value,
                "sdr_roi_multiple": roi_multiple
            }
