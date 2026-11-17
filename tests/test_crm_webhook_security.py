"""The HubSpot inbound webhook must accept only genuine, fresh, signed calls, and only change this workspace's clients."""

import base64
import hashlib
import hmac
import json
import time

import pytest

from database.db import get_db
from database.models import LeadRepository

SECRET = "hubspot-test-client-secret-0123456789"
URL = "/api/integrations/crm/hubspot"
EVENTS = [{"objectId": None, "propertyName": "lifecyclestage", "propertyValue": "customer"}]


@pytest.fixture
def lead(monkeypatch):
    monkeypatch.setenv("AGENCYBD_WEBHOOK_ORG_ID", "org_hs")
    monkeypatch.setenv("AGENCYBD_PUBLIC_BASE_URL", "https://bd.example.com")
    mine = LeadRepository.create_or_get_lead("Mine", "mine.example", source_channel="x", org_id="org_hs")["id"]
    theirs = LeadRepository.create_or_get_lead("Theirs", "theirs.example", source_channel="x", org_id="org_other")["id"]
    return mine, theirs


def signed(body: bytes, ts=None, secret=SECRET, path=URL):
    ts = str(ts if ts is not None else int(time.time() * 1000))
    msg = f"POST{'https://bd.example.com'}{path}{body.decode()}{ts}".encode()
    return {"x-hubspot-request-timestamp": ts, "x-hubspot-signature-v3": base64.b64encode(hmac.new(secret.encode(), msg, hashlib.sha256).digest()).decode(),
            "content-type": "application/json"}


def status_of(lead_id):
    with get_db() as db:
        return db.execute("SELECT status FROM leads WHERE id = ?", (lead_id,)).fetchone()["status"]


def body_for(lead_id):
    return json.dumps([{**EVENTS[0], "objectId": lead_id}]).encode()


def test_without_a_secret_the_endpoint_refuses_everything_and_changes_nothing(client, lead, monkeypatch):
    monkeypatch.delenv("HUBSPOT_CLIENT_SECRET", raising=False)
    mine, _ = lead
    r = client.post(URL, content=body_for(mine), headers={"content-type": "application/json"})
    assert r.status_code == 503 and r.json()["status"] == "not_configured" and status_of(mine) == "sourced"


def test_an_unsigned_or_wrongly_signed_call_is_refused_and_changes_nothing(client, lead, monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", SECRET)
    mine, _ = lead
    body = body_for(mine)
    assert client.post(URL, content=body, headers={"content-type": "application/json"}).status_code == 401
    assert client.post(URL, content=body, headers=signed(body, secret="some-other-secret-value-xxxxxxxx")).status_code == 401
    forged = signed(body)
    forged["x-hubspot-signature-v3"] = "AAAA" + forged["x-hubspot-signature-v3"][4:]
    assert client.post(URL, content=body, headers=forged).status_code == 401
    assert client.post(URL, content=body_for(mine) + b" ", headers=signed(body)).status_code == 401        # body changed after signing
    assert status_of(mine) == "sourced"


def test_an_old_signed_call_cannot_be_replayed(client, lead, monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", SECRET)
    mine, _ = lead
    body = body_for(mine)
    stale = int(time.time() * 1000) - 6 * 60 * 1000
    assert client.post(URL, content=body, headers=signed(body, ts=stale)).status_code == 401
    assert client.post(URL, content=body, headers=signed(body, ts="not-a-number")).status_code == 401
    assert status_of(mine) == "sourced"


def test_a_genuine_call_updates_only_this_workspaces_clients(client, lead, monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", SECRET)
    mine, theirs = lead
    body = json.dumps([{**EVENTS[0], "objectId": mine}, {**EVENTS[0], "objectId": theirs}, "junk", {"propertyName": "x"}]).encode()
    r = client.post(URL, content=body, headers=signed(body))
    assert r.status_code == 200 and r.json()["processed_events"] == 1
    assert status_of(mine) == "won" and status_of(theirs) == "sourced"                  # another workspace's client is untouched


def test_bad_json_with_a_good_signature_is_a_clear_error(client, lead, monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", SECRET)
    body = b"{not json"
    assert client.post(URL, content=body, headers=signed(body)).status_code == 400
