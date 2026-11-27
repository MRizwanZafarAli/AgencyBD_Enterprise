"""
Social Intent Intelligence helpers:
- Author-to-Company Identity Resolution (HN, Bluesky, GitHub, Dev.to + post text extraction)
- Offer-Aware Boolean Auto-Query Builder (from agency services & portfolio)
- Human-First Reply Studio (3 non-spammy tones + community anti-ban guardrails)
"""

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse

from connectors.social_radar import extract_external_urls
from connectors.text import clean_html
from database.db import get_db
from net.fetcher import SafeFetcher

UA = {"User-Agent": "AgencyBD-Enterprise/2.0 (social intel; read-only)"}
LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[A-Za-z0-9_.\-/]+", re.I)
X_HANDLE_RE = re.compile(r"(?:https?://(?:twitter\.com|x\.com)/|@)([A-Za-z0-9_]{2,20})", re.I)
COMPANY_HINT_RE = re.compile(r"\b(?:founder|ceo|cto|co-founder|building|working at|at)\s+([A-Z][A-Za-z0-9&.\-]{1,30})", re.I)


def _domain_from_url(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _company_from_domain(domain: str) -> str:
    if not domain:
        return ""
    base = domain.split(".")[0]
    return base.replace("-", " ").title()


def resolve_author_identity(
    platform: str,
    author: str,
    title: str = "",
    description: str = "",
    url: str = "",
) -> Dict[str, Any]:
    """Scan post text and public author profile for company, website domain, LinkedIn, and X handle."""
    combined = f"{title}\n{description}"
    ext_urls = extract_external_urls(combined)
    bio = ""
    profile_url = ""
    display_name = author or ""
    company_name = ""

    plat = (platform or "").lower()
    clean_author = (author or "").strip().lstrip("@").lstrip("u/")

    if clean_author:
        try:
            if "hacker news" in plat or plat in ("hn_ask", "hn_comment"):
                profile_url = f"https://news.ycombinator.com/user?id={quote_plus(clean_author)}"
                st, txt, _ = SafeFetcher.safe_get(
                    f"https://hacker-news.firebaseio.com/v0/user/{quote_plus(clean_author)}.json",
                    timeout=6,
                    headers=UA,
                )
                if st == 200 and txt:
                    about = clean_html(json.loads(txt).get("about") or "")
                    bio = about[:400]
                    ext_urls.extend(extract_external_urls(about))
                    combined += f"\n{about}"
            elif "bluesky" in plat:
                profile_url = f"https://bsky.app/profile/{clean_author}"
                st, txt, _ = SafeFetcher.safe_get(
                    f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={quote_plus(clean_author)}",
                    timeout=6,
                    headers=UA,
                )
                if st == 200 and txt:
                    prof = json.loads(txt)
                    display_name = prof.get("displayName") or display_name
                    bio = (prof.get("description") or "")[:400]
                    ext_urls.extend(extract_external_urls(bio))
                    combined += f"\n{bio}"
            elif "github" in plat:
                profile_url = f"https://github.com/{clean_author}"
                st, txt, _ = SafeFetcher.safe_get(
                    f"https://api.github.com/users/{quote_plus(clean_author)}",
                    timeout=6,
                    headers=UA,
                )
                if st == 200 and txt:
                    prof = json.loads(txt)
                    display_name = prof.get("name") or display_name
                    company_name = (prof.get("company") or "").lstrip("@").strip()
                    bio = (prof.get("bio") or "")[:400]
                    blog = (prof.get("blog") or "").strip()
                    if blog:
                        if not blog.startswith("http"):
                            blog = f"https://{blog}"
                        ext_urls.insert(0, blog)
                    if prof.get("twitter_username"):
                        combined += f"\nhttps://x.com/{prof['twitter_username']}"
                    combined += f"\n{bio}"
            elif "dev.to" in plat or plat == "devto":
                profile_url = f"https://dev.to/{clean_author}"
                st, txt, _ = SafeFetcher.safe_get(
                    f"https://dev.to/api/users/by_username?url={quote_plus(clean_author)}",
                    timeout=6,
                    headers=UA,
                )
                if st == 200 and txt:
                    prof = json.loads(txt)
                    display_name = prof.get("name") or display_name
                    bio = (prof.get("summary") or "")[:400]
                    if prof.get("website_url"):
                        ext_urls.insert(0, prof["website_url"])
                    if prof.get("twitter_username"):
                        combined += f"\nhttps://x.com/{prof['twitter_username']}"
                    combined += f"\n{bio}"
            elif "reddit" in plat:
                profile_url = f"https://www.reddit.com/user/{clean_author}"
        except Exception:
            pass

    # Deduplicate external URLs
    dedup_urls: List[str] = []
    for u in ext_urls:
        if u and u not in dedup_urls:
            dedup_urls.append(u)

    website_url = dedup_urls[0] if dedup_urls else ""
    website_domain = _domain_from_url(website_url)
    li_match = LINKEDIN_RE.search(combined)
    linkedin_url = li_match.group(0) if li_match else ""
    x_match = X_HANDLE_RE.search(combined)
    x_handle = f"@{x_match.group(1)}" if x_match else ""

    if not company_name:
        cm = COMPANY_HINT_RE.search(combined)
        if cm:
            company_name = cm.group(1).strip(".,")
        elif website_domain:
            company_name = _company_from_domain(website_domain)

    return {
        "author": clean_author,
        "display_name": display_name,
        "platform": platform,
        "profile_url": profile_url or url,
        "company_name": company_name,
        "website_url": website_url,
        "website_domain": website_domain,
        "linkedin_url": linkedin_url,
        "x_handle": x_handle,
        "bio": bio,
        "discovered_urls": dedup_urls[:5],
    }


def build_offer_queries(org_id: str) -> List[Dict[str, str]]:
    """Expand agency services & portfolio into buyer-intent boolean queries."""
    queries: List[Dict[str, str]] = []
    seen_labels = set()
    try:
        with get_db() as db:
            services = db.execute("SELECT name, offer FROM services WHERE org_id = ?", (org_id,)).fetchall()
            for row in services[:4]:
                name = (row["name"] or "").strip()
                offer = (row["offer"] or "").strip()
                if not name:
                    continue
                core = [w.lower() for w in re.findall(r"[a-zA-Z0-9+#]{3,}", name) if w.lower() not in {"and", "for", "the", "with", "services"}][:2]
                if not core:
                    continue
                core_expr = " OR ".join(f'"{w}"' for w in core)
                label = f"{name}"
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                queries.append({
                    "label": label,
                    "source_offer": offer[:100] or name,
                    "boolean_query": f'({core_expr}) AND ("agency" OR "freelancer" OR "developer" OR "help" OR "looking for")',
                })
    except Exception:
        pass

    if not queries:
        queries = [
            {
                "label": "Web Redesign & CRO",
                "source_offer": "High-converting website redesigns",
                "boolean_query": '("website" OR "redesign" OR "webflow") AND ("agency" OR "slow" OR "recommend" OR "looking for")',
            },
            {
                "label": "Shopify & Ecommerce",
                "source_offer": "Shopify speed & conversion optimization",
                "boolean_query": '("shopify" OR "ecommerce") AND ("agency" OR "freelancer" OR "redesign" OR "recommend")',
            },
            {
                "label": "SEO & Organic Growth",
                "source_offer": "Technical SEO & lead generation",
                "boolean_query": '("seo" OR "traffic" OR "rank") AND ("agency" OR "help" OR "recommend" OR "audit")',
            },
            {
                "label": "MVP & SaaS Engineering",
                "source_offer": "Full-stack React/Python product pods",
                "boolean_query": '("mvp" OR "react" OR "saas") AND ("developer" OR "agency" OR "contractor" OR "build")',
            },
        ]
    return queries[:6]


def community_guardrail(platform: str, community: str = "") -> str:
    plat = (platform or "").lower()
    comm = (community or "").lower()
    if "reddit" in plat:
        if "entrepreneur" in comm or "smallbusiness" in comm or "saas" in comm:
            return f"{community}: No direct links or hard pitches in comments — lead with a Value-First answer, then invite a DM."
        return "Reddit: Avoid promo links in top-level comments to prevent auto-mod bans. Give actionable steps first."
    if "hacker news" in plat:
        return "Hacker News: Technical substance only. Zero marketing fluff or sales CTAs."
    if "bluesky" in plat:
        return "Bluesky: Keep replies short, conversational, and peer-to-peer."
    if "github" in plat:
        return "GitHub: Address the technical issue or architecture directly; link only to relevant examples."
    return "Keep it human-first: answer their specific bottleneck before mentioning your agency."


def draft_social_reply(
    *,
    platform: str,
    community: str,
    title: str,
    description: str,
    intent_type: str,
    trigger_sentence: str,
    tone: str = "value_first",
    offer_hint: str = "",
) -> Dict[str, str]:
    """Generate a non-spammy, human-first reply tailored to the thread and selected tone."""
    focus = (trigger_sentence or title or "this").strip()
    if len(focus) > 140:
        focus = focus[:137] + "..."
    offer = offer_hint.strip() or "web & growth engineering"
    guardrail = community_guardrail(platform, community)

    if tone == "soft_case_study":
        draft = (
            f"Re: \"{focus}\" — we just helped a similar team untangle this exact bottleneck.\n\n"
            f"Two quick wins that usually move the needle immediately:\n"
            f"1. Audit the highest-friction step (load speed / onboarding / conversion path) before rewriting everything.\n"
            f"2. Ship a focused 7-day fix around {offer} metrics rather than a multi-month overhaul.\n\n"
            f"Happy to share the exact 5-point checklist we used if it's helpful (no strings attached)."
        )
    elif tone == "direct_dm":
        draft = (
            f"Hey! Saw your post in {community or platform} about \"{focus}\".\n\n"
            f"I run a small {offer} team and we've solved this a few times recently. "
            f"If you're still comparing options, I'd be glad to send over a quick 3-minute teardown of what I'd change first — just let me know!"
        )
    else:  # value_first
        if intent_type == "competitor_complaint":
            draft = (
                f"Totally feel the frustration with \"{focus}\". Before migrating, two things worth checking:\n"
                f"1. Export your core data/URLs first so you don't lose SEO equity or customer history.\n"
                f"2. Map out the 20% of workflows you actually use daily — most teams overpay for bloated features they never touch.\n\n"
                f"If you want a second pair of eyes on your migration checklist, drop your current stack here and I'll outline the cleanest path."
            )
        else:
            draft = (
                f"On \"{focus}\" — the fastest way to de-risk this before hiring anyone is to write down:\n"
                f"1. The single metric you need moved in the next 30 days.\n"
                f"2. What you already tried so nobody pitches you a generic reset.\n"
                f"3. A small paid discovery/audit milestone first before committing to a full retainer.\n\n"
                f"If you share a bit more about your current setup, happy to point out the top 2-3 fixes right here."
            )

    return {
        "tone": tone,
        "draft": draft,
        "guardrail": guardrail,
    }
