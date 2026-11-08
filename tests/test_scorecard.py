"""Weekly scorecard: counted from real records; rates only when there is something to divide by."""

import json
from datetime import date

from database.db import get_db
from database.models import LeadRepository
from workflows import scorecard as sc

ORG = "org_sc"
TODAY = date(2026, 11, 11)             # a Wednesday; this week starts Monday 2026-11-09, last week 2026-11-02


def row(card, key):
    return next(r for r in card["rows"] if r["key"] == key)


def lead(name, source="hiring", stage="sourced", created="2026-11-10 09:00:00"):
    l = LeadRepository.create_or_get_lead(name, f"{name.lower()}.example", source_channel=source, org_id=ORG)
    with get_db() as db:
        db.execute("UPDATE leads SET status = ?, created_at = ? WHERE id = ?", (stage, created, l["id"]))
        db.commit()
    return l["id"]


def ev(lead_id, kind, when):
    with get_db() as db:
        db.execute("INSERT INTO outreach_events (org_id, lead_id, recipient_email, event_type, created_at) VALUES (?, ?, 'a@b.c', ?, ?)", (ORG, lead_id, kind, when))
        db.commit()


def stage_event(lead_id, new_stage, when):
    with get_db() as db:
        db.execute("INSERT INTO audit_trail (lead_id, org_id, actor, action, metadata_json, created_at) VALUES (?, ?, 'u', 'STAGE_UPDATED', ?, ?)", (lead_id, ORG, json.dumps({"new_stage": new_stage}), when))
        db.commit()


def test_week_runs_monday_to_sunday():
    assert sc.week_bounds(TODAY) == (date(2026, 11, 9), date(2026, 11, 16))
    assert sc.week_bounds(date(2026, 11, 9))[0] == date(2026, 11, 9) and sc.week_bounds(date(2026, 11, 15))[0] == date(2026, 11, 9)


def test_an_empty_workspace_shows_zeros_and_no_invented_rate():
    c = sc.scorecard(ORG, TODAY)
    assert all(r["this_week"] == 0 and r["last_week"] == 0 for r in c["rows"])
    assert c["reply_rate_percent"] is None and c["last_reply_rate_percent"] is None and c["winners_by_source"] == []


def test_this_week_and_last_week_are_counted_separately_from_real_events():
    a, b = lead("Alpha"), lead("Beta", created="2026-11-03 09:00:00")
    ev(a, "sent", "2026-11-10 10:00:00"), ev(a, "sent", "2026-11-11 10:00:00"), ev(a, "replied", "2026-11-11 12:00:00"), ev(b, "sent", "2026-11-04 10:00:00")
    stage_event(a, "proposal_sent", "2026-11-11 08:00:00"), stage_event(b, "won", "2026-11-05 08:00:00"), stage_event(b, "proposal_sent", "2026-11-03 08:00:00")
    c = sc.scorecard(ORG, TODAY)
    assert (row(c, "sent")["this_week"], row(c, "sent")["last_week"]) == (2, 1)
    assert (row(c, "replies")["this_week"], row(c, "replies")["last_week"]) == (1, 0)
    assert (row(c, "proposals")["this_week"], row(c, "proposals")["last_week"]) == (1, 1) and (row(c, "wins")["this_week"], row(c, "wins")["last_week"]) == (0, 1)
    assert (row(c, "found")["this_week"], row(c, "found")["last_week"]) == (1, 1)
    assert c["reply_rate_percent"] == 50 and c["last_reply_rate_percent"] == 0


def test_the_week_boundary_is_exact():
    a = lead("Edge")
    ev(a, "sent", "2026-11-08 23:59:59"), ev(a, "sent", "2026-11-09 00:00:00"), ev(a, "sent", "2026-11-15 23:59:59"), ev(a, "sent", "2026-11-16 00:00:00")
    c = sc.scorecard(ORG, TODAY)
    assert (row(c, "sent")["last_week"], row(c, "sent")["this_week"]) == (1, 2)


def test_a_kept_hit_is_not_counted_twice_and_other_workspaces_are_ignored():
    lead("FromHit", source="lead_finder")
    with get_db() as db:
        db.execute("INSERT INTO lead_searches (id, org_id, name, source) VALUES (1, ?, 's', 'hiring')", (ORG,))
        db.execute("INSERT INTO lead_hits (org_id, search_id, key, title, first_seen_at) VALUES (?, 1, 'k', 't', '2026-11-10 09:00:00')", (ORG,))
        db.execute("INSERT INTO lead_hits (org_id, search_id, key, title, first_seen_at) VALUES ('someone_else', 1, 'k2', 't', '2026-11-10 09:00:00')")
        db.commit()
    assert row(sc.scorecard(ORG, TODAY), "found")["this_week"] == 1


def test_winners_are_named_only_by_sources_of_clients_you_won():
    lead("W1", source="local", stage="won"), lead("W2", source="local", stage="won"), lead("W3", source="referral", stage="won"), lead("L1", source="hiring", stage="lost")
    assert sc.scorecard(ORG, TODAY)["winners_by_source"] == [{"source": "local", "n": 2}, {"source": "referral", "n": 1}]


def test_messages_referrals_and_followups_are_counted():
    from alertdesk import engine
    from workflows import client_notes, partners
    engine.ingest(ORG, "fiverr", "Amina", "hello")
    p = partners.create(ORG, {"name": "P"})
    partners.add_event(ORG, p["id"], "referral_in", None)
    l = lead("Task")
    t = client_notes.add(ORG, l, "task", "Call", "2026-11-12", "u")
    client_notes.update(ORG, l, t["id"], {"done": True})
    today = date.today()
    c = sc.scorecard(ORG, today)
    assert row(c, "messages")["this_week"] == 1 and row(c, "referrals")["this_week"] == 1 and row(c, "followups")["this_week"] == 1


def test_the_api_is_tenant_scoped(client, make_key):
    h = make_key("growth_lead", ORG)
    assert client.get("/api/today/scorecard").status_code == 401
    body = client.get("/api/today/scorecard", headers=h).json()
    assert [r["key"] for r in body["rows"]][:2] == ["found", "sent"] and "note" in body
    assert all(r["this_week"] == 0 for r in client.get("/api/today/scorecard", headers=make_key("growth_lead", "org_sc_other")).json()["rows"])
