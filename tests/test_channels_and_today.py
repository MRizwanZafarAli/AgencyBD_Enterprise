"""Channels control centre and the Today summary: your own logs, validated, tenant-scoped, and no automation of third-party sites."""

from datetime import date, datetime, timedelta, timezone

import pytest

from workflows import channels as ch

ORG = "org_ch"
TODAY = date(2026, 10, 28)                                  # a Wednesday
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def test_the_registry_states_the_rules_and_covers_the_main_sites():
    assert {"linkedin", "fiverr", "upwork", "freelancer", "peopleperhour", "contra", "toptal", "guru", "other"} <= set(ch.PLATFORMS)
    fiverr = " ".join(ch.PLATFORMS["fiverr"]["rules"]).lower()
    assert "never logs in" in fiverr and "fake being online" in fiverr and "password" in fiverr
    assert "never logs in" in " ".join(ch.PLATFORMS["linkedin"]["rules"]).lower()
    assert ch.PLATFORMS["linkedin"]["limits"]["note_chars"] == 300


def test_no_endpoint_accepts_credentials_or_acts_on_a_third_party_site():
    from api import app
    for path, ops in app.openapi()["paths"].items():
        if path.startswith("/api/channels"):
            assert not any(w in path.lower() for w in ("login", "password", "credential", "refresh", "autosend", "auto_send"))
    import inspect
    src = inspect.getsource(ch)
    assert "requests." not in src and "SafeFetcher" not in src and "urlopen" not in src      # the module cannot reach those sites


def test_permissions_and_tenant_scoping(client, make_key):
    a, other, viewer = make_key("growth_lead", ORG), make_key("growth_lead", "org_ch_other"), make_key("auditor", ORG)
    body = {"type": "link", "data": {"title": "My Fiverr gigs", "url": "https://www.fiverr.com/me"}}
    assert client.post("/api/channels/fiverr/records", json=body).status_code == 401
    assert client.post("/api/channels/fiverr/records", headers=viewer, json=body).status_code == 403          # read-only roles cannot write
    rec = client.post("/api/channels/fiverr/records", headers=a, json=body).json()
    assert client.get("/api/channels/fiverr/records?type=link", headers=viewer).json()["records"][0]["title"] == "My Fiverr gigs"
    assert client.get("/api/channels/fiverr/records?type=link", headers=other).json()["records"] == []
    assert client.patch(f"/api/channels/fiverr/records/{rec['id']}", headers=other, json={"data": {"title": "x"}}).status_code == 404
    assert client.delete(f"/api/channels/fiverr/records/{rec['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/channels/fiverr/records/{rec['id']}", headers=a).status_code == 200
    assert client.get("/api/channels/notasite/records", headers=a).status_code == 422


@pytest.mark.parametrize("rtype,data", [("link", {"title": "x", "url": "javascript:alert(1)"}), ("link", {"title": "", "url": "https://a.com"}), ("pipeline", {"title": "t", "status": "bogus"}),
                                         ("pipeline", {"title": "t", "next_followup": "tomorrow"}), ("pipeline", {"title": "t", "value": -5}), ("activity", {"kind": "hack", "qty": 1, "day": "2026-10-28"}),
                                         ("message", {"received_at": "2026-10-28T10:00:00Z", "replied_at": "2026-10-28T09:00:00Z"}), ("setting", {"start": "17:00", "end": "09:00"}), ("template", {"name": "n", "body": "x" * 5000}),
                                         ("nonsense", {})])
def test_bad_records_are_rejected(client, make_key, rtype, data):
    assert client.post("/api/channels/upwork/records", headers=make_key("growth_lead", ORG), json={"type": rtype, "data": data}).status_code == 422


def test_routines_start_with_defaults_and_completion_is_idempotent_with_a_streak():
    routines = ch.list_records(ORG, "linkedin", "routine")
    assert len(routines) == len(ch.PLATFORMS["linkedin"]["routine"]) and len(ch.list_records(ORG, "linkedin", "routine")) == len(routines)       # seeded once
    for day in (TODAY - timedelta(days=1), TODAY):
        for r in routines:
            ch.add_record(ORG, "linkedin", "done", {"routine_id": r["id"], "day": day.isoformat()})
            ch.add_record(ORG, "linkedin", "done", {"routine_id": r["id"], "day": day.isoformat()})            # twice: still one record
    s = ch.summary(ORG, "linkedin", TODAY, NOW)["routine"]
    assert s == {"total": len(routines), "done_today": len(routines), "streak_days": 2}
    assert len(ch.list_records(ORG, "linkedin", "done")) == 2 * len(routines)
    assert ch.summary(ORG, "linkedin", TODAY + timedelta(days=3), NOW)["routine"]["streak_days"] == 0           # a missed day breaks it


def test_pipeline_followups_win_rate_and_values_come_only_from_entries():
    ch.add_record(ORG, "upwork", "pipeline", {"title": "React dashboard", "status": "applied", "next_followup": "2026-10-27", "value": 3000})
    ch.add_record(ORG, "upwork", "pipeline", {"title": "API work", "status": "interview", "next_followup": "2026-10-30"})
    ch.add_record(ORG, "upwork", "pipeline", {"title": "Old win", "status": "won", "value": 1200})
    ch.add_record(ORG, "upwork", "pipeline", {"title": "Old loss", "status": "lost"})
    p = ch.summary(ORG, "upwork", TODAY, NOW)["pipeline"]
    assert p["open"] == 2 and p["followups_due"] == 1 and p["due_titles"] == ["React dashboard"] and p["win_rate_percent"] == 50
    assert p["value_won"] == 1200 and p["value_open"] == 3000
    assert ch.summary("org_ch_empty", "upwork", TODAY, NOW)["pipeline"]["win_rate_percent"] is None            # nothing closed: no rate


def test_response_time_is_computed_from_logged_messages():
    base = NOW - timedelta(days=2)
    for mins in (10, 50, 600):
        ch.add_record(ORG, "fiverr", "message", {"received_at": base.isoformat(), "replied_at": (base + timedelta(minutes=mins)).isoformat()})
    ch.add_record(ORG, "fiverr", "message", {"received_at": (NOW - timedelta(hours=7)).isoformat()})            # still waiting
    ch.add_record(ORG, "fiverr", "message", {"received_at": (NOW - timedelta(days=60)).isoformat()})            # too old to count
    r = ch.summary(ORG, "fiverr", TODAY, NOW)["response"]
    assert r["messages_30d"] == 4 and r["replied"] == 3 and r["average_minutes"] == 220 and r["within_1h_pct"] == 67 and r["within_24h_pct"] == 100
    assert r["unanswered"] == 1 and r["oldest_unanswered_hours"] == 7.0


def test_weekly_activity_counts_from_monday_and_settings_are_replaced():
    for day, qty in (("2026-10-25", 9), ("2026-10-26", 3), ("2026-10-28", 4)):                                  # Sunday is last week
        ch.add_record(ORG, "linkedin", "activity", {"kind": "invite_sent", "qty": qty, "day": day})
    assert ch.summary(ORG, "linkedin", TODAY, NOW)["activity_this_week"] == {"invite_sent": 7}
    ch.add_record(ORG, "fiverr", "setting", {"work_days": [0, 1, 2], "start": "08:00", "end": "12:00", "remind_minutes": 30, "notify": True})
    ch.add_record(ORG, "fiverr", "setting", {"start": "10:00", "end": "18:00"})
    settings = ch.list_records(ORG, "fiverr", "setting")
    assert len(settings) == 1 and settings[0]["start"] == "10:00" and settings[0]["notify"] is False


def test_linkedin_links_are_plain_urls_for_your_own_browser():
    links = ch.linkedin_search_links("Acme & Sons", ["CEO", "CTO"], "Leeds")
    assert len(links) == 4 and all(l["url"].startswith("https://www.") for l in links)
    assert "Acme%20%26%20Sons" in links[0]["url"] and "site%3Alinkedin.com%2Fin" in links[2]["url"]
    with pytest.raises(ValueError):
        ch.linkedin_search_links("", [])


def test_search_url_endpoint(client, make_key):
    h = make_key("auditor", ORG)
    assert client.get("/api/channels/upwork/search_url?q=react native", headers=h).json()["url"] == "https://www.upwork.com/nx/search/jobs/?q=react%20native"
    assert client.get("/api/channels/toptal/search_url?q=x", headers=h).status_code == 422


def test_today_summary_counts_this_week_against_last_and_picks_a_focus(client, make_key):
    from database.db import get_db
    from database.models import LeadRepository
    from workflows.inbox import WorkItemRepository
    h = make_key("auditor", "org_td")
    for i in range(3):
        LeadRepository.create_or_get_lead(f"Co{i}", f"co{i}.example", org_id="org_td")
    with get_db() as db:
        db.execute("UPDATE leads SET created_at = datetime('now', '-10 days') WHERE company_name = 'Co0' AND org_id = 'org_td'")
        db.commit()
    WorkItemRepository.add("org_td", "find_contact", "Find a decision maker at Co1", "d", "lead", 1, 80, "k1")
    WorkItemRepository.add("org_td", "new_cve", "New vulnerability match for Co2: CVE-1", "d", "lead", 2, 90, "k2")
    ch.add_record("org_td", "linkedin", "pipeline", {"title": "Acme", "status": "applied", "next_followup": "2000-01-01"})
    out = client.get("/api/today/summary", headers=h).json()
    assert out["kpis"]["new_leads"] == {"now": 2, "before": 1} and out["kpis"]["open_tasks"] == 2
    titles = [f["title"] for f in out["focus"]]
    assert len(titles) == 3 and titles[0].startswith("New vulnerability match") and any("follow-up" in t for t in titles)
    assert any(a["what"] == "Added a lead" for a in out["activity"])
    assert any(c["platform"] == "linkedin" and c["followups_due"] == 1 for c in out["channels"])
    other = client.get("/api/today/summary", headers=make_key("auditor", "org_td_other")).json()
    assert other["kpis"]["new_leads"]["now"] == 0 and other["activity"] == [] and not any("Co" in f["title"] for f in other["focus"])
    assert client.get("/api/today/summary").status_code == 401


def test_every_platform_lists_public_pages_on_its_own_site_and_features():
    from urllib.parse import urlparse
    from workflows.channels import PLATFORMS
    for pid, p in PLATFORMS.items():
        assert p["features"], pid
        for page in p["pages"]:
            host = urlparse(page["url"]).hostname
            assert page["url"].startswith("https://") and host.split(".")[-2:] == urlparse(p["home"]).hostname.split(".")[-2:], (pid, page)
        for f in p["features"]:
            assert f["title"] and f["text"] and f["tip"]


def _lead(org, name="Acme Dental", domain="acmedental.example"):
    from database.models import LeadRepository
    return LeadRepository.create_or_get_lead(company_name=name, domain=domain, org_id=org)["id"]


def test_client_notes_tasks_and_followups(client, make_key):
    a, other, viewer = make_key("growth_lead", "org_cn"), make_key("growth_lead", "org_cn_other"), make_key("auditor", "org_cn")
    lead = _lead("org_cn")
    assert client.post(f"/api/clients/{lead}/notes", headers=viewer, json={"body": "x"}).status_code == 403
    assert client.post(f"/api/clients/{lead}/notes", headers=other, json={"body": "x"}).status_code == 404            # another tenant's client
    note = client.post(f"/api/clients/{lead}/notes", headers=a, json={"kind": "note", "body": "Spoke to the owner; wants a quote."}).json()
    task = client.post(f"/api/clients/{lead}/notes", headers=a, json={"kind": "task", "body": "Send the quote", "due_date": "2020-01-01"}).json()
    assert client.post(f"/api/clients/{lead}/notes", headers=a, json={"kind": "note", "body": "x", "due_date": "2020-01-01"}).status_code == 422
    assert client.post(f"/api/clients/{lead}/notes", headers=a, json={"kind": "task", "body": "x", "due_date": "not a date"}).status_code == 422
    assert client.post(f"/api/clients/{lead}/notes", headers=a, json={"kind": "note", "body": "   "}).status_code == 422
    assert client.get(f"/api/clients/{lead}/notes", headers=other).status_code == 404
    got = client.get(f"/api/clients/{lead}/notes", headers=viewer).json()
    assert [i["id"] for i in got["items"]] == [task["id"], note["id"]]
    due = client.get("/api/followups", headers=a).json()["due"]
    assert [d["body"] for d in due] == ["Send the quote"] and due[0]["company"] == "Acme Dental"
    assert client.get("/api/followups", headers=other).json() == {"due": [], "upcoming": []}
    summary = client.get("/api/today/summary", headers=a).json()
    assert summary["kpis"]["client_followups_due"] == 1 and any("follow-up" in f["title"] for f in summary["focus"])
    assert client.patch(f"/api/clients/{lead}/notes/{note['id']}", headers=a, json={"done": True}).status_code == 422     # notes are not tasks
    done = client.patch(f"/api/clients/{lead}/notes/{task['id']}", headers=a, json={"done": True}).json()
    assert done["done_at"] and client.get("/api/followups", headers=a).json()["due"] == []
    assert client.patch(f"/api/clients/{lead}/notes/{task['id']}", headers=other, json={"done": False}).status_code == 404
    assert client.delete(f"/api/clients/{lead}/notes/{note['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/clients/{lead}/notes/{note['id']}", headers=a).status_code == 200


# ---------------------------------------------------------------- quick log (plain sentence -> draft)

QL = date(2026, 10, 28)                                     # a Wednesday


@pytest.mark.parametrize("text,platform,status,value,due,title", [
    ("applied to react dashboard on upwork $1200 follow up friday", "upwork", "applied", 1200.0, "2026-10-30", "react dashboard"),
    ("saved wordpress fix on freelancer.com", "freelancer", "saved", None, None, "wordpress fix"),
    ("won seo audit linkedin 1.5k in 3 days", "linkedin", "won", 1500.0, "2026-10-31", "seo audit"),
    ("sent proposal for api project upwrok nov 5", "upwork", "applied", None, "2026-11-05", "api project"),      # a typo is understood and said so
    ("fivrr buyer replied about logo design tomorrow", "fiverr", "replied", None, "2026-10-29", "logo design"),
    ("applied web design bid on guru $300", "guru", "applied", 300.0, None, "web design"),
])
def test_quick_log_understands_a_sentence(text, platform, status, value, due, title):
    from workflows.quicklog import parse
    out = parse(text, QL)
    assert out["platform"] == platform and out["needs"] == []
    r = out["record"]
    assert (r["status"], r["value"], r["next_followup"], r["title"]) == (status, value, due, title)
    ch.clean("pipeline", r)                                  # whatever it proposes is valid to save


def test_quick_log_never_guesses_a_missing_platform_or_title():
    from workflows.quicklog import parse
    assert parse("react dashboard $500", QL)["needs"] == ["platform"]
    assert "title" in parse("applied upwork", QL)["needs"]
    assert parse("applied upwork react $500", QL)["notes"] == []
    assert parse("sent proposal upwrok x", QL)["notes"] == ["Read 'upwrok' as Upwork."]


@pytest.mark.parametrize("text,expected", [("call on 2026-12-01", "2026-12-01"), ("next monday", "2026-11-02"), ("5th jan", "2027-01-05"), ("friday", "2026-10-30"),
                                           ("wednesday", "2026-11-04"), ("in 2 weeks", "2026-11-11"), ("nothing here", None), ("31 feb", None)])
def test_date_phrases(text, expected):
    from workflows.quicklog import parse_date_phrase
    found = parse_date_phrase(text, QL)
    assert (found[0] if found else None) == expected


def test_parse_endpoints_need_a_key_and_save_nothing(client, make_key):
    k = make_key("growth_lead", "org_ql")
    assert client.post("/api/channels/parse", json={"text": "x"}).status_code == 401
    out = client.post("/api/channels/parse", headers=k, json={"text": "applied to logo job on fiverr $200"}).json()
    assert out["platform"] == "fiverr" and out["record"]["value"] == 200.0
    assert client.get("/api/channels/fiverr/records?type=pipeline", headers=k).json()["records"] == []
    assert client.get("/api/channels/parse_date?text=tomorrow", headers=k).json()["matched"] == "tomorrow"


# ---------------------------------------------------------------- funnel, cost, pacing, experiments

def test_funnel_and_cost_per_win_come_only_from_what_was_logged():
    org = "org_funnel"
    assert ch.summary(org, "upwork", TODAY, NOW)["funnel"]["reply_rate_percent"] is None            # nothing logged: no percentage
    for title, status, cost in [("a", "applied", 2.4), ("b", "replied", 2.4), ("c", "interview", 2.4), ("d", "won", 4.8), ("e", "saved", 9.0)]:
        ch.add_record(org, "upwork", "pipeline", {"title": title, "status": status, "cost": cost})
    f = ch.summary(org, "upwork", TODAY, NOW)["funnel"]
    assert f["applications"] == 4 and f["reply_rate_percent"] == 75 and f["win_rate_of_applied_percent"] == 25       # a saved item is not an application
    assert f["cost_total"] == 12.0 and f["cost_per_win"] == 12.0 and f["cost_per_reply"] == 4.0
    with pytest.raises(ValueError):
        ch.clean("pipeline", {"title": "x", "cost": -1})


def test_linkedin_invite_pacing_is_a_rolling_seven_days_against_your_own_limit():
    org = "org_pace"
    for day, qty in [("2026-10-21", 30), ("2026-10-22", 20), ("2026-10-27", 25), ("2026-10-28", 10)]:       # the 21st is 7 days back: outside the window
        ch.add_record(org, "linkedin", "activity", {"kind": "invite_sent", "qty": qty, "day": day})
    p = ch.summary(org, "linkedin", TODAY, NOW)["pacing"]
    assert p["invites_7d"] == 55 and p["today"] == 10 and p["limit"] == 80 and p["remaining"] == 25 and not p["over"]
    ch.add_record(org, "linkedin", "setting", {"weekly_invite_limit": 50})
    p = ch.summary(org, "linkedin", TODAY, NOW)["pacing"]
    assert p["over"] and p["remaining"] == 0
    assert ch.summary(org, "fiverr", TODAY, NOW)["pacing"] is None
    with pytest.raises(ValueError):
        ch.clean("setting", {"weekly_invite_limit": 5000})


def test_experiments_come_due_after_thirty_days_unless_marked_done():
    org = "org_exp"
    rec = ch.add_record(org, "fiverr", "experiment", {"what": "New gig thumbnail", "changed_on": "2026-09-20"})
    assert rec["review_on"] == "2026-10-20"
    assert [e["what"] for e in ch.summary(org, "fiverr", TODAY, NOW)["experiments_due"]] == ["New gig thumbnail"]
    ch.update_record(org, "fiverr", rec["id"], {"done": True, "result": "CTR up"})
    assert ch.summary(org, "fiverr", TODAY, NOW)["experiments_due"] == []
    with pytest.raises(ValueError):
        ch.clean("experiment", {"what": "x", "changed_on": "2026-09-20", "review_on": "2026-09-01"})


def test_suggestions_can_be_limited_to_one_kind_and_tolerate_typos(client, make_key):
    k = make_key("growth_lead", "org_sg")
    def sg(q, kinds):
        return client.get(f"/api/search/suggest?q={q}&kinds={kinds}", headers=k).json()["suggestions"]
    assert sg("new y", "city")[0]["label"] == "new york" and all(s["type"] == "city" for s in sg("l", "city"))
    assert sg("dentst", "business")[0]["label"] == "dentist"
    assert {s["type"] for s in sg("", "skill")} == {"skill"}
    assert all(s["type"] != "city" for s in sg("react", "skill,business"))
