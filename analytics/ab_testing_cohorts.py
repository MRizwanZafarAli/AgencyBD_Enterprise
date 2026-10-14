"""
Spintax & Copywriting A/B Cohort Bandit Optimizer.
Tracks conversion cohorts across subject lines, hooks, and CTAs, and dynamically
optimizes dispatch weighting using an Epsilon-Greedy Multi-Armed Bandit algorithm.
"""

import random
from typing import Dict, Any, List, Optional
from database.db import get_db

class SpintaxABOptimizer:
    @staticmethod
    def record_cohort_impression(org_id: str, variant_key: str, variant_type: str = "subject") -> None:
        """Records an outreach dispatch using a particular variant."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ab_test_cohorts (org_id, variant_key, variant_type, impressions)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(org_id, variant_key) DO UPDATE SET
                    impressions = impressions + 1
            """, (org_id, variant_key, variant_type))
            conn.commit()

    @staticmethod
    def record_cohort_event(org_id: str, variant_key: str, event_type: str) -> None:
        """
        Records an interaction event: 'open', 'reply', 'positive_reply', 'bounce'.
        """
        valid_cols = {
            "open": "opens",
            "reply": "replies",
            "positive_reply": "positive_replies",
            "bounce": "bounces"
        }
        col = valid_cols.get(event_type)
        if not col:
            return

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE ab_test_cohorts
                SET {col} = {col} + 1
                WHERE org_id = ? AND variant_key = ?
            """, (org_id, variant_key))
            conn.commit()

    @staticmethod
    def select_best_variant(
        org_id: str,
        candidates: List[Dict[str, str]],
        epsilon: float = 0.15
    ) -> Dict[str, str]:
        """
        Multi-Armed Bandit Selection (Epsilon-Greedy):
        - With probability (1 - epsilon): exploit best variant (highest positive reply / conversion rate).
        - With probability epsilon: explore random variant to discover new high-performing copy.
        - Automatically filters out any variant with bounce rate exceeding 2.0%.
        """
        if not candidates:
            raise ValueError("No candidates provided for selection")

        if len(candidates) == 1:
            return candidates[0]

        # Fetch stats from DB
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT variant_key, impressions, positive_replies, bounces
                FROM ab_test_cohorts
                WHERE org_id = ?
            """, (org_id,))
            stats = {row["variant_key"]: dict(row) for row in cursor.fetchall()}

        # Filter out dangerous high-bounce candidates
        safe_candidates = []
        for cand in candidates:
            v_key = cand["key"]
            s = stats.get(v_key)
            if s and s["impressions"] >= 20:
                bounce_rate = s["bounces"] / s["impressions"]
                if bounce_rate > 0.02:
                    continue  # suppress dangerous variant
            safe_candidates.append(cand)

        if not safe_candidates:
            safe_candidates = candidates

        # Exploration phase
        if random.random() < epsilon:
            return random.choice(safe_candidates)

        # Exploitation phase: pick highest positive conversion rate
        best_cand = safe_candidates[0]
        best_score = -1.0

        for cand in safe_candidates:
            v_key = cand["key"]
            s = stats.get(v_key)
            if not s or s["impressions"] == 0:
                score = 0.05  # optimistic prior for unexercised variants
            else:
                score = (s["positive_replies"] * 3.0) / s["impressions"]
            
            if score > best_score:
                best_score = score
                best_cand = cand

        return best_cand

    @staticmethod
    def get_cohort_report(org_id: str = "org_default") -> List[Dict[str, Any]]:
        """Returns performance rankings across all tested variations."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT variant_key, variant_type, impressions, opens, replies, positive_replies, bounces
                FROM ab_test_cohorts
                WHERE org_id = ?
                ORDER BY positive_replies DESC, impressions DESC
            """, (org_id,))
            rows = cursor.fetchall()

            report = []
            for r in rows:
                imp = max(r["impressions"], 1)
                report.append({
                    "variant_key": r["variant_key"],
                    "variant_type": r["variant_type"],
                    "impressions": r["impressions"],
                    "opens": r["opens"],
                    "open_rate_pct": round((r["opens"] / imp) * 100, 1),
                    "replies": r["replies"],
                    "reply_rate_pct": round((r["replies"] / imp) * 100, 1),
                    "positive_replies": r["positive_replies"],
                    "conversion_rate_pct": round((r["positive_replies"] / imp) * 100, 1),
                    "bounce_rate_pct": round((r["bounces"] / imp) * 100, 1)
                })
            return report
