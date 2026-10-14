"""
DispatchAgent: Deliverability Guard, Domain Rotator & Dispatch Scheduler.
Manages sending quotas, simulates randomized human delays, and protects sender domain reputation.
"""

import random
from datetime import datetime
from typing import Dict, Any, List, Optional
from database.models import LeadRepository, OutreachRepository
from database.db import get_db
from config.deliverability import SECONDARY_SENDING_DOMAINS
from config.settings import settings
from config.honesty import NotConfiguredError, PreconditionFailedError

class DispatchAgent:
    """
    Manages safe email dispatching across rotated inboxes.
    Enforces strict daily sending limits and prevents spam triggers.
    """

    def __init__(self):
        self.inbox_pool = SECONDARY_SENDING_DOMAINS

    def get_available_inbox(self) -> Optional[Dict[str, Any]]:
        for inbox in self.inbox_pool:
            if inbox["sent_today"] < inbox["daily_limit"]:
                return inbox
        return None

    def dispatch_lead(self, lead_id: int) -> Dict[str, Any]:
        lead = LeadRepository.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead ID {lead_id} does not exist.")

        sequences = OutreachRepository.get_sequences_by_lead(lead_id)
        if not sequences:
            raise ValueError(f"No outreach sequences found for Lead ID {lead_id}.")

        step_1 = sequences[0]
        if step_1["spam_score"] > settings.thresholds.spam_score_max_allowed:
            raise ValueError(f"Dispatch blocked by Deliverability Guard: Spam score ({step_1['spam_score']}) exceeds limit.")

        # Real sending is policy-gated and goes through /api/outbound/sequence/step. Nothing is marked 'sent' here.
        return {
            "lead_id": lead_id,
            "status": "not_sent",
            "reason": "Direct dispatch is disabled. Approve the sequence and send it via /api/outbound/sequence/step (verified, suppressed-checked, policy-gated).",
            "step_id": step_1["id"],
            "subject": step_1["subject"],
        }
