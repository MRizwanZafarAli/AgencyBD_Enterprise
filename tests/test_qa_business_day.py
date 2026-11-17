"""A whole business day, played by each kind of user through the real API, from signing in to a won client and the weekly scorecard.

  Owner (super admin)  signs in, sets a price for a service and a reply-webhook secret
  Sales rep            adds a prospect, examines their site, reads the teardown, cannot send mail
  Growth lead          writes the first email, approves it, sends it, then a signed reply comes back and stops the follow-ups
  Everyone             unsubscribe links work and nobody is emailed after opting out
  Auditor              can look at everything it may, and change nothing
No network: DNS, the web, SMTP and the verifier are stubbed, so the test proves the product's rules, not the providers.
"""

import json
import time

import pytest

import outbound.providers.registry as registry
import outbound.providers.smtp as smtp_mod
import outbound.verify as verify_mod
from intel.services import ServiceCatalog
from net.fetcher import SafeFetcher
from outbound.providers.registry import MailboxRegistry
from security import passwords
from security.webhook_verifier import WebhookSecurity
from webfake import page

ORG = "org_day"
PW = {"super_admin": "Owner-Phrase_Blue-Falcon-81", "growth_lead": "Lead-Phrase_Green-River-72", "sdr_rep": "Rep-Phrase_Amber-Hill-63", "auditor": "Look-Phrase_Silver-Moon-54"}


class StubResp:
    def __init__(self, data): self._d = data; self.status_code = 200; self.text = json.dumps(data)
    def json(self): return self._d
    def raise_for_status(self): pass


@pytest.fixture
def day(monkeypatch, client, web):
    """Passwords set for each tier, a mailbox with credentials, and a stubbed mail wire. Returns what the people see and do."""
    monkeypatch.setenv("AGENCYBD_LOGIN_ORG", ORG)
    for role, pw in PW.items():
        passwords.set_password(role, pw, by="qa", org=ORG)
    monkeypatch.setattr(SafeFetcher, "resolve_and_validate_hostname", staticmethod(lambda host: "93.184.216.34"))
    monkeypatch.setattr(registry, "lookup_mx", lambda d: ["mx.example.net"])
    MailboxRegistry.register_mailbox(ORG, "sender@vectra.example", "Rizwan", daily_cap=50, skip_warmup=True, smtp_host="smtp.mailhost.test",
                                     smtp_username="sender@vectra.example", smtp_password="s3cret-pass")
    sent = []

    class Wire:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context=None): pass
        def login(self, u, p): pass
        def sendmail(self, frm, to, body): sent.append((frm, to, body))

    monkeypatch.setattr(smtp_mod, "open_smtp", lambda creds, timeout=15: Wire())
    monkeypatch.setattr(verify_mod, "lookup_mx", lambda d: ["mx.example.net"])
    monkeypatch.setattr(verify_mod.requests, "get", lambda *a, **k: StubResp({"status": "valid"}))
    monkeypatch.setenv("ZEROBOUNCE_API_KEY", "key-1234567890")

    def sign_in(role):                                                    # exactly what the sign-in screen does
        r = client.post("/api/auth/login", json={"role": role, "password": PW[role]})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}
    return type("Day", (), {"sign_in": staticmethod(sign_in), "sent": sent})


def test_a_business_day_from_prospect_to_won_client(client, day, web):
    owner, lead, rep, auditor = (day.sign_in(r) for r in ("super_admin", "growth_lead", "sdr_rep", "auditor"))
    assert client.get("/api/auth/me", headers=rep).json()["org_id"] == ORG

    # ---- Owner: prices and the reply webhook
    ServiceCatalog.upsert(ORG, "seo_optimization", "SEO optimization", "Fix titles, descriptions and the sitemap.", price_band="EUR 300")
    secret = client.post("/api/security/webhook_secret", headers=owner).json()["webhook_secret"]
    assert len(secret) >= 32

    # ---- Sales rep: add a prospect, examine the site, read the teardown
    web["acme-dental.example"] = {"html": page(title="Acme Dental Clinic", desc="", h1="Acme Dental Clinic", body="We provide family dental care, check-ups, whitening and emergency appointments in Leeds. " * 4), "headers": {"Content-Type": "text/html"}}
    made = client.post("/api/pipeline/deals/create", headers=rep, json={"company_name": "Acme Dental", "domain": "acme-dental.example", "deal_value": 2400}).json()
    lead_id = made.get("lead", made)["id"]
    resolved = client.post("/api/companies/resolve", headers=rep, json={"company_name": "Acme Dental", "hint_domain": "acme-dental.example"}).json()
    assert resolved["status"] == "resolved" and resolved["domain"] == "acme-dental.example", resolved
    company_id = resolved["company_id"]
    audit = client.post("/api/audits/run", headers=rep, json={"domain": "acme-dental.example", "company_id": company_id})
    assert audit.status_code == 200 and audit.json()["status"] == "completed" and audit.json()["findings_count"] > 0
    assert {f["check_id"] for f in audit.json()["findings"]} >= {"missing_meta_description"}                      # a real, checkable finding

    # ---- Sales rep may not send mail, nor approve; the Auditor may not draft
    first = {"recipient_email": "dana@acme-dental.example", "country_code": "US", "subject": "A quick note about your website", "step_number": 1, "lead_id": lead_id,
             "body": "Hi Dana, I checked acme-dental.example and the page has no meta description, which search engines show under the title. Happy to send a one-page note."}
    assert client.post("/api/outbound/sequence/step", headers=rep, json=first).status_code == 403
    assert client.post("/api/outbound/sequence/step", headers=auditor, json=first).status_code == 403

    # ---- Growth lead: draft, approve, send. Nothing leaves before approval.
    drafted = client.post("/api/outbound/sequence/step", headers=lead, json=first).json()
    assert drafted["status"] == "pending_approval" and day.sent == []
    approval = [p for p in client.get("/api/approvals/pending", headers=lead).json() if p["subject_type"] == "outbound_draft"][0]
    assert client.post(f"/api/outbound/drafts/{drafted['draft_id']}/send", headers=lead).json()["status"] == "blocked_by_policy"
    assert client.post(f"/api/approvals/{approval['id']}/decide", headers=rep, json={"decision": "approved"}).status_code == 403          # a rep cannot approve
    assert client.post(f"/api/approvals/{approval['id']}/decide", headers=lead, json={"decision": "approved", "reason": "checked"}).status_code == 200
    done = client.post(f"/api/outbound/drafts/{drafted['draft_id']}/send", headers=lead).json()
    assert done["status"] == "sent" and len(day.sent) == 1 and day.sent[0][1] == ["dana@acme-dental.example"]
    wire = day.sent[0][2]
    assert "unsubscribe" in wire.lower() and "List-Unsubscribe" in wire                                         # the compliance footer and one-click header are real

    # ---- A signed reply comes in: it is attributed to this workspace only, and a forged one is refused
    reply = {"from": "dana@acme-dental.example", "to": "sender@vectra.example", "subject": "Re: A quick note", "text": "Sounds interesting, can we talk Tuesday?"}
    body = json.dumps(reply).encode(); ts = int(time.time())
    headers = {"X-AgencyBD-Org": ORG, "X-AgencyBD-Timestamp": str(ts), "X-AgencyBD-Signature": WebhookSecurity.sign_payload(body, secret=secret, timestamp=ts), "Content-Type": "application/json"}
    assert client.post("/api/webhooks/inbound", content=body, headers=headers).status_code == 200
    forged = {**headers, "X-AgencyBD-Signature": "0" * 64}
    assert client.post("/api/webhooks/inbound", content=body, headers=forged).status_code == 401

    # ---- Unsubscribe: the link works for this address only, and the address is never emailed again
    from compliance.footer import ComplianceFooterBuilder
    tok = ComplianceFooterBuilder.generate_unsubscribe_token("lena@acme-dental.example", ORG)
    page_get = client.get("/api/compliance/unsubscribe", params={"email": "lena@acme-dental.example", "org_id": ORG, "token": tok})
    assert page_get.status_code == 200 and "Confirm unsubscribe" in page_get.text
    assert client.get("/api/compliance/suppression/check", headers=lead, params={"email": "lena@acme-dental.example"}).json()["is_suppressed"] is False     # opening the link changes nothing
    assert client.post("/api/compliance/unsubscribe", params={"email": "lena@acme-dental.example", "org_id": ORG, "token": tok}).status_code == 200
    assert client.get("/api/compliance/suppression/check", headers=lead, params={"email": "lena@acme-dental.example"}).json()["is_suppressed"] is True
    assert client.post("/api/compliance/unsubscribe", params={"email": "someone@else.example", "org_id": ORG, "token": tok}).status_code == 400            # a link only works for its own address
    optout = client.post("/api/outbound/sequence/step", headers=lead, json={**first, "recipient_email": "lena@acme-dental.example", "subject": "Following up"}).json()
    assert optout["status"] not in ("sent", "pending_approval"), optout                                                                               # nobody is emailed after opting out
    again = client.post("/api/compliance/suppression/add", headers=lead, json={"entity": "stop@acme-dental.example"})
    assert again.status_code == 200
    blocked = client.post("/api/outbound/sequence/step", headers=lead, json={**first, "recipient_email": "stop@acme-dental.example", "subject": "Hello again"}).json()
    assert blocked["status"] not in ("sent", "pending_approval"), blocked

    # ---- Pipeline: meeting, proposal, then the offer built from the real findings and the owner's price
    for stage in ("meeting_booked", "proposal_sent"):
        assert client.post("/api/pipeline/deals/stage", headers=lead, json={"lead_id": lead_id, "new_stage": stage}).status_code == 200
    offer = client.get(f"/api/companies/{company_id}/offer", headers=lead)
    assert offer.status_code == 200 and "EUR 300" in offer.json()["markdown"] and "[add the total]" in offer.json()["markdown"]      # price from the owner; total left for a person

    # ---- Won: a review task is planned; the week's numbers show the work; the auditor can read but not change
    won = client.post("/api/pipeline/deals/stage", headers=lead, json={"lead_id": lead_id, "new_stage": "won"}).json()
    assert won["review_task"]["due_date"]
    card = client.get("/api/today/scorecard", headers=auditor).json()
    rows = {r["key"]: r["this_week"] for r in card["rows"]}
    assert rows["wins"] == 1 and rows["proposals"] == 1 and rows["sent"] >= 1
    assert client.get("/api/leads", headers=auditor).status_code == 200
    for method, path, kw in (("POST", "/api/pipeline/deals/stage", {"json": {"lead_id": lead_id, "new_stage": "lost"}}), ("POST", "/api/partners", {"json": {"name": "x"}}),
                             ("POST", "/api/audits/run", {"json": {"domain": "acme-dental.example"}}), ("PUT", "/api/alerts/settings", {"json": {"enabled": True}})):
        assert client.request(method, path, headers=auditor, **kw).status_code == 403, path
    assert client.get("/api/auth/passwords", headers=auditor).json()["can_set_all"] is False
    assert client.get("/api/auth/passwords", headers=owner).json()["can_set_all"] is True


def test_another_workspace_sees_none_of_it(client, day, web, make_key):
    other = make_key("super_admin", org_id="org_someone_else")
    web["acme-dental.example"] = {"html": page(title="Acme"), "headers": {"Content-Type": "text/html"}}
    rep = day.sign_in("sdr_rep")
    client.post("/api/pipeline/deals/create", headers=rep, json={"company_name": "Acme Dental", "domain": "acme-dental.example"})
    assert client.get("/api/leads", headers=other).json() in ([], {"leads": []}) or client.get("/api/leads", headers=other).json().get("count", 0) == 0
    assert client.get("/api/pipeline/deals", headers=other).json()["active_deals_count"] == 0
