"""The contact finder reports only what a company's own pages say, with the page each item came from."""

import pytest

from intel import contacts
from webfake import page

HOME = '<html><body><a href="/team">Our team</a><a href="/contact">Contact</a><a href="https://other.example/team">Partner</a><a href="https://www.linkedin.com/company/acme-co">in</a></body></html>'
TEAM = """<html><body>
<div class="member"><h3>Jane Doe</h3><p>Chief Executive Officer</p><a href="https://www.linkedin.com/in/janedoe">LinkedIn</a></div>
<div class="member"><h3>Raj Patel</h3><span>Head of Engineering</span></div>
<div class="member"><h3>Our Team</h3><p>Director of nothing</p></div>
<div class="member"><h3>Sam Lee</h3><p>Loves hiking</p></div>
<script type="application/ld+json">{"@type":"Person","name":"Mia Chen","jobTitle":"Founder","email":"mailto:mia@acme.example","sameAs":["https://www.linkedin.com/in/miachen"]}</script>
</body></html>"""
CONTACT = '<html><body><a href="mailto:info@acme.example">Email us</a> raj.patel@acme.example, someone@gmail.com, hello@acme.example. <img src="logo@2x.png"></body></html>'


@pytest.fixture
def site(web):
    web["acme.example"] = {"html": HOME}
    web["acme.example/team"] = {"html": TEAM}
    web["acme.example/contact"] = {"html": CONTACT}
    return web


def test_people_need_a_name_and_a_title_written_together(site):
    out = contacts.find_contacts("acme.example")
    people = {c["name"]: c for c in out["candidates"] if c["kind"] == "person"}
    assert set(people) == {"Jane Doe", "Raj Patel", "Mia Chen"}                 # not "Our Team", not Sam Lee (no job title)
    assert people["Jane Doe"]["title"] == "Chief Executive Officer" and people["Jane Doe"]["linkedin_url"].endswith("/in/janedoe")
    assert people["Mia Chen"]["email"] == "mia@acme.example" and "schema.org" in people["Mia Chen"]["evidence"]
    assert all(c["source_url"].startswith("https://acme.example") for c in out["candidates"])


def test_emails_are_same_domain_only_and_linked_to_a_person_only_when_the_name_matches(site):
    out = contacts.find_contacts("acme.example")
    by_email = {c["email"]: c for c in out["candidates"] if c["email"]}
    assert "someone@gmail.com" not in by_email and not any("logo" in e for e in by_email)
    assert by_email["raj.patel@acme.example"]["kind"] == "person" and by_email["raj.patel@acme.example"]["name"] == "Raj Patel"
    assert by_email["info@acme.example"]["kind"] == "generic_email" and by_email["hello@acme.example"]["kind"] == "generic_email"
    jane = next(c for c in out["candidates"] if c["name"] == "Jane Doe")
    assert jane["email"] is None and "no email published" in jane["evidence"]       # an address is never guessed


def test_ranking_puts_decision_makers_first_and_generic_addresses_last(site):
    kinds = [(c["kind"], c["rank"]) for c in contacts.find_contacts("acme.example")["candidates"]]
    ranks = [r for _, r in kinds]
    assert ranks == sorted(ranks, reverse=True) and kinds[0][1] == 100 and kinds[-1][0] == "generic_email"


def test_it_follows_only_the_companys_own_links_and_reads_a_bounded_number_of_pages(site):
    out = contacts.find_contacts("acme.example")
    assert all("other.example" not in p for p in out["pages_checked"]) and len(out["pages_checked"]) <= contacts.MAX_PAGES
    assert out["company_linkedin"].endswith("/company/acme-co")


def test_a_site_that_cannot_be_read_returns_nothing_and_says_so(web):
    out = contacts.find_contacts("unreachable.example")
    assert out["candidates"] == [] and out["pages_checked"] == [] and any("No page could be read" in l for l in out["limitations"])


def test_endpoint_is_tenant_scoped_and_refuses_businesses_without_a_website(client, make_key, site):
    from database.models import LeadRepository
    lead = LeadRepository.create_or_get_lead("Acme", "acme.example", org_id="org_cf")
    nosite = LeadRepository.create_or_get_lead("Nowhere Cafe", "nosite-x.invalid", org_id="org_cf")
    h = make_key("growth_lead", "org_cf")
    res = client.post(f"/api/clients/{lead['id']}/find_contacts", headers=h)
    assert res.status_code == 200 and {c["name"] for c in res.json()["candidates"][:2]} == {"Jane Doe", "Mia Chen"}   # both rank 100
    assert client.post(f"/api/clients/{nosite['id']}/find_contacts", headers=h).status_code == 422
    assert client.post(f"/api/clients/{lead['id']}/find_contacts", headers=make_key("growth_lead", "org_cf_other")).status_code in (403, 404)
    assert client.post(f"/api/clients/{lead['id']}/find_contacts", headers=make_key("auditor", "org_cf")).status_code == 403
