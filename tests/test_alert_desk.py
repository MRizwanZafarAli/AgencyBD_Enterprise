"""Alert Desk: client message detection from notification emails, the escalation ladder (Telegram, WhatsApp, phone call), schedule, acknowledgement,
failure handling, and the promise that no secret ever leaves the server."""

import json
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime

import pytest

from alertdesk import channels, engine, mailwatch
from alertdesk.parsers import parse_email

ORG = "org_ad"
T0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)          # a Monday, 15:00 in Karachi
KARACHI_NIGHT = datetime(2026, 11, 2, 18, 30, 0, tzinfo=timezone.utc)   # 23:30 in Karachi


@pytest.fixture
def sent(monkeypatch):
    """Replaces every channel with a recorder, so no test touches a real service."""
    calls = []
    outcome = {"telegram": (True, "ok"), "ntfy": (True, "ok"), "whatsapp": (True, "ok"), "call": (True, "ok")}

    def fake(name):
        def _f(cfg, text, *a, **k):
            calls.append((name, text))
            return outcome[name]
        return _f
    monkeypatch.setattr(channels, "send_telegram", fake("telegram"))
    monkeypatch.setattr(channels, "send_ntfy", fake("ntfy"))
    monkeypatch.setattr(channels, "send_whatsapp", fake("whatsapp"))
    monkeypatch.setattr(channels, "place_call", fake("call"))
    monkeypatch.setattr(channels, "telegram_configured", lambda cfg: False)       # no acknowledgement polling unless a test asks for it
    calls_outcome = type("R", (), {"calls": calls, "outcome": outcome})
    return calls_outcome


def on(**over):
    cfg = {"enabled": True, "steps": [{"after_minutes": 0, "channel": "telegram"}, {"after_minutes": 5, "channel": "whatsapp"}, {"after_minutes": 15, "channel": "call"}]}
    cfg.update(over)
    return engine.save_settings(ORG, cfg)


def msg(when=T0, sender="Amina K.", platform="fiverr", text="I need a website for my clinic. Can you start this week?", ref=None):
    return engine.ingest(ORG, platform, sender, text, received_at=when, source_ref=ref or f"t:{when}:{sender}")


def kinds(r):
    return [c[0] for c in r.calls]


# ---------------------------------------------------------------- reading notification emails

@pytest.mark.parametrize("frm,subject,alert,platform,sender", [
    ("Fiverr <noreply@e.fiverr.com>", "Amina K. sent you a message", True, "fiverr", "Amina K."),
    ("Upwork <donotreply@upwork.com>", "New message from Daniel", True, "upwork", "Daniel"),
    ("LinkedIn <messages-noreply@linkedin.com>", "Sara Lopez messaged you", True, "linkedin", "Sara Lopez"),
    ("Upwork <donotreply@upwork.com>", "You have a new invitation to interview", True, "upwork", "Upwork"),
    ("Upwork <donotreply@upwork.com>", "Jobs matching your skills this week", False, "upwork", None),
    ("Fiverr <noreply@e.fiverr.com>", "Your weekly digest: tips for more orders", False, "fiverr", None),
    ("Fiverr <noreply@e.fiverr.com>", "New sign-in to your account", False, "fiverr", None),
    ("Mum <mum@gmail.com>", "New message", None, None, None),                      # not a watched platform: never touched
])
def test_which_emails_wake_you(frm, subject, alert, platform, sender):
    p = parse_email(frm, subject, "Hi, I need a quote.\nUnsubscribe here")
    if alert is None:
        assert p is None
        return
    assert p.alert is alert and p.platform == platform
    if sender:
        assert p.sender == sender


def test_the_preview_drops_links_and_the_footer_and_finds_the_conversation_link():
    html = ('<p>Hi, can you do this by Friday?</p><a href="https://www.fiverr.com/inbox/amina">Reply</a><a href="https://www.fiverr.com/help">Help</a>'
            '<p>You received this email because you have an account. Unsubscribe</p>')
    p = parse_email("Fiverr <noreply@e.fiverr.com>", "Amina sent you a message", "", html)
    assert p.preview == "Hi, can you do this by Friday? Reply Help" or p.preview.startswith("Hi, can you do this by Friday?")
    assert "Unsubscribe" not in p.preview and "http" not in p.preview
    assert p.url == "https://www.fiverr.com/inbox/amina"


def test_extra_senders_you_add_are_watched():
    assert parse_email("Client <a@acme-client.com>", "New message", "hi") is None
    p = parse_email("Client <a@acme-client.com>", "New message", "hi", extra_senders=["acme-client.com"])
    assert p and p.platform == "other" and p.alert


# ---------------------------------------------------------------- settings

def test_settings_are_validated_with_sentences_a_person_can_act_on():
    bad = [({"timezone": "Mars/Base"}, "Time zone"), ({"steps": []}, "between 1 and"), ({"steps": [{"after_minutes": 5, "channel": "pigeon"}]}, "channel"),
           ({"steps": [{"after_minutes": 9999, "channel": "call"}]}, "24 hours"), ({"channels": {"call": {"to": "03001234567"}}}, "international form"),
           ({"channels": {"telegram": {"chat_id": "abc"}}}, "number"), ({"channels": {"ntfy": {"topic": "abc"}}}, "8 to 64"),
           ({"schedule": {"days": []}}, "working day"), ({"schedule": {"start": "9am"}}, "09:00"), ({"watch": {"platforms": ["myspace"]}}, "platforms"),
           ({"channels": {"ntfy": {"server": "http://x.com"}}}, "https")]
    for data, word in bad:
        with pytest.raises(ValueError, match=word):
            engine.validate({"enabled": True, **data})
    ok = engine.validate({"steps": [{"after_minutes": 30, "channel": "call"}, {"after_minutes": 0, "channel": "whatsapp"}], "channels": {"call": {"to": "+92 340-4095953"}}})
    assert [s["after_minutes"] for s in ok["steps"]] == [0, 30] and ok["channels"]["call"]["to"] == "+923404095953"      # sorted, number normalised


def test_only_the_administrator_changes_destinations_and_nothing_secret_is_ever_returned(client, make_key, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AAH-super-secret-token-value-123456")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-secret-auth-token-0000")
    admin, lead = make_key("super_admin", ORG), make_key("growth_lead", ORG)
    assert client.get("/api/alerts/settings").status_code == 401
    assert client.put("/api/alerts/settings", headers=lead, json={"enabled": True}).status_code == 403
    assert client.post("/api/alerts/test/telegram", headers=lead).status_code == 403
    assert client.put("/api/alerts/settings", headers=admin, json={"enabled": True, "channels": {"telegram": {"chat_id": "123456"}}}).status_code == 200
    body = client.get("/api/alerts/settings", headers=lead).text
    assert "AAH-super-secret" not in body and "twilio-secret" not in body and json.loads(body)["status"]["channels_ready"]["telegram"] is True
    assert client.put("/api/alerts/settings", headers=admin, json={"timezone": "Nope"}).status_code == 422


# ---------------------------------------------------------------- the ladder

def test_the_ladder_whatsapp_then_call_in_order_and_stops_when_you_acknowledge(sent):
    on()
    m = msg()
    engine.cycle(ORG, T0, mail=False)
    assert kinds(sent) == ["telegram"] and "Amina K." in sent.calls[0][1] and "Fiverr" in sent.calls[0][1]
    engine.cycle(ORG, T0 + timedelta(minutes=4), mail=False)
    assert kinds(sent) == ["telegram"]                                              # nothing before it is due
    engine.cycle(ORG, T0 + timedelta(minutes=5), mail=False)
    assert kinds(sent) == ["telegram", "whatsapp"] and "Reminder" in sent.calls[1][1]
    engine.set_status(ORG, m["id"], "acknowledged", "test")                         # you answered
    engine.cycle(ORG, T0 + timedelta(minutes=15), mail=False)
    assert kinds(sent) == ["telegram", "whatsapp"]                                  # no call: you are on it


def test_the_call_comes_after_fifteen_minutes_with_what_the_client_wrote(sent):
    on()
    msg()
    for minute in (0, 5, 15):
        engine.cycle(ORG, T0 + timedelta(minutes=minute), mail=False)
    assert kinds(sent) == ["telegram", "whatsapp", "call"]
    speech = sent.calls[2][1]
    assert "Amina K." in speech and "Fiverr" in speech and "15 minutes ago" in speech and "website for my clinic" in speech


def test_several_calls_at_times_you_choose(sent):
    on(steps=[{"after_minutes": 0, "channel": "whatsapp"}, {"after_minutes": 15, "channel": "call"}, {"after_minutes": 30, "channel": "call"}, {"after_minutes": 60, "channel": "call"}])
    msg()
    for minute in (0, 15, 30, 45, 60, 90):
        engine.cycle(ORG, T0 + timedelta(minutes=minute), mail=False)
    assert kinds(sent) == ["whatsapp", "call", "call", "call"]                       # exactly the times configured, each once


def test_a_channel_that_is_not_set_up_is_skipped_and_the_ladder_carries_on(sent):
    on()
    sent.outcome["whatsapp"] = (False, "WhatsApp is not set up (a Cloud API token, a phone number ID and your number are needed).")
    m = msg()
    for minute in (0, 5, 15):
        engine.cycle(ORG, T0 + timedelta(minutes=minute), mail=False)
    got = {a["step_index"]: a for a in engine.list_messages(ORG)[0]["attempts"]}
    assert got[1]["status"] == "skipped" and "not set up" in got[1]["detail"] and got[2]["status"] == "sent" and kinds(sent)[-1] == "call"


def test_a_failed_send_is_retried_after_a_minute_at_most_three_times(sent):
    on(steps=[{"after_minutes": 0, "channel": "telegram"}])
    sent.outcome["telegram"] = (False, "Could not reach Telegram: ConnectionError")
    msg()
    for seconds in (0, 30, 61, 130, 200, 400, 800):
        engine.cycle(ORG, T0 + timedelta(seconds=seconds), mail=False)
    a = engine.list_messages(ORG)[0]["attempts"][0]
    assert a["status"] == "failed" and len(sent.calls) == 3                          # tried 3 times, not on every pass, and then gave up
    sent.outcome["telegram"] = (True, "ok")


def test_after_downtime_only_the_latest_due_step_is_sent_not_a_burst(sent):
    on()
    msg()
    engine.cycle(ORG, T0 + timedelta(minutes=20), mail=False)                        # the app was off: all three steps are overdue
    assert kinds(sent) == ["call"]
    got = engine.list_messages(ORG)[0]["attempts"]
    assert [a["status"] for a in got] == ["skipped", "skipped", "sent"] and "Superseded" in got[0]["detail"]


def test_disabled_and_paused_desks_say_nothing_and_resume_works(sent):
    msg()
    engine.cycle(ORG, T0, mail=False)
    assert sent.calls == []                                                          # never switched on
    on()
    engine.pause(ORG, 60, now=T0)
    engine.cycle(ORG, T0 + timedelta(minutes=10), mail=False)
    assert sent.calls == [] and engine.status(ORG, T0 + timedelta(minutes=10))["paused"] is True
    engine.pause(ORG, None)
    engine.cycle(ORG, T0 + timedelta(minutes=11), mail=False)
    assert kinds(sent) and kinds(sent)[-1] in ("whatsapp", "call", "telegram")


# ---------------------------------------------------------------- your working hours

def hours(**over):
    base = {"timezone": "Asia/Karachi", "schedule": {"days": [0, 1, 2, 3, 4], "start": "09:00", "end": "18:00", "off_hours": "hold"}}
    base.update(over)
    return base


def test_outside_working_hours_alerts_wait_until_you_are_back(sent):
    on(**hours())
    msg(KARACHI_NIGHT)                                                               # 23:30 in Karachi
    engine.cycle(ORG, KARACHI_NIGHT + timedelta(minutes=30), mail=False)
    assert sent.calls == []
    morning = datetime(2026, 11, 3, 4, 0, 0, tzinfo=timezone.utc)                    # 09:00 Karachi, Tuesday
    engine.cycle(ORG, morning, mail=False)
    assert kinds(sent) == ["telegram"]                                               # the ladder starts when your day starts
    engine.cycle(ORG, morning + timedelta(minutes=15), mail=False)
    assert kinds(sent)[-1] == "call"


def test_first_only_sends_one_gentle_alert_at_night_and_holds_the_rest(sent):
    on(**hours(schedule={"days": [0, 1, 2, 3, 4], "start": "09:00", "end": "18:00", "off_hours": "first_only"}))
    msg(KARACHI_NIGHT)
    engine.cycle(ORG, KARACHI_NIGHT, mail=False)
    assert kinds(sent) == ["telegram"]
    engine.cycle(ORG, KARACHI_NIGHT + timedelta(hours=2), mail=False)
    assert kinds(sent) == ["telegram"]


def test_weekends_are_off_when_you_say_so(sent):
    on(**hours())
    saturday = datetime(2026, 11, 7, 6, 0, 0, tzinfo=timezone.utc)                   # Saturday 11:00 Karachi
    msg(saturday)
    engine.cycle(ORG, saturday, mail=False)
    assert sent.calls == []
    monday = datetime(2026, 11, 9, 4, 0, 0, tzinfo=timezone.utc)
    engine.cycle(ORG, monday, mail=False)
    assert kinds(sent) == ["telegram"]


def test_no_phone_call_in_quiet_hours_it_waits_until_they_end(sent):
    on(quiet_hours={"enabled": True, "start": "23:00", "end": "07:00"})
    msg(KARACHI_NIGHT)                                                               # 23:30 Karachi: inside quiet hours
    for minute in (0, 5, 15, 60):
        engine.cycle(ORG, KARACHI_NIGHT + timedelta(minutes=minute), mail=False)
    assert "call" not in kinds(sent) and kinds(sent) == ["telegram", "whatsapp"]
    engine.cycle(ORG, datetime(2026, 11, 3, 2, 0, 0, tzinfo=timezone.utc), mail=False)    # 07:00 Karachi
    assert kinds(sent)[-1] == "call"


# ---------------------------------------------------------------- messages and tenants

def test_the_same_email_is_never_stored_twice_and_tenants_are_separate(client, make_key):
    a, b = make_key("growth_lead", ORG), make_key("growth_lead", "org_ad_other")
    assert engine.ingest(ORG, "fiverr", "Amina", "hi", source_ref="<m1@x>") is not None
    assert engine.ingest(ORG, "fiverr", "Amina", "hi", source_ref="<m1@x>") is None
    mine = client.get("/api/alerts/messages", headers=a).json()["messages"]
    assert len(mine) == 1 and client.get("/api/alerts/messages", headers=b).json()["messages"] == []
    assert client.post(f"/api/alerts/messages/{mine[0]['id']}/ack", headers=b).status_code == 404            # not yours
    assert client.post(f"/api/alerts/messages/{mine[0]['id']}/ack", headers=a).status_code == 200
    assert client.post(f"/api/alerts/messages/{mine[0]['id']}/ack", headers=a).status_code == 404            # already done
    assert client.get("/api/alerts/messages?status=new", headers=a).json()["messages"] == []
    assert client.get("/api/alerts/messages?status=bogus", headers=a).status_code == 422


def test_a_message_added_by_hand_runs_the_same_ladder_and_shows_on_today(client, make_key, sent):
    admin = make_key("super_admin", ORG)
    client.put("/api/alerts/settings", headers=admin, json={"enabled": True})
    r = client.post("/api/alerts/messages", headers=admin, json={"platform": "upwork", "sender": "Daniel", "text": "Are you free for a quick call about a Shopify store?"})
    assert r.status_code == 200 and client.post("/api/alerts/messages", headers=admin, json={"platform": "myspace", "sender": "x", "text": "y"}).status_code == 422
    assert client.post("/api/alerts/messages", headers=admin, json={"platform": "upwork", "sender": "x", "text": "y", "url": "javascript:alert(1)"}).status_code == 422
    summary = client.get("/api/today/summary", headers=admin).json()
    assert summary["kpis"]["client_messages_waiting"] == 1 and "client message" in summary["focus"][0]["title"] and "Daniel" in summary["focus"][0]["title"]
    engine.cycle(ORG, utc_now := engine.utcnow() + timedelta(seconds=1), mail=False)
    assert kinds(sent)[0] == "telegram"


# ---------------------------------------------------------------- acknowledging from Telegram, with no public address

def test_a_telegram_button_tap_or_reply_acknowledges(sent, monkeypatch):
    on(channels={"telegram": {"chat_id": "555"}})
    monkeypatch.setattr(channels, "telegram_configured", lambda cfg: True)
    m1, m2 = msg(sender="A", ref="a"), msg(sender="B", ref="b")
    answered = []
    monkeypatch.setattr(channels, "telegram_answer_callback", lambda cid, text="": answered.append(cid))
    updates = [{"update_id": 1, "callback_query": {"id": "cb1", "data": f"ack:{m1['id']}", "message": {"chat": {"id": 555}}}},
               {"update_id": 2, "callback_query": {"id": "cb2", "data": f"ack:{m2['id']}", "message": {"chat": {"id": 999}}}}]    # a tap from another chat is ignored
    monkeypatch.setattr(channels, "telegram_updates", lambda offset: (updates, 3))
    assert engine.poll_acks(ORG, engine.get_settings(ORG)) == 1
    assert {m["sender"]: m["status"] for m in engine.list_messages(ORG)} == {"A": "acknowledged", "B": "new"}
    monkeypatch.setattr(channels, "telegram_updates", lambda offset: ([{"update_id": 3, "message": {"chat": {"id": 555}, "text": "on it"}}], 4))
    assert engine.poll_acks(ORG, engine.get_settings(ORG)) == 1
    assert all(m["status"] == "acknowledged" for m in engine.list_messages(ORG)) and engine.get_state(ORG, "telegram_offset") == "4" and answered


# ---------------------------------------------------------------- what is actually sent to each service

class Resp:
    def __init__(self, status=200, text="{}"):
        self.status_code, self.text = status, text


def capture(monkeypatch, resp):
    seen = {}
    def fake(url, timeout=20, headers=None, method="GET", json_body=None, form_body=None, max_bytes=0):
        seen.update(url=url, headers=headers or {}, method=method, json=json_body, form=form_body)
        return resp
    monkeypatch.setattr(channels.SafeFetcher, "safe_fetch", staticmethod(fake))
    return seen


def test_telegram_request_shape_and_errors_without_leaking_the_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AAH-super-secret-token-value-123456")
    seen = capture(monkeypatch, Resp(200))
    ok, detail = channels.send_telegram({"chat_id": "555"}, "hello", message_id=7)
    assert ok and seen["url"].startswith("https://api.telegram.org/bot123456789:") and seen["json"]["chat_id"] == "555"
    assert seen["json"]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "ack:7"
    for status, word in ((401, "token"), (403, "any message first"), (500, "500")):
        capture(monkeypatch, Resp(status))
        ok, detail = channels.send_telegram({"chat_id": "555"}, "x")
        assert not ok and word in detail and "AAH" not in detail
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    assert channels.send_telegram({"chat_id": "555"}, "x") == (False, "Telegram is not set up (a bot token and your chat ID are needed).")


def test_whatsapp_explains_the_24_hour_window_and_never_echoes_the_token(monkeypatch):
    monkeypatch.setenv("WHATSAPP_CLOUD_TOKEN", "EAAB-secret-whatsapp-token-0000")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "109876543210987")
    seen = capture(monkeypatch, Resp(200))
    assert channels.send_whatsapp({"to": "+923404095953"}, "hi")[0]
    assert seen["url"].endswith("/109876543210987/messages") and seen["json"]["to"] == "923404095953" and seen["headers"]["Authorization"].startswith("Bearer EAAB")
    capture(monkeypatch, Resp(400, json.dumps({"error": {"code": 131047}})))
    ok, detail = channels.send_whatsapp({"to": "+923404095953"}, "hi")
    assert not ok and "24 hours" in detail and "EAAB" not in detail
    assert channels.send_whatsapp({"to": "03404095953"}, "hi")[1].startswith("WhatsApp is not set up")


def test_the_phone_call_reads_the_message_aloud_escapes_it_and_hides_the_account(monkeypatch):
    for k, v in {"TWILIO_ACCOUNT_SID": "AC" + "a" * 32, "TWILIO_AUTH_TOKEN": "tok" * 10, "TWILIO_FROM_NUMBER": "+15551234567"}.items():
        monkeypatch.setenv(k, v)
    seen = capture(monkeypatch, Resp(201))
    ok, detail = channels.place_call({"to": "+923404095953"}, 'Amina says "call me" <now> & fast')
    assert ok and seen["url"].endswith("/Calls.json") and seen["form"]["To"] == "+923404095953" and seen["form"]["From"] == "+15551234567"
    assert "&lt;now&gt;" in seen["form"]["Twiml"] and "&amp;" in seen["form"]["Twiml"] and "<Say" in seen["form"]["Twiml"]
    capture(monkeypatch, Resp(400, json.dumps({"message": "The number +923404095953 is unverified. Trial accounts cannot call unverified numbers. AC" + "a" * 32})))
    ok, detail = channels.place_call({"to": "+923404095953"}, "x")
    assert not ok and "Trial accounts" in detail and "a" * 32 not in detail


def test_the_spoken_line_uses_your_first_name_and_survives_a_model_failure(monkeypatch, sent):
    from config.settings import settings
    monkeypatch.setattr(settings.agency, "founder_name", "Rizwan Zafar")
    m = {"sender": "Amina K.", "platform": "fiverr", "preview": "Can you start this week?", "subject": "", "received_at": "2026-11-02 10:00:00"}
    cfg = engine.validate({"ai_summary": True})
    assert engine.speech_text(m, cfg, T0 + timedelta(minutes=15)).startswith("Hello Rizwan. Amina K. messaged you on Fiverr 15 minutes ago.")
    import llm.client as c
    monkeypatch.setattr(c.LLMGateway, "has_provider", staticmethod(lambda: True))
    monkeypatch.setattr(c.LLMGateway, "complete", classmethod(lambda cls, *a, **k: {"text": "Amina wants to start this week."}))
    assert "Amina wants to start this week." in engine.speech_text(m, cfg, T0)
    monkeypatch.setattr(c.LLMGateway, "complete", classmethod(lambda cls, *a, **k: (_ for _ in ()).throw(RuntimeError("down"))))
    assert "Can you start this week?" in engine.speech_text(m, cfg, T0)                           # falls back to the plain text


# ---------------------------------------------------------------- the mailbox, read-only

def mail(uid, frm, subject, body, when=T0, mid=None):
    m = EmailMessage()
    m["From"], m["Subject"], m["Date"], m["Message-ID"] = frm, subject, format_datetime(when), mid or f"<{uid}@mail.test>"
    m.set_content(body)
    return uid, m.as_bytes()


class FakeBox:
    def __init__(self, mails):
        self.mails, self.readonly, self.peeked, self.logged_out = dict(mails), None, True, False

    def select(self, name, readonly=False):
        self.readonly = readonly
        return "OK", [b"1"]

    def uid(self, cmd, *args):
        if cmd == "SEARCH":
            crit = args[-1]
            ids = sorted(self.mails)
            if crit.startswith("(UID "):
                lo = int(crit.split()[1].split(":")[0])
                ids = [u for u in ids if u >= lo] or ids[-1:]                                 # real servers always return the last message for n:*
            return "OK", [b" ".join(str(i).encode() for i in ids)]
        if cmd == "FETCH":
            if "BODY.PEEK" not in args[1]:
                self.peeked = False
            return "OK", [(b"1 (UID x BODY[]<0> {1}", self.mails[int(args[0])]), b")"]
        raise AssertionError(cmd)

    def logout(self):
        self.logged_out = True


def poll(box, now=T0 + timedelta(hours=1)):
    return mailwatch.poll(ORG, engine.validate({"enabled": True}), now, connect=lambda: box)


def test_only_client_message_emails_from_watched_platforms_are_stored_and_the_mailbox_is_left_untouched():
    box = FakeBox([mail(1, "Fiverr <noreply@e.fiverr.com>", "Amina K. sent you a message", "Hi, I need a website. Can you start Monday?"),
                   mail(2, "Upwork <donotreply@upwork.com>", "Jobs matching your skills this week", "Ten jobs"),
                   mail(3, "Friend <friend@gmail.com>", "New message", "lunch?"),
                   mail(4, "LinkedIn <messages-noreply@linkedin.com>", "Sara Lopez messaged you", "Are you taking new clients?")])
    n, err = poll(box)
    assert (n, err) == (2, None)
    got = {m["sender"]: m for m in engine.list_messages(ORG)}
    assert set(got) == {"Amina K.", "Sara Lopez"} and "start Monday" in got["Amina K."]["preview"] and got["Sara Lopez"]["platform"] == "linkedin"
    assert box.readonly is True and box.peeked is True and box.logged_out is True            # read-only, nothing marked read, always logged out


def test_polling_twice_does_not_duplicate_and_only_new_mail_is_read():
    first = [mail(1, "Fiverr <noreply@e.fiverr.com>", "Amina K. sent you a message", "one")]
    assert poll(FakeBox(first))[0] == 1
    assert engine.get_state(ORG, "imap_last_uid") == "1"
    second = first + [mail(2, "Fiverr <noreply@e.fiverr.com>", "Bilal sent you a message", "two")]
    assert poll(FakeBox(second))[0] == 1 and len(engine.list_messages(ORG)) == 2
    assert poll(FakeBox(second))[0] == 0


def test_the_first_run_looks_back_one_day_only_so_it_never_floods_you():
    old = mail(1, "Fiverr <noreply@e.fiverr.com>", "Old Client sent you a message", "last week", when=T0 - timedelta(days=6))
    fresh = mail(2, "Fiverr <noreply@e.fiverr.com>", "New Client sent you a message", "today", when=T0)
    assert poll(FakeBox([old, fresh]))[0] == 1 and engine.list_messages(ORG)[0]["sender"] == "New Client"


def test_a_mailbox_problem_is_reported_in_plain_words_and_never_raises(monkeypatch):
    def boom():
        raise Exception("[AUTHENTICATIONFAILED] Invalid credentials (Failure)")
    n, err = mailwatch.poll(ORG, engine.validate({"enabled": True}), T0, connect=boom)
    assert n == 0 and "app password" in err
    monkeypatch.delenv("ALERT_IMAP_HOST", raising=False)
    assert "not set up" in mailwatch.poll(ORG, engine.validate({}), T0)[1]


def test_the_mail_check_shows_how_emails_would_be_read_without_storing_anything():
    box = FakeBox([mail(1, "Fiverr <noreply@e.fiverr.com>", "Amina K. sent you a message", "hi"), mail(2, "Upwork <donotreply@upwork.com>", "Jobs matching your skills", "x")])
    out = mailwatch.preview(connect=lambda: box)
    assert out["ok"] and [(e["platform"], e["would_alert"]) for e in out["emails"]] == [("upwork", False), ("fiverr", True)] and engine.list_messages(ORG) == []


def test_the_worker_runs_every_enabled_workspace(sent, monkeypatch):
    from alertdesk import worker
    on()
    engine.save_settings("org_ad_off", {"enabled": False})
    assert worker.enabled_orgs() == [ORG]
    seen = []
    monkeypatch.setattr(engine, "cycle", lambda org, *a, **k: seen.append(org))
    w = worker.AlertWorker(interval=0.01)
    w.start()
    import time
    time.sleep(0.1)
    w.stop()
    assert ORG in seen and "org_ad_off" not in seen


def test_the_new_secrets_are_validated_masked_and_never_returned(client, make_key):
    from config import integrations
    admin = make_key("super_admin", ORG)
    put = lambda name, v: client.put(f"/api/integrations/{name}", headers=admin, json={"value": v})
    assert put("TELEGRAM_BOT_TOKEN", "not-a-token").status_code == 422
    assert put("TELEGRAM_BOT_TOKEN", "123456789:AAH-super-secret-token-value-123456").status_code == 200
    assert put("TWILIO_ACCOUNT_SID", "XX123").status_code == 422 and put("TWILIO_FROM_NUMBER", "0300").status_code == 422
    assert put("ALERT_IMAP_USER", "not an email").status_code == 422 and put("ALERT_IMAP_HOST", "imap.gmail.com").status_code == 200
    rows = {r["name"]: r for r in client.get("/api/integrations", headers=admin).json()["integrations"]}
    assert rows["TELEGRAM_BOT_TOKEN"]["display"] == "••••3456" and "AAH-super" not in json.dumps(rows) and rows["ALERT_IMAP_HOST"]["display"] == "imap.gmail.com"
    assert rows["TELEGRAM_BOT_TOKEN"]["group"] == "Message alerts"
    for name in ("TELEGRAM_BOT_TOKEN", "ALERT_IMAP_HOST"):                              # these were applied to this process's environment: put it back
        integrations.clear_key(name)
