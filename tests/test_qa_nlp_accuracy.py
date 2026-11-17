"""Accuracy of the smart-search language parser on a labelled set of realistic queries (typos, other phrasing, nonsense).
Measured at QA time: intent accuracy 45/45 after fixing "sam.gov"; places 18/18. The thresholds below stop it getting worse."""

import pytest

from intel.nlp import parser as P

LOCAL = [("dentists in leeds", "Leeds", "dentist"), ("dentist leeds no website", "Leeds", "dentist"), ("plumbers in Manchester", "Manchester", "plumber"), ("restaurants in dubai", "Dubai", "restaurant"),
         ("restraunts in dubai with a slow site", "Dubai", "restaurant"), ("denists in dublin", "Dublin", "dentist"), ("gyms in lahore without a website", "Lahore", "gym"), ("law firms in london", "London", "lawyer"),
         ("hair salons in karachi", "Karachi", "salon"), ("accountants in glasgow", "Glasgow", "accountant"), ("bakeries in cork", "Cork", "bakery"), ("electricians in birmingham", "Birmingham", "electrician"),
         ("vets in bristol with bad websites", "Bristol", "vet"), ("clinics in islamabad", "Islamabad", "clinic"), ("cafes in Edinburgh no website", "Edinburgh", "cafe"), ("photographers in sydney", "Sydney", "photographer")]
JOBS = ["react developer remote", "react developer remote over $5k", "python freelance jobs", "wordpress projects under $2000", "shopify developer needed", "next.js contract work", "looking for a node developer",
        "freelance php jobs", "laravel developer remote", "seo freelance projects", "flutter app developer jobs", "vue.js jobs", "typescript contractor"]
TENDERS = ["government tenders for software in UK", "public tenders website development", "tenders for it services", "sam.gov software contracts", "ted tenders web", "government contracts for app development"]
NONSENSE = ["asdf qwer zxcv", "hello", "???", "the quick brown fox", "🙂🙂", "   ", "a", "how are you today"]


@pytest.mark.parametrize("q,place,business", LOCAL)
def test_local_searches_find_the_place_and_the_kind_of_business(q, place, business):
    r = P.parse(q)
    assert r["intent"] == "local" and (r["location"] or "").lower() == place.lower() and r["business"] and business in r["business"][0]


@pytest.mark.parametrize("q", JOBS)
def test_job_searches_are_recognised(q):
    assert P.parse(q)["intent"] == "jobs"


@pytest.mark.parametrize("q", TENDERS)
def test_tender_searches_are_recognised(q):
    assert P.parse(q)["intent"] == "tenders"


@pytest.mark.parametrize("q", NONSENSE)
def test_nonsense_is_never_guessed_at(q):
    assert (P.parse(q).get("intent") or "unknown") == "unknown"
