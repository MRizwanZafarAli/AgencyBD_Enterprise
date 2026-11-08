"""Decides whether an email is a client message notification from a freelance or networking platform, and pulls out who wrote and what.

These are heuristics on sender domain and subject, because the platforms publish no stable email format. That is why Settings has a "show how my
recent emails are read" check: you can see exactly what would and would not alert you before turning anything on."""

import re
from dataclasses import dataclass
from email.utils import parseaddr
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

PLATFORM_DOMAINS: Dict[str, List[str]] = {
    "fiverr": ["fiverr.com"], "upwork": ["upwork.com"], "linkedin": ["linkedin.com"], "freelancer": ["freelancer.com"], "peopleperhour": ["peopleperhour.com"],
    "contra": ["contra.com"], "toptal": ["toptal.com"], "guru": ["guru.com"],
}
PLATFORM_LABEL = {"fiverr": "Fiverr", "upwork": "Upwork", "linkedin": "LinkedIn", "freelancer": "Freelancer.com", "peopleperhour": "PeoplePerHour", "contra": "Contra",
                  "toptal": "Toptal", "guru": "Guru", "other": "Other"}

MESSAGE = re.compile(r"\b(sent you a message|messaged you|new message|replied|reply from|wrote to you|sent you|your inbox|unread message|direct message|message from)\b", re.I)
PROPOSAL = re.compile(r"\b(invit\w+ you|invitation|offer|proposal|interview|hired|contract|new order|order (placed|received)|custom offer|request for|inquiry|enquiry)\b", re.I)
NOISE = re.compile(r"\b(newsletter|digest|webinar|promo|discount|\d+% off|tips for|weekly|recommended for you|jobs? (matching|for you)|top picks|trending|survey|rate your|"
                   r"verify your|password|security alert|new sign.?in|receipt|invoice|connects (balance|are)|how.?to)\b", re.I)
FOOTER = re.compile(r"(unsubscribe|you received this|to stop receiving|manage (your )?(email )?(settings|preferences)|view in browser|privacy policy|©)", re.I)
SENDER_IN_SUBJECT = re.compile(r"^(?P<n>[A-Z][\w .'’-]{1,40}?)\s+(sent you|messaged|replied|invited|wrote)\b")
SENDER_AFTER = re.compile(r"(?:message|reply|replied|response|invitation|offer) (?:from|by)\s+(?P<n>[A-Z][\w .'’-]{1,40})", re.I)


@dataclass
class Parsed:
    platform: str
    kind: str                      # message | proposal | other
    sender: str
    subject: str
    preview: str
    url: Optional[str]
    alert: bool                    # worth waking you for


def domain_of(from_header: str) -> str:
    addr = parseaddr(from_header or "")[1].lower()
    return addr.split("@")[-1] if "@" in addr else ""


def platform_for(from_header: str, extra_senders: Optional[List[str]] = None) -> Optional[str]:
    dom = domain_of(from_header)
    addr = parseaddr(from_header or "")[1].lower()
    for platform, domains in PLATFORM_DOMAINS.items():
        if any(dom == d or dom.endswith("." + d) for d in domains):
            return platform
    for extra in extra_senders or []:                               # your own additions: a domain or a full address
        extra = extra.strip().lower()
        if extra and (addr == extra or dom == extra or dom.endswith("." + extra)):
            return "other"
    return None


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "head"]):
        t.decompose()
    return re.sub(r"[ \t\r\f\v]+", " ", soup.get_text("\n")).strip()


def _preview(text: str, limit: int = 700) -> str:
    text = re.sub(r"https?://\S+", "", text or "")
    keep: List[str] = []
    for line in (l.strip() for l in text.splitlines()):
        if not line:
            continue
        if FOOTER.search(line):
            break
        keep.append(line)
    out = re.sub(r"\s+", " ", " ".join(keep)).strip()
    return out[:limit].rstrip() + ("…" if len(out) > limit else "")


def _link(html: str, platform: str) -> Optional[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    hosts = PLATFORM_DOMAINS.get(platform, [])
    links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("http") and any(h in a["href"] for h in hosts)]
    pick = next((l for l in links if re.search(r"(message|inbox|conversation|chat|thread|room)", l, re.I)), None)
    return pick or (links[0] if links else None)


def parse_email(from_header: str, subject: str, text: str, html: str = "", extra_senders: Optional[List[str]] = None) -> Optional[Parsed]:
    """None when the email is not from a watched platform. Otherwise a Parsed whose `alert` says whether it looks like a client writing to you."""
    platform = platform_for(from_header, extra_senders)
    if not platform:
        return None
    subject = (subject or "").strip()
    body = text or html_to_text(html)
    is_msg = bool(MESSAGE.search(subject))
    is_prop = bool(PROPOSAL.search(subject))
    noisy = bool(NOISE.search(subject))
    kind = "message" if is_msg else "proposal" if is_prop else "other"
    m = SENDER_IN_SUBJECT.match(subject) or SENDER_AFTER.search(subject)
    display = parseaddr(from_header)[0].strip()
    generic = {"fiverr", "upwork", "linkedin", "no-reply", "noreply", "notifications", "freelancer"}
    sender = m.group("n").strip() if m else ("" if display.lower() in generic or any(g in display.lower() for g in generic) and len(display) < 14 else display)
    return Parsed(platform, kind, sender or PLATFORM_LABEL.get(platform, platform), subject, _preview(body), _link(html, platform), alert=(is_msg or is_prop) and not noisy)
