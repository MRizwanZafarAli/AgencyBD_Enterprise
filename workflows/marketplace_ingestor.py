"""Zero-Ban-Risk Email Notification Ingestor for Marketplace & Directory Alerts."""

import fnmatch
import json
import re
from typing import Any, Dict, List, Optional

from database.db import get_db
from workflows.channel_shields import check_fiverr_compliance

PLATFORM_SENDER_RULES: Dict[str, List[str]] = {
    "fiverr": ["noreply@e.fiverr.com", "noreply@fiverr.com", "*@*.fiverr.com", "*@fiverr.com"],
    "upwork": ["donotreply@upwork.com", "notifications@upwork.com", "*@upwork.com"],
    "freelancer": ["noreply@freelancer.com", "*@freelancer.com"],
    "contra": ["notifications@contra.com", "hello@contra.com", "*@contra.com"],
    "clutch": ["leads@clutch.co", "notifications@clutch.co", "*@clutch.co"],
    "toptal": ["matchers@toptal.com", "noreply@toptal.com", "*@toptal.com"],
    "pph": ["noreply@peopleperhour.com", "*@peopleperhour.com"],
    "guru": ["notifications@guru.com", "*@guru.com"],
}

PLATFORM_DEFAULT_LINKS: Dict[str, str] = {
    "fiverr": "https://www.fiverr.com/inbox",
    "upwork": "https://www.upwork.com/ab/messages/",
    "freelancer": "https://www.freelancer.com/messages/",
    "contra": "https://contra.com/opportunities",
    "clutch": "https://clutch.co/",
    "toptal": "https://www.toptal.com/",
    "pph": "https://www.peopleperhour.com/freelance-jobs",
    "guru": "https://www.guru.com/d/jobs/",
}


def match_platform_from_sender(org_id: str, from_email: str) -> Optional[str]:
    clean = (from_email or "").strip().lower()
    if "<" in clean and ">" in clean:
        clean = clean.split("<", 1)[1].split(">", 1)[0].strip()
    if not clean:
        return None

    for plat, patterns in PLATFORM_SENDER_RULES.items():
        for pat in patterns:
            if fnmatch.fnmatch(clean, pat.lower()):
                return plat

    with get_db() as db:
        rows = db.execute(
            "SELECT slug, sender_pattern FROM custom_channels WHERE org_id = ? AND active = 1 AND sender_pattern != ''",
            (org_id,),
        ).fetchall()
    for r in rows:
        for pat in (r["sender_pattern"] or "").split(","):
            p = pat.strip().lower()
            if p and fnmatch.fnmatch(clean, p):
                return r["slug"]
    return None


def _draft_reply(platform: str, buyer_name: str, title: str) -> str:
    who = buyer_name or "there"
    if platform == "fiverr":
        return f"Hi {who}, thanks for reaching out about {title or 'your project'}! Could you share your target deadline and any reference links here in Fiverr chat so I can send a tailored scope?"
    if platform == "upwork":
        return f"Hi {who} — saw your brief on {title or 'this project'}. We recently shipped a similar build with measurable speed and conversion gains; happy to share a 2-minute breakdown if you're free."
    if platform == "clutch":
        return f"Hi {who}, thank you for contacting us via Clutch regarding {title or 'your initiative'}. To prepare an accurate estimate, could you share your target launch window and preferred budget range?"
    return f"Hi {who}, thanks for your message regarding {title or 'this opportunity'}. I'm reviewing the details now and will follow up with next steps shortly."


def ingest_marketplace_email(
    org_id: str,
    from_email: str,
    subject: str,
    body: str,
    external_msg_id: str,
    platform_override: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Parses a marketplace notification email into marketplace_events (idempotent) and fires initial alert."""
    platform = platform_override or match_platform_from_sender(org_id, from_email)
    if not platform:
        return None

    clean_body = re.sub(r"<[^>]+>", " ", body or "")
    clean_body = re.sub(r"\s+", " ", clean_body).strip()
    snippet = clean_body[:280]

    # Extract buyer name heuristics ("from John Doe", "John Doe sent you")
    buyer = ""
    m_buyer = re.search(r"(?:from|by)\s+([A-Z][a-zA-Z0-9._-]+(?:\s+[A-Z][a-zA-Z0-9._-]+)?)", subject or "")
    if m_buyer:
        buyer = m_buyer.group(1).strip()
    if not buyer:
        buyer = "Prospect"

    # Extract deep link URL if present in body
    link_match = re.search(r"https?://[^\s\"'<>]+", body or "")
    deep_link = link_match.group(0) if link_match else PLATFORM_DEFAULT_LINKS.get(platform, "")

    title = (subject or f"New {platform.title()} inquiry")[:180]
    event_type = "new_job" if "job" in title.lower() or "project" in title.lower() else ("match_invite" if platform == "toptal" else "buyer_message")
    ai_reply = _draft_reply(platform, buyer, title)
    warnings = check_fiverr_compliance(ai_reply)["warnings"] if platform == "fiverr" else []

    with get_db() as db:
        cur = db.execute(
            """INSERT OR IGNORE INTO marketplace_events
               (org_id, platform, event_type, external_msg_id, buyer_name, title, snippet, deep_link, ai_draft_reply, compliance_warnings)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (org_id, platform, event_type, external_msg_id, buyer, title, snippet, deep_link, ai_reply, json.dumps(warnings)),
        )
        db.commit()
        if cur.rowcount == 0:
            row = db.execute(
                "SELECT * FROM marketplace_events WHERE org_id = ? AND external_msg_id = ?",
                (org_id, external_msg_id),
            ).fetchone()
            return {"event": dict(row), "deduplicated": True}
        ev = dict(db.execute("SELECT * FROM marketplace_events WHERE id = ?", (cur.lastrowid,)).fetchone())

    from workflows.alert_dispatcher import trigger_initial_alert
    dispatch_res = trigger_initial_alert(ev["id"], org_id)
    return {"event": ev, "deduplicated": False, "dispatch": dispatch_res}
