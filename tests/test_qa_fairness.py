"""Fairness and accuracy checks for the app's rule-based decisions. There is no trained model, so these test the rules: a prospect's score must
come from what was observed (site problems, presence, reviews, source, contact), never from the name, language, country or address."""

import pytest

from database.db import get_db
from database.models import LeadRepository
from intel import lead_priority
from intel.nlp import parser as P

ORG = "org_fair"
NAMES = [("Acme Dental Clinic", "acme-dental.example"), ("عيادة الدكتور أحمد", "ahmed-clinic.example"), ("张伟牙科诊所", "zhang-dental.example"),
         ("Ó Briain Fiaclóirí", "obriain.example"), ("Dr. Priya Sharma Dental", "priya.example"), ("Müller Zahnarzt GmbH", "mueller-zahn.example"),
         ("Aisha Khan Orthodontics", "aisha-ortho.example"), ("John Smith DDS", "jsmith-dds.example")]
ADDRESSES = ["12 High Street, Leeds, UK", "شارع الملك فهد، الرياض", "北京市朝阳区", "Main St, Lagos, Nigeria", "Calle Mayor 1, Madrid", None]


def make(name, domain, address=None, rating=4.2, reviews=30, source="google_maps", phone=None):
    lead = LeadRepository.create_or_get_lead(name, domain, phone=phone, address=address, rating=rating, reviews_count=reviews, source_channel=source, org_id=ORG)
    return lead["id"]


def score(lead_id):
    return lead_priority.score_lead(lead_id, ORG, persist=False)


def test_the_name_language_or_origin_of_a_business_never_changes_its_score():
    scores = {score(make(n, d))["score"] for n, d in NAMES}
    assert len(scores) == 1, f"scores differed by name alone: {scores}"


def test_the_address_and_country_never_change_the_score():
    scores = {score(make("Same Dental", f"same{i}.example", address=a))["score"] for i, a in enumerate(ADDRESSES)}
    assert len(scores) == 1, f"scores differed by address alone: {scores}"


def test_the_country_of_a_phone_number_never_changes_the_score_but_having_one_may():
    with_phone = {score(make("Phone Co", f"phone{i}.example", phone=p))["score"] for i, p in enumerate(["+923404095953", "+353861234567", "+14155552671", "+8613800138000"])}
    assert len(with_phone) == 1                                       # four countries, one score
    without = score(make("No Phone Co", "nophone.example", phone=None))
    assert without["score"] <= next(iter(with_phone))                  # being reachable can only help, and the reasons say so


def test_only_observed_facts_move_the_score_and_every_point_is_explained():
    base = make("Facts Co", "facts.example", rating=4.0, reviews=10)
    better_rated = make("Facts Co 2", "facts2.example", rating=4.9, reviews=400)
    a, b = score(base), score(better_rated)
    for r in (a, b):
        assert r["reasons"] and all(isinstance(x, str) and x for x in r["reasons"])
        assert 0 <= r["score"] <= 100 and r["band"] in ("hot", "warm", "cold")


@pytest.mark.parametrize("a,b", [("dentists in leeds", "DENTISTS IN LEEDS"), ("dentists in leeds", "  dentists   in   leeds  "), ("react developer remote", "React Developer REMOTE")])
def test_search_understanding_ignores_case_and_spacing(a, b):
    x, y = P.parse(a), P.parse(b)
    for key in ("intent", "business", "skills", "location"):
        assert x[key] == y[key]


def test_search_understanding_is_not_skewed_by_the_place_name_it_has_never_seen():
    places = ["Leeds", "Lagos", "Lahore", "Lviv", "Ljubljana", "Łódź", "Quetta", "Zürich", "São Paulo", "Nairobi", "Hà Nội", "Wrocław"]
    for place in places:
        r = P.parse(f"dentists in {place}")
        assert r["intent"] == "local" and r["business"] == ["dentist"] and r["location"], f"{place}: {r['intent']} {r['location']}"
