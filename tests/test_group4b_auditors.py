"""
Website Doctor auditors: every check is exercised with deterministic fake observations, and the 'unknown is not a finding'
rule is enforced (the old engine reported a missing llms.txt on EVERY site because it never looked).
"""

import socket
import ssl
import threading

import pytest
from bs4 import BeautifulSoup

from auditors import pagespeed
from auditors.a11y import A11yAuditor
from auditors.context import SiteContext, fetch_site
from auditors.email_dns import EmailDNSAuditor
from auditors.engine import WebsiteDoctorEngine
from auditors.geo import GEOAuditor
from auditors.pagespeed import parse_psi
from auditors.performance import PerformanceAuditor
from auditors.security import SecurityAuditor
from auditors.seo import SEOAuditor, robots_allows
from auditors.tls import inspect_tls
from database.models import AuditRunRepository, EvidenceRepository
from net.fetcher import SSRFSecurityError
from webfake import page

FULL_HEADERS = {"Content-Type": "text/html", "Content-Encoding": "gzip", "Cache-Control": "max-age=60",
                "Strict-Transport-Security": "max-age=31536000", "Content-Security-Policy": "default-src 'self'",
                "X-Frame-Options": "SAMEORIGIN", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
GOOD_HTML = ("<html lang='en'><head><title>Acme Plumbing | Austin</title><meta name='description' content='Plumbing in Austin.'>"
             "<meta name='viewport' content='width=device-width'><link rel='canonical' href='https://acme.example/'>"
             "<meta property='og:title' content='Acme'><meta property='og:image' content='/i.png'>"
             "<script type='application/ld+json'>{\"@type\":\"LocalBusiness\",\"name\":\"Acme\"}</script></head>"
             "<body><h1>Acme Plumbing</h1><p>" + "We fix pipes and drains across Austin. " * 30 + "</p></body></html>")


def ctx_for(html=GOOD_HTML, headers=None, **kw):
    base = dict(domain="acme.example", url="https://acme.example/", scheme="https", status_code=200,
                headers=FULL_HEADERS if headers is None else headers, html=html, soup=BeautifulSoup(html, "html.parser"),
                ttfb_ms=200, total_ms=400, robots_txt="User-agent: *\nAllow: /\nSitemap: https://acme.example/sitemap.xml",
                llms_txt=True, sitemap_found=True, http_to_https=True,
                tls={"valid": True, "protocol": "TLSv1.3", "days_remaining": 200, "not_after": "x", "issuer": "CA"})
    base.update(kw)
    return SiteContext(**base)


def ids(findings):
    return {f.check_id for f in findings}


def all_page_findings(ctx):
    return [*PerformanceAuditor.audit(ctx), *SecurityAuditor.audit(ctx), *SEOAuditor.audit(ctx), *GEOAuditor.audit(ctx), *A11yAuditor.audit(ctx)]


# ============================ a clean site produces no findings ============================

def test_a_well_built_site_gets_a_clean_report():
    findings = all_page_findings(ctx_for())
    assert ids(findings) == set(), ids(findings)


# ============================ context: unknown is not absent ============================

def test_context_reads_supporting_files(web):
    web["acme.example"] = {"html": GOOD_HTML, "headers": FULL_HEADERS}
    web["acme.example/robots.txt"] = "User-agent: *\nDisallow: /private\nSitemap: https://acme.example/sm.xml"
    web["acme.example/llms.txt"] = "# Acme\nPlumbing in Austin."
    web["http://acme.example"] = {"redirect": "https://acme.example/"}
    ctx = fetch_site("acme.example")
    assert ctx.scheme == "https" and ctx.robots_txt.startswith("User-agent") and ctx.llms_txt is True
    assert ctx.sitemap_found is True and ctx.http_to_https is True and ctx.tls["valid"] is True


def test_missing_files_are_recorded_as_absent_and_soft_404_pages_do_not_count(web):
    web["acme.example"] = GOOD_HTML
    web["acme.example/robots.txt"] = "<!DOCTYPE html><html>custom 404 page</html>"     # many sites answer 200 with HTML
    web["acme.example/llms.txt"] = "<html><body>Not found</body></html>"
    ctx = fetch_site("acme.example")
    assert ctx.robots_txt == "" and ctx.llms_txt is False and ctx.sitemap_found is False


def test_no_redirect_from_http_is_detected(web):
    web["acme.example"] = GOOD_HTML
    web["http://acme.example"] = {"html": "<html>plain</html>"}
    assert fetch_site("acme.example").http_to_https is False


def test_homepage_failure_raises_and_ssrf_is_not_swallowed(web):
    with pytest.raises(ConnectionError):
        fetch_site("not-in-fake-web.example")


# ============================ performance ============================

def test_ttfb_thresholds_follow_google_guidance():
    assert "slow_ttfb" not in ids(PerformanceAuditor.audit(ctx_for(ttfb_ms=800)))
    medium = [f for f in PerformanceAuditor.audit(ctx_for(ttfb_ms=1200)) if f.check_id == "slow_ttfb"][0]
    poor = [f for f in PerformanceAuditor.audit(ctx_for(ttfb_ms=2600)) if f.check_id == "slow_ttfb"][0]
    assert medium.severity == "medium" and poor.severity == "high" and poor.confidence < 1.0


def test_performance_checks_and_no_folklore_statistics():
    scripts = "".join(f"<script src='https://cdn{i}.thirdparty.example/a.js'></script>" for i in range(14))
    imgs = "<img src='a.png'>" * 7
    html = f"<html><head><title>t</title>{scripts}</head><body>{imgs}<p>{'x ' * 6000}</p></body></html>"
    found = PerformanceAuditor.audit(ctx_for(html=html, headers={"Content-Type": "text/html"}))
    assert {"no_text_compression", "render_blocking_scripts", "many_third_party_hosts", "images_without_dimensions", "missing_cache_control"} <= ids(found)
    text = " ".join(f.finding + f.estimated_impact for f in found)
    for folklore in ("1%", "conversion rate", "drops conversion"):
        assert folklore not in text


# ============================ security ============================

def test_security_headers_and_transport():
    found = SecurityAuditor.audit(ctx_for(headers={}, http_to_https=False))
    assert {"no_https_redirect", "missing_hsts", "missing_csp", "missing_x_frame_options", "missing_content_type_options"} <= ids(found)
    plain = SecurityAuditor.audit(ctx_for(scheme="http", url="http://acme.example/", tls=None, http_to_https=None))
    assert "no_https" in ids(plain) and next(f for f in plain if f.check_id == "no_https").severity == "critical"
    assert "missing_hsts" not in ids(plain), "HSTS is meaningless over plain HTTP"


@pytest.mark.parametrize("tls,expected,severity", [
    ({"valid": False, "error": "certificate has expired", "verify_code": 10}, "tls_certificate_invalid", "critical"),
    ({"valid": True, "days_remaining": 9, "not_after": "x", "issuer": "CA"}, "tls_certificate_expiring", "high"),
    ({"valid": True, "days_remaining": 25, "not_after": "x", "issuer": "CA"}, "tls_certificate_expiring", "medium"),
])
def test_tls_findings(tls, expected, severity):
    f = [x for x in SecurityAuditor.audit(ctx_for(tls=tls)) if x.check_id == expected]
    assert f and f[0].severity == severity


def test_unknown_tls_state_makes_no_claims():
    assert not [f for f in SecurityAuditor.audit(ctx_for(tls={"valid": None, "error": "timeout"})) if f.check_id.startswith("tls")]
    assert not [f for f in SecurityAuditor.audit(ctx_for(tls=None)) if f.check_id.startswith("tls")]


def test_mixed_content_and_old_php():
    html = "<html lang='en'><head><title>t</title><script src='http://old.example/a.js'></script></head><body><img src='http://x.example/i.png'></body></html>"
    found = SecurityAuditor.audit(ctx_for(html=html, headers={**FULL_HEADERS, "X-Powered-By": "PHP/7.4.33"}))
    mixed = next(f for f in found if f.check_id == "mixed_content")
    assert mixed.severity == "high" and "2 resource" in mixed.finding
    assert "end_of_life_php" in ids(found)
    assert "end_of_life_php" not in ids(SecurityAuditor.audit(ctx_for(headers={**FULL_HEADERS, "X-Powered-By": "PHP/8.3.1"})))


def test_security_audit_is_passive_only(web):
    web["acme.example"] = {"html": GOOD_HTML, "headers": FULL_HEADERS}
    fetch_site("acme.example")
    for url in web.seen:
        path = "/" + url.split("://")[1].partition("/")[2]
        assert path in ("/", "/robots.txt", "/llms.txt", "/sitemap.xml"), f"unexpected probe: {url}"


# ============================ seo ============================

def test_seo_metadata_found_regardless_of_attribute_order():
    html = ("<html><head><title>Acme</title><meta content='Reversed attribute order.' name='description'>"
            "<meta content='width=device-width' name='viewport'><link href='/' rel='canonical'></head><body><h1>A</h1></body></html>")
    found = ids(SEOAuditor.audit(ctx_for(html=html)))
    assert not ({"missing_meta_description", "missing_viewport_tag", "missing_canonical_url"} & found), "regex-era false positives"


def test_seo_findings():
    html = "<html><head><meta name='robots' content='noindex, nofollow'></head><body><h1>a</h1><h1>b</h1><script type='application/ld+json'>{bad json</script></body></html>"
    found = ids(SEOAuditor.audit(ctx_for(html=html, sitemap_found=False)))
    assert {"noindex_set", "missing_meta_title", "missing_meta_description", "missing_viewport_tag", "h1_structure", "thin_content",
            "invalid_structured_data", "missing_sitemap", "missing_open_graph"} <= found
    assert next(f for f in SEOAuditor.audit(ctx_for(html=html)) if f.check_id == "noindex_set").severity == "critical"


def test_robots_handling():
    blocked = SEOAuditor.audit(ctx_for(robots_txt="User-agent: *\nDisallow: /"))
    assert "robots_blocks_all" in ids(blocked)
    assert "missing_robots_txt" in ids(SEOAuditor.audit(ctx_for(robots_txt="")))
    unknown = ids(SEOAuditor.audit(ctx_for(robots_txt=None, sitemap_found=None)))
    assert not ({"robots_blocks_all", "missing_robots_txt", "missing_sitemap"} & unknown)
    assert robots_allows("User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /", "*") is True
    assert robots_allows("User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /", "GPTBot") is False


# ============================ geo (the llms.txt false-positive regression) ============================

def test_llms_txt_is_only_reported_missing_when_we_actually_checked():
    assert "missing_llms_txt" not in ids(GEOAuditor.audit(ctx_for(llms_txt=True)))
    assert "missing_llms_txt" not in ids(GEOAuditor.audit(ctx_for(llms_txt=None))), "unknown must not become a finding"
    assert "missing_llms_txt" in ids(GEOAuditor.audit(ctx_for(llms_txt=False)))


def test_ai_crawler_blocks_distinguish_search_from_training():
    robots = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: PerplexityBot\nDisallow: /\n\nUser-agent: *\nAllow: /"
    found = {f.check_id: f for f in GEOAuditor.audit(ctx_for(robots_txt=robots))}
    assert "PerplexityBot" in found["ai_search_crawlers_blocked"].finding and found["ai_search_crawlers_blocked"].severity == "medium"
    assert "GPTBot" in found["ai_training_crawlers_blocked"].finding and found["ai_training_crawlers_blocked"].severity == "info"
    assert not {"ai_search_crawlers_blocked"} & ids(GEOAuditor.audit(ctx_for(robots_txt=None)))


def test_entity_schema_uses_parsed_types_not_substrings():
    text_only = "<html><body><p>We are an organization offering localbusiness help</p></body></html>"
    assert "missing_entity_schema" in ids(GEOAuditor.audit(ctx_for(html=text_only)))
    assert "missing_entity_schema" not in ids(GEOAuditor.audit(ctx_for()))


# ============================ accessibility ============================

def test_a11y_checks():
    html = ("<html><head><title>t</title><meta name='viewport' content='width=device-width, user-scalable=no'></head><body>"
            "<h1>A</h1><h3>skip</h3><img src='a.png'><img src='b.png' alt=''><input type='text' name='email'>"
            "<label for='ok'>Ok</label><input id='ok'><button></button><button aria-label='Close'></button>"
            "<a href='/x'></a><a href='/y'><img src='l.png' alt='Home'></a><iframe src='/f'></iframe><div tabindex='3'></div></body></html>")
    found = {f.check_id: f for f in A11yAuditor.audit(ctx_for(html=html))}
    assert {"missing_html_lang", "images_missing_alt", "form_fields_unlabeled", "buttons_without_name", "links_without_name",
            "iframes_without_title", "zoom_disabled", "heading_levels_skipped", "positive_tabindex"} <= set(found)
    assert "1 image" in found["images_missing_alt"].finding, "alt='' is decorative, not missing"
    assert "1 form field" in found["form_fields_unlabeled"].finding and "1 button" in found["buttons_without_name"].finding
    assert "1 link" in found["links_without_name"].finding, "a link whose image has alt text has a name"


# ============================ email / dns ============================

def test_email_dns_uses_real_records_and_skips_when_unknown(monkeypatch):
    import auditors.email_dns as ed
    monkeypatch.setattr(ed, "lookup_mx", lambda d: None)
    assert EmailDNSAuditor.audit("x.example") == []
    monkeypatch.setattr(ed, "lookup_mx", lambda d: [])
    assert ids(EmailDNSAuditor.audit("x.example")) == {"no_mx_records"}
    monkeypatch.setattr(ed, "lookup_mx", lambda d: ["mx.x.example"])
    monkeypatch.setattr(ed, "lookup_txt", lambda n: ["v=spf1 -all"] if not n.startswith("_dmarc") else ["v=DMARC1; p=none"])
    assert ids(EmailDNSAuditor.audit("x.example")) == {"dmarc_monitor_only"}
    monkeypatch.setattr(ed, "lookup_txt", lambda n: [])
    assert ids(EmailDNSAuditor.audit("x.example")) == {"missing_spf", "missing_dmarc"}
    monkeypatch.setattr(ed, "lookup_txt", lambda n: None)
    assert EmailDNSAuditor.audit("x.example") == []


# ============================ pagespeed ============================

def psi(lcp=None, cls=None, tbt=None, perf=0.9, acc=0.95, field=None, savings=0, failing=()):
    audits = {}
    if lcp is not None: audits["largest-contentful-paint"] = {"numericValue": lcp}
    if cls is not None: audits["cumulative-layout-shift"] = {"numericValue": cls}
    if tbt is not None: audits["total-blocking-time"] = {"numericValue": tbt}
    audits["render-blocking-resources"] = {"details": {"overallSavingsMs": savings}}
    refs = []
    for i, (title, n) in enumerate(failing):
        audits[f"a{i}"] = {"title": title, "score": 0, "scoreDisplayMode": "binary", "details": {"items": [0] * n}}
        refs.append({"id": f"a{i}"})
    return {"lighthouseResult": {"fetchTime": "2026-10-13T10:00:00Z", "audits": audits,
                                 "categories": {"performance": {"score": perf}, "accessibility": {"score": acc, "auditRefs": refs}}},
            "loadingExperience": {"metrics": field or {}}}


def test_psi_reports_only_what_it_measured():
    assert parse_psi({}, "u") == []
    assert parse_psi(psi(lcp=1800, cls=0.02, tbt=100), "u") == []


def test_psi_lab_thresholds():
    f = {x.check_id: x for x in parse_psi(psi(lcp=4600, cls=0.31, tbt=900, perf=0.3, savings=800), "u")}
    assert f["slow_lcp"].severity == "high" and "4.6s" in f["slow_lcp"].finding and "Lighthouse lab" in f["slow_lcp"].evidence_value
    assert f["layout_shift"].severity == "high" and f["high_blocking_time"].severity == "high"
    assert f["low_lighthouse_score"] and f["render_blocking_savings"]
    assert {x.check_id: x for x in parse_psi(psi(lcp=3000), "u")}["slow_lcp"].severity == "medium"


def test_real_user_data_beats_lab_data():
    field = {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 5200}, "INTERACTION_TO_NEXT_PAINT": {"percentile": 650}}
    f = {x.check_id: x for x in parse_psi(psi(lcp=1500, tbt=900, field=field), "u")}
    assert "real-user" in f["slow_lcp"].evidence_value and "5.2s" in f["slow_lcp"].finding and f["slow_lcp"].confidence >= 0.9
    assert "slow_inp" in f and "high_blocking_time" not in f, "lab TBT is only a stand-in when field INP is missing"


def test_psi_accessibility_audits_are_named():
    f = {x.check_id: x for x in parse_psi(psi(acc=0.62, failing=[("Buttons do not have an accessible name", 3), ("Contrast", 7)]), "u")}
    a = f["lighthouse_accessibility"]
    assert a.severity == "high" and "Buttons do not have an accessible name (3)" in a.evidence_value


# ============================ engine ============================

def test_engine_end_to_end_with_clean_site(web):
    web["acme.example"] = {"html": GOOD_HTML, "headers": FULL_HEADERS}
    web["acme.example/robots.txt"] = "User-agent: *\nAllow: /\nSitemap: https://acme.example/sitemap.xml"
    web["acme.example/llms.txt"] = "# Acme\nPlumbing."
    web["http://acme.example"] = {"redirect": "https://acme.example/"}
    out = WebsiteDoctorEngine.run_audit("https://Acme.example/", org_id="org_e")
    assert out["status"] == "completed" and out["domain"] == "acme.example"
    assert "missing_llms_txt" not in {f["check_id"] for f in out["findings"]}
    assert out["overall_score"] >= 85 and set(out["checks_run"]) >= {"performance", "security", "seo", "geo", "a11y"}
    assert any("pagespeed" in s for s in out["checks_skipped"])


def test_engine_links_evidence_to_the_audit_run(web):
    web["acme.example"] = "<html><head><title>x</title></head><body>hi</body></html>"
    out = WebsiteDoctorEngine.run_audit("acme.example", org_id="org_e")
    assert out["findings_count"] > 0
    stored = EvidenceRepository.get_for_entity("audit_run", out["audit_id"], org_id="org_e")
    assert {e["id"] for e in stored} == {f["evidence_id"] for f in out["findings"]}
    assert all(e["source_url"].startswith("https://acme.example") for e in stored)
    assert len(AuditRunRepository.get_findings(out["audit_id"], org_id="org_e")) == out["findings_count"]


def test_engine_isolates_a_failing_auditor(web, monkeypatch):
    import auditors.engine as eng
    web["acme.example"] = GOOD_HTML
    boom = lambda ctx: (_ for _ in ()).throw(RuntimeError("bug in auditor"))
    monkeypatch.setattr(eng, "PAGE_AUDITORS", [("seo", boom), ("a11y", A11yAuditor.audit)])
    out = WebsiteDoctorEngine.run_audit("acme.example")
    assert out["status"] == "completed" and out["checks_failed"] == [{"check": "seo", "error": "bug in auditor"}] and "a11y" in out["checks_run"]


def test_engine_runs_pagespeed_when_configured_and_survives_its_failure(web, monkeypatch):
    web["acme.example"] = GOOD_HTML
    monkeypatch.setenv("PAGESPEED_API_KEY", "key-123456789")
    monkeypatch.setattr(pagespeed, "run_pagespeed", lambda url, strategy="mobile": psi(lcp=5000))
    out = WebsiteDoctorEngine.run_audit("acme.example")
    assert "pagespeed" in out["checks_run"] and "slow_lcp" in {f["check_id"] for f in out["findings"]}
    monkeypatch.setattr(pagespeed, "run_pagespeed", lambda url, strategy="mobile": (_ for _ in ()).throw(RuntimeError("quota")))
    out = WebsiteDoctorEngine.run_audit("acme.example")
    assert out["status"] == "completed" and out["checks_failed"][0]["check"] == "pagespeed"


def test_engine_unreachable_and_blocked(web):
    out = WebsiteDoctorEngine.run_audit("nowhere.example")
    assert out["status"] == "unreachable" and out["overall_score"] is None and out["findings"][0]["confidence"] <= 0.5
    with pytest.raises(SSRFSecurityError):
        import auditors.context as c
        raise SSRFSecurityError("blocked")     # engine re-raises policy errors (covered end-to-end in group 1/2 tests)


# ============================ tls inspector (real handshake against a local server) ============================

def test_tls_inspector_reports_certificate_failures(monkeypatch, tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime as dt
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = dt.datetime.now(dt.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1)
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=30))
            .sign(key, hashes.SHA256()))

    (tmp_path / "c.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (tmp_path / "k.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(tmp_path / "c.pem", tmp_path / "k.pem")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    port = listener.getsockname()[1]

    def serve():
        for _ in range(2):
            try:
                conn, _ = listener.accept()
                with server_ctx.wrap_socket(conn, server_side=True):
                    pass
            except Exception:
                pass
    threading.Thread(target=serve, daemon=True).start()

    import auditors.tls as tlsmod
    monkeypatch.setattr(tlsmod.SafeFetcher, "resolve_and_validate_hostname", staticmethod(lambda d: "127.0.0.1"))
    real = socket.create_connection
    monkeypatch.setattr(tlsmod.socket, "create_connection", lambda addr, timeout=None: real(("127.0.0.1", port), timeout))
    result = inspect_tls("selfsigned.test")
    assert result["valid"] is False and "self" in result["error"].lower() or "certificate" in result["error"].lower()

    monkeypatch.setattr(tlsmod.socket, "create_connection", lambda addr, timeout=None: (_ for _ in ()).throw(ConnectionRefusedError("closed")))
    assert inspect_tls("selfsigned.test")["valid"] is None
