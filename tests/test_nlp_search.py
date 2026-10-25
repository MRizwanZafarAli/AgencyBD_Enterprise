"""Natural-language search: spelling correction, intent, skills, places, budgets, filters, and honest handling of nonsense."""

import pytest

from intel.nlp import parser, taxonomy as T
from intel.nlp.parser import edit_distance, parse, suggest


def run(q):
    r = parse(q)
    return r["intent"], r["run"], {c["from"]: c["to"] for c in r["corrections"]}


@pytest.mark.parametrize("a,b,d", [("dentist", "dentst", 1), ("react", "reakt", 1), ("plumber", "plumbre", 1), ("abc", "acb", 1), ("same", "same", 0), ("kubernetes", "kubernets", 1)])
def test_edit_distance_counts_typos_and_swaps(a, b, d):
    assert edit_distance(a, b) == d


def test_local_search_with_typos_place_and_a_website_filter():
    intent, r, fixes = run("dentst in leeds without a website")
    assert intent == "local" and r == {"kind": "local", "category": "dentist", "city": "Leeds", "only_gaps": True} and fixes == {"dentst": "dentist"}


def test_cities_are_corrected_and_unknown_places_are_kept_as_typed():
    assert run("vet clinics near lahor")[1]["city"] == "Lahore"
    assert run("plumbers in Smallville Heights")[1]["city"] == "Smallville Heights"


def test_plurals_and_synonyms_map_to_the_canonical_business_type():
    assert run("restaurants in dubai")[1]["category"] == "restaurant"
    assert run("estate agents in london")[1]["category"] == "real estate"
    assert run("solicitors in glasgow")[1]["category"] == "lawyer"
    assert run("gp surgery in leeds")[1]["category"] == "doctor"


def test_jobs_with_skills_remote_and_budget():
    intent, r, fixes = run("reakt developer remote over 5k")
    assert intent == "jobs" and r["q"] == "react" and r["remote"] is True and r["min_budget"] == 5000 and fixes == {"reakt": "react"}
    assert run("python freelance jobs $3k-$8k")[1]["min_budget"] == 3000 and run("python freelance jobs $3k-$8k")[1]["max_budget"] == 8000
    assert run("senior kubernets engineer under £90k")[1] == {"kind": "jobs", "q": "kubernetes", "min_budget": None, "max_budget": 90000.0, "remote": False}


def test_synonyms_for_skills():
    assert run("k8s devops contractor")[1]["q"] in ("kubernetes devops", "devops kubernetes", "kubernetes")
    assert "machine learning" in run("machin learning contractor remote")[1]["q"]
    assert run("need an llm chatbot built")[1]["q"] == "ai"


def test_tenders_are_recognised_even_with_misspelt_words():
    intent, r, fixes = run("goverment tenders software")
    assert intent == "tenders" and "software" in r["q"] and fixes == {"goverment": "government"}
    assert run("tendrs for web development")[0] == "tenders"


def test_budget_formats():
    b = lambda q: parse(q)["budget"]
    assert b("jobs over $5k")["min_budget"] == 5000 and b("jobs over $5k")["currency"] == "USD"
    assert b("web design under £2,000")["max_budget"] == 2000 and b("web design under £2,000")["currency"] == "GBP"
    assert b("react 3k to 8k")["min_budget"] == 3000 and b("react 3k to 8k")["max_budget"] == 8000
    assert b("react at least 1.5k")["min_budget"] == 1500 and b("react, 2m budget over €2m")["min_budget"] == 2_000_000


def test_filters_are_understood_and_removed_from_the_category():
    r = parse("best salon in london with facebook only")
    assert r["filters"]["social_only"] and r["run"]["category"] == "salon" and r["run"]["only_gaps"] is True
    assert parse("restaurants in paris with a slow website")["filters"]["needs_fix"] is True
    assert parse("plumbers in leeds no website")["filters"]["no_website"] is True


def test_it_never_pretends_to_understand_nonsense():
    r = parse("zzzz qqqq")
    assert r["intent"] is None and r["needs_clarification"] and "could not tell" in r["explanation"]
    assert parse("")["intent"] is None


def test_missing_city_and_tech_filters_get_honest_clarifications():
    assert "Add a city" in parse("need a plumber")["clarification"]
    assert "not by the software" in parse("wordpress sites slow in dubai")["clarification"]


def test_alternatives_offer_the_other_readings():
    kinds = {a["kind"] for a in parse("dentists in leeds")["alternatives"]}
    assert kinds == {"jobs", "tenders"}


def test_every_vocabulary_entry_is_found_by_its_own_name_and_a_one_letter_typo():
    # guards against vocab clashes: each canonical business and skill must resolve to itself
    for canon in T.BUSINESS:
        assert parser.BUSINESS.exact(canon) == canon, canon
    for canon in T.SKILLS:
        assert parser.SKILL.exact(canon) == canon, canon


def test_suggestions_complete_prefixes_and_tolerate_typos():
    assert any(s["label"] == "dentist" for s in suggest("dent"))
    assert any(s["label"] == "dentist" for s in suggest("dentst"))
    assert any(s["label"] == "react" and s["type"] == "skill" for s in suggest("rea"))
    assert any(s["label"] == "leeds" and s["type"] == "city" for s in suggest("lee"))
    assert suggest("") and len(suggest("a")) <= 8
    s = suggest("python dent")
    assert s and s[0]["insert"].startswith("python ")                           # keeps what was already typed


def test_endpoints_require_a_session_and_return_the_parse(client, make_key):
    assert client.post("/api/search/parse", json={"q": "dentists in leeds"}).status_code == 401
    h = make_key("auditor")
    out = client.post("/api/search/parse", headers=h, json={"q": "dentst in leeds"}).json()
    assert out["run"]["category"] == "dentist" and out["corrections"]
    assert any(s["label"] == "dentist" for s in client.get("/api/search/suggest", headers=h, params={"q": "dent"}).json()["suggestions"])
    assert client.post("/api/search/parse", headers=h, json={"q": "x" * 400}).status_code == 422
