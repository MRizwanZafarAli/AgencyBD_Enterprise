"""
Enterprise Autonomy Policy Engine.
Governs autonomous vs human-in-the-loop decisions across tenants.
Enforces autonomy levels:
- L0 Observe: Collect and score only (Radar ingestion, audits, briefs)
- L1 Draft: Prepare; human approves each item (Marketplace proposals, first-touch outbound)
- L2 Guarded Auto: Act automatically ONLY IF all guard conditions pass (Sequence follow-ups, CRM sync)
- L3 Delegated: Auto within daily caps and circuit breakers (Approved templates to verified contacts)
- NEVER AUTO: Absolute safety blocks (Marketplace submission, LinkedIn automation, unverified emails, suppressed addresses)
"""

import json
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from database.db import get_db

@dataclass
class PolicyDecision:
    allowed: bool
    requires_human_approval: bool
    autonomy_level: str  # L0 | L1 | L2 | L3 | NEVER
    rule_name: str
    reason: str
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "requires_human_approval": self.requires_human_approval,
            "autonomy_level": self.autonomy_level,
            "rule_name": self.rule_name,
            "reason": self.reason,
            "context": self.context
        }

class PolicyEngine:
    # Hard-coded safety invariants per Section 5
    HARD_NEVER_AUTO_ACTIONS = {
        "marketplace_submit": "Upwork / Freelancer terms strictly prohibit autonomous proposal submission. Human review required.",
        "linkedin_action": "LinkedIn platform rules prohibit programmatic automation and scraping. Read-only companion mode only.",
    }

    # Actions that put a message in front of a real person.
    OUTBOUND_ACTIONS = {"outbound_send", "outbound_first_touch", "outbound_followup", "sequence_followup"}

    @classmethod
    def _block(cls, rule: str, reason: str, context: Dict[str, Any]) -> "PolicyDecision":
        return PolicyDecision(
            allowed=False, requires_human_approval=False, autonomy_level="NEVER",
            rule_name=rule, reason=reason, context=context
        )

    @classmethod
    def _outbound_guard(cls, org_id: str, context: Dict[str, Any]) -> Optional["PolicyDecision"]:
        """
        Returns a blocking decision, or None when every guard is satisfied.
        Facts are looked up here whenever the recipient/country is supplied; a caller can never
        *assert* its way past a guard, and a missing fact is treated as a failure.
        """
        # Verification must be positively 'verified'.
        if context.get("email_verification_status") != "verified":
            return cls._block("no_send_unverified", "Outbound delivery blocked: recipient email is not verified.", context)

        # Suppression: authoritative DB lookup when the recipient is known; otherwise the caller
        # must explicitly state False. A caller claiming True always blocks.
        recipient = context.get("recipient_email")
        if context.get("is_suppressed") is True:
            return cls._block("no_send_suppressed", "Outbound delivery blocked: recipient is in the suppression vault.", context)
        if recipient:
            from compliance.suppression import KeyedSuppressionVault
            if KeyedSuppressionVault.is_suppressed(recipient, org_id):
                return cls._block("no_send_suppressed", "Outbound delivery blocked: recipient is in the suppression vault.", context)
        elif context.get("is_suppressed") is not False:
            return cls._block("missing_suppression_check", "Outbound delivery blocked: suppression status was not established.", context)

        # Jurisdiction: computed from the country code when present; otherwise must be explicitly True.
        country = context.get("country_code")
        if country:
            from compliance.country_policy import CountryComplianceEngine
            verdict = CountryComplianceEngine.evaluate(country)
            if not verdict.allowed:
                return cls._block("jurisdiction_blocked", verdict.reason, context)
        elif context.get("jurisdiction_allowed") is not True:
            return cls._block("missing_jurisdiction_check", "Outbound delivery blocked: recipient jurisdiction was not established.", context)

        return None

    @staticmethod
    def get_tenant_policy(org_id: str, rule_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a tenant-specific autonomy policy rule."""
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("""
                SELECT * FROM policies WHERE org_id = ? AND rule_name = ?
            """, (org_id, rule_name))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                if data.get("config_json"):
                    data["config"] = json.loads(data["config_json"])
                return data
            return None

    @staticmethod
    def set_tenant_policy(org_id: str, rule_name: str, level: str, config: Optional[Dict[str, Any]] = None) -> None:
        """Sets or updates an autonomy policy rule for a tenant."""
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO policies (org_id, rule_name, level, config_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(org_id, rule_name) DO UPDATE SET
                    level = excluded.level,
                    config_json = excluded.config_json
            """, (org_id, rule_name, level, json.dumps(config or {})))
            db.commit()

    @classmethod
    def evaluate(
        cls,
        org_id: str,
        action_type: str,
        context: Dict[str, Any]
    ) -> PolicyDecision:
        """
        Evaluates whether an action can execute autonomously, requires human approval, or is hard-blocked.
        Logs every decision to the policy_decisions table.
        """
        decision: Optional[PolicyDecision] = None

        # 1. Hard-Coded Invariants (Never Auto)
        if action_type in cls.HARD_NEVER_AUTO_ACTIONS:
            decision = PolicyDecision(
                allowed=False,
                requires_human_approval=True,
                autonomy_level="NEVER",
                rule_name=f"hard_invariant_{action_type}",
                reason=cls.HARD_NEVER_AUTO_ACTIONS[action_type],
                context=context
            )

        # 2-4. Outbound safety guards. These FAIL CLOSED: anything the engine cannot prove is blocked.
        elif action_type in cls.OUTBOUND_ACTIONS:
            decision = cls._outbound_guard(org_id, context)

        # Generic belt-and-braces: an explicit negative signal blocks ANY action type.
        if not decision and context.get("is_suppressed") is True:
            decision = cls._block("no_send_suppressed", "Blocked: target is in the suppression vault.", context)
        if not decision and context.get("jurisdiction_allowed") is False:
            decision = cls._block("jurisdiction_blocked", context.get("jurisdiction_reason", "Jurisdiction rules prohibit this action."), context)

        # 5. Deal Value / Enterprise Tier Escalation
        if not decision:
            deal_value = context.get("deal_value", 0)
            threshold = context.get("high_value_threshold", 5000)
            if deal_value >= threshold:
                decision = PolicyDecision(
                    allowed=True,
                    requires_human_approval=True,
                    autonomy_level="L1",
                    rule_name="high_value_deal_approval",
                    reason=f"Deal value ${deal_value} meets or exceeds high-value threshold ${threshold}. Human review required.",
                    context=context
                )

        # 6. Tenant-Configured Autonomy Rule
        if not decision:
            policy = cls.get_tenant_policy(org_id, action_type)
            level = policy["level"] if policy else "L1"

            if level == "L0":
                decision = PolicyDecision(
                    allowed=False,
                    requires_human_approval=False,
                    autonomy_level="L0",
                    rule_name=f"tenant_l0_{action_type}",
                    reason="Tenant policy set to L0 Observe: data collection only.",
                    context=context
                )
            elif level == "L1":
                decision = PolicyDecision(
                    allowed=True,
                    requires_human_approval=True,
                    autonomy_level="L1",
                    rule_name=f"tenant_l1_{action_type}",
                    reason="Tenant policy set to L1 Draft: human approval required before execution.",
                    context=context
                )
            elif level in ("L2", "L3"):
                decision = PolicyDecision(
                    allowed=True,
                    requires_human_approval=False,
                    autonomy_level=level,
                    rule_name=f"tenant_{level.lower()}_{action_type}",
                    reason=f"Tenant policy authorizes autonomous execution at {level}.",
                    context=context
                )
            else:
                decision = PolicyDecision(
                    allowed=True,
                    requires_human_approval=True,
                    autonomy_level="L1",
                    rule_name="default_fallback_l1",
                    reason="Defaulting to L1 Draft for safety.",
                    context=context
                )

        # Log decision into policy_decisions table for enterprise governance
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO policy_decisions (org_id, rule_name, input_json, allowed, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (
                org_id,
                decision.rule_name,
                json.dumps(context),
                1 if decision.allowed and not decision.requires_human_approval else 0,
                decision.reason
            ))
            db.commit()

        return decision
