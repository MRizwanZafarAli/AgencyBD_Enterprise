"""
Natural-language search: understand what a person typed, fix their spelling, and say plainly what was understood.

Deterministic and offline (no AI key needed, no data leaves the machine). It works in five steps:
  1. pull out budgets ("over $5k", "$3k-$8k") and filter phrases ("without a website", "slow site");
  2. match the remaining words and 1-3 word phrases against the vocabularies in `taxonomy` (exact, plural-insensitive, then typo-tolerant);
  3. find the place ("in Leeds", "near Dubai"), correcting known cities;
  4. decide the kind of search (local businesses, jobs and projects, or tenders) from the evidence;
  5. report what it understood, every correction it made, and the alternative readings.
It never silently guesses: when nothing matched, it says so and offers close suggestions.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from intel.nlp import taxonomy as T

STOP = {"a", "an", "the", "for", "of", "to", "me", "my", "find", "search", "show", "get", "looking", "look", "need", "want", "any", "all", "with", "and", "or", "who", "that", "are", "is",
        "have", "has", "do", "does", "please", "some", "give", "list", "best", "top", "good", "new", "i", "im", "we", "us", "can", "you", "on", "by", "doing", "offering", "wanting", "site", "sites", "website", "websites", "web", "page", "pages", "built", "build", "make", "made", "create", "someone", "anyone", "help", "helps", "needed", "using", "based", "built"}
LOCATION_PREPS = {"in", "near", "around", "at", "from", "within", "nearby"}
CURRENCY = {"$": "USD", "£": "GBP", "€": "EUR"}


# ------------------------------------------------------------------ text helpers

def normalize(text: str) -> str:
    text = (text or "").lower().replace("’", "'")
    text = re.sub(r"[^\w\s$£€.,'+#/-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def edit_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein (insert, delete, substitute, swap adjacent letters)."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > 3:
        return 9
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


def _singular(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _forms(phrase: str) -> List[str]:
    words = phrase.split()
    out = [phrase]
    if words:
        out.append(" ".join(words[:-1] + [_singular(words[-1])]))
    return list(dict.fromkeys(out))


# ------------------------------------------------------------------ vocabulary index

class _Index:
    def __init__(self, table: Dict[str, List[str]], kind: str):
        self.kind = kind
        self.phrases: Dict[str, str] = {}                        # phrase -> canonical
        for canon, synonyms in table.items():
            for p in [canon] + synonyms:
                self.phrases[p.lower()] = canon

    def exact(self, phrase: str) -> Optional[str]:
        for f in _forms(phrase):
            if f in self.phrases:
                return self.phrases[f]
        return None

    def fuzzy(self, phrase: str) -> Optional[Tuple[str, int, str]]:
        """(canonical, distance, matched phrase) for the closest phrase within the typo budget, else None.

        Short words get one edit, medium words two. Words of 9+ letters get three (restraunt -> restaurant), but only when the first three letters
        agree and exactly one vocabulary entry is that close, so a long unrelated word is never forced onto a business type or skill."""
        n = len(phrase)
        if n < 4:
            return None
        budget = 1 if n <= 7 else 2 if n <= 8 else 3
        best: Optional[Tuple[str, int, str]] = None
        close: Dict[str, int] = {}                                             # canonical -> best distance, for the 3-edit uniqueness rule
        for cand, canon in self.phrases.items():
            if abs(len(cand) - n) > budget or cand[0] != phrase[0]:        # a typo rarely changes the first letter
                continue
            for form in _forms(phrase):
                dist = edit_distance(form, cand)
                if dist <= budget:
                    if dist == 3 and cand[:3] != form[:3]:
                        continue
                    close[canon] = min(close.get(canon, 9), dist)
                    if best is None or dist < best[1]:
                        best = (canon, dist, cand)
        if best and best[1] == 3 and len(close) != 1:
            return None
        return best


BUSINESS = _Index(T.BUSINESS, "business")
SKILL = _Index(T.SKILLS, "skill")
QUAL = _Index(T.QUALIFIERS, "qualifier")
CITY = _Index({c: [] for c in T.CITIES}, "city")


# ------------------------------------------------------------------ extractors

def _extract_phrases(text: str, phrases: List[str]) -> Tuple[str, bool]:
    found = False
    for p in sorted(phrases, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", text):
            text = re.sub(rf"(?<!\w){re.escape(p)}(?!\w)", " ", text)
            found = True
    return re.sub(r"\s+", " ", text).strip(), found


def _num(raw: str, suffix: Optional[str]) -> float:
    value = float(raw.replace(",", ""))
    return value * {"k": 1_000, "m": 1_000_000}.get((suffix or "").lower(), 1)


def _extract_budget(text: str) -> Tuple[str, Dict[str, Any]]:
    out: Dict[str, Any] = {}
    cur = r"([$£€])?\s*"
    num = r"(\d+(?:[.,]\d+)*)\s*([km])?\b"
    rng = re.search(rf"{cur}{num}\s*(?:-|to|–)\s*{cur}{num}", text)
    if rng and (rng.group(1) or rng.group(4) or rng.group(3) or rng.group(6)):
        lo, hi = _num(rng.group(2), rng.group(3) or rng.group(6)), _num(rng.group(5), rng.group(6))
        if lo > hi:
            lo, hi = hi, lo
        out.update(min_budget=lo, max_budget=hi, currency=CURRENCY.get(rng.group(1) or rng.group(4) or "", None))
        return (text[:rng.start()] + " " + text[rng.end():]).strip(), out
    m = re.search(rf"\b(over|above|more than|at least|minimum|min|from|greater than)\s*{cur}{num}", text)
    if m:
        out.update(min_budget=_num(m.group(3), m.group(4)), currency=CURRENCY.get(m.group(2) or "", None))
        return (text[:m.start()] + " " + text[m.end():]).strip(), out
    m = re.search(rf"\b(under|below|less than|up to|at most|maximum|max|within|budget of)\s*{cur}{num}", text)
    if m:
        out.update(max_budget=_num(m.group(3), m.group(4)), currency=CURRENCY.get(m.group(2) or "", None))
        return (text[:m.start()] + " " + text[m.end():]).strip(), out
    m = re.search(rf"([$£€])\s*{num}", text)
    if m:
        out.update(min_budget=_num(m.group(2), m.group(3)), currency=CURRENCY[m.group(1)])
        return (text[:m.start()] + " " + text[m.end():]).strip(), out
    return text, out


def _title(place: str) -> str:
    return " ".join(w.capitalize() for w in place.split())


# ------------------------------------------------------------------ the parser

def parse(raw: str) -> Dict[str, Any]:
    original = (raw or "").strip()
    text = normalize(original)
    corrections: List[Dict[str, str]] = []
    understood: List[str] = []

    text, no_site = _extract_phrases(text, T.NO_WEBSITE)
    text, needs_fix = _extract_phrases(text, T.NEEDS_FIX)
    text, social_only = _extract_phrases(text, T.SOCIAL_ONLY)
    text, budget = _extract_budget(text)

    tokens = [t for t in re.findall(r"[\w$£€.+#/'-]+", text) if t not in {".", ","}]
    tokens = [t.strip(".,'-") or t for t in tokens]

    # location: "in/near/around <words>" up to the next stop/qualifier word
    location, loc_span = None, set()
    for i, t in enumerate(tokens):
        if t in LOCATION_PREPS and i + 1 < len(tokens):
            j = i + 1
            words: List[str] = []
            while j < len(tokens) and len(words) < 4 and tokens[j] not in STOP and tokens[j] not in T.JOB_WORDS and tokens[j] not in LOCATION_PREPS:
                words.append(tokens[j]); j += 1
            if words:
                place = " ".join(words)
                exact = CITY.exact(place)
                fuzzy = None if exact else CITY.fuzzy(place)
                if exact:
                    location = _title(exact)
                elif fuzzy:
                    location = _title(fuzzy[0]); corrections.append({"from": place, "to": fuzzy[0]})
                else:
                    location = _title(place)
                loc_span = set(range(i, j))
                break

    # vocabulary matches over the remaining tokens (3-, 2-, then 1-word phrases)
    cands: List[Tuple[int, int, str, str, int, str]] = []        # (start, end, kind, canonical, distance, original)
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            span = range(i, i + n)
            if any(k in loc_span for k in span):
                continue
            phrase = " ".join(tokens[i:i + n])
            if n == 1 and (phrase in STOP or phrase in LOCATION_PREPS or phrase in T.LOCAL_WORDS or phrase in T.TENDER_WORDS) :
                continue
            if n == 1 and phrase in T.JOB_WORDS and QUAL.exact(phrase) is None:
                continue
            for idx in (BUSINESS, SKILL, QUAL, CITY):
                exact = idx.exact(phrase)
                if exact:
                    cands.append((i, i + n, idx.kind, exact, 0, phrase))
                else:
                    fz = idx.fuzzy(phrase)
                    if fz:
                        cands.append((i, i + n, idx.kind, fz[0], fz[1], phrase))
    cands.sort(key=lambda c: (c[4], -(c[1] - c[0]), c[0]))
    taken: set = set()
    business: List[str] = []
    skills: List[str] = []
    quals: List[str] = []
    for s, e, kind, canon, dist, original in cands:
        if any(k in taken for k in range(s, e)):
            continue
        taken.update(range(s, e))
        if dist:
            corrections.append({"from": original, "to": canon})
        target = {"business": business, "skill": skills, "qualifier": quals}.get(kind)
        if kind == "city":
            if not location:
                location = _title(canon)
        elif canon not in target:
            target.append(canon)

    word_hits = {"tender": False}
    for i, t in enumerate(tokens):
        if i in taken or i in loc_span or t in STOP or len(t) < 6 or t in T.TENDER_WORDS or t in T.JOB_WORDS or _singular(t) in T.TENDER_WORDS or _singular(t) in T.JOB_WORDS:
            continue
        for vocab, label in ((T.TENDER_WORDS, "tender"), (T.JOB_WORDS, "job")):
            near = [w for w in vocab if abs(len(w) - len(t)) <= 2 and w[0] == t[0] and edit_distance(t, w) <= (1 if len(t) <= 7 else 2)]
            if near:
                best = min(near, key=lambda w: edit_distance(t, w))
                corrections.append({"from": t, "to": best}); taken.add(i); word_hits[label if label == "tender" else "tender"] |= label == "tender"
                tokens[i] = best
                break
    unmatched = [t for i, t in enumerate(tokens) if i not in taken and i not in loc_span and t not in STOP and t not in LOCATION_PREPS
                 and t not in T.JOB_WORDS and t not in T.LOCAL_WORDS and t not in T.TENDER_WORDS]
    lowered = set(tokens) | {" ".join(tokens)}
    tender_hit = word_hits["tender"] or any(w in lowered or re.search(rf"(?<!\w){re.escape(w)}(?!\w)", normalize(original)) for w in T.TENDER_WORDS)
    job_hits = len([t for t in tokens if t in T.JOB_WORDS])
    local_hits = len([t for t in tokens if t in T.LOCAL_WORDS])
    remote = "remote" in quals
    filters = {"no_website": no_site, "needs_fix": needs_fix, "social_only": social_only}

    # decide the kind of search from the evidence
    score = {"tenders": 0, "jobs": 0, "local": 0}
    if tender_hit:
        score["tenders"] += 4
    score["jobs"] += min(job_hits, 3) + (2 if skills else 0) + (2 if (remote or "freelance" in quals) else 0) + (1 if budget else 0)
    score["local"] += (3 if business else 0) + min(local_hits, 2) + (1 if location and business else 0) + (3 if any(filters.values()) else 0)
    if business and skills and not any(filters.values()) and not location:
        score["jobs"] += 1
    intent = max(score, key=lambda k: (score[k], {"tenders": 2, "local": 1, "jobs": 0}[k])) if any(score.values()) else None

    # build the plain-language summary
    bits: List[str] = []
    if intent == "local":
        what = ", ".join(business) if business else "local businesses"
        bits.append(f"local businesses: {what}")
        if location: bits.append(f"in {location}")
        if no_site: bits.append("with no website")
        if needs_fix: bits.append("with a slow or poor website")
        if social_only: bits.append("with only a social page")
    elif intent == "jobs":
        bits.append("jobs and projects" + (f" for {', '.join(skills)}" if skills else ""))
        if remote: bits.append("remote")
        if "freelance" in quals: bits.append("freelance or contract")
        if location: bits.append(f"in {location}")
    elif intent == "tenders":
        bits.append("public tenders" + (f" for {', '.join(skills + business)}" if (skills or business) else ""))
    sym = {"USD": "$", "GBP": "£", "EUR": "€"}.get(budget.get("currency") or "", "")
    if budget.get("min_budget") and budget.get("max_budget"): bits.append(f"budget {sym}{int(budget['min_budget']):,} to {sym}{int(budget['max_budget']):,}")
    elif budget.get("min_budget"): bits.append(f"budget over {sym}{int(budget['min_budget']):,}")
    elif budget.get("max_budget"): bits.append(f"budget under {sym}{int(budget['max_budget']):,}")
    explanation = ("Searching " + ", ".join(bits) + ".") if intent else "I could not tell what to search for."
    if corrections:
        explanation += " Corrected: " + ", ".join(f"{c['from']} to {c['to']}" for c in corrections) + "."

    free_text = " ".join(unmatched).strip() or None
    run: Dict[str, Any] = {"kind": intent}
    if intent == "local":
        run.update(category=(business[0] if business else ("" if skills else (free_text or ""))), city=location or "", only_gaps=bool(no_site or needs_fix or social_only))
    elif intent == "jobs":
        run.update(q=" ".join(skills + ([free_text] if free_text else [])) or "", min_budget=budget.get("min_budget"), max_budget=budget.get("max_budget"), remote=remote)
    elif intent == "tenders":
        run.update(q=" ".join(skills + business + ([free_text] if free_text else [])), min_budget=budget.get("min_budget"))

    needs_clarification = intent is None or (intent == "local" and not run["category"]) or (intent == "local" and not run["city"])
    alternatives = [{"kind": k, "label": {"local": "Search local businesses instead", "jobs": "Search jobs and projects instead", "tenders": "Search tenders instead"}[k]}
                    for k in ("local", "jobs", "tenders") if k != intent]
    return {"raw": original, "intent": intent, "business": business, "skills": skills, "qualifiers": quals, "location": location, "budget": budget, "filters": filters,
            "free_text": free_text, "corrections": corrections, "explanation": explanation, "run": run, "needs_clarification": needs_clarification,
            "clarification": ("Local search finds businesses by type, not by the software their website runs. Pick a type of business, for example 'restaurants in Dubai with a slow website'." if (intent == "local" and skills and not business) else
                              "Add a city to search local businesses, for example 'in Leeds'." if (intent == "local" and not run.get("city")) else
                              "Try a business type (dentist, plumber), a skill (react, python) or 'tenders'." if intent is None else None),
            "alternatives": alternatives, "unmatched": unmatched}


# ------------------------------------------------------------------ suggestions as you type

def suggest(prefix: str, limit: int = 8, kinds: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Suggestions for what is being typed. With `kinds` (for example ["city"]) the whole input is one phrase and only those kinds are offered."""
    q = normalize(prefix)
    last = q if kinds else (q.split(" ")[-1] if q else "")
    head = "" if kinds else q[: len(q) - len(last)].strip()
    if not last and kinds:                                         # nothing typed yet: a few popular starting points for that field
        popular = {"business": ["dentist", "restaurant", "plumber", "law firm", "real estate agent", "gym"], "skill": ["react", "python", "wordpress", "shopify", "seo", "ai"],
                   "city": ["london", "new york", "dubai", "toronto", "sydney", "karachi"]}
        return [{"type": k, "label": w, "insert": w} for k in kinds for w in popular.get(k, [])][:limit]
    if not last and not kinds:
        base = ["dentist", "restaurant", "plumber", "react", "python", "wordpress", "ai", "cybersecurity"]
        return [{"type": "business" if b in T.BUSINESS else "skill", "label": b, "insert": b} for b in base][:limit]
    scored: List[Tuple[int, str, str, str]] = []
    for idx in (BUSINESS, SKILL, CITY):
        if kinds and idx.kind not in kinds:
            continue
        for phrase, canon in idx.phrases.items():
            words = phrase.split()
            if phrase.startswith(last) or any(w.startswith(last) for w in words):
                rank = 0 if phrase.startswith(last) else 1
                scored.append((rank + (0 if phrase == canon else 1), idx.kind, canon, phrase))
            elif len(last) >= 4 and phrase[0] == last[0] and min(edit_distance(last, phrase[: len(last)]), edit_distance(last, phrase[: len(last) + 1])) <= 1:
                scored.append((3, idx.kind, canon, phrase))              # typo-tolerant prefix: "dentst" still offers dentist
    seen, out = set(), []
    for _, kind, canon, phrase in sorted(scored, key=lambda s: (s[0], len(s[3]), s[3])):
        if (kind, canon) in seen:
            continue
        seen.add((kind, canon))
        out.append({"type": kind, "label": canon, "insert": (head + " " + canon).strip()})
        if len(out) >= limit:
            break
    return out
