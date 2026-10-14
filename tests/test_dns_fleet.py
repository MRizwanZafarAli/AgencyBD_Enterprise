"""DNS guidance generator and live verification (DNS is stubbed; no network)."""

import pytest

import agents.deliverability_sentinel as ds
from config.dns_fleet_configurator import DNSFleetConfigurator
from outbound.providers.registry import ramp_cap


def test_google_workspace_records_never_contain_placeholder_keys():
    r = DNSFleetConfigurator.generate_dns_records("apexcore-labs.com", esp_provider="google_workspace")
    assert r["domain"] == "apexcore-labs.com" and r["spf"]["value"].startswith("v=spf1 include:_spf.google.com")
    assert len(r["mx"]) == 5
    assert r["dkim"]["value"] is None and "Google Admin" in r["dkim"]["how_to_get_value"], "the DKIM key comes from the provider, never invented"
    assert "publickey" not in str(r) and "custom_tracking_cname" not in r and "bimi" not in r


def test_dmarc_starts_in_monitor_mode_and_validates_policy():
    assert "p=none" in DNSFleetConfigurator.generate_dns_records("x.example")["dmarc"]["value"]
    assert "p=reject" in DNSFleetConfigurator.generate_dns_records("x.example", dmarc_policy="reject")["dmarc"]["value"]
    with pytest.raises(ValueError):
        DNSFleetConfigurator.generate_dns_records("x.example", dmarc_policy="maybe")
    with pytest.raises(ValueError):
        DNSFleetConfigurator.generate_dns_records("x.example", esp_provider="somebody")
    with pytest.raises(ValueError):
        DNSFleetConfigurator.generate_dns_records("-bad domain")


def test_microsoft_records():
    r = DNSFleetConfigurator.generate_dns_records("apexcore-hq.io", esp_provider="microsoft_365")
    assert "spf.protection.outlook.com" in r["spf"]["value"] and "mail.protection.outlook.com" in r["mx"][0]["value"]
    assert r["dkim"]["type"] == "CNAME" and "<your-tenant>" in r["dkim"]["value"]


def test_live_audit_reports_real_lookups(monkeypatch):
    records = {"good.example": ["v=spf1 -all"], "_dmarc.good.example": ["v=DMARC1; p=quarantine"], "google._domainkey.good.example": ["v=DKIM1; p=KEY"]}
    monkeypatch.setattr(ds, "lookup_txt", lambda n: records.get(n, []))
    monkeypatch.setattr(ds, "lookup_cname", lambda n: [])
    monkeypatch.setattr(ds, "lookup_mx", lambda d: ["mx.good.example"])
    audit = DNSFleetConfigurator.audit_live_dns("good.example")
    assert audit["mx_active"] and audit["spf_active"] and audit["dkim_active"] and audit["dmarc_active"] and audit["ready_for_outreach"]
    monkeypatch.setattr(ds, "lookup_txt", lambda n: None)
    monkeypatch.setattr(ds, "lookup_cname", lambda n: None)
    monkeypatch.setattr(ds, "lookup_mx", lambda d: None)
    unknown = DNSFleetConfigurator.audit_live_dns("good.example")
    assert unknown["spf_active"] is None and not unknown["ready_for_outreach"] and len(unknown["unverifiable_checks"]) == 4


def test_warmup_curve_matches_the_ramp_the_registry_enforces():
    curve = DNSFleetConfigurator.generate_21_day_warmup_curve(daily_target_cap=40)
    assert curve[0] == {"day": 1, "send_volume": 5} and curve[-1]["day"] == 22 and curve[-1]["send_volume"] == 40
    assert all("target_replies" not in d for d in curve), "no engagement targets: warm-up is organic, not faked"
    # the generator and the enforcement code can never drift apart
    from datetime import datetime, timedelta, timezone
    for entry in curve[:-1]:
        created = (datetime.now(timezone.utc) - timedelta(days=entry["day"] - 1)).strftime("%Y-%m-%d %H:%M:%S")
        assert ramp_cap(created, 40, False) == entry["send_volume"]
