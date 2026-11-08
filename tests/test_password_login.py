"""Tier passwords: the only way in. Different secret per tier, hashed, throttled, never echoed, and a change ends old sessions."""

import logging
import time

import pytest

from security import passwords
from security.auth import ROLE_PERMISSIONS

PW = {"super_admin": "Tr1cky-Admin-Passphrase!", "growth_lead": "Lead-Gen_Phrase-7391x", "sdr_rep": "S3ller#Quiet#Morning", "auditor": "Audit0r-Green-Lantern-88"}


@pytest.fixture
def all_set():
    for role, pw in PW.items():
        passwords.set_password(role, pw, by="test")


def login(client, role, password, ip=None):
    return client.post("/api/auth/login", json={"role": role, "password": password})


# ---------------------------------------------------------------- the rules for a good password

@pytest.mark.parametrize("bad,word", [("", "Type a password"), ("short1A!", "at least 12"), ("a" * 129, "at most 128"), ("   padded-Passw0rd!  ", "spaces at the start"),
                                      ("aaaaaaaaaaaa", "repeats too much"), ("lowercaseonly1", "mix upper case"), ("Password1234", "too easy"),
                                      ("MyAuditor-Pass-123!", "too easy"), ("AgencyBD-Strong-77!x", "too easy")])
def test_weak_passwords_are_refused_with_a_reason(bad, word):
    with pytest.raises(ValueError, match=word):
        passwords.set_password("auditor", bad, by="t")
    assert not passwords.is_set("auditor")


def test_a_long_passphrase_is_fine_without_symbols():
    passwords.set_password("auditor", "correct horse battery staple", by="t")
    assert passwords.verify("auditor", "correct horse battery staple")


def test_every_tier_must_have_its_own_password(all_set):
    with pytest.raises(ValueError, match="Another tier already uses this password"):
        passwords.set_password("auditor", PW["growth_lead"], by="t")
    assert passwords.verify("auditor", PW["auditor"])                      # the refused change did not touch the old one


def test_only_a_salted_hash_is_stored(all_set):
    from database.db import get_db
    with get_db() as db:
        rows = db.execute("SELECT * FROM access_passwords").fetchall()
    assert len(rows) == 4 and len({r["salt"] for r in rows}) == 4
    blob = " ".join(str(tuple(r)) for r in rows)
    assert not any(pw in blob for pw in PW.values())


def test_generated_passwords_pass_the_rules_and_are_unique():
    seen = {passwords.generate() for _ in range(20)}
    assert len(seen) == 20
    for pw in seen:
        passwords.check_policy(pw, "super_admin")


# ---------------------------------------------------------------- signing in

def test_without_any_password_nobody_can_sign_in_and_the_screen_is_told_how(client):
    assert client.get("/api/auth/tiers").json()["any_set"] is False
    r = login(client, "super_admin", "anything-at-all-123")
    assert r.status_code == 503 and "scripts/set_passwords.py" in r.json()["detail"]


def test_the_right_tier_and_password_opens_that_tier_and_no_more(client, all_set):
    for role in PW:
        r = login(client, role, PW[role])
        assert r.status_code == 200
        body = r.json()
        assert body["me"]["role"] == role and body["me"]["permissions"] == ROLE_PERMISSIONS[role] and body["expires_in"] == 12 * 3600
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"}).json()
        assert me["role"] == role


def test_a_lower_tier_password_never_opens_a_higher_tier(client, all_set):
    for role, pw in PW.items():
        for other in PW:
            if other != role:
                assert login(client, other, pw).status_code in (401, 429)


def test_wrong_passwords_and_unknown_tiers_get_the_same_plain_answer(client, all_set):
    answers = {login(client, "super_admin", "wrong-password-123").json()["detail"], login(client, "root", PW["super_admin"]).json()["detail"],
               login(client, "super_admin", "").json()["detail"]}
    assert answers == {"That tier and password do not match."}


def test_a_tier_without_a_password_is_indistinguishable_from_a_wrong_one(client):
    passwords.set_password("auditor", PW["auditor"], by="t")
    a = login(client, "growth_lead", "Some-Guess-123456!")
    b = login(client, "auditor", "Some-Guess-123456!")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_the_screen_lists_tiers_without_secrets(client):
    passwords.set_password("auditor", PW["auditor"], by="t")
    body = client.get("/api/auth/tiers")
    assert body.status_code == 200 and PW["auditor"] not in body.text
    assert {t["role"]: t["available"] for t in body.json()["tiers"]} == {"super_admin": False, "growth_lead": False, "sdr_rep": False, "auditor": True}


def test_an_old_style_key_header_opens_nothing(client, all_set):
    assert client.get("/api/auth/me", headers={"X-API-Key": PW["super_admin"]}).status_code == 401
    assert client.get("/api/leads", headers={"X-API-Key": "agy_live_" + "0" * 48}).status_code == 401


# ---------------------------------------------------------------- guessing

def test_five_wrong_tries_lock_the_address_out_and_a_right_password_cannot_skip_the_wait(client, all_set):
    for _ in range(5):
        assert login(client, "super_admin", "wrong-password-123").status_code == 401
    locked = login(client, "super_admin", PW["super_admin"])
    assert locked.status_code == 429 and int(locked.headers["Retry-After"]) > 0 and "minute" in locked.json()["detail"]


def test_the_lockout_ends_after_fifteen_minutes(all_set):
    now = time.time()
    for i in range(5):
        passwords.record("9.9.9.9", "auditor", False, now=now - 100 + i)
    assert passwords.retry_after("9.9.9.9", now=now) > 0
    assert passwords.retry_after("9.9.9.9", now=now + 16 * 60) == 0
    assert passwords.retry_after("8.8.8.8", now=now) == 0                    # other addresses are not affected


def test_a_good_sign_in_clears_earlier_mistakes(client, all_set):
    for _ in range(3):
        login(client, "auditor", "nope-nope-nope-1")
    assert login(client, "auditor", PW["auditor"]).status_code == 200
    for _ in range(4):
        assert login(client, "auditor", "nope-nope-nope-1").status_code == 401       # the count started again from zero


def test_behind_a_proxy_each_visitor_has_their_own_lockout_but_only_when_trusted(client, all_set, monkeypatch):
    def tries(n, ip):
        return [client.post("/api/auth/login", json={"role": "auditor", "password": "nope-nope-nope-1"}, headers={"X-Real-IP": ip}).status_code for _ in range(n)]
    monkeypatch.delenv("AGENCYBD_TRUST_PROXY", raising=False)
    assert tries(5, "1.1.1.1") == [401] * 5                     # not trusted: the header is ignored, every caller is the same address
    assert client.post("/api/auth/login", json={"role": "auditor", "password": PW["auditor"]}, headers={"X-Real-IP": "2.2.2.2"}).status_code == 429
    from database.db import get_db
    with get_db() as db:
        db.execute("DELETE FROM login_attempts")
        db.commit()
    monkeypatch.setenv("AGENCYBD_TRUST_PROXY", "1")
    assert tries(5, "1.1.1.1") == [401] * 5
    assert client.post("/api/auth/login", json={"role": "auditor", "password": PW["auditor"]}, headers={"X-Real-IP": "1.1.1.1"}).status_code == 429       # the attacker is locked out
    assert client.post("/api/auth/login", json={"role": "auditor", "password": PW["auditor"]}, headers={"X-Real-IP": "2.2.2.2"}).status_code == 200       # a real user elsewhere is not


def test_many_failures_from_many_addresses_slow_everyone_down(all_set):
    now = time.time()
    for i in range(passwords.FAILS_GLOBAL):
        passwords.record(f"10.0.0.{i}", "auditor", False, now=now - 50 + i)
    assert passwords.retry_after("203.0.113.5", now=now) > 0


# ---------------------------------------------------------------- changing passwords

def token(client, role):
    return {"Authorization": f"Bearer {login(client, role, PW[role]).json()['token']}"}


def test_changing_a_password_ends_every_older_session_of_that_tier(client, all_set):
    admin, auditor_old = token(client, "super_admin"), token(client, "auditor")
    time.sleep(0.02)
    r = client.post("/api/auth/password", headers=admin, json={"role": "auditor", "new_password": "Brand-New_Phrase-Of-Five5!"})
    assert r.status_code == 200 and "token" not in r.json()                  # someone else's password: no session handed back
    stale = client.get("/api/auth/me", headers=auditor_old)
    assert stale.status_code == 401 and "password was changed" in stale.json()["detail"]
    assert client.get("/api/auth/me", headers=admin).status_code == 200      # other tiers keep working
    assert login(client, "auditor", PW["auditor"]).status_code == 401
    assert login(client, "auditor", "Brand-New_Phrase-Of-Five5!").status_code == 200


def test_changing_your_own_password_needs_the_current_one_and_keeps_you_signed_in(client, all_set):
    h = token(client, "growth_lead")
    assert client.post("/api/auth/password", headers=h, json={"role": "growth_lead", "new_password": "Another-Lead_Phrase-42!"}).status_code == 401
    assert client.post("/api/auth/password", headers=h, json={"role": "growth_lead", "current_password": "wrong-wrong-1234!", "new_password": "Another-Lead_Phrase-42!"}).status_code == 401
    time.sleep(0.02)
    ok = client.post("/api/auth/password", headers=h, json={"role": "growth_lead", "current_password": PW["growth_lead"], "new_password": "Another-Lead_Phrase-42!"})
    assert ok.status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401           # the old session ended
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {ok.json()['token']}"}).status_code == 200


def test_only_the_super_admin_can_change_other_tiers(client, all_set):
    for role in ("growth_lead", "sdr_rep", "auditor"):
        h = token(client, role)
        assert client.post("/api/auth/password", headers=h, json={"role": "super_admin", "new_password": "Takeover-Phrase_999!x"}).status_code == 403
    assert login(client, "super_admin", PW["super_admin"]).status_code == 200


def test_a_new_password_must_pass_the_rules_and_be_different_from_other_tiers(client, all_set):
    h = token(client, "super_admin")
    assert client.post("/api/auth/password", headers=h, json={"role": "sdr_rep", "new_password": "short"}).status_code == 422
    r = client.post("/api/auth/password", headers=h, json={"role": "sdr_rep", "new_password": PW["auditor"]})
    assert r.status_code == 422 and "Another tier" in r.json()["detail"]
    assert client.post("/api/auth/password", headers=h, json={"role": "janitor", "new_password": "Whatever-Phrase_123!"}).status_code == 422


def test_password_status_shows_when_not_what(client, all_set):
    admin = client.get("/api/auth/passwords", headers=token(client, "super_admin")).json()
    assert [t["role"] for t in admin["tiers"]] == ["super_admin", "growth_lead", "sdr_rep", "auditor"] and admin["can_set_all"] and all(t["is_set"] and t["updated_at"] for t in admin["tiers"])
    mine = client.get("/api/auth/passwords", headers=token(client, "auditor")).json()
    assert [t["role"] for t in mine["tiers"]] == ["auditor"] and not mine["can_set_all"]
    assert not any(pw in str(admin) + str(mine) for pw in PW.values())


def test_a_wrong_current_password_counts_toward_the_lockout(client, all_set):
    h = token(client, "auditor")
    for _ in range(5):
        client.post("/api/auth/password", headers=h, json={"role": "auditor", "current_password": "wrong-wrong-1234!", "new_password": "Whatever-Phrase_123!"})
    assert client.post("/api/auth/password", headers=h, json={"role": "auditor", "current_password": PW["auditor"], "new_password": "Whatever-Phrase_123!"}).status_code == 429


# ---------------------------------------------------------------- secrets never leak

def test_no_password_appears_in_logs_or_error_messages(client, all_set, caplog):
    caplog.set_level(logging.DEBUG)
    bodies = [login(client, "super_admin", "Guess-Which-Phrase_1!").text, login(client, "super_admin", PW["super_admin"]).text.replace(login(client, "super_admin", PW["super_admin"]).json()["token"], "")]
    client.post("/api/auth/password", headers=token(client, "super_admin"), json={"role": "auditor", "new_password": "weak"})
    blob = " ".join(bodies) + caplog.text
    for secret in list(PW.values()) + ["Guess-Which-Phrase_1!"]:
        assert secret not in blob


def test_the_session_token_carries_no_password(client, all_set):
    import base64, json
    tok = login(client, "auditor", PW["auditor"]).json()["token"]
    payload = json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "=="))
    assert PW["auditor"] not in json.dumps(payload) and payload["role"] == "auditor"


def test_the_sign_in_screen_script_and_page_source_ship_no_password(client):
    html = client.get("/").text
    assert not any(pw in html for pw in PW.values())
