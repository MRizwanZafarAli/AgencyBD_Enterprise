"""Who to chase today: quiet clients in a live stage with no follow-up planned; dates come only from real activity."""

from datetime import date, datetime, timedelta, timezone

from database.db import get_db
from database.models import LeadRepository
from workflows import chase, client_notes

ORG = "org_chase"
TODAY = date(2026, 11, 10)


def lead(name, stage, days_ago, org=ORG):
    l = LeadRepository.create_or_get_lead(name, f"{name.lower().replace(' ', '')}.example", source_channel="x", org_id=org)
    when = (datetime(2026, 11, 10, 9, tzinfo=timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        db.execute("UPDATE leads SET status = ?, created_at = ? WHERE id = ?", (stage, when, l["id"]))
        db.commit()
    return l["id"]


def stamp(table_sql, args):
    with get_db() as db:
        db.execute(table_sql, args)
        db.commit()


def test_a_quiet_live_client_is_listed_with_the_reason_and_days():
    lead("Acme", "proposal_sent", 5)
    out = chase.to_chase(ORG, TODAY)
    assert len(out) == 1 and out[0]["days_quiet"] == 5 and out[0]["stage_label"] == "Proposal sent"
    assert "nothing has happened for 5 days" in out[0]["reason"] and "No follow-up is planned" in out[0]["reason"]


def test_recent_activity_and_other_stages_are_left_alone():
    lead("Fresh", "proposal_sent", 1)            # under the limit for a proposal (3 days)
    lead("Cold", "sourced", 30)                  # not in a live stage
    lead("Done", "won", 30)
    lead("Gone", "lost", 30)
    assert chase.to_chase(ORG, TODAY) == []


def written_long_ago():
    """Notes are stamped with the real clock when they are added; the scenario's clock is fixed, so move them into the scenario's past."""
    with get_db() as db:
        db.execute("UPDATE client_notes SET created_at = '2026-10-01 09:00:00'")
        db.commit()


def test_a_planned_follow_up_in_the_future_covers_the_client_but_an_overdue_one_does_not():
    a, b = lead("Planned", "meeting_booked", 6), lead("Late", "meeting_booked", 6)
    client_notes.add(ORG, a, "task", "Call about the proposal", (TODAY + timedelta(days=2)).isoformat(), "u")
    client_notes.add(ORG, b, "task", "Call about the proposal", (TODAY - timedelta(days=1)).isoformat(), "u")
    written_long_ago()
    assert [c["company"] for c in chase.to_chase(ORG, TODAY)] == ["Late"]
    client_notes.add(ORG, b, "task", "Follow up", TODAY.isoformat(), "u")        # one due today counts as planned
    assert chase.to_chase(ORG, TODAY) == []


def test_real_activity_resets_the_clock():
    a = lead("Noted", "sequence_active", 9)
    b = lead("Mailed", "sequence_active", 9)
    c = lead("Replied", "sequence_active", 9)
    d = lead("Moved", "sequence_active", 9)
    recent = "2026-11-09 10:00:00"
    stamp("INSERT INTO client_notes (org_id, lead_id, kind, body, created_by, created_at) VALUES (?, ?, 'note', 'spoke', 'u', ?)", (ORG, a, recent))
    stamp("INSERT INTO outreach_events (org_id, lead_id, recipient_email, event_type, created_at) VALUES (?, ?, 'x@y.z', 'sent', ?)", (ORG, b, recent))
    stamp("INSERT INTO inbound_replies (lead_id, reply_text, sentiment, objection_category, auto_rebuttal_draft, created_at) VALUES (?, 'hi', 'neutral', 'none', '', ?)", (c, recent))
    stamp("INSERT INTO audit_trail (lead_id, org_id, actor, action, created_at) VALUES (?, ?, 'u', 'STAGE_UPDATED', ?)", (d, ORG, recent))
    assert chase.to_chase(ORG, TODAY) == []


def test_an_automatic_re_check_does_not_count_as_contact():
    a = lead("Rechecked", "proposal_sent", 8)
    stamp("INSERT INTO audit_trail (lead_id, org_id, actor, action, created_at) VALUES (?, ?, 'system', 'AUDIT_COMPLETED', ?)", (a, ORG, "2026-11-10 02:00:00"))
    assert len(chase.to_chase(ORG, TODAY)) == 1


def test_the_closest_to_a_decision_comes_first_then_the_quietest():
    lead("Outreach old", "sequence_active", 20)
    lead("Proposal", "proposal_sent", 4)
    lead("Meeting", "meeting_booked", 9)
    lead("Proposal older", "proposal_sent", 10)
    assert [c["company"] for c in chase.to_chase(ORG, TODAY)] == ["Proposal older", "Proposal", "Meeting", "Outreach old"]


def test_workspaces_are_separate_and_the_api_and_today_use_it(client, make_key):
    lead("Mine", "proposal_sent", 60, org=ORG)
    lead("Theirs", "proposal_sent", 60, org="org_chase_other")
    h = make_key("growth_lead", ORG)
    assert client.get("/api/chase").status_code == 401
    body = client.get("/api/chase", headers=h).json()
    assert [c["company"] for c in body["items"]] == ["Mine"] and body["quiet_after_days"]["proposal_sent"] == 3
    today = client.get("/api/today/summary", headers=h).json()
    assert today["kpis"]["clients_to_chase"] == 1
    assert any("1 client to chase: Mine" in f["title"] for f in today["focus"])
