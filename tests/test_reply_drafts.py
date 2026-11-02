"""Reply drafts for client messages: built only from what is set up; nothing invented."""

import pytest

from alertdesk import engine, reply
from config.settings import settings
from intel.services import ServiceCatalog

ORG = "org_reply"


@pytest.fixture(autouse=True)
def agency(monkeypatch):
    monkeypatch.setattr(settings.agency, "name", "Future Builders")
    monkeypatch.setattr(settings.agency, "founder_name", "Rizwan Zafar")
    monkeypatch.setattr(settings.agency, "booking_link", "")
    monkeypatch.setattr(settings.agency, "case_study_metric", "")


def msg(text, sender="Amina K."):
    return engine.ingest(ORG, "fiverr", sender, text)["id"]


def by_label(out):
    return {d["label"]: d["text"] for d in out["drafts"]}


def test_a_question_about_a_site_gets_a_greeting_a_question_and_a_signature():
    out = reply.drafts(ORG, msg("I need a new website for my clinic. Can you start this week?"))
    assert out["service"] == "Digital presence build (site + Google profile)" and "start" in out["intents"]
    quick = by_label(out)["Ask first"]
    assert quick.startswith("Hi Amina,") and "link to your current site" in quick and quick.rstrip().endswith("Future Builders") and "Rizwan Zafar" in quick


def test_without_a_booking_link_it_asks_for_times_and_says_what_to_set_up():
    out = reply.drafts(ORG, msg("Can we talk on a call about my store?"))
    assert "Which two times suit you" in by_label(out)["Move to a call"] and "http" not in by_label(out)["Move to a call"]
    assert any("booking link" in n for n in out["needs"])


def test_with_a_booking_link_the_call_draft_uses_it(monkeypatch):
    monkeypatch.setattr(settings.agency, "booking_link", "https://cal.com/future/intro")
    out = reply.drafts(ORG, msg("Let's discuss this on a call"))
    assert "https://cal.com/future/intro" in by_label(out)["Move to a call"] and not any("booking link" in n for n in out["needs"])


def test_a_price_is_stated_only_if_you_set_one_for_that_service():
    out = reply.drafts(ORG, msg("How much would an SEO audit cost?"))
    assert "Give the price" not in by_label(out) and any("Your price for SEO optimization" in n for n in out["needs"])
    assert "budget" in by_label(out)["Ask first"]                       # it asks instead of guessing
    ServiceCatalog.upsert(ORG, "seo_optimization", "SEO optimization", "Audit and fix.", price_band="$300 to $500")
    out = reply.drafts(ORG, msg("How much would an SEO audit cost? ", sender="Dan"))
    price = by_label(out)["Give the price"]
    assert "$300 to $500" in price and "confirm it in writing" in price and "Recent result" not in price


def test_a_result_is_quoted_only_when_set(monkeypatch):
    ServiceCatalog.upsert(ORG, "security_hardening", "Security hardening", "Fix.", price_band="EUR 250")
    mid = msg("What's the price to fix our SSL certificate?")
    assert "Recent result" not in by_label(reply.drafts(ORG, mid))["Give the price"]
    monkeypatch.setattr(settings.agency, "case_study_metric", "Cut load time from 4.1 s to 1.3 s")
    assert "A recent result: Cut load time from 4.1 s to 1.3 s" in by_label(reply.drafts(ORG, mid))["Give the price"]


def test_a_vague_message_still_gets_safe_drafts_and_odd_names_are_not_used():
    out = reply.drafts(ORG, msg("hello", sender="New client"))
    assert out["intents"] == [] and out["service"] is None
    assert by_label(out)["Ask first"].startswith("Hello,") and "link to your current site" in by_label(out)["Ask first"]
    assert reply.drafts(ORG, msg("hi there", sender="fiverr_user_9921x"))["drafts"][0]["text"].startswith("Hi fiverr_user_9921x,") is False


def test_nothing_is_promised_that_was_not_set_up():
    text = " ".join(d["text"] for d in reply.drafts(ORG, msg("How much and how long for a new website? Are you available?"))["drafts"]).lower()
    for promise in ("years of experience", "guarantee", "100%", "within 24 hours", "best in", "award"):
        assert promise not in text


def test_the_api_is_tenant_scoped(client, make_key):
    mid = msg("Need help with a slow website")
    mine, other = make_key("growth_lead", ORG), make_key("growth_lead", "org_reply_other")
    assert client.get(f"/api/alerts/messages/{mid}/replies").status_code == 401
    ok = client.get(f"/api/alerts/messages/{mid}/replies", headers=mine)
    assert ok.status_code == 200 and ok.json()["service"] == "Performance engineering" and len(ok.json()["drafts"]) >= 2
    assert client.get(f"/api/alerts/messages/{mid}/replies", headers=other).status_code == 404
    assert client.get("/api/alerts/messages/99999/replies", headers=mine).status_code == 404
