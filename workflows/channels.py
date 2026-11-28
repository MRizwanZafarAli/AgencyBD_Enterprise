"""
Channels: a control centre for the networks and marketplaces you work in by hand (LinkedIn, Fiverr, Upwork, Freelancer, ...).

What it is: your own tracker. A daily routine, an application/outreach pipeline with follow-up dates, templates, an activity log, response-time
tracking, saved search links and check-in reminders, all built from what YOU log.

What it deliberately is not: it never logs in to these sites, never stores their passwords, never scrapes them, never sends messages for you,
and never refreshes pages to look "online". Those things break the platforms' terms and put your account at risk. Every number shown here comes
from your own entries and says so.
"""

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

from database.db import get_db
from workflows.channel_registry import ACTIVITY_LABELS, ARCHETYPES, CHANNEL_REGISTRY, get_channel_spec

PLATFORMS: Dict[str, Dict[str, Any]] = {
    "linkedin": {
        "label": "LinkedIn", "kind": "network", "home": "https://www.linkedin.com/", "terms": "https://www.linkedin.com/legal/user-agreement",
        "search": "https://www.linkedin.com/search/results/people/?keywords={q}",
        "rules": ["This app never logs in to LinkedIn, scrapes it, or sends anything for you.", "LinkedIn's terms prohibit bots and automated scraping; accounts that use them get restricted.",
                  "Use the search links here in your own browser, and keep outreach personal and low-volume."],
        "routine": ["Reply to new messages and connection requests", "Send a few personalised connection notes by hand", "Comment usefully on 3 posts from target companies", "Follow up with people who are due today", "Log what you did here"],
        "profile": ["Headline says who you help and with what", "About section states your offer and how to reach you", "Featured section shows 2-3 case studies you can prove", "Services section is switched on", "Custom profile URL", "Some activity (a post or comments) in the last 30 days"],
        "templates": [{"name": "Connection note (under 300 characters)", "body": "Hi {first_name}, I looked at {company} and noticed {specific_observation}. I help teams like yours with {what_you_do}. Happy to connect."},
                      {"name": "Follow-up after connecting", "body": "Thanks for connecting, {first_name}. I mentioned {specific_observation} on {domain}. If it is useful I can send a short note on how to fix it, no obligation."}],
        "limits": {"note_chars": 300},
    },
    "fiverr": {
        "label": "Fiverr", "kind": "marketplace", "home": "https://www.fiverr.com/", "terms": "https://www.fiverr.com/terms_of_service",
        "search": "https://www.fiverr.com/search/gigs?query={q}",
        "rules": ["This app never logs in to Fiverr or stores your Fiverr password.", "It does not refresh pages or fake being online. Marketplaces treat artificial activity as manipulation and can restrict or ban the account.",
                  "Real availability comes from replying quickly: use the response-time tracker and check-in reminders instead."],
        "routine": ["Check messages and reply to every buyer", "Review orders due this week", "Look at gig impressions and clicks; note them here", "Improve one gig element (title, thumbnail, FAQ or tags)", "Ask a delivered buyer for a review"],
        "profile": ["Each gig title says exactly what the buyer gets", "Gig images and a short video show real work", "Three packages priced clearly", "FAQ answers the top three pre-sale questions", "Portfolio samples you can prove", "Profile shows your response hours honestly"],
        "templates": [{"name": "First reply to an enquiry", "body": "Hi {first_name}, thanks for getting in touch. To quote accurately I need to know {question_1} and {question_2}. I can start {start_date}."},
                      {"name": "Delivery message", "body": "Hi {first_name}, your {deliverable} is ready. It includes {what_is_included}. Tell me if anything needs adjusting and I will fix it."}],
        "limits": {},
    },
    "upwork": {
        "label": "Upwork", "kind": "marketplace", "home": "https://www.upwork.com/", "terms": "https://www.upwork.com/legal",
        "search": "https://www.upwork.com/nx/search/jobs/?q={q}",
        "rules": ["Apply by hand on Upwork. Bots and automated bidding are against Upwork's terms.", "Proposals are drafted in Find > Jobs and projects, then copied by you.", "Connects cost money: the tracker helps you apply selectively."],
        "routine": ["Check saved searches for new jobs", "Send 1-3 well-fitted proposals", "Reply to client messages", "Follow up on proposals older than 3 days", "Log the day here"],
        "profile": ["Title states a specialty, not just a role", "Overview opens with the client's problem", "Portfolio items with measurable results you can prove", "Skills match the jobs you want", "Availability and rate are accurate"],
        "templates": [{"name": "Proposal skeleton", "body": "Hi {first_name}, you need {their_problem}. I have done {relevant_proof}. My approach: {approach}. First step this week: {first_step}. Question: {clarifying_question}?"}],
        "limits": {},
    },
    "freelancer": {"label": "Freelancer.com", "kind": "marketplace", "home": "https://www.freelancer.com/", "terms": "https://www.freelancer.com/about/terms", "search": "https://www.freelancer.com/jobs/?keywords={q}",
                   "rules": ["Bid by hand. Automated bidding tools are not allowed by most marketplaces.", "Use the tracker to follow up on bids that got no answer."],
                   "routine": ["Check new projects in your skills", "Place 1-3 considered bids", "Reply to project messages", "Follow up on older bids", "Log the day here"],
                   "profile": ["Headline states a specialty", "Portfolio you can prove", "Skills and exams relevant to target projects", "Verified profile details"],
                   "templates": [{"name": "Bid message", "body": "Hi {first_name}, I read your brief on {project}. I can deliver {deliverable} by {date}. Similar work: {proof}. Quick question: {question}?"}], "limits": {}},
    "peopleperhour": {"label": "PeoplePerHour", "kind": "marketplace", "home": "https://www.peopleperhour.com/", "terms": "https://www.peopleperhour.com/static/terms", "search": "https://www.peopleperhour.com/freelance-jobs?q={q}",
                      "rules": ["Respond by hand; do not automate proposals."], "routine": ["Check new briefs", "Send 1-2 proposals", "Reply to messages", "Log the day here"],
                      "profile": ["Clear headline and hourly rate", "Portfolio samples", "Fast-response settings kept truthful"], "templates": [{"name": "Proposal", "body": "Hi {first_name}, for {project} I would {approach}. Timeline {timeline}. Similar: {proof}."}], "limits": {}},
    "contra": {"label": "Contra", "kind": "marketplace", "home": "https://contra.com/", "terms": "https://contra.com/terms", "search": None,
               "rules": ["Contra is portfolio-led: your work samples do the selling."], "routine": ["Add or improve a portfolio project", "Reply to enquiries", "Share one project on LinkedIn", "Log the day here"],
               "profile": ["3+ portfolio projects with results", "Clear services and rates", "Availability set honestly"], "templates": [{"name": "Reply to an enquiry", "body": "Hi {first_name}, thanks for reaching out about {project}. A few questions: {questions}."}], "limits": {}},
    "toptal": {"label": "Toptal", "kind": "network", "home": "https://www.toptal.com/", "terms": "https://www.toptal.com/terms", "search": None,
               "rules": ["Toptal is a vetted network: opportunities arrive through the platform, so the tracker is for your own follow-ups."], "routine": ["Check matched opportunities", "Reply to the talent team", "Update availability", "Log the day here"],
               "profile": ["Profile current and accurate", "Availability updated"], "templates": [], "limits": {}},
    "guru": {"label": "Guru", "kind": "marketplace", "home": "https://www.guru.com/", "terms": "https://www.guru.com/terms-of-service", "search": "https://www.guru.com/d/jobs/q/{q}/",
             "rules": ["Quote by hand; avoid automated bidding."], "routine": ["Check new jobs", "Send 1-2 quotes", "Reply to messages", "Log the day here"],
             "profile": ["SEO-friendly headline", "Portfolio and certifications you can prove"], "templates": [{"name": "Quote", "body": "Hi {first_name}, I can deliver {deliverable} for {project} in {timeline}. Proof: {proof}."}], "limits": {}},
    "clutch": {"label": "Clutch", "kind": "directory", "home": "https://clutch.co/", "terms": "https://clutch.co/terms", "search": "https://clutch.co/search?q={q}",
               "rules": ["Clutch drives high-intent inbound agency leads via verified client reviews and Leader Matrix rankings.",
                         "Invite completed Upwork, LinkedIn, or direct retainer clients to submit verified Clutch reviews.",
                         "Track referral traffic and inbound inquiries here with UTM portfolio links."],
               "routine": ["Request 1 verified review from a delivered client", "Check Clutch profile messages & referral clicks", "Update portfolio case studies & hourly rate band", "Log inbound Clutch inquiries here"],
               "profile": ["5+ verified client reviews with project cost & outcomes", "Clear service-line focus percentages", "Portfolio case studies with live links", "UTM-tagged website & booking link"],
               "templates": [{"name": "Verified review request", "body": "Hi {first_name}, really glad the {project} launch hit {measurable_result}. Would you be open to sharing a quick 3-minute verified review on Clutch? It helps other teams find us: {clutch_review_link}."}],
               "limits": {}},
    "other": {"label": "Other site", "kind": "marketplace", "home": None, "terms": None, "search": None, "rules": ["Use any site by hand; add its links and templates here."], "routine": ["Check for new work", "Reply to messages", "Follow up", "Log the day here"], "profile": [], "templates": [], "limits": {}},
}

def _f(title: str, text: str, tip: str) -> Dict[str, str]:
    return {"title": title, "text": text, "tip": tip}


# What each site offers and where to find it, so the page can open the right place in YOUR browser. Addresses are public pages only.
EXTRAS: Dict[str, Dict[str, Any]] = {
    "linkedin": {
        "pages": [("Feed", "https://www.linkedin.com/feed/"), ("Messages", "https://www.linkedin.com/messaging/"), ("My network", "https://www.linkedin.com/mynetwork/"),
                  ("Jobs", "https://www.linkedin.com/jobs/"), ("Notifications", "https://www.linkedin.com/notifications/"), ("Who viewed my profile", "https://www.linkedin.com/me/profile-views/")],
        "features": [_f("Profile and Services page", "Your headline, About and Featured sections are what people read after your message.", "Feature two case studies you can prove, and switch the Services section on."),
                     _f("People and company search", "Filter by title, company and location. Sales Navigator (paid) adds deeper filters and lead lists.", "Use the link builder on this page to open searches for a company's decision makers."),
                     _f("Connection notes", "A note on a request is limited to 300 characters.", "Mention one specific thing you noticed about their business. Use the 300-character counter in Pipeline & Templates."),
                     _f("Posts and comments", "Useful comments on target companies' posts get you seen without cold outreach.", "Three genuine comments a day beats a mass message."),
                     _f("Jobs and company pages", "Hiring posts show what a company is investing in.", "Log a promising job here as an application so you remember to follow up.")],
    },
    "fiverr": {
        "pages": [("Seller dashboard", "https://www.fiverr.com/seller_dashboard"), ("Inbox", "https://www.fiverr.com/inbox"), ("Browse gigs", "https://www.fiverr.com/categories")],
        "features": [_f("Gigs and three packages", "Each gig sells a defined result at up to three price levels.", "Make the title say exactly what the buyer gets, and price the middle package to be the obvious choice."),
                     _f("Gig analytics", "Fiverr shows impressions, clicks and orders per gig.", "Copy the weekly numbers into Activity here. Click rate shows the thumbnail and title; order rate shows the description and price."),
                     _f("Custom offers and extras", "You can send a tailored offer in the chat and add paid extras such as fast delivery.", "Offer a custom quote for any enquiry that does not fit a package."),
                     _f("Orders, delivery and reviews", "Delivery and the review that follows drive your ranking over time.", "Ask each delivered buyer for a review, politely and once."),
                     _f("Seller levels and response rate", "Level and response rate depend on real performance and quick replies.", "Reply fast by checking in on schedule. Do not try to look online while away.")],
    },
    "upwork": {
        "pages": [("Find work", "https://www.upwork.com/nx/find-work/"), ("Proposals", "https://www.upwork.com/nx/proposals/"), ("Messages", "https://www.upwork.com/ab/messages/")],
        "features": [_f("Connects", "Sending a proposal uses Connects, which cost money.", "Apply to fewer jobs that fit well, and log the result of each here to learn what wins."),
                     _f("Saved searches and alerts", "Save a search for your skills and get alerted to new jobs.", "Open your saved searches first thing, and be early with a strong first line."),
                     _f("Hourly and fixed-price contracts", "Hourly contracts track time; fixed price uses milestones.", "Break fixed-price work into milestones you can deliver and be paid for."),
                     _f("Specialized profiles and portfolio", "You can show different profiles for different services.", "Match the profile's wording to the jobs you want."),
                     _f("Client history", "Clients show spend, hire rate and reviews.", "Prefer clients with a payment method verified and a history of hiring.")],
    },
    "freelancer": {
        "pages": [("Browse projects", "https://www.freelancer.com/jobs/"), ("Messages", "https://www.freelancer.com/messages/")],
        "features": [_f("Bidding on projects", "You place a bid with a price and delivery time.", "Read the whole brief and answer its specific question in the first line."),
                     _f("Milestones", "Payments can be released in stages as work is accepted.", "Propose small milestones so both sides stay comfortable."),
                     _f("Contests", "Clients run design contests where several people submit work.", "Enter only where the brief is clear and the prize is worth your time."),
                     _f("Exams and preferred freelancer programs", "Exams and verifications add credibility to a profile.", "Take the ones that match the work you want.")],
    },
    "peopleperhour": {
        "pages": [("Find work", "https://www.peopleperhour.com/freelance-jobs")],
        "features": [_f("Proposals", "You respond to a buyer's brief with a proposal and price.", "Open with their goal, then your plan, then a timeline."),
                     _f("Hourlies", "Fixed-price offers (Hourlies) that buyers can purchase directly.", "Sell one clear deliverable with a fixed scope."),
                     _f("Workstream", "Work and payments are managed in a shared workspace.", "Keep communication inside the platform.")],
    },
    "contra": {
        "pages": [("Opportunities", "https://contra.com/opportunities")],
        "features": [_f("Portfolio-first profile", "Your project pages are the main thing clients see.", "Add projects with the problem, your work and the result you can prove."),
                     _f("Inbound enquiries", "Clients reach out from your profile.", "Reply quickly and ask two clear questions."),
                     _f("Fees", "Fee terms change over time.", "Read their current terms before quoting.")],
    },
    "toptal": {
        "pages": [("Apply or sign in", "https://www.toptal.com/")],
        "features": [_f("Vetted network", "Talent passes a screening process before getting matched.", "Prepare real examples of your work before applying."),
                     _f("Matched opportunities", "Work arrives through the talent team rather than open bidding.", "Keep your availability current so you are matched correctly.")],
    },
    "guru": {
        "pages": [("Find jobs", "https://www.guru.com/d/jobs/")],
        "features": [_f("Quotes", "You send a quote against an employer's job.", "Quote for a defined scope, with proof of similar work."),
                     _f("Workrooms and payment protection", "Each job has a workroom to share files and agree on payments.", "Keep agreements and files in the workroom."),
                     _f("Categories and specialties", "Profiles are searchable by category.", "Use the exact words clients search for in your headline.")],
    },
    "clutch": {
        "pages": [("Directory", "https://clutch.co/"), ("Leave a review", "https://review.clutch.co/")],
        "features": [_f("Verified Client Reviews", "B2B buyers filter agencies by verified third-party interviews.", "Ask every satisfied retainer or Upwork client for a 3-minute Clutch review."),
                     _f("Leader Matrix & Service Focus", "Rankings depend on verified reviews, service focus percentages, and portfolio.", "Keep your core service lines focused rather than listing 20 generic skills."),
                     _f("UTM Referral Tracking", "Track clicks from your Clutch profile back to your agency site.", "Tag your Clutch website link with ?utm_source=clutch so Visitor Radar spots referrals.")],
    },
    "other": {"pages": [], "features": [_f("Your own checklist", "Any site works here: add its links, templates and routine.", "Save the pages you open daily as links.")]},
}
for _id, _x in EXTRAS.items():
    PLATFORMS[_id]["pages"] = [{"label": l, "url": u} for l, u in _x["pages"]]
    PLATFORMS[_id]["features"] = _x["features"]


STATUSES = ["saved", "applied", "replied", "interview", "won", "lost"]
OPEN_STATUSES = ("saved", "applied", "replied", "interview")
ACTIVITY_KINDS = list(ACTIVITY_LABELS.keys())
TYPES = ["link", "pipeline", "template", "routine", "done", "activity", "message", "setting", "experiment"]
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _text(v: Any, name: str, max_len: int, required: bool = True) -> Optional[str]:
    v = (v or "").strip() if isinstance(v, str) or v is None else str(v).strip()
    if required and not v:
        raise ValueError(f"{name} is required.")
    if len(v) > max_len:
        raise ValueError(f"{name} is too long (max {max_len}).")
    return v or None


def _url(v: Any, required: bool = False) -> Optional[str]:
    v = _text(v, "url", 500, required)
    if v is None:
        return None
    p = urlparse(v if "://" in v else f"https://{v}")
    if p.scheme not in ("http", "https") or not p.hostname or "." not in p.hostname:
        raise ValueError("url must be a web address such as https://example.com/page")
    return v if "://" in v else f"https://{v}"


def _day(v: Any, name: str, required: bool = False) -> Optional[str]:
    if v in (None, ""):
        if required:
            raise ValueError(f"{name} is required.")
        return None
    if not isinstance(v, str) or not DAY.match(v):
        raise ValueError(f"{name} must be a date like 2026-10-25.")
    date.fromisoformat(v)
    return v


def _iso(v: Any, name: str, required: bool = False) -> Optional[str]:
    if v in (None, ""):
        if required:
            raise ValueError(f"{name} is required.")
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{name} must be a date and time.")
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def clean(rtype: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if rtype not in TYPES:
        raise ValueError(f"type must be one of {TYPES}")
    d = data or {}
    if rtype == "link":
        return {"title": _text(d.get("title"), "title", 120), "url": _url(d.get("url"), True)}
    if rtype == "pipeline":
        status = d.get("status") or "saved"
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        value = d.get("value")
        if value not in (None, ""):
            value = float(value)
            if value < 0:
                raise ValueError("value cannot be negative.")
        cost = d.get("cost")
        if cost not in (None, ""):
            cost = float(cost)
            if cost < 0:
                raise ValueError("cost cannot be negative.")
        crm_lead_id = int(d["crm_lead_id"]) if d.get("crm_lead_id") not in (None, "") else None
        return {"title": _text(d.get("title"), "title", 160), "url": _url(d.get("url")), "cost": cost if cost not in (None, "") else None, "counterparty": _text(d.get("counterparty"), "counterparty", 120, False), "status": status,
                "value": value if value not in (None, "") else None, "next_followup": _day(d.get("next_followup"), "next_followup"), "notes": _text(d.get("notes"), "notes", 1000, False), "crm_lead_id": crm_lead_id}
    if rtype == "template":
        return {"name": _text(d.get("name"), "name", 100), "body": _text(d.get("body"), "body", 4000)}
    if rtype == "routine":
        return {"label": _text(d.get("label"), "label", 140)}
    if rtype == "done":
        return {"routine_id": int(d.get("routine_id")), "day": _day(d.get("day"), "day", True)}
    if rtype == "activity":
        if d.get("kind") not in ACTIVITY_KINDS:
            raise ValueError(f"kind must be one of {ACTIVITY_KINDS}")
        qty = int(d.get("qty", 1))
        if not 0 <= qty <= 100000:
            raise ValueError("qty must be between 0 and 100000.")
        return {"kind": d["kind"], "qty": qty, "day": _day(d.get("day"), "day", True)}
    if rtype == "experiment":
        changed = _day(d.get("changed_on"), "changed_on", True)
        review = _day(d.get("review_on"), "review_on") or (date.fromisoformat(changed) + timedelta(days=30)).isoformat()
        if review < changed:
            raise ValueError("The review date cannot be before the change.")
        return {"what": _text(d.get("what"), "what", 160), "changed_on": changed, "review_on": review, "result": _text(d.get("result"), "result", 300, False), "done": bool(d.get("done", False))}
    if rtype == "message":
        rec, rep = _iso(d.get("received_at"), "received_at", True), _iso(d.get("replied_at"), "replied_at")
        if rep and rep < rec:
            raise ValueError("The reply cannot be earlier than the message.")
        return {"received_at": rec, "replied_at": rep, "note": _text(d.get("note"), "note", 300, False)}
    days = d.get("work_days", [0, 1, 2, 3, 4])
    if not isinstance(days, list) or not all(isinstance(x, int) and 0 <= x <= 6 for x in days):
        raise ValueError("work_days must be numbers 0 (Monday) to 6 (Sunday).")
    hm = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    start, end = d.get("start", "09:00"), d.get("end", "17:00")
    if not hm.match(start) or not hm.match(end) or start >= end:
        raise ValueError("start and end must be times like 09:00 and 17:00, with start before end.")
    return {"work_days": sorted(set(days)), "start": start, "end": end, "remind_minutes": int(d.get("remind_minutes", 0)) if int(d.get("remind_minutes", 0)) in (0, 30, 60, 120) else 60, "notify": bool(d.get("notify", False)), "weekly_invite_limit": _limit(d.get("weekly_invite_limit", 80))}


def _limit(v: Any) -> int:
    v = int(v)
    if not 0 <= v <= 500:
        raise ValueError("weekly_invite_limit must be between 0 and 500 (0 turns the pacing meter off).")
    return v


def _check_platform(platform: str, org_id: Optional[str] = None) -> Dict[str, Any]:
    if platform in PLATFORMS:
        return PLATFORMS[platform]
    if org_id:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM custom_channels WHERE org_id = ? AND slug = ? AND active = 1",
                (org_id, platform),
            ).fetchone()
            if row:
                return {
                    "label": row["label"],
                    "kind": "custom",
                    "archetype": row["archetype"],
                    "home": row["home_url"] or None,
                    "terms": None,
                    "search": None,
                    "rules": [f"Custom channel ({row['archetype'].replace('_', ' ')}) — tracked manually and via Side-Panel capture."],
                    "routine": ["Check new opportunities", "Send tailored outreach", "Follow up on open deals", "Log activity"],
                    "profile": ["Profile and portfolio updated"],
                    "templates": [],
                    "limits": {},
                    "pages": json.loads(row["quick_links_json"] or "[]"),
                    "features": [],
                }
    raise ValueError(f"Unknown platform '{platform}'.")


def _row(r) -> Dict[str, Any]:
    return {"id": r["id"], "platform": r["platform"], "type": r["type"], **json.loads(r["data_json"]), "created_at": r["created_at"], "updated_at": r["updated_at"]}


def list_records(org_id: str, platform: str, rtype: Optional[str] = None) -> List[Dict[str, Any]]:
    pmeta = _check_platform(platform, org_id)
    with get_db() as db:
        if rtype == "routine" and not db.execute("SELECT 1 FROM channel_records WHERE org_id = ? AND platform = ? AND type = 'routine'", (org_id, platform)).fetchone():
            for label in pmeta["routine"]:        # first visit: start with a sensible routine the person can edit or delete
                db.execute("INSERT INTO channel_records (org_id, platform, type, data_json) VALUES (?, ?, 'routine', ?)", (org_id, platform, json.dumps({"label": label})))
            db.commit()
        q, params = "SELECT * FROM channel_records WHERE org_id = ? AND platform = ?", [org_id, platform]
        if rtype:
            q, params = q + " AND type = ?", params + [rtype]
        rows = db.execute(q + " ORDER BY id", params).fetchall()
    return [_row(r) for r in rows]


def add_record(org_id: str, platform: str, rtype: str, data: Dict[str, Any]) -> Dict[str, Any]:
    _check_platform(platform, org_id)
    cleaned = clean(rtype, data)
    with get_db() as db:
        if rtype == "setting":
            db.execute("DELETE FROM channel_records WHERE org_id = ? AND platform = ? AND type = 'setting'", (org_id, platform))
        if rtype == "done":                                   # marking the same routine done twice for a day is one record
            for r in db.execute("SELECT id, data_json FROM channel_records WHERE org_id = ? AND platform = ? AND type = 'done'", (org_id, platform)).fetchall():
                j = json.loads(r["data_json"])
                if j["routine_id"] == cleaned["routine_id"] and j["day"] == cleaned["day"]:
                    return {**_row(db.execute("SELECT * FROM channel_records WHERE id = ?", (r["id"],)).fetchone())}
        cur = db.execute("INSERT INTO channel_records (org_id, platform, type, data_json) VALUES (?, ?, ?, ?)", (org_id, platform, rtype, json.dumps(cleaned)))
        db.commit()
        return _row(db.execute("SELECT * FROM channel_records WHERE id = ?", (cur.lastrowid,)).fetchone())


def update_record(org_id: str, platform: str, record_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    _check_platform(platform, org_id)
    with get_db() as db:
        row = db.execute("SELECT * FROM channel_records WHERE id = ? AND org_id = ? AND platform = ?", (record_id, org_id, platform)).fetchone()
        if not row:
            return None
        merged = {**json.loads(row["data_json"]), **(data or {})}
        db.execute("UPDATE channel_records SET data_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (json.dumps(clean(row["type"], merged)), record_id))
        db.commit()
        return _row(db.execute("SELECT * FROM channel_records WHERE id = ?", (record_id,)).fetchone())


def delete_record(org_id: str, platform: str, record_id: int) -> bool:
    _check_platform(platform, org_id)
    with get_db() as db:
        n = db.execute("DELETE FROM channel_records WHERE id = ? AND org_id = ? AND platform = ?", (record_id, org_id, platform)).rowcount
        db.commit()
    return n > 0


def summary(org_id: str, platform: str, today: Optional[date] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Everything here is computed from the person's own logs and native archetype tables."""
    pmeta = _check_platform(platform, org_id)
    spec = get_channel_spec(platform, pmeta.get("archetype"))
    today = today or date.today()
    now = now or datetime.now(timezone.utc)
    recs = list_records(org_id, platform)
    by = lambda t: [r for r in recs if r["type"] == t]
    pipeline = by("pipeline")
    counts = {s: sum(1 for r in pipeline if r["status"] == s) for s in STATUSES}
    due = [r for r in pipeline if r["status"] in OPEN_STATUSES and r["next_followup"] and r["next_followup"] <= today.isoformat()]
    closed = counts["won"] + counts["lost"]

    msgs = [m for m in by("message") if m["received_at"] >= (now - timedelta(days=30)).isoformat()]
    replied = [m for m in msgs if m["replied_at"]]
    minutes = [(datetime.fromisoformat(m["replied_at"]) - datetime.fromisoformat(m["received_at"])).total_seconds() / 60 for m in replied]
    waiting = [m for m in msgs if not m["replied_at"]]
    oldest = max(((now - datetime.fromisoformat(m["received_at"])).total_seconds() / 3600 for m in waiting), default=0)
    response = {"messages_30d": len(msgs), "replied": len(replied), "average_minutes": round(sum(minutes) / len(minutes)) if minutes else None,
                "within_1h_pct": round(100 * sum(1 for x in minutes if x <= 60) / len(minutes)) if minutes else None,
                "within_24h_pct": round(100 * sum(1 for x in minutes if x <= 1440) / len(minutes)) if minutes else None,
                "unanswered": len(waiting), "oldest_unanswered_hours": round(oldest, 1)}

    monday = (today - timedelta(days=today.weekday())).isoformat()
    week: Dict[str, int] = {}
    for a in by("activity"):
        if a["day"] >= monday:
            week[a["kind"]] = week.get(a["kind"], 0) + a["qty"]

    routines = by("routine")
    done_days: Dict[str, set] = {}
    for d in by("done"):
        done_days.setdefault(d["day"], set()).add(d["routine_id"])
    ids = {r["id"] for r in routines}
    done_today = len(done_days.get(today.isoformat(), set()) & ids)
    streak, day = 0, today if routines and done_days.get(today.isoformat(), set()) >= ids else today - timedelta(days=1)
    while routines and done_days.get(day.isoformat(), set()) >= ids:
        streak += 1
        day -= timedelta(days=1)
    setting = next(iter(by("setting")), None)

    # Funnel from where each application is now. Lost counts as "no reply" unless it was moved through Replied first.
    sent = [r for r in pipeline if r["status"] != "saved"]
    got_reply = counts["replied"] + counts["interview"] + counts["won"]
    cost_total = sum((r.get("cost") or 0) for r in sent)
    funnel = {"applications": len(sent), "reply_rate_percent": round(100 * got_reply / len(sent)) if sent else None,
              "interview_rate_percent": round(100 * (counts["interview"] + counts["won"]) / len(sent)) if sent else None,
              "win_rate_of_applied_percent": round(100 * counts["won"] / len(sent)) if sent else None,
              "cost_total": cost_total, "cost_per_reply": round(cost_total / got_reply, 2) if got_reply and cost_total else None,
              "cost_per_win": round(cost_total / counts["won"], 2) if counts["won"] and cost_total else None}

    pacing = None
    if platform == "linkedin":
        since = (today - timedelta(days=6)).isoformat()
        sent7 = sum(a["qty"] for a in by("activity") if a["kind"] == "invite_sent" and since <= a["day"] <= today.isoformat())
        limit = (setting or {}).get("weekly_invite_limit", 80)
        pacing = {"invites_7d": sent7, "today": sum(a["qty"] for a in by("activity") if a["kind"] == "invite_sent" and a["day"] == today.isoformat()), "limit": limit,
                  "remaining": max(limit - sent7, 0) if limit else None, "over": bool(limit and sent7 > limit),
                  "note": "LinkedIn publishes no official number. About 100 invites a week is the figure most often reported, applied over a rolling 7 days. Your own limit is the one set here."}

    # Query native archetype tables
    with get_db() as db:
        bids = [dict(r) for r in db.execute("SELECT * FROM channel_bids WHERE org_id = ? AND platform = ? ORDER BY id DESC", (org_id, platform)).fetchall()]
        gigs = [dict(r) for r in db.execute("SELECT * FROM channel_gigs WHERE org_id = ? AND platform = ? ORDER BY id DESC", (org_id, platform)).fetchall()]
        reviews = [dict(r) for r in db.execute("SELECT * FROM channel_reviews WHERE org_id = ? AND platform = ? ORDER BY id DESC", (org_id, platform)).fetchall()]
        pacing_rows = [dict(r) for r in db.execute("SELECT * FROM channel_pacing WHERE org_id = ? AND platform = ? ORDER BY day DESC LIMIT 14", (org_id, platform)).fetchall()]
        won_clients = [dict(r) for r in db.execute("SELECT id, company_name, domain, updated_at FROM leads WHERE org_id = ? AND status = 'won' ORDER BY updated_at DESC LIMIT 20", (org_id,)).fetchall()] if spec["archetype"] == "review_directory" else []

    # Compute archetype-native summaries
    arch = spec["archetype"]
    currency = spec.get("native_currency")
    unit_cost = (currency or {}).get("unit_cost_usd", 0.0)
    curr_name = (currency or {}).get("name", "Credits")

    active_bids = [b for b in bids if b["status"] in ("saved", "applied", "viewed", "replied", "interview")]
    won_bids = [b for b in bids if b["status"] == "won"]
    lost_bids = [b for b in bids if b["status"] == "lost"]
    viewed_bids = [b for b in bids if b["status"] in ("viewed", "replied", "interview", "won")]
    replied_bids = [b for b in bids if b["status"] in ("replied", "interview", "won")]
    total_curr_spent = sum((b.get("currency_spent") or 0) for b in bids)
    spend_usd = round(total_curr_spent * unit_cost, 2) if unit_cost else round(cost_total, 2)
    bids_open_val = sum((b.get("bid_amount") or 0) for b in active_bids)
    bids_won_val = sum((b.get("bid_amount") or 0) for b in won_bids)
    combined_open_val = round(sum((r["value"] or 0) for r in pipeline if r["status"] in OPEN_STATUSES) + bids_open_val, 2)
    combined_won_val = round(sum((r["value"] or 0) for r in pipeline if r["status"] == "won") + bids_won_val, 2)
    combined_closed = closed + len(won_bids) + len(lost_bids)
    combined_won_cnt = counts["won"] + len(won_bids)
    combined_win_rate = round(100 * combined_won_cnt / combined_closed) if combined_closed else None

    # Hook A/B leaderboard across bids
    hook_stats: Dict[str, Dict[str, Any]] = {}
    for b in bids:
        hid = (b.get("hook_template_id") or "").strip()
        if not hid:
            continue
        hs = hook_stats.setdefault(hid, {"hook": hid, "sent": 0, "viewed": 0, "replied": 0, "won": 0})
        hs["sent"] += 1
        if b["status"] in ("viewed", "replied", "interview", "won"):
            hs["viewed"] += 1
        if b["status"] in ("replied", "interview", "won"):
            hs["replied"] += 1
        if b["status"] == "won":
            hs["won"] += 1
    hooks_leaderboard = sorted(
        [{**v, "reply_rate_pct": round(100 * v["replied"] / v["sent"]) if v["sent"] else 0} for v in hook_stats.values()],
        key=lambda x: (-x["reply_rate_pct"], -x["sent"]),
    )

    # Gigs summary
    gig_impr = sum((g.get("impressions") or 0) for g in gigs) + sum(a["qty"] for a in by("activity") if a["kind"] in ("gig_impressions", "gig_impression"))
    gig_clicks = sum((g.get("clicks") or 0) for g in gigs) + sum(a["qty"] for a in by("activity") if a["kind"] in ("gig_clicks", "gig_click"))
    gig_orders = sum((g.get("orders") or 0) for g in gigs) + sum(a["qty"] for a in by("activity") if a["kind"] in ("gig_orders", "gig_order"))
    gig_rev = sum((g.get("revenue") or 0) for g in gigs) + combined_won_val
    ctr_pct = round(100 * gig_clicks / gig_impr, 1) if gig_impr else None
    cvr_pct = round(100 * gig_orders / gig_clicks, 1) if gig_clicks else None

    # Reviews summary
    pub_reviews = [r for r in reviews if r["status"] == "published"]
    ratings = [r["rating"] for r in pub_reviews if r.get("rating") is not None]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    # LinkedIn pacing details
    since7 = (today - timedelta(days=6)).isoformat()
    li_invites_7d = (pacing["invites_7d"] if pacing else 0) + sum(r["invites_sent"] for r in pacing_rows if r["day"] >= since7)
    li_accepted_7d = sum(a["qty"] for a in by("activity") if a["kind"] == "invite_accepted" and a["day"] >= since7)
    li_replies_7d = sum(a["qty"] for a in by("activity") if a["kind"] == "reply_received" and a["day"] >= since7)
    li_sent_msgs_7d = sum(a["qty"] for a in by("activity") if a["kind"] == "message_sent" and a["day"] >= since7) + sum(r["inmails_sent"] for r in pacing_rows if r["day"] >= since7)
    li_meetings = sum(a["qty"] for a in by("activity") if a["kind"] == "call_booked") + counts["interview"] + counts["won"]
    li_ssi = max([r.get("ssi_score") or 0 for r in pacing_rows] or [0])

    # Build 5 platform-specific KPI cards (no hardcoded "Open applications" across non-bidding sites!)
    if arch == "social_outbound":
        kpis = [
            {"id": "weekly_invites_left", "label": "Weekly Invites Left", "value": pacing["remaining"] if pacing and pacing["remaining"] is not None else "—", "hint": f"{li_invites_7d}/{pacing['limit'] if pacing else 80} used (7d)"},
            {"id": "acceptance_rate", "label": "Acceptance Rate", "value": f"{round(100 * li_accepted_7d / li_invites_7d)}%" if li_invites_7d else "n/a", "hint": f"{li_accepted_7d} accepted / {li_invites_7d} sent"},
            {"id": "reply_rate", "label": "Reply Rate", "value": f"{round(100 * li_replies_7d / li_sent_msgs_7d)}%" if li_sent_msgs_7d else "n/a", "hint": f"{li_replies_7d} replies (7d)"},
            {"id": "meetings_booked", "label": "Meetings Booked", "value": li_meetings, "hint": f"{combined_open_val:,.0f} USD in play" if combined_open_val else "log calls booked"},
            {"id": "ssi_score", "label": "SSI / Profile Score", "value": f"{li_ssi}/100" if li_ssi else "Not set", "hint": f"{done_today}/{len(routines)} routine today"},
        ]
    elif arch == "bidding_marketplace":
        cost_per_reply_curr = round(total_curr_spent / len(replied_bids), 1) if replied_bids and total_curr_spent else None
        view_to_reply = round(100 * len(replied_bids) / len(viewed_bids)) if viewed_bids else None
        kpis = [
            {"id": "active_bids_value", "label": "Active Bids & Value", "value": len(active_bids) + sum(counts[s] for s in OPEN_STATUSES), "hint": f"${combined_open_val:,.0f} in play" if combined_open_val else "no valued bids"},
            {"id": "currency_roi", "label": f"{curr_name} / Reply", "value": f"{cost_per_reply_curr} {curr_name}" if cost_per_reply_curr is not None else f"{int(total_curr_spent)} {curr_name}", "hint": f"${spend_usd:,.2f} total spend"},
            {"id": "view_to_reply", "label": "View-to-Reply Rate", "value": f"{view_to_reply}%" if view_to_reply is not None else "n/a", "hint": f"{len(viewed_bids)} viewed · {len(replied_bids)} replied"},
            {"id": "win_rate", "label": "Win Rate", "value": f"{combined_win_rate}%" if combined_win_rate is not None else "n/a", "hint": f"${combined_won_val:,.0f} won" if combined_won_val else "needs won/lost"},
            {"id": "followups_due", "label": "Follow-ups Due", "value": len(due), "hint": due[0]["title"] if due else "all caught up"},
        ]
    elif arch == "inbound_storefront":
        sla_mins = response["average_minutes"] or (round(sum(g.get("avg_response_mins") or 0 for g in gigs) / len(gigs)) if gigs else None)
        kpis = [
            {"id": "active_gigs", "label": "Active Gigs / Services", "value": len(gigs), "hint": f"{gig_orders} total orders"},
            {"id": "ctr_pct", "label": "Impressions -> Clicks", "value": f"{ctr_pct}%" if ctr_pct is not None else "n/a", "hint": f"{gig_impr:,} impr · {gig_clicks:,} clicks"},
            {"id": "cvr_pct", "label": "Click -> Order (CVR)", "value": f"{cvr_pct}%" if cvr_pct is not None else "n/a", "hint": f"{gig_orders} orders"},
            {"id": "avg_response_sla", "label": "Avg Response (SLA)", "value": f"{sla_mins} min" if sla_mins is not None else "n/a", "hint": f"Target <= {spec['sla_target_mins']}m ({response['unanswered']} waiting)"},
            {"id": "monthly_revenue", "label": "Storefront Revenue", "value": f"${gig_rev:,.0f}", "hint": f"{done_today}/{len(routines)} routine today"},
        ]
    elif arch == "vetted_network":
        trials = sum(1 for b in bids if b["status"] == "interview") + sum(a["qty"] for a in by("activity") if a["kind"] == "trial_started")
        matches = len(bids) + sum(a["qty"] for a in by("activity") if a["kind"] == "match_received")
        avail_label = "Available" if (setting and setting.get("notify")) else "Set Bench Status"
        avg_rate = round(sum((b.get("bid_amount") or 0) for b in bids) / len(bids)) if bids else None
        kpis = [
            {"id": "availability_status", "label": "Availability Status", "value": avail_label, "hint": "Keep bench status current"},
            {"id": "active_matches", "label": "Active Matches", "value": len(active_bids) + sum(counts[s] for s in OPEN_STATUSES), "hint": f"{matches} total matches"},
            {"id": "interview_to_trial", "label": "Interview-to-Trial %", "value": f"{round(100 * trials / matches)}%" if matches else "n/a", "hint": f"{trials} trials"},
            {"id": "trial_to_hire", "label": "Trial-to-Hire %", "value": f"{combined_win_rate}%" if combined_win_rate is not None else "n/a", "hint": f"{combined_won_cnt} hires"},
            {"id": "avg_rate", "label": "Avg Hourly Rate", "value": f"${avg_rate}/hr" if avg_rate else "n/a", "hint": f"${combined_won_val:,.0f} won"},
        ]
    elif arch == "review_directory":
        inquiries = sum(a["qty"] for a in by("activity") if a["kind"] == "inquiry_received") + sum(counts[s] for s in OPEN_STATUSES)
        utm_clicks = sum(a["qty"] for a in by("activity") if a["kind"] == "profile_view")
        kpis = [
            {"id": "verified_reviews", "label": "Verified Reviews", "value": len(pub_reviews), "hint": f"{len([r for r in reviews if r['status'] == 'invited'])} pending invites"},
            {"id": "avg_rating", "label": "Avg Star Rating", "value": f"{avg_rating} / 5.0" if avg_rating else "n/a", "hint": f"{len(pub_reviews)} published"},
            {"id": "directory_rank", "label": "Leader Matrix Rank", "value": f"#{setting.get('weekly_invite_limit')}" if (setting and setting.get("weekly_invite_limit")) else "Track Rank", "hint": "Category & city rank"},
            {"id": "inbound_inquiries", "label": "Inbound Inquiries", "value": inquiries, "hint": f"${combined_open_val:,.0f} in play" if combined_open_val else "UTM & direct"},
            {"id": "utm_traffic", "label": "UTM Referral Clicks", "value": utm_clicks, "hint": f"${combined_won_val:,.0f} won"},
        ]
    else:
        kpis = [
            {"id": "active_bids_value", "label": "Open Pipeline", "value": len(active_bids) + sum(counts[s] for s in OPEN_STATUSES), "hint": f"${combined_open_val:,.0f} in play"},
            {"id": "followups_due", "label": "Follow-ups Due", "value": len(due), "hint": due[0]["title"] if due else "nothing overdue"},
            {"id": "win_rate", "label": "Win Rate", "value": f"{combined_win_rate}%" if combined_win_rate is not None else "n/a", "hint": f"${combined_won_val:,.0f} won"},
            {"id": "avg_response_sla", "label": "Avg Reply Time", "value": f"{response['average_minutes']} min" if response["average_minutes"] is not None else "n/a", "hint": f"{response['unanswered']} waiting"},
            {"id": "routine_streak", "label": "Routine Streak", "value": f"{streak} d", "hint": f"{done_today}/{len(routines)} done today"},
        ]

    experiments = [{"id": e["id"], "what": e["what"], "review_on": e["review_on"]} for e in by("experiment") if not e["done"] and e["review_on"] <= today.isoformat()]
    return {
        "platform": platform,
        "spec": spec,
        "kpis": kpis,
        "funnel": funnel,
        "pacing": pacing,
        "experiments_due": experiments,
        "pipeline": {
            "counts": counts,
            "open": sum(counts[s] for s in OPEN_STATUSES) + len(active_bids),
            "followups_due": len(due),
            "due_titles": [r["title"] for r in due][:5],
            "win_rate_percent": combined_win_rate,
            "value_won": combined_won_val,
            "value_open": combined_open_val,
        },
        "native": {
            "bids": bids,
            "gigs": gigs,
            "reviews": reviews,
            "won_clients": won_clients,
            "pacing_rows": pacing_rows,
            "hooks_leaderboard": hooks_leaderboard,
            "spend_usd": spend_usd,
            "total_currency_spent": total_curr_spent,
        },
        "response": response,
        "activity_this_week": week,
        "routine": {"total": len(routines), "done_today": done_today, "streak_days": streak},
        "setting": setting,
        "note": "Built only from what you log here. Nothing is read from the platform.",
    }


def linkedin_search_links(company: str, titles: List[str], location: Optional[str] = None) -> List[Dict[str, str]]:
    """Plain links to open in your own browser. Nothing is fetched."""
    company = _text(company, "company", 120)
    titles = [t for t in (_text(x, "title", 60, False) for x in (titles or ["CEO", "Founder", "CTO", "Head of Engineering"])) if t][:6]
    q = " OR ".join(f'"{t}"' for t in titles)
    loc = f' "{location.strip()}"' if location and location.strip() else ""
    return [
        {"label": f"LinkedIn people at {company}", "url": f"https://www.linkedin.com/search/results/people/?keywords={quote(company + ' ' + ' '.join(titles[:2]), safe='')}"},
        {"label": "LinkedIn company page search", "url": f"https://www.linkedin.com/search/results/companies/?keywords={quote(company, safe='')}"},
        {"label": "Google: leadership on LinkedIn", "url": f"https://www.google.com/search?q={quote(f'site:linkedin.com/in {chr(34)}{company}{chr(34)} ({q}){loc}', safe='')}"},
        {"label": "Google: the company's own team page", "url": f"https://www.google.com/search?q={quote(f'{company} team OR leadership OR about us{loc}', safe='')}"},
    ]


def get_hidden_platforms(org_id: str) -> List[str]:
    with get_db() as db:
        row = db.execute("SELECT hidden_platforms_json FROM channel_preferences WHERE org_id = ?", (org_id,)).fetchone()
    if not row:
        return []
    try:
        return json.loads(row["hidden_platforms_json"] or "[]")
    except Exception:
        return []


def set_hidden_platforms(org_id: str, hidden: List[str]) -> List[str]:
    clean_hidden = sorted(set(str(x).strip() for x in (hidden or []) if str(x).strip()))
    with get_db() as db:
        db.execute(
            "INSERT INTO channel_preferences (org_id, hidden_platforms_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(org_id) DO UPDATE SET hidden_platforms_json = excluded.hidden_platforms_json, updated_at = CURRENT_TIMESTAMP",
            (org_id, json.dumps(clean_hidden)),
        )
        db.commit()
    return clean_hidden


def list_platforms_with_specs(org_id: str) -> Dict[str, Any]:
    out = []
    for k, v in PLATFORMS.items():
        spec = get_channel_spec(k)
        out.append({
            "id": k,
            **{x: v[x] for x in ("label", "kind", "home", "terms", "rules", "profile", "limits", "templates", "pages", "features")},
            "has_search": bool(v["search"]),
            **spec,
            "is_custom": False,
        })
    with get_db() as db:
        custom_rows = db.execute("SELECT * FROM custom_channels WHERE org_id = ? AND active = 1 ORDER BY id", (org_id,)).fetchall()
    for r in custom_rows:
        spec = get_channel_spec("other", r["archetype"])
        out.append({
            "id": r["slug"],
            "label": r["label"],
            "kind": "custom",
            "home": r["home_url"] or None,
            "terms": None,
            "rules": [f"Custom channel ({spec['archetype_label']}) — tracked manually and via Side-Panel capture."],
            "profile": ["Profile and portfolio updated"],
            "limits": {},
            "templates": [],
            "pages": json.loads(r["quick_links_json"] or "[]"),
            "features": [],
            "has_search": False,
            **spec,
            "is_custom": True,
        })
    return {
        "platforms": out,
        "hidden_platforms": get_hidden_platforms(org_id),
        "statuses": STATUSES,
        "activity_kinds": ACTIVITY_KINDS,
        "activity_labels": ACTIVITY_LABELS,
        "archetypes": [{"id": k, "label": v["label"]} for k, v in ARCHETYPES.items()],
    }


def overview(org_id: str) -> Dict[str, Any]:
    catalog = list_platforms_with_specs(org_id)
    hidden = set(catalog["hidden_platforms"])
    out = []
    alerts: List[Dict[str, Any]] = []
    for p in catalog["platforms"]:
        pid = p["id"]
        if pid == "other" or pid in hidden:
            continue
        s = summary(org_id, pid)
        spend_usd = s["native"]["spend_usd"]
        won_val = s["pipeline"]["value_won"]
        net_roi_pct = round(((won_val - spend_usd) / spend_usd) * 100, 1) if spend_usd > 0 else None
        out.append({
            "platform": pid,
            "label": p["label"],
            "kind": p["kind"],
            "archetype": p["archetype"],
            "archetype_label": p["archetype_label"],
            "category": p["category"],
            "native_currency": p["native_currency"],
            "open": s["pipeline"]["open"],
            "followups_due": s["pipeline"]["followups_due"],
            "value_open": s["pipeline"]["value_open"],
            "value_won": won_val,
            "spend_usd": spend_usd,
            "net_roi_pct": net_roi_pct,
            "win_rate_percent": s["pipeline"]["win_rate_percent"],
            "applications": s["funnel"]["applications"],
            "cost_total": spend_usd,
            "routine": s["routine"],
            "unanswered": s["response"]["unanswered"],
            "average_minutes": s["response"]["average_minutes"],
            "sla_target_mins": p["sla_target_mins"],
        })
        if s["response"]["unanswered"] > 0 and p["sla_target_mins"] <= 60:
            alerts.append({"platform": pid, "label": p["label"], "tone": "bad", "text": f"{p['label']}: {s['response']['unanswered']} inquiry waiting (1h SLA)"})
        elif s["pipeline"]["followups_due"] > 0:
            alerts.append({"platform": pid, "label": p["label"], "tone": "warn", "text": f"{p['label']}: {s['pipeline']['followups_due']} follow-up(s) due"})
        if pid == "linkedin" and s.get("pacing") and s["pacing"].get("remaining") is not None:
            rem = s["pacing"]["remaining"]
            lim = s["pacing"]["limit"]
            alerts.append({"platform": pid, "label": p["label"], "tone": "info" if rem > 10 else "warn", "text": f"LinkedIn: {rem}/{lim} weekly invites remaining"})
        viewed_n = len([b for b in s["native"]["bids"] if b["status"] == "viewed"])
        if viewed_n > 0:
            alerts.append({"platform": pid, "label": p["label"], "tone": "accent", "text": f"{p['label']}: {viewed_n} proposal(s) viewed by client"})
    return {"platforms": out, "alerts": alerts}


def _normalize_job_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    p = urlparse(raw_url.strip())
    host = (p.hostname or "").lower()
    port = f":{p.port}" if p.port else ""
    path = (p.path or "").rstrip("/")
    return f"{p.scheme.lower()}://{host}{port}{path}" + (f"?{p.query}" if p.query else "")


def capture_from_sidepanel(org_id: str, platform: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """1-click Side-Panel Auto-Capture: idempotent on normalized job_url, updates channel_bids + CRM lead."""
    pmeta = _check_platform(platform, org_id)
    spec = get_channel_spec(platform, pmeta.get("archetype"))
    title = _text(payload.get("title") or payload.get("job_title"), "title", 180)
    raw_url = _url(payload.get("url") or payload.get("job_url"), False) or ""
    url = _normalize_job_url(raw_url)
    client_name = _text(payload.get("client_name") or payload.get("company_name"), "client_name", 120, False) or ""
    budget = float(payload.get("budget") or payload.get("bid_amount") or 0)
    currency_spent = float(payload.get("currency_spent") or 0)
    hook_id = _text(payload.get("hook_template_id"), "hook_template_id", 100, False) or ""
    notes = _text(payload.get("notes"), "notes", 1000, False) or ""
    curr_name = (spec.get("native_currency") or {}).get("name") or ""

    from database.models import LeadRepository

    with get_db() as db:
        existing_bid = None
        if url:
            existing_bid = db.execute(
                "SELECT * FROM channel_bids WHERE org_id = ? AND platform = ? AND lower(rtrim(job_url, '/')) = lower(rtrim(?, '/')) ORDER BY id ASC LIMIT 1",
                (org_id, platform, url),
            ).fetchone()

        if existing_bid:
            bid_id = existing_bid["id"]
            db.execute(
                """UPDATE channel_bids SET
                     job_url = ?, title = ?,
                     client_name = CASE WHEN ? != '' THEN ? ELSE client_name END,
                     bid_amount = CASE WHEN ? > 0 THEN ? ELSE bid_amount END,
                     currency_spent = CASE WHEN ? > 0 THEN ? ELSE currency_spent END,
                     boosted = ?,
                     hook_template_id = CASE WHEN ? != '' THEN ? ELSE hook_template_id END,
                     notes = CASE WHEN ? != '' THEN ? ELSE notes END,
                     updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND org_id = ?""",
                (
                    url, title, client_name, client_name, budget, budget,
                    currency_spent, currency_spent, 1 if payload.get("boosted") else 0,
                    hook_id, hook_id, notes, notes, bid_id, org_id,
                ),
            )
            crm_lead_id = existing_bid["crm_lead_id"]
            lead = LeadRepository.get_lead(crm_lead_id, org_id) if crm_lead_id else None
            if lead and budget > 0:
                new_notes = re.sub(r"EST VALUE:\s*\$[0-9,]+\s*(\|\s*)?", "", lead.get("notes") or "").strip(" | ")
                prefix = f"EST VALUE: ${budget:,.0f}"
                merged_notes = f"{prefix} | {new_notes}" if new_notes else prefix
                db.execute("UPDATE leads SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND org_id = ?", (merged_notes, lead["id"], org_id))
                lead["notes"] = merged_notes
            db.commit()
            bid = dict(db.execute("SELECT * FROM channel_bids WHERE id = ?", (bid_id,)).fetchone())
            return {"bid": bid, "lead": lead, "deduplicated": True}

    slug = re.sub(r"[^a-z0-9]+", "-", (client_name or title).lower()).strip("-")[:32] or "lead"
    domain = f"{slug}.{platform}.channel"
    lead = LeadRepository.create_or_get_lead(
        company_name=(client_name or title)[:120],
        domain=domain,
        source_channel=platform,
        source_query=title,
        notes=(f"EST VALUE: ${budget:,.0f} | " if budget > 0 else "") + f"Captured from {pmeta['label']} Side Panel: {title} {url}".strip(),
        org_id=org_id,
    )

    with get_db() as db:
        cur = db.execute(
            """INSERT INTO channel_bids
               (org_id, platform, job_url, title, client_name, bid_amount, currency_name, currency_spent, boosted, hook_template_id,
                client_payment_verified, client_hire_rate, client_avg_hourly, status, notes, crm_lead_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                org_id, platform, url, title, client_name, budget, curr_name, currency_spent,
                1 if payload.get("boosted") else 0, hook_id,
                1 if payload.get("client_payment_verified") else 0,
                int(payload.get("client_hire_rate") or 0),
                float(payload.get("client_avg_hourly") or 0),
                payload.get("status") or "applied",
                notes, lead["id"],
            ),
        )
        db.commit()
        bid = dict(db.execute("SELECT * FROM channel_bids WHERE id = ?", (cur.lastrowid,)).fetchone())
    return {"bid": bid, "lead": lead, "deduplicated": False}


def add_bid(org_id: str, platform: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    pmeta = _check_platform(platform, org_id)
    spec = get_channel_spec(platform, pmeta.get("archetype"))
    curr_name = (spec.get("native_currency") or {}).get("name") or ""
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO channel_bids
               (org_id, platform, job_url, title, client_name, bid_amount, currency_name, currency_spent, boosted, hook_template_id,
                client_payment_verified, client_hire_rate, client_avg_hourly, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                org_id, platform, _url(payload.get("job_url"), False) or "",
                _text(payload.get("title"), "title", 180),
                _text(payload.get("client_name"), "client_name", 120, False) or "",
                float(payload.get("bid_amount") or 0),
                payload.get("currency_name") or curr_name,
                float(payload.get("currency_spent") or 0),
                1 if payload.get("boosted") else 0,
                _text(payload.get("hook_template_id"), "hook_template_id", 100, False) or "",
                1 if payload.get("client_payment_verified") else 0,
                int(payload.get("client_hire_rate") or 0),
                float(payload.get("client_avg_hourly") or 0),
                payload.get("status") or "applied",
                _text(payload.get("notes"), "notes", 1000, False) or "",
            ),
        )
        db.commit()
        return dict(db.execute("SELECT * FROM channel_bids WHERE id = ?", (cur.lastrowid,)).fetchone())


def update_bid(org_id: str, platform: str, bid_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    _check_platform(platform, org_id)
    allowed = ("status", "bid_amount", "currency_spent", "boosted", "hook_template_id", "notes")
    sets, vals = [], []
    for k in allowed:
        if k in payload:
            sets.append(f"{k} = ?")
            vals.append((1 if payload[k] else 0) if k == "boosted" else payload[k])
    if not sets:
        return None
    sets.append("updated_at = CURRENT_TIMESTAMP")
    with get_db() as db:
        cur = db.execute(f"UPDATE channel_bids SET {', '.join(sets)} WHERE id = ? AND org_id = ? AND platform = ?", (*vals, bid_id, org_id, platform))
        db.commit()
        if not cur.rowcount:
            return None
        return dict(db.execute("SELECT * FROM channel_bids WHERE id = ?", (bid_id,)).fetchone())


def delete_bid(org_id: str, platform: str, bid_id: int) -> bool:
    _check_platform(platform, org_id)
    with get_db() as db:
        n = db.execute("DELETE FROM channel_bids WHERE id = ? AND org_id = ? AND platform = ?", (bid_id, org_id, platform)).rowcount
        db.commit()
        return n > 0


def add_gig(org_id: str, platform: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _check_platform(platform, org_id)
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO channel_gigs (org_id, platform, title, url, impressions, clicks, inquiries, orders, revenue, avg_response_mins, keywords)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                org_id, platform, _text(payload.get("title"), "title", 180),
                _url(payload.get("url"), False) or "",
                int(payload.get("impressions") or 0), int(payload.get("clicks") or 0),
                int(payload.get("inquiries") or 0), int(payload.get("orders") or 0),
                float(payload.get("revenue") or 0), int(payload.get("avg_response_mins") or 0),
                _text(payload.get("keywords"), "keywords", 300, False) or "",
            ),
        )
        db.commit()
        return dict(db.execute("SELECT * FROM channel_gigs WHERE id = ?", (cur.lastrowid,)).fetchone())


def update_gig(org_id: str, platform: str, gig_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    _check_platform(platform, org_id)
    allowed = ("title", "impressions", "clicks", "inquiries", "orders", "revenue", "avg_response_mins", "keywords", "status")
    sets, vals = [], []
    for k in allowed:
        if k in payload:
            sets.append(f"{k} = ?")
            vals.append(payload[k])
    if not sets:
        return None
    sets.append("updated_at = CURRENT_TIMESTAMP")
    with get_db() as db:
        cur = db.execute(f"UPDATE channel_gigs SET {', '.join(sets)} WHERE id = ? AND org_id = ? AND platform = ?", (*vals, gig_id, org_id, platform))
        db.commit()
        if not cur.rowcount:
            return None
        return dict(db.execute("SELECT * FROM channel_gigs WHERE id = ?", (gig_id,)).fetchone())


def delete_gig(org_id: str, platform: str, gig_id: int) -> bool:
    _check_platform(platform, org_id)
    with get_db() as db:
        n = db.execute("DELETE FROM channel_gigs WHERE id = ? AND org_id = ? AND platform = ?", (gig_id, org_id, platform)).rowcount
        db.commit()
        return n > 0


def invite_review(org_id: str, platform: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _check_platform(platform, org_id)
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO channel_reviews (org_id, platform, client_id, client_name, status, rating, review_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                org_id, platform, payload.get("client_id"),
                _text(payload.get("client_name"), "client_name", 140),
                payload.get("status") or "invited",
                float(payload["rating"]) if payload.get("rating") not in (None, "") else None,
                _url(payload.get("review_url"), False) or "",
            ),
        )
        db.commit()
        return dict(db.execute("SELECT * FROM channel_reviews WHERE id = ?", (cur.lastrowid,)).fetchone())


def update_review(org_id: str, platform: str, review_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    _check_platform(platform, org_id)
    status = payload.get("status") or "published"
    with get_db() as db:
        cur = db.execute(
            "UPDATE channel_reviews SET status = ?, rating = COALESCE(?, rating), review_url = COALESCE(?, review_url), "
            "published_at = CASE WHEN ? = 'published' THEN CURRENT_TIMESTAMP ELSE published_at END "
            "WHERE id = ? AND org_id = ? AND platform = ?",
            (status, payload.get("rating"), payload.get("review_url"), status, review_id, org_id, platform),
        )
        db.commit()
        if not cur.rowcount:
            return None
        return dict(db.execute("SELECT * FROM channel_reviews WHERE id = ?", (review_id,)).fetchone())


def upsert_pacing(org_id: str, platform: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _check_platform(platform, org_id)
    day = _day(payload.get("day"), "day", False) or date.today().isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO channel_pacing (org_id, platform, day, invites_sent, inmails_sent, profile_views, comments_left, weekly_limit, ssi_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(org_id, platform, day) DO UPDATE SET
                 invites_sent = excluded.invites_sent,
                 inmails_sent = excluded.inmails_sent,
                 profile_views = excluded.profile_views,
                 comments_left = excluded.comments_left,
                 weekly_limit = excluded.weekly_limit,
                 ssi_score = CASE WHEN excluded.ssi_score > 0 THEN excluded.ssi_score ELSE channel_pacing.ssi_score END""",
            (
                org_id, platform, day,
                int(payload.get("invites_sent") or 0),
                int(payload.get("inmails_sent") or 0),
                int(payload.get("profile_views") or 0),
                int(payload.get("comments_left") or 0),
                int(payload.get("weekly_limit") or 80),
                int(payload.get("ssi_score") or 0),
            ),
        )
        db.commit()
        return dict(db.execute("SELECT * FROM channel_pacing WHERE org_id = ? AND platform = ? AND day = ?", (org_id, platform, day)).fetchone())


def create_custom_channel(org_id: str, label: str, archetype: str, home_url: str = "", quick_links: Optional[List[Dict[str, str]]] = None, sender_pattern: str = "") -> Dict[str, Any]:
    clean_label = _text(label, "label", 60)
    if archetype not in ARCHETYPES:
        raise ValueError(f"archetype must be one of {list(ARCHETYPES.keys())}")
    slug = re.sub(r"[^a-z0-9]+", "_", clean_label.lower()).strip("_")[:32]
    reserved = {"all", "overview", "platforms", "preferences", "custom", "parse", "parse_date"}
    if not slug or slug in PLATFORMS or slug in reserved:
        slug = f"custom_{slug or 'channel'}"
    url = _url(home_url, False) or ""
    clean_sender = (sender_pattern or "").strip()[:180]
    with get_db() as db:
        db.execute(
            """INSERT INTO custom_channels (org_id, slug, label, archetype, home_url, quick_links_json, sender_pattern)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(org_id, slug) DO UPDATE SET label = excluded.label, archetype = excluded.archetype, home_url = excluded.home_url, quick_links_json = excluded.quick_links_json, sender_pattern = excluded.sender_pattern, active = 1""",
            (org_id, slug, clean_label, archetype, url, json.dumps(quick_links or []), clean_sender),
        )
        db.commit()
        return dict(db.execute("SELECT * FROM custom_channels WHERE org_id = ? AND slug = ?", (org_id, slug)).fetchone())


def delete_custom_channel(org_id: str, slug: str) -> bool:
    with get_db() as db:
        n = db.execute("UPDATE custom_channels SET active = 0 WHERE org_id = ? AND slug = ?", (org_id, slug)).rowcount
        db.commit()
        return n > 0


def promote_to_crm(org_id: str, platform: str, record_id: int) -> Optional[Dict[str, Any]]:
    """Promotes a channel pipeline record into the main CRM leads table."""
    pmeta = _check_platform(platform, org_id)
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM channel_records WHERE id = ? AND org_id = ? AND platform = ? AND type = 'pipeline'",
            (record_id, org_id, platform),
        ).fetchone()
    if not row:
        return None
    data = json.loads(row["data_json"])
    from database.models import LeadRepository

    url = data.get("url") or ""
    domain = ""
    if url:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = (parsed.hostname or "").lower()
    if not domain:
        domain = f"channel-{platform}-{record_id}.local"
    company = data.get("counterparty") or data.get("title") or f"{pmeta['label']} Lead #{record_id}"
    notes_parts = [f"Promoted from {pmeta['label']} ({data.get('status', 'applied')})"]
    if data.get("title"):
        notes_parts.append(f"Project: {data['title']}")
    if data.get("value") is not None:
        notes_parts.append(f"Est. Value: ${data['value']}")
    if url:
        notes_parts.append(f"URL: {url}")
    if data.get("notes"):
        notes_parts.append(f"Notes: {data['notes']}")

    lead = LeadRepository.create_or_get_lead(
        company_name=company[:120],
        domain=domain,
        source_channel=platform,
        source_query=data.get("title"),
        notes="\n".join(notes_parts),
        org_id=org_id,
    )
    updated = update_record(org_id, platform, record_id, {"crm_lead_id": lead["id"]})
    return {"lead": lead, "record": updated}
