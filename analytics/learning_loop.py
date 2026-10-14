"""
Learning loop: what is actually working, with the sample sizes to judge it.

Everything here is computed from stored events. Where there is not enough data the report says so ("insufficient_data")
instead of declaring a winner. Costs include LLM spend (agent_runs) and manually recorded expenses (financial_ledger);
costs that are not tracked are listed so nobody mistakes "0" for "free".
"""

import math
from typing import Any, Dict, List, Optional

from database.db import get_db

MIN_DECIDED_PER_VARIANT = 10     # won+lost proposals needed per variant before comparing
SIGNIFICANCE = 0.10              # two-sided p-value for calling a difference "directional"
UNTRACKED_COSTS = ["email verification credits", "Upwork Connects", "mailbox and domain subscriptions", "data-vendor subscriptions", "your own time"]


def two_proportion_p_value(x1: int, n1: int, x2: int, n2: int) -> Optional[float]:
    """Two-sided z-test for a difference between two win rates. None when it cannot be computed."""
    if n1 <= 0 or n2 <= 0:
        return None
    p1, p2, pooled = x1 / n1, x2 / n2, (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = abs(p1 - p2) / se
    return round(math.erfc(z / math.sqrt(2)), 4)


def _rate(num: int, den: int, digits: int = 2) -> Optional[float]:
    return round(num / den * 100, digits) if den else None


class LearningLoopEngine:
    @staticmethod
    def generate_learning_report(org_id: str = "org_default") -> Dict[str, Any]:
        with get_db() as db:
            variants: Dict[str, Dict[str, int]] = {}
            for r in db.execute("SELECT variant, status, COUNT(*) AS n FROM proposals WHERE org_id = ? GROUP BY variant, status", (org_id,)):
                v = variants.setdefault(r["variant"] or "A", {"total": 0, "approved": 0, "submitted": 0, "won": 0, "lost": 0})
                v["total"] += r["n"]
                if r["status"] in v:
                    v[r["status"]] += r["n"]
            events = {r["event_type"]: r["n"] for r in db.execute(
                "SELECT event_type, COUNT(*) AS n FROM outreach_events WHERE org_id = ? GROUP BY event_type", (org_id,))}
            evidence_count = db.execute("SELECT COUNT(*) FROM evidence WHERE org_id = ?", (org_id,)).fetchone()[0]
            ledger = {r["expense_type"]: round(r["t"], 4) for r in db.execute(
                "SELECT expense_type, SUM(amount_usd) AS t FROM financial_ledger WHERE org_id = ? GROUP BY expense_type", (org_id,))}
            llm_cost = db.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM agent_runs WHERE org_id = ?", (org_id,)).fetchone()[0]
            llm_calls = db.execute("SELECT COUNT(*) FROM agent_runs WHERE org_id = ? AND status = 'success'", (org_id,)).fetchone()[0]
            meetings = db.execute("SELECT COUNT(*) FROM meeting_bookings WHERE org_id = ?", (org_id,)).fetchone()[0]
            drafts = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) AS n FROM outbound_drafts WHERE org_id = ? GROUP BY status", (org_id,))}

        sent, bounced, complaints, replies = (events.get(k, 0) for k in ("sent", "bounced", "complaint", "replied"))
        bounce_rate, complaint_rate, reply_rate = _rate(bounced, sent), _rate(complaints, sent, 3), _rate(replies, sent)

        expenses = {**ledger, "llm": round(llm_cost, 4)}
        total_spend = round(sum(expenses.values()), 4)
        won = sum(v["won"] for v in variants.values())

        # ---- variant comparison, only when the data can support it
        for v in variants.values():
            decided = v["won"] + v["lost"]
            v["decided"], v["win_rate_percent"] = decided, _rate(v["won"], decided, 1)
        recs: List[str] = []
        a, b = variants.get("A"), variants.get("B")
        comparison: Dict[str, Any] = {"status": "insufficient_data", "p_value": None}
        if a and b and a["decided"] >= MIN_DECIDED_PER_VARIANT and b["decided"] >= MIN_DECIDED_PER_VARIANT:
            p = two_proportion_p_value(a["won"], a["decided"], b["won"], b["decided"])
            comparison = {"status": "compared", "p_value": p}
            if p is not None and p < SIGNIFICANCE and a["win_rate_percent"] != b["win_rate_percent"]:
                best, worst = ("A", "B") if a["win_rate_percent"] > b["win_rate_percent"] else ("B", "A")
                recs.append(f"Variant {best} wins more often ({variants[best]['win_rate_percent']}% vs {variants[worst]['win_rate_percent']}%, "
                            f"p={p}, n={a['decided']}+{b['decided']}). This is directional evidence, not proof: keep exploring.")
            else:
                recs.append(f"No significant difference between variants yet (p={p}). Keep testing both.")
        else:
            have = {k: v["decided"] for k, v in variants.items()}
            recs.append(f"Not enough won/lost outcomes to compare proposal variants (need {MIN_DECIDED_PER_VARIANT} decided per variant; have {have or 'none'}). "
                        "Record outcomes on each proposal so the system can learn.")

        if sent == 0:
            health = "NO_DATA"
        elif bounce_rate > 2.0 or (complaint_rate or 0) >= 0.1:
            health = "CIRCUIT_BREAKER_ACTIVE"
            recs.append(f"CRITICAL: bounce rate {bounce_rate}% / complaint rate {complaint_rate}% is over the safe limits (2% / 0.1%). Pause sending and clean the list.")
        elif bounce_rate > 1.0 or (complaint_rate or 0) > 0.05:
            health = "WARNING"
            recs.append(f"Watch deliverability: bounce {bounce_rate}%, complaints {complaint_rate}%.")
        else:
            health = "HEALTHY" if sent >= 50 else "HEALTHY_LOW_VOLUME"
        pending_review = drafts.get("pending_approval", 0)
        if pending_review:
            recs.append(f"{pending_review} outbound draft(s) are waiting for approval.")

        return {
            "org_id": org_id,
            "summary": {
                "total_outreach_sent": sent, "total_replies": replies, "reply_rate_percent": reply_rate,
                "bounce_rate_percent": bounce_rate, "complaint_rate_percent": complaint_rate,
                "evidence_records_stored": evidence_count, "meetings_booked": meetings, "proposals_won": won,
                "total_spend_usd": total_spend, "llm_calls": llm_calls,
                "cost_per_meeting_usd": round(total_spend / meetings, 2) if meetings else None,
                "cost_per_won_proposal_usd": round(total_spend / won, 2) if won else None,
            },
            "proposal_variant_performance": variants,
            "variant_comparison": comparison,
            "outbound_drafts": drafts,
            "expense_breakdown": expenses,
            "costs_not_tracked": UNTRACKED_COSTS,
            "strategic_recommendations": recs,
            "deliverability_health": health,
        }
