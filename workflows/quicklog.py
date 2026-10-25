"""Understands a plain sentence such as "applied to react dashboard on upwork $1200 follow up friday" and turns it into a draft
application for the Channels tracker. Deterministic and offline: it never guesses a missing piece, it says what it still needs.
The person confirms the draft before anything is saved."""

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from intel.nlp.parser import edit_distance

PLATFORM_WORDS = {
    "linkedin": "linkedin", "linked in": "linkedin", "fiverr": "fiverr", "upwork": "upwork", "up work": "upwork", "freelancer": "freelancer", "freelancer.com": "freelancer",
    "peopleperhour": "peopleperhour", "people per hour": "peopleperhour", "pph": "peopleperhour", "contra": "contra", "toptal": "toptal", "guru": "guru",
}
STATUS_WORDS = [
    ("won", r"\b(won|hired|got the (?:job|project|gig)|awarded|closed won)\b"), ("lost", r"\b(lost|rejected|declined|not selected|turned down)\b"),
    ("interview", r"\b(interview|call booked|booked a call|meeting|shortlisted)\b"), ("replied", r"\b(replied|responded|answered|got a reply|they wrote back)\b"),
    ("saved", r"\b(saved|bookmark(?:ed)?|for later|to apply)\b"), ("applied", r"\b(applied|bid|bidded|proposal sent|sent (?:a )?proposal|pitched|sent|quoted)\b"),
]
WEEKDAYS = {"monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6}
MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9


def parse_date_phrase(text: str, today: Optional[date] = None) -> Optional[Tuple[str, str]]:
    """First date phrase in the text as (ISO date, the words matched), or None. Weekdays mean the next one after today."""
    today = today or date.today()
    t = text.lower()

    def m(pattern: str):
        return re.search(pattern, t)

    if (x := m(r"\b(\d{4})-(\d{2})-(\d{2})\b")):
        try:
            return date(int(x[1]), int(x[2]), int(x[3])).isoformat(), x[0]
        except ValueError:
            return None
    if (x := m(r"\btoday\b")):
        return today.isoformat(), x[0]
    if (x := m(r"\btomorrow\b|\btmrw\b")):
        return (today + timedelta(days=1)).isoformat(), x[0]
    if (x := m(r"\bin (\d{1,3}) (day|days|week|weeks|month|months)\b")):
        n = int(x[1]) * {"day": 1, "week": 7, "month": 30}[x[2].rstrip("s")]
        return (today + timedelta(days=n)).isoformat(), x[0]
    if (x := m(r"\bnext week\b")):
        return (today + timedelta(days=7)).isoformat(), x[0]
    if (x := m(r"\b(?:next |this |on )?(monday|mon|tuesday|tues|tue|wednesday|wed|thursday|thurs|thur|thu|friday|fri|saturday|sat|sunday|sun)\b")):
        ahead = (WEEKDAYS[x[1]] - today.weekday()) % 7 or 7
        return (today + timedelta(days=ahead)).isoformat(), x[0]
    month_re = "|".join(sorted(MONTHS, key=len, reverse=True))
    for pattern, order in ((rf"\b(?:on )?(\d{{1,2}})(?:st|nd|rd|th)? ({month_re})(?: (\d{{4}}))?\b", "dm"), (rf"\b(?:on )?({month_re}) (\d{{1,2}})(?:st|nd|rd|th)?(?:,? (\d{{4}}))?\b", "md")):
        if (x := m(pattern)):
            day, mon = (int(x[1]), MONTHS[x[2]]) if order == "dm" else (int(x[2]), MONTHS[x[1]])
            year = int(x[3]) if x[3] else today.year
            try:
                d = date(year, mon, day)
            except ValueError:
                return None
            if not x[3] and d < today:
                d = date(year + 1, mon, day)
            return d.isoformat(), x[0]
    return None


def _value(text: str) -> Tuple[Optional[float], Optional[str]]:
    x = re.search(r"(?:\$|usd\s*)\s?(\d[\d,]*(?:\.\d+)?)\s?(k)?\b|\b(\d[\d,]*(?:\.\d+)?)\s?(k)?\s?(?:usd|dollars|bucks)\b|\b(\d+(?:\.\d+)?)(k)\b", text, re.I)
    if not x:
        return None, None
    num, k = (x[1], x[2]) if x[1] else (x[3], x[4]) if x[3] else (x[5], x[6])
    return float(num.replace(",", "")) * (1000 if k else 1), x[0]


def _platform(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    low = text.lower()
    for word in sorted(PLATFORM_WORDS, key=len, reverse=True):
        if re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", low):
            return PLATFORM_WORDS[word], word, None
    for w in re.findall(r"[a-z]{5,}", low):                                      # a typo such as "upwrok" or "fivrr"
        for word, pid in PLATFORM_WORDS.items():
            if len(word) >= 5 and " " not in word and edit_distance(w, word) <= 1:
                return pid, w, f"Read '{w}' as {pid.capitalize()}."
    return None, None, None


def parse(text: str, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    raw = (text or "").strip()[:400]
    understood: List[str] = []
    rest = raw
    notes: List[str] = []

    platform, hit, note = _platform(rest)
    if platform:
        rest = re.sub(rf"(?i)(?<![a-z]){re.escape(hit)}(?![a-z])", " ", rest, count=1)
        understood.append(f"Platform: {platform}")
        if note:
            notes.append(note)

    status = None
    for name, pattern in STATUS_WORDS:
        if (x := re.search(pattern, rest, re.I)):
            status = name
            rest = re.sub(pattern, " ", rest, flags=re.I)
            rest = re.sub(STATUS_WORDS[-1][1], " ", rest, flags=re.I)                  # "applied ... bid" says the same thing twice
            break
    understood.append(f"Status: {status or 'applied'}" + ("" if status else " (assumed: say 'saved' if you have not applied yet)"))

    value, vtext = _value(rest)
    if vtext:
        rest = rest.replace(vtext, " ", 1)
        understood.append(f"Value: ${value:,.0f}")

    due = parse_date_phrase(rest, today)
    if due:
        iso, words = due
        rest = re.sub(re.escape(words), " ", rest, count=1, flags=re.I)
        rest = re.sub(r"(?i)\b(follow[- ]?up|remind me|remind|chase|check back|check in)\b", " ", rest)
        understood.append(f"Follow up: {iso}")

    counterparty = None
    if (x := re.search(r"(?i)\b(?:client|from|with)\s+([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){0,3})", rest)):
        counterparty = x[1].strip()
        rest = rest[: x.start()] + " " + rest[x.end():]
        understood.append(f"Client: {counterparty}")

    title = re.sub(r"\s+", " ", rest).strip(" ,.;:-")
    while (cut := re.sub(r"(?i)^(?:to|for|on|at|a|an|the|job|project|gig|buyer|they|he|she|about|regarding|re)\b\s*", "", title)) != title:
        title = cut
    title = re.sub(r"(?i)\b(on|at|to|for|a|an|the|and|-)\s*$", "", title).strip(" ,.;:-")
    needs = ([] if platform else ["platform"]) + ([] if title else ["title"])
    return {"text": raw, "platform": platform, "record": {"title": title or None, "status": status or "applied", "value": value, "next_followup": due[0] if due else None, "counterparty": counterparty},
            "understood": understood, "notes": notes, "needs": needs}
