"""
HITLApprovalGateAgent: Tiered Human-in-the-Loop Governance & Quality Gate.
Separates high-ticket Enterprise accounts (Tier 1: $50k+ contracts) requiring founder 1-click review
from standard accounts (Tier 3: $10k contracts) running on 100% autopilot.
"""

from typing import Dict, Any, List
from database.models import LeadRepository, OutreachRepository
from database.db import log_audit_trail

class HITLApprovalGateAgent:
    """
    Tiered Approval Gate protecting agency reputation on high-ticket enterprise deals.
    """

    ENTERPRISE_VALUATION_THRESHOLD = 50000.0  # Accounts above $50k require founder approval

    @staticmethod
    def classify_governance_tier(source_channel: str, est_deal_value: float = 25000.0) -> str:
        """Classifies account into TIER_1_ENTERPRISE_REVIEW or TIER_3_AUTOPILOT."""
        if source_channel == "venture_database" or est_deal_value >= HITLApprovalGateAgent.ENTERPRISE_VALUATION_THRESHOLD:
            return "TIER_1_ENTERPRISE_APPROVAL_REQUIRED"
        return "TIER_3_FULL_AUTOPILOT"

    @staticmethod
    def route_for_approval_or_autopilot(lead_id: int, est_deal_value: float = 25000.0) -> Dict[str, Any]:
        lead = LeadRepository.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead ID {lead_id} does not exist.")

        tier = HITLApprovalGateAgent.classify_governance_tier(lead["source_channel"], est_deal_value)

        if tier == "TIER_1_ENTERPRISE_APPROVAL_REQUIRED":
            LeadRepository.update_status(lead_id, "pending_approval")
            log_audit_trail(lead_id, "HITLApprovalGate", "HOLD_FOR_FOUNDER_APPROVAL", {"deal_value": est_deal_value})
            status = "HELD_IN_APPROVAL_BUCKET"
        else:
            status = "APPROVED_FOR_AUTOPILOT_SEND"

        return {
            "lead_id": lead_id,
            "company_name": lead["company_name"],
            "governance_tier": tier,
            "dispatch_status": status,
            "requires_human_signoff": tier == "TIER_1_ENTERPRISE_APPROVAL_REQUIRED"
        }

    @staticmethod
    def approve_lead_dispatch(lead_id: int, approver: str = "operator") -> Dict[str, Any]:
        """Approves a held Tier 1 lead and queues it for immediate dispatch."""
        LeadRepository.update_status(lead_id, "queued")
        log_audit_trail(lead_id, "HITLApprovalGate", "FOUNDER_APPROVAL_GRANTED", {"approver": approver})
        return {
            "lead_id": lead_id,
            "status": "queued",
            "approver": approver,
            "message": "Outreach approved for dispatch."
        }
