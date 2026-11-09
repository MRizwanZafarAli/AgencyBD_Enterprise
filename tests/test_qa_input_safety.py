"""Hostile text typed into every place people type: nothing crashes, nothing is executed, nothing leaks, and the database stays intact."""

import pytest

from database.db import get_db

ORG = "org_fuzz"
PAYLOADS = [
    "'; DROP TABLE leads; --",
    "\" OR \"1\"=\"1",
    "<script>window.__xss=1</script>",
    "<img src=x onerror=window.__xss=1>",
    "{{7*7}} ${7*7} %{7*7}",
    "../../../../etc/passwd",
    "A" * 5000,
    "\u0000null\u0000byte",
    "emoji 😀 and RTL ‮evil‬ text",
    "line1\r\nX-Injected: header",
    "javascript:alert(1)",
]


def tables():
    with get_db() as db:
        return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


@pytest.fixture
def lead(client, make_key):
    h = make_key("growth_lead", ORG)
    return h, client.post("/api/pipeline/deals/create", headers=h, json={"company_name": "Safe Co", "domain": "safe.example"}).json()


def lid(made):
    return made.get("lead", made)["id"]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_text_fields_survive_hostile_input(client, make_key, lead, payload):
    h, made = lead
    before = tables()
    calls = [
        ("POST", "/api/partners", {"name": payload, "contact_where": payload, "notes": payload}),
        ("POST", f"/api/clients/{lid(made)}/notes", {"kind": "note", "body": payload}),
        ("POST", f"/api/clients/{lid(made)}/notes", {"kind": "task", "body": payload, "due_date": payload}),
        ("POST", "/api/leadfinder/searches", {"name": payload, "source": "hiring", "params": {"keywords": [payload]}}),
        ("POST", "/api/leadfinder/searches", {"name": "x", "source": "new_companies_ie", "params": {"location": payload}}),
        ("POST", "/api/pipeline/deals/create", {"company_name": payload, "domain": payload}),
        ("POST", "/api/companies/resolve", {"company_name": payload, "hint_domain": payload}),
        ("POST", "/api/alerts/messages", {"platform": "other", "sender": payload, "text": payload, "url": payload}),
        ("POST", "/api/hunt/local", {"category": payload, "city": payload}),
        ("POST", "/api/search/interpret", {"query": payload}),
        ("POST", "/api/audits/run", {"domain": payload}),
        ("POST", "/api/compliance/suppression/add", {"entity": payload}),
        ("POST", "/api/outbound/sequence/step", {"recipient_email": payload, "country_code": "US", "subject": payload, "body": payload}),
        ("POST", "/api/replies/triage", {"lead_id": lid(made), "reply_text": payload}),
        ("POST", "/api/auth/login", {"role": payload, "password": payload}),
        ("GET", "/api/leadfinder/xray", {"role": payload}),
        ("GET", "/api/compliance/suppression/check", {"email": payload}),
        ("GET", "/api/leads", {"status": payload}),
    ]
    for method, url, body in calls:
        r = client.request(method, url, headers=h, json=body) if method == "POST" else client.request(method, url, headers=h, params=body)
        assert r.status_code < 500 or r.status_code == 503, f"{method} {url} -> {r.status_code}: {r.text[:120]}"
        if r.status_code >= 400:
            assert r.headers["content-type"].startswith("application/json"), f"{method} {url} answered with {r.headers['content-type']}"       # never HTML, so nothing can run
            assert "Traceback" not in r.text and "sqlite" not in r.text.lower() and "/Applications/" not in r.text, f"{method} {url} leaked: {r.text[:160]}"
    assert before <= tables() and "leads" in tables()                    # no table was dropped
    with get_db() as db:
        assert db.execute("SELECT COUNT(*) FROM leads WHERE company_name = 'Safe Co'").fetchone()[0] == 1


def test_stored_text_comes_back_exactly_as_typed_never_changed_or_run(client, lead):
    h, made = lead
    p = "<img src=x onerror=window.__xss=1> & \"quotes\" 'and' ;--"
    client.post("/api/partners", headers=h, json={"name": p})
    back = client.get("/api/partners", headers=h).json()["partners"][0]["name"]
    assert back == p                                                     # stored verbatim; the screen shows it as text (checked in the browser)
    assert client.get("/api/partners", headers=h).headers["content-type"].startswith("application/json")


def test_api_errors_never_show_internals(client, make_key):
    h = make_key("super_admin", ORG)
    for url in ("/api/leads/999999", "/api/companies/999999/teardown", "/api/clients/999999/notes", "/api/leadfinder/searches/999999/run", "/api/nope"):
        r = client.get(url, headers=h) if "run" not in url else client.post(url, headers=h)
        body = r.text
        assert "Traceback" not in body and "File \"/" not in body and "sqlite3" not in body and "/Applications/" not in body, f"{url}: {body[:200]}"


def test_the_pipeline_never_sends_an_unbounded_list_but_counts_everyone(client, make_key):
    from database.models import PIPELINE_MAX_PER_STAGE
    h = make_key("growth_lead", "org_big")
    with get_db() as db:
        db.executemany("INSERT INTO leads (org_id, company_name, domain, source_channel, status) VALUES ('org_big', ?, ?, 'x', 'sourced')",
                       [(f"Co {i}", f"co{i}.example") for i in range(PIPELINE_MAX_PER_STAGE + 25)])
        db.commit()
    stage = client.get("/api/pipeline/deals", headers=h).json()["stages"]["sourced"]
    assert stage["count"] == PIPELINE_MAX_PER_STAGE + 25 and len(stage["leads"]) == PIPELINE_MAX_PER_STAGE and stage["truncated"] is True
    assert stage["leads"][0]["company_name"] == f"Co {PIPELINE_MAX_PER_STAGE + 24}"                    # newest first


def test_every_answer_carries_the_security_headers(client, make_key):
    for path in ("/healthz/live", "/api/auth/tiers", "/"):
        h = client.get(path).headers
        assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "SAMEORIGIN" and h["referrer-policy"] == "no-referrer"
        csp = h["content-security-policy"]
        assert "default-src 'self'" in csp and "script-src 'self'" in csp and "object-src 'none'" in csp and "frame-ancestors 'self'" in csp
        assert "unsafe-eval" not in csp and "script-src 'self' 'unsafe-inline'" not in csp          # scripts can never be injected inline
        assert "camera=()" in h["permissions-policy"]
