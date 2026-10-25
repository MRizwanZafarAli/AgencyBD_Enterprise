"""
Contact finder: who can we actually reach at this company, according to its OWN public pages?

It reads the homepage plus its team / about / contact / leadership pages (found from the homepage's own links and a few standard paths)
and reports only what those pages say:

  * people: a name together with the job title written next to it (schema.org Person data, or a team "card"), with their LinkedIn link if
    the same card has one;
  * emails published on the site (same domain only), marked "generic" (info@, sales@ …) or "personal", and linked to a person only when
    the address visibly matches that person's name.

Nothing is guessed: no email permutations, no invented titles, no people from search snippets. Every item carries the page it came from.
Candidates are suggestions for a person to review; saving one stores it UNVERIFIED.
"""

import json
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup

from net.fetcher import SSRFSecurityError, SafeFetcher
from net.validate import clean_domain

PAGE_HINTS = re.compile(r"team|about|contact|leader|people|company|who-we-are|our-story|management|staff|founders?", re.IGNORECASE)
DEFAULT_PATHS = ["/about", "/about-us", "/team", "/our-team", "/leadership", "/contact", "/company", "/people"]
MAX_PAGES = 7
GENERIC_LOCALS = {"info", "hello", "contact", "sales", "support", "admin", "office", "team", "hr", "jobs", "careers", "press", "media", "billing",
                  "accounts", "enquiries", "inquiries", "help", "mail", "marketing", "service", "general", "legal", "privacy", "webmaster", "noreply", "no-reply"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
NAME = re.compile(r"^[A-Z][A-Za-z'’.-]+(?: [A-Z][A-Za-z'’.-]+){1,3}$")
NOT_NAMES = {"our team", "the team", "contact us", "about us", "read more", "learn more", "get started", "our story", "meet the team", "join us", "view all", "see all",
             "privacy policy", "terms conditions", "case studies", "our values", "our mission", "book demo", "request demo", "get in touch", "sign in", "log in"}
ROLE_WORDS = ["ceo", "chief", "founder", "owner", "president", "partner", "director", "head of", "vp ", "vice president", "manager", "lead", "principal", "managing",
              "cto", "cfo", "coo", "cmo", "cpo", "engineer", "architect"]
RANKS = [(100, ["ceo", "chief executive", "founder", "owner", "managing director", "president"]), (90, ["cto", "chief technology", "vp engineering", "vp of engineering",
         "head of engineering", "head of technology", "technical director"]), (80, ["cpo", "chief product", "head of product", "product director"]),
         (75, ["coo", "cfo", "cmo", "chief"]), (70, ["director", "head of", "vp ", "vice president", "partner", "principal", "managing"]), (40, ["manager", "lead"])]


def _rank(title: str) -> int:
    t = f" {title.lower()} "
    for score, words in RANKS:
        if any(w in t for w in words):
            return score
    return 20


def _is_name(text: str) -> bool:
    return bool(NAME.match(text)) and text.lower() not in NOT_NAMES and not any(w in text.lower() for w in ("team", "contact", "about", "service", "solution", "company"))


def _has_role(text: str) -> bool:
    t = f" {text.lower()} "
    return any(w in t for w in ROLE_WORDS) and len(text) <= 90


def _fetch(url: str) -> Optional[str]:
    try:
        r = SafeFetcher.safe_fetch(url, timeout=6, max_bytes=600_000)
        return r.text if r.status_code == 200 else None
    except SSRFSecurityError:
        raise
    except Exception:
        return None


def _candidate_urls(domain: str, home_html: Optional[str]) -> List[str]:
    base = f"https://{domain}"
    urls = [base + "/"]
    if home_html:
        for a in BeautifulSoup(home_html, "html.parser").find_all("a", href=True):
            full = urljoin(base + "/", a["href"])
            p = urlparse(full)
            if p.hostname and p.hostname.removeprefix("www.") == domain.removeprefix("www.") and PAGE_HINTS.search(p.path) and len(p.path) < 60:
                urls.append(f"{p.scheme}://{p.hostname}{p.path}".rstrip("/") or full)
    urls += [base + p for p in DEFAULT_PATHS]
    seen, out = set(), []
    for u in urls:
        key = u.rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out[:MAX_PAGES + 3]


def _people_from_jsonld(soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
    out = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            types = node.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if "Person" in types and node.get("name") and node.get("jobTitle") and _is_name(str(node["name"]).strip()):
                same = node.get("sameAs") or []
                same = [same] if isinstance(same, str) else same
                out.append({"name": str(node["name"]).strip(), "title": str(node["jobTitle"]).strip()[:90], "email": str(node.get("email", "")).replace("mailto:", "").lower() or None,
                            "linkedin_url": next((s for s in same if "linkedin.com/in/" in s), None), "source_url": url, "evidence": "schema.org Person data on the page"})
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            walk(json.loads(script.string or script.get_text() or ""))
        except (ValueError, TypeError):
            continue
    return out


def _people_from_cards(soup: BeautifulSoup, url: str) -> List[Dict[str, Any]]:
    out = []
    for heading in soup.find_all(["h2", "h3", "h4", "h5", "strong"]):
        name = heading.get_text(" ", strip=True)
        if not _is_name(name):
            continue
        card = heading
        for _ in range(3):                                           # the card is the nearest small ancestor holding this heading
            parent = card.parent
            if not parent or len(parent.get_text(" ", strip=True)) > 400 or len(parent.find_all(["h2", "h3", "h4", "h5"])) > 1:
                break
            card = parent
        title = None
        for el in card.find_all(["p", "span", "div", "small", "em", "h5", "h6"]):
            text = el.get_text(" ", strip=True)
            if text and text != name and name not in text and _has_role(text) and not el.find(["h2", "h3", "h4"]):
                title = text
                break
        if not title and heading.find_next_sibling():
            sib = heading.find_next_sibling().get_text(" ", strip=True)
            title = sib if sib and _has_role(sib) else None
        if not title:
            continue
        li = next((a["href"] for a in card.find_all("a", href=True) if "linkedin.com/in/" in a["href"]), None)
        mail = next((a["href"].replace("mailto:", "").split("?")[0].lower() for a in card.find_all("a", href=True) if a["href"].lower().startswith("mailto:")), None)
        out.append({"name": name, "title": title[:90], "email": mail, "linkedin_url": li, "source_url": url, "evidence": "name and title shown together on the team page"})
    return out


def _emails(soup: BeautifulSoup, html: str, domain: str, url: str) -> List[Dict[str, Any]]:
    found: Dict[str, str] = {}
    for a in soup.select('a[href^="mailto:"]'):
        found.setdefault(a["href"][7:].split("?")[0].strip().lower(), "mailto link")
    for m in EMAIL.findall(soup.get_text(" ")):
        found.setdefault(m.strip(".").lower(), "text on the page")
    bare = domain.removeprefix("www.")
    out = []
    for email, how in found.items():
        host = email.split("@")[-1]
        if host.endswith((".png", ".jpg", ".svg", ".gif", ".webp")) or not (host == bare or host.endswith("." + bare)):
            continue                                                  # only addresses on the company's own domain
        local = email.split("@")[0]
        out.append({"email": email, "generic": local.split("+")[0] in GENERIC_LOCALS, "source_url": url, "evidence": f"published as a {how}"})
    return out


def _match_email(person: Dict[str, Any], emails: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    parts = [re.sub(r"[^a-z]", "", p.lower()) for p in person["name"].split()]
    first, last = parts[0], parts[-1]
    for e in emails:
        local = re.sub(r"[^a-z]", "", e["email"].split("@")[0].lower())
        if not e["generic"] and (first in local or (last in local and len(last) > 2) or local == first[0] + last):
            return e
    return None


def find_contacts(domain: str) -> Dict[str, Any]:
    domain = clean_domain(domain).split(":")[0]
    home = _fetch(f"https://{domain}/")
    pages_checked: List[str] = []
    people: Dict[str, Dict[str, Any]] = {}
    emails: Dict[str, Dict[str, Any]] = {}
    company_linkedin: Optional[str] = None

    for url in _candidate_urls(domain, home):
        if len(pages_checked) >= MAX_PAGES:
            break
        html = home if url.rstrip("/") == f"https://{domain}" and home else _fetch(url)
        if not html:
            continue
        pages_checked.append(url)
        soup = BeautifulSoup(html, "html.parser")
        for p in _people_from_jsonld(soup, url) + _people_from_cards(soup, url):
            people.setdefault(p["name"].lower(), p)
        for e in _emails(soup, html, domain, url):
            emails.setdefault(e["email"], e)
        company_linkedin = company_linkedin or next((a["href"] for a in soup.find_all("a", href=True) if "linkedin.com/company/" in a["href"]), None)

    email_list = list(emails.values())
    candidates: List[Dict[str, Any]] = []
    for p in people.values():
        linked = _match_email(p, email_list) if not p.get("email") else {"email": p["email"], "source_url": p["source_url"], "evidence": "published beside the person"}
        email = linked["email"] if linked else None
        candidates.append({"kind": "person", "name": p["name"], "title": p["title"], "email": email, "linkedin_url": p.get("linkedin_url"), "rank": _rank(p["title"]),
                           "source_url": p["source_url"], "evidence": p["evidence"] + ("; email " + linked["evidence"] if linked else "; no email published")})
    used = {c["email"] for c in candidates if c["email"]}
    for e in email_list:
        if e["email"] not in used:
            candidates.append({"kind": "generic_email" if e["generic"] else "email", "name": None, "title": None, "email": e["email"], "linkedin_url": None,
                               "rank": 5 if e["generic"] else 10, "source_url": e["source_url"], "evidence": e["evidence"]})
    candidates.sort(key=lambda c: -c["rank"])
    return {"domain": domain, "pages_checked": pages_checked, "candidates": candidates, "company_linkedin": company_linkedin,
            "linkedin_search_url": f"https://www.linkedin.com/search/results/people/?keywords={quote(domain.split('.')[0])}%20founder%20OR%20CEO%20OR%20CTO",
            "limitations": ["Only the company's own public pages were read; people who are not listed there will not appear.",
                            "A published email is not a verified one: saving a contact stores it unverified until a verification service confirms it.",
                            "Generic addresses (info@, sales@) reach a team inbox, not a decision maker."] +
                           ([] if pages_checked else ["No page could be read from this domain."])}
