"""Localization and globalization: other alphabets, other time zones (including half-hour zones and clock changes), other countries' phone numbers
and mailing rules. What is not supported (translated screens, other currencies) is listed in docs/QA_REPORT.md, not hidden."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from alertdesk import channels, engine

ORG = "org_global"
NAMES = ["عيادة الدكتور أحمد", "测试公司 有限公司", "Café Münchën & Söhne", "Здоровье Плюс", "דנטל קלינק", "ڈاکٹر احمد کلینک", "😀 Smile Dental 🦷", "Ångström AB"]


@pytest.mark.parametrize("name", NAMES)
def test_names_in_any_alphabet_round_trip_through_clients_partners_and_notes(client, make_key, name):
    h = make_key("growth_lead", ORG)
    made = client.post("/api/pipeline/deals/create", headers=h, json={"company_name": name, "domain": "intl-test.example"}).json()
    lead = made.get("lead", made)
    assert lead["company_name"] == name
    assert client.post("/api/partners", headers=h, json={"name": name, "notes": name}).json()["name"] == name
    note = client.post(f"/api/clients/{lead['id']}/notes", headers=h, json={"kind": "note", "body": name * 3}).json()
    assert note["body"] == name * 3
    listed = client.get("/api/leads", headers=h).json()
    assert any(l["company_name"] == name for l in (listed if isinstance(listed, list) else listed.get("leads", [])))


def test_a_csv_export_keeps_other_alphabets_intact(client, make_key):
    h = make_key("super_admin", ORG)
    client.post("/api/pipeline/deals/create", headers=h, json={"company_name": "عيادة الدكتور أحمد", "domain": "csv-intl.example"})
    r = client.get("/api/integrations/crm/export-all", headers=h)
    assert r.status_code == 200 and "عيادة الدكتور أحمد" in r.text                  # JSON carries the characters as they are, not as ???


CFG = lambda tz, **k: engine.validate({"timezone": tz, "schedule": {"days": [0, 1, 2, 3, 4], "start": "09:00", "end": "18:00"}, **k})


@pytest.mark.parametrize("zone", ["Asia/Karachi", "Asia/Kolkata", "Asia/Kathmandu", "Europe/Dublin", "America/New_York", "Asia/Dubai", "Australia/Adelaide", "America/Sao_Paulo", "Pacific/Auckland"])
def test_working_hours_follow_the_local_clock_in_every_zone_including_half_hour_offsets(zone):
    cfg = CFG(zone)
    tz = ZoneInfo(zone)
    monday = datetime(2026, 11, 2, tzinfo=tz)
    for hour, minute, expect in ((8, 59, False), (9, 0, True), (13, 30, True), (18, 0, True), (18, 1, False), (23, 30, False)):
        local = monday.replace(hour=hour, minute=minute)
        assert engine.is_active(local.astimezone(timezone.utc), cfg) is expect, f"{zone} {hour:02d}:{minute:02d}"


def test_working_hours_stay_correct_across_a_clock_change():
    cfg = CFG("Europe/Dublin")
    tz = ZoneInfo("Europe/Dublin")
    before, after = datetime(2026, 3, 27, 10, 0, tzinfo=tz), datetime(2026, 3, 30, 10, 0, tzinfo=tz)    # clocks go forward on 29 March 2026
    assert engine.is_active(before.astimezone(timezone.utc), cfg) and engine.is_active(after.astimezone(timezone.utc), cfg)
    assert (after.astimezone(timezone.utc) - before.astimezone(timezone.utc)) == timedelta(days=3) - timedelta(hours=1)      # and the two UTC moments differ by the lost hour


def test_a_weekend_in_one_country_is_a_working_day_in_another():
    cfg = engine.validate({"timezone": "Asia/Dubai", "schedule": {"days": [0, 1, 2, 3, 6], "start": "09:00", "end": "18:00"}})          # Sunday to Thursday
    sunday = datetime(2026, 11, 8, 10, 0, tzinfo=ZoneInfo("Asia/Dubai")).astimezone(timezone.utc)
    friday = datetime(2026, 11, 6, 10, 0, tzinfo=ZoneInfo("Asia/Dubai")).astimezone(timezone.utc)
    assert engine.is_active(sunday, cfg) and not engine.is_active(friday, cfg)


def test_an_unknown_time_zone_is_refused_with_a_reason():
    with pytest.raises(ValueError):
        engine.validate({"timezone": "Mars/Olympus"})


@pytest.mark.parametrize("number,ok", [("+923404095953", True), ("+353861234567", True), ("+447911123456", True), ("+971501234567", True), ("+14155552671", True), ("+8613800138000", True),
                                       ("+5511987654321", True), ("03404095953", False), ("+92 340 4095953", False), ("+0123456789", False), ("00923404095953", False), ("+", False), ("", False)])
def test_phone_numbers_must_be_international_format(number, ok):
    assert bool(channels.E164.match(number)) is ok


@pytest.mark.parametrize("code", ["US", "GB", "IE", "DE", "FR", "NL", "ES", "IT", "SE", "PK", "AE", "SA", "IN", "CA", "AU", "NZ", "BR", "JP", "SG", "ZA"])
def test_every_country_gets_an_explicit_mailing_decision_never_a_silent_default(client, make_key, code):
    body = client.get(f"/api/compliance/country/{code}", headers=make_key("auditor", ORG)).json()
    assert body["country_code"] == code and body["status"] and isinstance(body["allowed"], bool) and body["reason"]


@pytest.mark.parametrize("code", ["", "XX", "ZZZ", "u s", "1", "<script>"])
def test_an_unknown_country_is_blocked_not_assumed(client, make_key, code):
    r = client.get(f"/api/compliance/country/{code or '-'}", headers=make_key("auditor", ORG))
    if r.status_code == 200:
        assert r.json()["allowed"] is False
