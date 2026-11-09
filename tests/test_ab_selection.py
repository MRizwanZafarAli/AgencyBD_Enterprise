"""The email A/B chooser must not lock onto the worse variant when sends are few (a small agency sends tens, not thousands)."""

import random

from analytics.ab_testing_cohorts import SpintaxABOptimizer

CANDS = [{"key": "A"}, {"key": "B"}]


def simulate(rates, sends, seed):
    rng = random.Random(seed)
    stats = {k: {"impressions": 0, "positive_replies": 0} for k in rates}
    for _ in range(sends):
        pick = SpintaxABOptimizer.pick_by_posterior(stats, [{"key": k} for k in rates], rng)["key"]
        stats[pick]["impressions"] += 1
        stats[pick]["positive_replies"] += rng.random() < rates[pick]
    return stats


def test_with_no_evidence_both_variants_are_tried_about_equally_whichever_is_listed_first():
    shares = [simulate({"A": 0.03, "B": 0.03}, 60, s)["A"]["impressions"] / 60 for s in range(300)]
    assert 0.40 < sum(shares) / len(shares) < 0.60                       # the old rule gave the first-listed variant almost every early send


def test_the_better_variant_wins_at_realistic_small_volumes_even_when_listed_second():
    for sends, floor in ((200, 0.70), (500, 0.80)):
        wins = sum(simulate({"A": 0.03, "B": 0.06}, sends, s)["B"]["impressions"] > sends / 2 for s in range(400)) / 400
        assert wins >= floor, f"{sends} sends: better variant led in only {wins:.0%} of runs"          # the old rule managed 34% and 59%


def test_it_rarely_locks_all_sends_onto_the_worse_variant():
    locked = sum(simulate({"A": 0.03, "B": 0.06}, 200, s)["A"]["impressions"] > 0.85 * 200 for s in range(400)) / 400
    assert locked <= 0.10                                                # the old rule: 44%


def test_a_clear_winner_is_chosen_and_a_new_variant_still_gets_its_chance():
    stats = {"A": {"impressions": 50, "positive_replies": 1}, "B": {"impressions": 50, "positive_replies": 10}}
    rng = random.Random(1)
    assert sum(SpintaxABOptimizer.pick_by_posterior(stats, CANDS, rng)["key"] == "B" for _ in range(500)) > 495
    fresh = {"A": {"impressions": 200, "positive_replies": 6}}           # B has never been sent
    picks = [SpintaxABOptimizer.pick_by_posterior(fresh, CANDS, rng)["key"] for _ in range(500)]
    assert 100 < picks.count("B") < 400                                  # an untried variant is not ignored, and not preferred outright
