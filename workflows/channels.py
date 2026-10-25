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
                     _f("Connection notes", "A note on a request is limited to 300 characters.", "Mention one specific thing you noticed about their business. The counter below helps."),
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
    "other": {"pages": [], "features": [_f("Your own checklist", "Any site works here: add its links, templates and routine.", "Save the pages you open daily as links.")]},
}
for _id, _x in EXTRAS.items():
    PLATFORMS[_id]["pages"] = [{"label": l, "url": u} for l, u in _x["pages"]]
    PLATFORMS[_id]["features"] = _x["features"]


STATUSES = ["saved", "applied", "replied", "interview", "won", "lost"]
OPEN_STATUSES = ("saved", "applied", "replied", "interview")
ACTIVITY_KINDS = ["invite_sent", "message_sent", "reply_received", "profile_view", "proposal_sent", "order_received", "gig_impressions", "gig_clicks", "gig_orders", "invite_accepted", "connects_spent"]
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
        return {"title": _text(d.get("title"), "title", 160), "url": _url(d.get("url")), "cost": cost if cost not in (None, "") else None, "counterparty": _text(d.get("counterparty"), "counterparty", 120, False), "status": status,
                "value": value if value not in (None, "") else None, "next_followup": _day(d.get("next_followup"), "next_followup"), "notes": _text(d.get("notes"), "notes", 1000, False)}
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


def _check_platform(platform: str) -> None:
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform '{platform}'.")


def _row(r) -> Dict[str, Any]:
    return {"id": r["id"], "platform": r["platform"], "type": r["type"], **json.loads(r["data_json"]), "created_at": r["created_at"], "updated_at": r["updated_at"]}


def list_records(org_id: str, platform: str, rtype: Optional[str] = None) -> List[Dict[str, Any]]:
    _check_platform(platform)
    with get_db() as db:
        if rtype == "routine" and not db.execute("SELECT 1 FROM channel_records WHERE org_id = ? AND platform = ? AND type = 'routine'", (org_id, platform)).fetchone():
            for label in PLATFORMS[platform]["routine"]:        # first visit: start with a sensible routine the person can edit or delete
                db.execute("INSERT INTO channel_records (org_id, platform, type, data_json) VALUES (?, ?, 'routine', ?)", (org_id, platform, json.dumps({"label": label})))
            db.commit()
        q, params = "SELECT * FROM channel_records WHERE org_id = ? AND platform = ?", [org_id, platform]
        if rtype:
            q, params = q + " AND type = ?", params + [rtype]
        rows = db.execute(q + " ORDER BY id", params).fetchall()
    return [_row(r) for r in rows]


def add_record(org_id: str, platform: str, rtype: str, data: Dict[str, Any]) -> Dict[str, Any]:
    _check_platform(platform)
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
    _check_platform(platform)
    with get_db() as db:
        row = db.execute("SELECT * FROM channel_records WHERE id = ? AND org_id = ? AND platform = ?", (record_id, org_id, platform)).fetchone()
        if not row:
            return None
        merged = {**json.loads(row["data_json"]), **(data or {})}
        db.execute("UPDATE channel_records SET data_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (json.dumps(clean(row["type"], merged)), record_id))
        db.commit()
        return _row(db.execute("SELECT * FROM channel_records WHERE id = ?", (record_id,)).fetchone())


def delete_record(org_id: str, platform: str, record_id: int) -> bool:
    _check_platform(platform)
    with get_db() as db:
        n = db.execute("DELETE FROM channel_records WHERE id = ? AND org_id = ? AND platform = ?", (record_id, org_id, platform)).rowcount
        db.commit()
    return n > 0


def summary(org_id: str, platform: str, today: Optional[date] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Everything here is computed from the person's own logs."""
    _check_platform(platform)
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
    experiments = [{"id": e["id"], "what": e["what"], "review_on": e["review_on"]} for e in by("experiment") if not e["done"] and e["review_on"] <= today.isoformat()]
    return {"platform": platform, "funnel": funnel, "pacing": pacing, "experiments_due": experiments, "pipeline": {"counts": counts, "open": sum(counts[s] for s in OPEN_STATUSES), "followups_due": len(due), "due_titles": [r["title"] for r in due][:5],
                                                  "win_rate_percent": round(100 * counts["won"] / closed) if closed else None,
                                                  "value_won": sum((r["value"] or 0) for r in pipeline if r["status"] == "won"), "value_open": sum((r["value"] or 0) for r in pipeline if r["status"] in OPEN_STATUSES)},
            "response": response, "activity_this_week": week, "routine": {"total": len(routines), "done_today": done_today, "streak_days": streak}, "setting": setting,
            "note": "Built only from what you log here. Nothing is read from the platform."}


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


def overview(org_id: str) -> List[Dict[str, Any]]:
    out = []
    for pid, p in PLATFORMS.items():
        if pid == "other":
            continue
        s = summary(org_id, pid)
        out.append({"platform": pid, "label": p["label"], "open": s["pipeline"]["open"], "followups_due": s["pipeline"]["followups_due"], "routine": s["routine"],
                    "unanswered": s["response"]["unanswered"], "average_minutes": s["response"]["average_minutes"]})
    return out
