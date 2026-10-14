"""
Regression tests for the independent audit's first fix group (P0-1, P0-5, P0-7, P0-8).
Each test reproduces the original finding: it failed before the fix.
"""

import http.server
import re
import socket
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest

from compliance.footer import ComplianceFooterBuilder
from compliance.suppression import KeyedSuppressionVault
from database.db import get_db
from net.fetcher import SafeFetcher, SSRFSecurityError
from net.validate import clean_domain, is_valid_hostname
from policy.engine import PolicyEngine

ROOT = Path(__file__).resolve().parent.parent


# ============================ P0-1: SSRF ============================

@pytest.fixture
def canary():
    """A loopback 'internal service'. Any request that reaches it is an SSRF."""
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.send_header("content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>INTERNAL-SECRET wp-content</html>")

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{server.server_address[1]}", hits
    server.shutdown()


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://localhost/", "http://[::1]/", "http://0.0.0.0/",
    "http://169.254.169.254/latest/meta-data/", "http://10.1.2.3/", "http://192.168.1.1/",
    "http://172.16.0.9/", "http://100.64.0.1/", "http://[::ffff:127.0.0.1]/", "http://224.0.0.1/",
])
def test_fetcher_blocks_non_public_targets(url):
    with pytest.raises(SSRFSecurityError):
        SafeFetcher.safe_fetch(url)


def test_fetcher_rejects_odd_urls():
    for bad in ("ftp://example.com/", "http://user:pw@example.com/", "file:///etc/passwd"):
        with pytest.raises(SSRFSecurityError):
            SafeFetcher.safe_fetch(bad)


def test_dns_rebinding_is_stopped_at_connect_time(monkeypatch):
    """First lookup (validation) says public, second lookup (connection) says loopback."""
    import net.fetcher as nf
    calls = {"n": 0}
    real = socket.getaddrinfo

    def flipping(host, port, *a, **k):
        if host == "rebind.example":
            calls["n"] += 1
            ip = "93.184.216.34" if calls["n"] == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 80))]
        return real(host, port, *a, **k)

    monkeypatch.setattr(nf.socket, "getaddrinfo", flipping)
    with pytest.raises(SSRFSecurityError):
        SafeFetcher.safe_fetch("http://rebind.example/")
    assert calls["n"] >= 2, "the connect-time check must re-validate the address it actually uses"


def test_legacy_endpoints_cannot_reach_internal_services(client, growth_headers, canary):
    target, hits = canary
    for path, body in [
        ("/api/native/fingerprint_tech", {"domain": target}),
        ("/api/enrich/site_crawl", {"domain": target}),
        ("/api/audits/run", {"domain": target}),
    ]:
        res = client.post(path, json=body, headers=growth_headers)
        assert res.status_code in (400, 200), (path, res.status_code)
        assert "INTERNAL-SECRET" not in res.text and "WordPress" not in res.text, path
    assert hits == [], f"internal service was contacted: {hits}"


def test_malformed_domains_are_client_errors_not_500s(client, growth_headers):
    for bad in ("-oX", "-q=mx", "exa mple.com", "user@evil.com"):
        for path in ("/api/native/fingerprint_tech", "/api/enrich/site_crawl"):
            res = client.post(path, json={"domain": bad}, headers=growth_headers)
            assert res.status_code == 400, (path, bad, res.status_code)


def test_tech_audit_agent_cannot_reach_internal_services(canary):
    from agents.tech_audit_agent import TechAuditAgent
    from database.models import LeadRepository
    target, hits = canary
    lead = LeadRepository.create_or_get_lead("Internal", target)
    with pytest.raises(SSRFSecurityError):
        TechAuditAgent().audit_lead(lead["id"])
    assert hits == []


def test_smtp_probe_refuses_internal_mx():
    from engines.native_smtp_verifier import NativeSMTPVerifier
    out = NativeSMTPVerifier().probe_smtp_handshake("127.0.0.1", "a@b.com")
    assert out["status"] == "blocked"


def test_smtp_syntax_rejects_newline_injection():
    from engines.native_smtp_verifier import NativeSMTPVerifier
    assert NativeSMTPVerifier().validate_syntax("a@b.com\n") is False
    assert NativeSMTPVerifier().validate_syntax("a@b.com>\r\nQUIT") is False


def test_hostname_validation():
    assert is_valid_hostname("example.com") and is_valid_hostname("sub.example.co.uk")
    for bad in ("-oX", "-q=mx", "exa mple.com", "a" * 64 + ".com", "", "a..b"):
        assert not is_valid_hostname(bad), bad
    assert clean_domain("https://Example.com/path?x=1") == "example.com"
    with pytest.raises(ValueError):
        clean_domain("user@evil.com")


# Files that may talk to the network directly, with the reason. Anything else must use net.fetcher.
_NETWORK_ALLOWLIST = {
    "llm/client.py": "fixed hosts: api.anthropic.com and the configured local model server",
    "adapters/vendor_connectors.py": "fixed vendor API hosts only; user input never forms the URL",
    "outbound/providers/smartlead.py": "fixed vendor API host",
    "outbound/providers/smtp.py": "smtplib; relay host validated and connected by validated IP (see open_smtp)",
    "outbound/verify.py": "fixed vendor hosts: api.zerobounce.net and api.millionverifier.com",
    "auditors/pagespeed.py": "fixed vendor host: www.googleapis.com",
    "auditors/tls.py": "raw socket to the IP already validated by SafeFetcher.resolve_and_validate_hostname",
    "intel/places.py": "fixed vendor host: places.googleapis.com",
    "intel/search.py": "fixed vendor host: api.search.brave.com",
    "engines/native_smtp_verifier.py": "raw socket, but the MX address is validated first (see test above)",
}
_NETWORK_PATTERNS = re.compile(
    r"\brequests\.(get|post|put|delete|head|request|Session)\b|urllib\.request|\burlopen\(|\bhttpx\.|"
    r"socket\.create_connection|socket\.socket\(|smtplib\.SMTP"
)


def test_no_unsafe_network_calls_outside_the_safe_client():
    offenders = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("tests/", "frontend/", "net/", "scripts/")) or "__pycache__" in rel or ".venv" in rel:
            continue
        if rel in _NETWORK_ALLOWLIST:
            continue
        for lineno, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if _NETWORK_PATTERNS.search(line) and not line.strip().startswith("#"):
                offenders.append(f"{rel}:{lineno}: {line.strip()[:80]}")
    assert not offenders, "Route these through net.fetcher.SafeFetcher or justify in the allow-list:\n" + "\n".join(offenders)


# ============================ P0-7: unsubscribe ============================

def _link(email, org="org_default", base=""):
    return ComplianceFooterBuilder.build_unsubscribe_url(email, org, base or "http://testserver").replace("http://testserver", "")


def test_unsubscribe_without_token_does_nothing(client):
    res = client.post("/api/compliance/unsubscribe?email=victim@target.com&org_id=org_default")
    assert res.status_code == 400
    assert KeyedSuppressionVault.is_suppressed("victim@target.com") is False


def test_unsubscribe_forged_token_does_nothing(client):
    res = client.post("/api/compliance/unsubscribe?email=victim@target.com&org_id=org_default&token=" + "0" * 64)
    assert res.status_code == 400
    assert KeyedSuppressionVault.is_suppressed("victim@target.com") is False


def test_token_is_bound_to_email_and_org(client):
    qs = parse_qs(urlparse(_link("alice@a.com")).query)
    token = qs["token"][0]
    # Re-using Alice's token for Bob, or for another tenant, must fail
    assert client.post(f"/api/compliance/unsubscribe?email=bob@a.com&org_id=org_default&token={token}").status_code == 400
    assert client.post(f"/api/compliance/unsubscribe?email=alice@a.com&org_id=org_other&token={token}").status_code == 400
    assert KeyedSuppressionVault.is_suppressed("bob@a.com") is False


def test_get_never_changes_state_and_post_with_valid_token_works(client):
    link = _link("carol@c.com")
    page = client.get(link)
    assert page.status_code == 200 and "Confirm unsubscribe" in page.text
    assert KeyedSuppressionVault.is_suppressed("carol@c.com") is False  # link scanners can't trigger it
    done = client.post(link)
    assert done.status_code == 200 and "You have been unsubscribed" in done.text
    assert KeyedSuppressionVault.is_suppressed("carol@c.com") is True


def test_unsubscribe_page_escapes_html(client):
    evil = "<script>alert(1)</script>@x.com"
    token = ComplianceFooterBuilder.generate_unsubscribe_token(evil, "org_default")
    res = client.get("/api/compliance/unsubscribe", params={"email": evil, "org_id": "org_default", "token": token})
    assert "<script>alert(1)</script>" not in res.text


def test_footer_headers_carry_a_verifiable_signed_link():
    _, html_footer, headers = ComplianceFooterBuilder.build_footer("dave@d.com", "org_x", base_url="https://agency.test")
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    url = headers["List-Unsubscribe"].strip("<>")
    qs = parse_qs(urlparse(url).query)
    assert ComplianceFooterBuilder.verify_unsubscribe_token(qs["email"][0], qs["org_id"][0], qs["token"][0])
    assert url.startswith("https://agency.test/api/compliance/unsubscribe?")
    assert "agency.example.com" not in html_footer


def test_suppression_hash_is_keyed_and_legacy_rows_still_honoured():
    import hashlib, hmac
    legacy = hmac.new(b"agencybd_enterprise_vault_salt_2026", b"old@legacy.com", hashlib.sha256).hexdigest()
    assert KeyedSuppressionVault.hash_entity("old@legacy.com") != legacy, "new hashes must not use the public salt"
    with get_db() as db:
        db.execute("INSERT INTO suppression_vault (entity_hash, entity_type, reason, source, org_id) VALUES (?,?,?,?,?)",
                   (legacy, "email", "legacy", "test", "org_default"))
        db.commit()
    assert KeyedSuppressionVault.is_suppressed("old@legacy.com") is True


# ============================ P0-5: policy fails closed ============================

OK_CTX = {"email_verification_status": "verified", "is_suppressed": False, "jurisdiction_allowed": True}


def test_policy_blocks_when_facts_are_missing():
    org = "org_policy"
    for missing in ("is_suppressed", "jurisdiction_allowed", "email_verification_status"):
        ctx = {k: v for k, v in OK_CTX.items() if k != missing}
        d = PolicyEngine.evaluate(org, "outbound_first_touch", ctx)
        assert d.allowed is False and d.autonomy_level == "NEVER", missing
    assert PolicyEngine.evaluate(org, "outbound_first_touch", {}).allowed is False


def test_policy_does_not_trust_a_false_suppression_claim_when_recipient_is_known():
    KeyedSuppressionVault.suppress("blocked@x.com", org_id="org_policy")
    d = PolicyEngine.evaluate("org_policy", "outbound_followup",
                              {**OK_CTX, "recipient_email": "blocked@x.com", "is_suppressed": False})
    assert d.allowed is False and d.rule_name == "no_send_suppressed"


def test_policy_computes_jurisdiction_from_country_code():
    d = PolicyEngine.evaluate("org_policy", "outbound_send",
                              {"email_verification_status": "verified", "recipient_email": "a@b.ca",
                               "is_suppressed": False, "country_code": "CA", "jurisdiction_allowed": True})
    assert d.allowed is False and d.rule_name == "jurisdiction_blocked"


def test_policy_allows_when_everything_is_established():
    PolicyEngine.set_tenant_policy("org_policy", "outbound_followup", "L2")
    d = PolicyEngine.evaluate("org_policy", "outbound_followup",
                              {"email_verification_status": "verified", "recipient_email": "ok@clean-example.com",
                               "country_code": "US"})
    assert d.allowed is True and d.requires_human_approval is False and d.autonomy_level == "L2"


def test_policy_explicit_negative_signal_blocks_any_action():
    d = PolicyEngine.evaluate("org_policy", "crm_sync", {"is_suppressed": True})
    assert d.allowed is False


# ============================ P0-8: UI authentication ============================

def test_every_ui_api_call_goes_through_the_authenticated_wrapper():
    bare = []
    for path in (ROOT / "frontend" / "src").rglob("*.ts*"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.endswith("lib/api.ts"):
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"(?<![A-Za-z_.])fetch\(", line):
                bare.append(f"{rel}:{lineno}: {line.strip()[:70]}")
    assert not bare, "Use apiFetch() so requests carry X-API-Key:\n" + "\n".join(bare)
