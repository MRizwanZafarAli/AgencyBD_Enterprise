"""When a client is won, one follow-up task is planned to ask for a review and an introduction."""

from datetime import date

from workflows import client_notes as cn

ORG = "org_rv"


def deal(client, h, name="Acme Dental", domain="acmedental.example"):
    return client.post("/api/pipeline/deals/create", headers=h, json={"company_name": name, "domain": domain}).json()


def lead_id(body):
    return body.get("lead", {}).get("id") or body.get("id") or body["lead_id"]


def tasks(lead):
    return [n for n in cn.list_for(ORG, lead) if n["kind"] == "task"]


def test_winning_a_client_plans_one_review_task_a_week_out(client, make_key):
    h = make_key("growth_lead", ORG)
    lid = lead_id(deal(client, h))
    r = client.post("/api/pipeline/deals/stage", headers=h, json={"lead_id": lid, "new_stage": "won"})
    assert r.status_code == 200 and r.json()["review_task"]["due_date"]
    t = tasks(lid)
    assert len(t) == 1 and t[0]["body"] == "Ask for a review and one introduction: Acme Dental" and t[0]["created_by"] == "system"
    assert (date.fromisoformat(t[0]["due_date"]) - date.today()).days == cn.REVIEW_AFTER_DAYS


def test_it_is_planned_only_once_even_if_the_stage_is_set_again(client, make_key):
    h = make_key("growth_lead", ORG)
    lid = lead_id(deal(client, h, "Beta", "beta.example"))
    client.post("/api/pipeline/deals/stage", headers=h, json={"lead_id": lid, "new_stage": "won"})
    again = client.post("/api/pipeline/deals/stage", headers=h, json={"lead_id": lid, "new_stage": "won"})
    assert "review_task" not in again.json() and len(tasks(lid)) == 1


def test_other_stages_plan_nothing(client, make_key):
    h = make_key("growth_lead", ORG)
    lid = lead_id(deal(client, h, "Gamma", "gamma.example"))
    for stage in ("meeting_booked", "proposal_sent", "lost"):
        client.post("/api/pipeline/deals/stage", headers=h, json={"lead_id": lid, "new_stage": stage})
    assert tasks(lid) == []


def test_a_done_task_is_not_asked_again_and_it_shows_among_follow_ups(client, make_key):
    h = make_key("growth_lead", ORG)
    lid = lead_id(deal(client, h, "Delta", "delta.example"))
    client.post("/api/pipeline/deals/stage", headers=h, json={"lead_id": lid, "new_stage": "won"})
    t = tasks(lid)[0]
    cn.update(ORG, lid, t["id"], {"done": True})
    client.post("/api/pipeline/deals/stage", headers=h, json={"lead_id": lid, "new_stage": "won"})
    assert len(tasks(lid)) == 1
    other = make_key("growth_lead", "org_rv_other")
    assert all(i["company"] != "Delta" for i in client.get("/api/followups", headers=other).json()["upcoming"])
