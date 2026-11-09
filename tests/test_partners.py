"""Referral partners: you type everything; the tracker only remembers, counts and reminds."""

from datetime import date, timedelta

import pytest

from workflows import partners as pt

ORG = "org_pt"
TODAY = date(2026, 11, 10)


def add(**k):
    base = {"name": "Brightside Marketing", "kind": "agency"}
    base.update(k)
    return pt.create(ORG, base)


def test_a_partner_is_saved_with_only_what_you_typed():
    p = add(contact_name="Leila", contact_where="leila@brightside.example", website="https://brightside.example", offer="White-label builds, 10% on the first project")
    assert p["stage"] == "to_contact" and p["referrals_in"] == 0 and p["attention"] is None and p["last_contact_at"] is None
    assert p["offer"].startswith("White-label") and p["contact_where"] == "leila@brightside.example"


@pytest.mark.parametrize("data,word", [({"name": " "}, "Name is required"), ({"name": "x", "kind": "wizard"}, "Unknown kind"), ({"name": "x", "stage": "won"}, "Unknown stage"),
                                       ({"name": "x", "website": "not a site"}, "example.com"), ({"name": "x", "next_step_date": "soon"}, "2026-11-20"), ({"name": "x" * 101}, "too long")])
def test_mistakes_are_explained(data, word):
    with pytest.raises(ValueError, match=word):
        pt.create(ORG, data)


def test_contacting_a_new_partner_moves_it_on_and_a_referral_makes_it_active():
    p = add()
    p = pt.add_event(ORG, p["id"], "contacted", "Sent a short intro by email")
    assert p["stage"] == "contacted" and p["last_contact_at"]
    p = pt.add_event(ORG, p["id"], "referral_out", "Sent them a client who needed a logo")
    assert p["stage"] == "active_partner" and p["referrals_out"] == 1
    p = pt.add_event(ORG, p["id"], "referral_in", "A dental clinic from them")
    assert p["referrals_in"] == 1 and p["referrals_out"] == 1
    assert [e["kind"] for e in pt.events(ORG, p["id"])] == ["referral_in", "referral_out", "contacted"]


def test_notes_need_text_and_unknown_kinds_are_refused():
    p = add()
    with pytest.raises(ValueError, match="Note is required"):
        pt.add_event(ORG, p["id"], "note", " ")
    with pytest.raises(ValueError, match="kind must be"):
        pt.add_event(ORG, p["id"], "spam", "x")
    assert pt.add_event(ORG, 9999, "contacted", None) is None


def test_a_due_next_step_and_quiet_partners_are_flagged_but_new_and_declined_ones_are_not():
    ago = lambda d: (TODAY - timedelta(days=d)).isoformat() + " 10:00:00"
    from database.db import get_db
    due = add(name="Due", stage="talking", next_step_date=(TODAY - timedelta(days=1)).isoformat())
    quiet = add(name="Quiet", stage="contacted")
    fresh = add(name="Fresh", stage="contacted")
    old_active = add(name="Old", stage="active_partner")
    new, declined = add(name="New"), add(name="Declined", stage="not_a_fit", next_step_date=TODAY.isoformat())
    with get_db() as db:
        for pid, days in ((quiet["id"], 9), (fresh["id"], 2), (old_active["id"], 50), (due["id"], 1)):
            db.execute("UPDATE partners SET last_contact_at = ? WHERE id = ?", (ago(days), pid))
        db.commit()
    got = {p["name"]: p["attention"] for p in pt.list_partners(ORG, TODAY)["partners"]}
    assert got["Due"] == "Your next step is due." and "No reply for 9 days. Follow up once, then leave it." == got["Quiet"] and got["Old"] == "No contact for 50 days."
    assert got["Fresh"] is None and got["New"] is None and got["Declined"] is None


def test_contacting_clears_a_due_step_and_update_keeps_what_you_did_not_change():
    p = add(stage="talking", next_step_date="2026-01-01", notes="Met at the chamber event")
    p = pt.add_event(ORG, p["id"], "contacted", None)
    assert p["next_step_date"] is None
    p = pt.update(ORG, p["id"], {"offer": "Referral fee on first project"})
    assert p["offer"] == "Referral fee on first project" and p["notes"] == "Met at the chamber event" and p["stage"] == "talking"
    assert pt.update(ORG, 9999, {"name": "x"}) is None


def test_summary_counts_and_deleting_removes_the_history():
    a, b = add(name="A"), add(name="B")
    pt.add_event(ORG, a["id"], "referral_in", None)
    pt.add_event(ORG, a["id"], "referral_in", None)
    pt.add_event(ORG, b["id"], "referral_out", None)
    s = pt.list_partners(ORG, TODAY)["summary"]
    assert s["total"] == 2 and s["active"] == 2 and s["referrals_in"] == 2 and s["referrals_out"] == 1
    assert pt.delete(ORG, a["id"]) and pt.events(ORG, a["id"]) is None and not pt.delete(ORG, a["id"])


def test_the_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(pt, "LIMIT", 2)
    add(name="1"), add(name="2")
    with pytest.raises(ValueError, match="up to 2"):
        add(name="3")


def test_api_permissions_tenancy_and_today(client, make_key):
    mine, other, reader = make_key("growth_lead", ORG), make_key("growth_lead", "org_pt_other"), make_key("auditor", ORG)
    assert client.get("/api/partners").status_code == 401
    made = client.post("/api/partners", headers=mine, json={"name": "Plan9 Studio", "kind": "agency", "stage": "talking", "next_step_date": "2020-01-01"})
    assert made.status_code == 200
    pid = made.json()["id"]
    assert client.post("/api/partners", headers=reader, json={"name": "x"}).status_code == 403
    assert client.post("/api/partners", headers=mine, json={"name": "x", "kind": "wizard"}).status_code == 422
    assert client.get("/api/partners", headers=reader).json()["summary"]["total"] == 1
    assert client.get("/api/partners", headers=other).json()["partners"] == []
    for call in (lambda: client.put(f"/api/partners/{pid}", headers=other, json={"name": "y"}), lambda: client.delete(f"/api/partners/{pid}", headers=other),
                 lambda: client.post(f"/api/partners/{pid}/events", headers=other, json={"kind": "note", "body": "x"}), lambda: client.get(f"/api/partners/{pid}/events", headers=other)):
        assert call().status_code == 404
    assert client.post(f"/api/partners/{pid}/events", headers=mine, json={"kind": "note", "body": "Spoke on the phone"}).status_code == 200
    assert client.get(f"/api/partners/{pid}/events", headers=mine).json()["events"][0]["body"] == "Spoke on the phone"
    focus = client.get("/api/today/summary", headers=mine).json()["focus"]
    assert any(f["title"] == "1 partner needs a nudge: Plan9 Studio" for f in focus)
    assert client.delete(f"/api/partners/{pid}", headers=mine).status_code == 200


def test_the_limit_holds_when_many_requests_arrive_at_the_same_moment(monkeypatch):
    import threading
    monkeypatch.setattr(pt, "LIMIT", 20)
    results = []

    def go(i):
        try:
            pt.create(ORG, {"name": f"P{i}"}); results.append("ok")
        except ValueError:
            results.append("refused")
    threads = [threading.Thread(target=go, args=(i,)) for i in range(60)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert results.count("ok") == 20 and results.count("refused") == 40 and pt.list_partners(ORG)["summary"]["total"] == 20
