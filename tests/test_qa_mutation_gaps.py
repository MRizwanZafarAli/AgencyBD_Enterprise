"""Tests added because deliberate breakage of the code (mutation testing) went unnoticed. Each one pins an exact boundary or number that the
earlier tests only brushed past: lockout limits, session cut-off, scoring points, quiet-day limits, report percentages."""

import json
import time
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest

from database.db import get_db
from database.models import AuditRunRepository, CompanyRepository, EvidenceRepository, LeadRepository
from security import auth as auth_mod, passwords

NOW = 1_800_000_000.0


# ------------------------------------------------------------------ passwords: exact lockout limits and what a good sign-in clears

def test_four_failures_do_not_lock_but_the_fifth_does_and_the_wait_is_exact():
    for i in range(4):
        passwords.record("5.5.5.5", "auditor", False, now=NOW - 60 + i)
    assert passwords.retry_after("5.5.5.5", now=NOW) == 0
    passwords.record("5.5.5.5", "auditor", False, now=NOW - 60 + 4)
    wait = passwords.retry_after("5.5.5.5", now=NOW)
    assert wait == int((NOW - 60) + passwords.WINDOW_SECONDS - NOW) + 1 == 841              # until the oldest of the five leaves the 15-minute window


def test_the_global_limit_is_exactly_one_hundred():
    for i in range(passwords.FAILS_GLOBAL - 1):
        passwords.record(f"9.9.{i // 250}.{i % 250}", "auditor", False, now=NOW - 30 + i * 0.01)
    assert passwords.retry_after("1.2.3.4", now=NOW) == 0
    passwords.record("9.9.9.9", "auditor", False, now=NOW - 1)
    assert passwords.retry_after("1.2.3.4", now=NOW) > 0


def test_a_good_sign_in_clears_only_that_addresss_mistakes():
    for ip in ("1.1.1.1", "2.2.2.2"):
        for i in range(3):
            passwords.record(ip, "auditor", False, now=NOW - 10 + i)
    passwords.record("1.1.1.1", "auditor", True, now=NOW)
    with get_db() as db:
        left = {r[0]: r[1] for r in db.execute("SELECT ip, COUNT(*) FROM login_attempts WHERE ok = 0 GROUP BY ip")}
    assert left == {"2.2.2.2": 3}


def test_a_generated_password_is_twenty_characters_from_the_safe_alphabet():
    for _ in range(50):
        pw = passwords.generate()
        assert len(pw) == 20 and all(c.isalnum() or c in "-_" for c in pw) and not set(pw) & set("0O1lI")


def test_old_attempts_are_swept_away():
    passwords.record("7.7.7.7", "auditor", False, now=NOW - 2 * 86400)
    passwords.record("7.7.7.7", "auditor", False, now=NOW)
    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM login_attempts WHERE ip = '7.7.7.7'").fetchone()[0] == 1


# ------------------------------------------------------------------ sessions end exactly at the moment the password changed

def test_a_session_issued_at_the_moment_of_the_change_lives_and_one_a_moment_earlier_does_not(monkeypatch):
    passwords.set_password("auditor", "Quiet-River_Stone-Lamp-71", by="t", org="org_cut")
    changed = passwords.updated_at("auditor", "org_cut")
    assert auth_mod._session_is_current("org_cut", "auditor", changed) is True
    assert auth_mod._session_is_current("org_cut", "auditor", changed - 0.001) is False
    assert auth_mod._session_is_current("org_cut", "auditor", changed + 5) is True
    assert auth_mod._session_is_current("org_without_password", "auditor", 1.0) is True              # no password row: nothing to compare with


def test_a_token_without_an_org_belongs_to_the_default_workspace():
    tok = jwt.encode({"sub": "x", "role": "auditor", "iss": "agencybd-enterprise", "aud": "agencybd-api", "iat": time.time(), "exp": time.time() + 600}, auth_mod.JWT_SECRET_KEY, algorithm="HS256")
    from fastapi.security import HTTPAuthorizationCredentials
    p = auth_mod.get_current_principal(auth_creds=HTTPAuthorizationCredentials(scheme="Bearer", credentials=tok))
    assert p.org_id == "org_default"


# ------------------------------------------------------------------ lead score: every point has a source

def lead_with(org, name, notes=None, reviews=0, source="manual", phone=None, verified=False, findings=()):
    lead = LeadRepository.create_or_get_lead(name, f"{name.lower().replace(' ', '')}.example", phone=phone, reviews_count=reviews, source_channel=source, notes=notes, org_id=org)
    if findings:
        c = CompanyRepository.create_or_get(name, lead["domain"], org_id=org)
        rows = []
        for i, sev in enumerate(findings):
            ev = EvidenceRepository.record_evidence("audit", c["id"], "x", "v", "auditors.security", f"https://{lead['domain']}", 1.0, org)
            rows.append({"category": "security", "check_id": f"c{i}", "severity": sev, "finding": "f", "fix": "x", "estimated_impact": "i", "service_id": "security_hardening",
                         "evidence_value": "v", "confidence": 0.9, "evidence_id": ev["id"]})
        AuditRunRepository.record_run(domain=lead["domain"], overall_score=50, summary="s", findings=rows, company_id=c["id"], org_id=org, status="completed")
    if verified:
        with get_db() as db:
            db.execute("INSERT INTO decision_makers (lead_id, org_id, first_name, last_name, title, email, verification_status) VALUES (?, ?, 'A', 'B', 'Owner', ?, 'verified')", (lead["id"], org, f"a@{lead['domain']}"))
            db.commit()
    return lead["id"]


def comp(lead_id, org):
    from intel import lead_priority
    return lead_priority.score_lead(lead_id, org, persist=False)


@pytest.mark.parametrize("sev,points", [("critical", 12), ("high", 8), ("medium", 4), ("low", 1), ("info", 0)])
def test_each_severity_of_finding_adds_its_exact_points(sev, points):
    r = comp(lead_with("org_sc", f"Sev {sev}", findings=[sev]), "org_sc")
    assert r["components"]["need"] == points


def test_the_need_part_never_exceeds_its_weight_and_adds_up():
    assert comp(lead_with("org_sc", "Two", findings=["critical", "high"]), "org_sc")["components"]["need"] == 20
    assert comp(lead_with("org_sc", "Many", findings=["critical"] * 9), "org_sc")["components"]["need"] == 45          # 9 x 12 = 108, capped at 45


@pytest.mark.parametrize("tag,points", [("no_website_listed", 20), ("no_website_in_osm", 12), ("social_only", 18), ("domain_unreachable", 18), ("domain_parked", 18), ("tls_broken", 16), ("something_else", 0)])
def test_each_web_presence_adds_its_exact_points(tag, points):
    assert comp(lead_with("org_sc", f"Pres {tag}", notes=f"WEB PRESENCE: {tag}"), "org_sc")["components"]["presence"] == points


@pytest.mark.parametrize("reviews,points", [(0, 0), (4, 0), (5, 5), (14, 5), (15, 10), (49, 10), (50, 15), (5000, 15)])
def test_review_counts_move_reputation_at_exact_thresholds(reviews, points):
    assert comp(lead_with("org_sc", f"Rev {reviews}", reviews=reviews), "org_sc")["components"]["reputation"] == points


@pytest.mark.parametrize("source,points", [("hiring_intent", 15), ("sec_edgar_form_d", 12), ("google_maps", 8), ("map_osm", 6), ("crm_pipeline", 5), ("manual", 0)])
def test_each_source_adds_its_exact_points(source, points):
    assert comp(lead_with("org_sc", f"Src {source}", source=source), "org_sc")["components"]["signal"] == points


def test_a_verified_contact_beats_a_phone_and_neither_is_invented():
    assert comp(lead_with("org_sc", "Verified", verified=True, phone="+353861234567"), "org_sc")["components"]["reachability"] == 5
    assert comp(lead_with("org_sc", "Phone only", phone="+353861234567"), "org_sc")["components"]["reachability"] == 2
    none = comp(lead_with("org_sc", "Nobody"), "org_sc")
    assert none["components"]["reachability"] == 0 and "find_contact" in none["needs"]


@pytest.mark.parametrize("points,band", [(34, "cold"), (35, "warm"), (59, "warm"), (60, "hot")])
def test_bands_change_at_exactly_35_and_60(points, band):
    from intel import lead_priority
    assert lead_priority._band(points) == band


def test_the_weights_add_up_to_one_hundred_and_an_unaudited_lead_says_so():
    from intel import lead_priority
    assert sum(lead_priority.WEIGHTS.values()) == 100
    r = comp(lead_with("org_sc", "Unaudited"), "org_sc")
    assert r["confidence"] == "low" and "run_audit" in r["needs"] and any("Not audited" in x for x in r["reasons"])


# ------------------------------------------------------------------ chase list: exact quiet-day limits for each stage

@pytest.mark.parametrize("stage,limit", [("proposal_sent", 3), ("meeting_booked", 2), ("sequence_active", 4)])
def test_a_client_is_listed_after_exactly_the_stage_limit_and_not_a_day_sooner(stage, limit):
    from workflows import chase
    today = date(2026, 11, 10)
    for days, listed in ((limit - 1, False), (limit, True)):
        with get_db() as db:
            db.execute("DELETE FROM leads WHERE org_id = 'org_ch'")
            db.commit()
        lead = LeadRepository.create_or_get_lead("Edge", "edge.example", source_channel="x", org_id="org_ch")["id"]
        when = (datetime(2026, 11, 10, 9, tzinfo=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as db:
            db.execute("UPDATE leads SET status = ?, created_at = ? WHERE id = ?", (stage, when, lead))
            db.commit()
        got = chase.to_chase("org_ch", today)
        assert bool(got) is listed, f"{stage} quiet for {days} days"
        if listed:
            assert got[0]["days_quiet"] == days and f"nothing has happened for {days} day" in got[0]["reason"]


def test_the_quiet_limits_and_order_are_the_documented_ones():
    from workflows import chase
    assert chase.QUIET_AFTER_DAYS == {"proposal_sent": 3, "meeting_booked": 2, "sequence_active": 4}
    assert chase.STAGE_RANK["proposal_sent"] < chase.STAGE_RANK["meeting_booked"] < chase.STAGE_RANK["sequence_active"]


# ------------------------------------------------------------------ scorecard: the weeks and the rate

def test_the_previous_week_starts_exactly_seven_days_before_this_one_and_a_rate_rounds_correctly():
    from workflows import scorecard as sc
    card = sc.scorecard("org_sc2", date(2026, 11, 11))
    assert card["week_start"] == "2026-11-09" and card["last_week_start"] == "2026-11-02"
    assert [r["key"] for r in card["rows"]][:3] == ["found", "sent", "replies"]
    with get_db() as db:
        for i, kind in enumerate(["sent", "sent", "sent", "replied"]):
            db.execute("INSERT INTO outreach_events (org_id, lead_id, recipient_email, event_type, created_at) VALUES ('org_sc2', 1, 'a@b.c', ?, '2026-11-10 10:00:00')", (kind,))
        db.commit()
    assert sc.scorecard("org_sc2", date(2026, 11, 11))["reply_rate_percent"] == 33                    # 1 of 3
    with get_db() as db:
        db.execute("INSERT INTO outreach_events (org_id, lead_id, recipient_email, event_type, created_at) VALUES ('org_sc2', 1, 'a@b.c', 'replied', '2026-11-10 11:00:00')")
        db.commit()
    assert sc.scorecard("org_sc2", date(2026, 11, 11))["reply_rate_percent"] == 67                    # 2 of 3


# ------------------------------------------------------------------ saved searches and the alert plan: exact limits

def test_a_search_name_may_be_80_characters_and_no_more():
    from leadfinder import engine
    assert engine.create_search("org_nm", "x" * 80, "hiring", {"keywords": ["react"]})["name"] == "x" * 80
    with pytest.raises(ValueError, match="short name"):
        engine.create_search("org_nm", "x" * 81, "hiring", {"keywords": ["react"]})


def test_a_run_reports_what_it_found_and_the_cycle_counts_the_searches_it_ran():
    from leadfinder import engine
    with get_db() as db:
        db.execute("INSERT INTO opportunities (org_id, type, source, external_id, title, description, fit_score) VALUES ('org_cy', 'hiring_signal', 'hn', 'z1', 'React dev', '', 0.5)")
        db.commit()
    s = engine.create_search("org_cy", "React", "hiring", {"keywords": ["react"]})
    assert engine.cycle(datetime(2026, 11, 10, tzinfo=timezone.utc))["ran"] >= 1
    assert engine.get_search("org_cy", s["id"])["last_detail"] == "1 found, 1 new."
    assert engine.cycle(datetime(2026, 11, 10, tzinfo=timezone.utc))["ran"] == 0                      # not due again yet


def test_the_alert_plan_allows_ten_steps_and_working_days_must_be_real_days():
    from alertdesk import engine
    ten = [{"after_minutes": i * 5, "channel": "telegram"} for i in range(10)]
    assert len(engine.validate({"enabled": False, "steps": ten})["steps"]) == 10
    with pytest.raises(ValueError, match="between 1 and 10"):
        engine.validate({"enabled": False, "steps": ten + [{"after_minutes": 99, "channel": "telegram"}]})
    for bad in ([7], [-1], ["1"], "mon", [1.5]):
        with pytest.raises(ValueError, match="working day"):
            engine.validate({"schedule": {"days": bad}})
    assert engine.validate({"schedule": {"days": [0, 6]}})["schedule"]["days"] == [0, 6]


# ------------------------------------------------------------------ email A/B: report numbers and the safety filter

def test_the_cohort_report_shows_exact_percentages():
    from analytics.ab_testing_cohorts import SpintaxABOptimizer as ab
    for _ in range(8):
        ab.record_cohort_impression("org_ab", "s1")
    for kind, n in (("open", 4), ("reply", 2), ("positive_reply", 1), ("bounce", 1)):
        for _ in range(n):
            ab.record_cohort_event("org_ab", "s1", kind)
    r = ab.get_cohort_report("org_ab")[0]
    assert (r["open_rate_pct"], r["reply_rate_pct"], r["conversion_rate_pct"], r["bounce_rate_pct"]) == (50.0, 25.0, 12.5, 12.5)


@pytest.mark.parametrize("sends,bounces,dropped", [(19, 19, False), (20, 0, False), (20, 1, True), (50, 1, False), (50, 2, True), (100, 2, False), (100, 3, True)])
def test_a_variant_that_bounces_more_than_two_percent_is_dropped_only_after_twenty_sends(sends, bounces, dropped):
    from analytics.ab_testing_cohorts import SpintaxABOptimizer as ab
    org = f"org_bounce_{sends}_{bounces}"
    for _ in range(sends):
        ab.record_cohort_impression(org, "risky")
    for _ in range(bounces):
        ab.record_cohort_event(org, "risky", "bounce")
    picks = {ab.select_best_variant(org, [{"key": "risky"}, {"key": "other"}], epsilon=0.0)["key"] for _ in range(60)}
    assert ("risky" not in picks) is dropped
