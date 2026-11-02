"""Reply drafts for a client message. Plain rules, no AI key needed, and nothing in a draft is invented: a price appears only if you set one
for the service the client asked about, a result only if you set one with proof, and a call link only if you set a booking link."""

import re
from typing import Any, Dict, List, Optional

from config.settings import settings
from database.db import get_db
from intel.services import ServiceCatalog

INTENTS = {
    "price": re.compile(r"\b(how much|price|prices|pricing|cost|costs|quote|rate|rates|budget|charge|fee|fees|afford)\b", re.I),
    "time": re.compile(r"\b(when|how long|deadline|asap|urgent|urgently|this week|next week|timeline|turnaround|by (monday|tuesday|wednesday|thursday|friday)|days?)\b", re.I),
    "call": re.compile(r"\b(call|zoom|meet|meeting|talk|phone|whatsapp|discuss|chat)\b", re.I),
    "start": re.compile(r"\b(available|availability|free|start|begin|take on|can you|are you able|could you)\b", re.I),
}
SERVICE_WORDS = {
    "seo_optimization": r"\bseo\b|search engine|google ranking|rank",
    "performance_engineering": r"\bslow\b|speed|performance|loading|page ?speed",
    "security_hardening": r"security|hack|hacked|malware|\bssl\b|https|certificate|vulnerab",
    "a11y_compliance": r"accessib|wcag|\bada\b|screen reader",
    "mobile_optimization": r"mobile|responsive|phone friendly",
    "presence_rescue": r"new (web)?site|website|web site|redesign|rebuild|landing page|shopify|wordpress|wix|online store|e-?commerce",
}
QUESTIONS = {
    "price": "What result do you need, and roughly what budget do you have in mind?",
    "time": "When do you need this live?",
    "start": "Could you share the link to your current site, or a few lines on what you have today?",
    "scope": "Could you share the link to your current site, or a few lines on what you have today?",
}


def _first_name(sender: str) -> str:
    word = re.split(r"[\s,]+", (sender or "").strip())[0]
    return word if re.fullmatch(r"[A-Za-z][A-Za-z'’-]{1,24}", word or "") and word.lower() not in ("client", "buyer", "someone", "new") else ""


def _service_for(org_id: str, text: str) -> Optional[Dict[str, Any]]:
    for key, pattern in SERVICE_WORDS.items():
        if re.search(pattern, text, re.I):
            svc = ServiceCatalog.get(org_id, key)
            return {"key": key, "label": ServiceCatalog.label(key), "price_band": (svc or {}).get("price_band") or None}
    return None


def drafts(org_id: str, message_id: int) -> Dict[str, Any]:
    with get_db() as db:
        m = db.execute("SELECT * FROM client_messages WHERE id = ? AND org_id = ?", (message_id, org_id)).fetchone()
    if not m:
        raise LookupError("message not found")
    text = f"{m['subject'] or ''} {m['preview'] or ''}"
    found = [k for k, rx in INTENTS.items() if rx.search(text)]
    svc = _service_for(org_id, text)
    a = settings.agency
    hi = f"Hi {_first_name(m['sender'])}," if _first_name(m["sender"]) else "Hello,"
    sign = f"\n\nBest regards,\n{a.founder_name or '[your name]'}" + (f"\n{a.name}" if a.name else "")
    about = f" about {svc['label'].lower()}" if svc else ""
    asks = [QUESTIONS[k] for k in ("price", "time", "start") if k in found] or [QUESTIONS["scope"]]
    asks = list(dict.fromkeys(asks))[:3]
    needs: List[str] = []

    quick = f"{hi}\n\nThanks for your message{about}. I have read it and I can help.\n\nSo that I give you an accurate answer, " + (
        asks[0][0].lower() + asks[0][1:] if len(asks) == 1 else "could you tell me:\n" + "\n".join(f"- {q}" for q in asks)) + sign

    if a.booking_link:
        call = f"{hi}\n\nThanks for writing{about}. The quickest way is a short call, where I can ask the right questions and give you a clear answer. You can pick a time here: {a.booking_link}\n\nIf you prefer to write, just reply here." + sign
    else:
        call = f"{hi}\n\nThanks for writing{about}. A short call is the quickest way to give you a clear answer. Which two times suit you this week?" + sign
        needs.append("A booking link (Settings > Agency profile), so this draft can offer one click instead of asking for times.")

    out = [{"label": "Ask first", "text": quick}, {"label": "Move to a call", "text": call}]
    if "price" in found:
        if svc and svc["price_band"]:
            proof = (getattr(a, "case_study_metric", None) or "").strip()
            price = (f"{hi}\n\nThanks for asking. For {svc['label'].lower()} my price is {svc['price_band']}. The exact figure depends on what is on your site today, so please send me the link and I will confirm it in writing before any work starts."
                     + (f"\n\nA recent result: {proof}" if proof else "") + sign)
            out.append({"label": "Give the price", "text": price})
        else:
            needs.append(f"Your price for {svc['label']} (Settings > Services and proof), so a draft can state it." if svc else "Your prices (Settings > Services and proof), so a draft can state one.")
    return {"message_id": message_id, "intents": found, "service": svc["label"] if svc else None, "drafts": out, "needs": needs,
            "note": "Edit before sending. Drafts use only what you have set up; they never claim experience, results or prices you have not entered. Written for English messages."}
