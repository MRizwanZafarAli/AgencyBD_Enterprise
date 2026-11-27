"""
Enterprise Social Media Buying-Intent Radar Connector.
Monitors Hacker News (Algolia posts + comments), Bluesky (public ATProto API),
Reddit (OAuth / RSS / SERP fallback + custom communities), GitHub Discussions/Issues,
Dev.to, Lobsters, and IndieHackers for buyer-intent signals.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import html as html_lib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlparse

import defusedxml.ElementTree as ET
import httpx

from connectors.base import BaseConnector, OpportunityItem
from connectors.text import clean_html
from net.fetcher import SafeFetcher

logger = logging.getLogger("AgencyBD.social_radar")

NS = {"a": "http://www.w3.org/2005/Atom"}
UA = {"User-Agent": "AgencyBD-Enterprise/2.0 (social intent radar; read-only)"}

INTENT_BUCKETS: List[Tuple[str, int, List[str]]] = [
    (
        "buying_request",
        46,
        [
            "looking for an agency",
            "looking for a developer",
            "looking for a dev",
            "looking for",
            "need a developer",
            "need an agency",
            "need a website",
            "recommend a",
            "anyone know a",
            "who do you use for",
            "hire a",
            "hiring a",
            "freelancer",
            "contractor",
            "redesign",
            "quotes for",
            "budget for",
        ],
    ),
    (
        "competitor_complaint",
        40,
        [
            "alternative to",
            "switching from",
            "leaving ",
            "hate wix",
            "hate wordpress",
            "hate hubspot",
            "hate shopify",
            "hate webflow",
            "fed up with",
            "migrating off",
            "terrible agency",
            "fired our agency",
            "replacing ",
        ],
    ),
    (
        "pain_point",
        32,
        [
            "website slow",
            "site is slow",
            "losing leads",
            "can't rank",
            "not ranking",
            "seo help",
            "conversion rate",
            "broken site",
            "core web vitals",
            "no leads",
            "low traffic",
            "bounce rate",
        ],
    ),
    (
        "launch_trigger",
        34,
        [
            "just raised",
            "pre-seed",
            "seed round",
            "launching next",
            "launching soon",
            "build an mvp",
            "building an mvp",
            "just launched",
            "show hn:",
        ],
    ),
]

NOISE_PHRASES = [
    "for hire",
    "[for hire]",
    "looking for a job",
    "open to work",
    "junior devs",
    "my resume",
    "getting hired",
    "leetcode",
    "interview prep",
    "roast my resume",
]

DEFAULT_REDDIT_FEEDS = [
    "smallbusiness",
    "entrepreneur",
    "SaaS",
]

PLATFORM_HOSTS = {
    "reddit.com", "www.reddit.com", "old.reddit.com", "redd.it",
    "news.ycombinator.com", "bsky.app", "github.com", "dev.to",
    "lobste.rs", "indiehackers.com", "www.indiehackers.com",
    "twitter.com", "x.com", "linkedin.com", "www.linkedin.com",
    "youtube.com", "youtu.be", "imgur.com", "i.redd.it",
}

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        clean = ts.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _within_window(posted_at: Optional[str], time_window: str) -> bool:
    if not time_window or time_window == "all":
        return True
    dt = _parse_iso(posted_at)
    if not dt:
        return True
    now = datetime.now(timezone.utc)
    hours = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}.get(time_window)
    if not hours:
        return True
    return (now - dt) <= timedelta(hours=hours)


def _window_cutoff_unix(time_window: str) -> Optional[int]:
    hours = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}.get(time_window or "all")
    if not hours:
        return None
    return int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())


def _strip_html_entities(raw: str) -> str:
    return clean_html(html_lib.unescape(raw or ""))


def _canonical_url(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower().lstrip("www.")
        path = (p.path or "").rstrip("/").lower()
        return f"{host}{path}" if host else ""
    except Exception:
        return ""


def _title_author_hash(title: str, author: str) -> str:
    norm_title = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    norm_author = re.sub(r"[^a-z0-9]+", "", (author or "").lower()).strip()
    raw = f"{norm_title}::{norm_author}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def extract_external_urls(text: str) -> List[str]:
    urls: List[str] = []
    seen = set()
    for raw in URL_RE.findall(text or ""):
        cleaned = raw.rstrip(".,;:!?")
        try:
            host = (urlparse(cleaned).hostname or "").lower()
        except Exception:
            continue
        if not host or any(host == p or host.endswith("." + p) for p in PLATFORM_HOSTS):
            continue
        if cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
        if len(urls) >= 5:
            break
    return urls


def _matches_query(text: str, query: Optional[str]) -> bool:
    if not query or not query.strip():
        return True
    low = text.lower()
    q = query.strip()
    # Support simple boolean expressions like ("shopify" OR "ecommerce") AND ("agency" OR "redesign")
    if " OR " in q or " AND " in q:
        and_groups = [g.strip() for g in re.split(r"\s+AND\s+", q, flags=re.I) if g.strip()]
        for grp in and_groups:
            inner = grp.strip("() ")
            or_terms = [t.strip().strip('"').strip("'").lower() for t in re.split(r"\s+OR\s+", inner, flags=re.I) if t.strip()]
            if or_terms and not any(term in low for term in or_terms):
                return False
        return True
    tokens = [t.strip().strip('"').lower() for t in q.split() if t.strip()]
    return all(tok in low for tok in tokens)


def classify_intent(
    text: str,
    query: Optional[str] = None,
    competitors: Optional[List[str]] = None,
    posted_at: Optional[str] = None,
    reply_count: int = 0,
    is_comment: bool = False,
) -> Optional[Dict[str, Any]]:
    low = (text or "").lower()
    if any(n in low for n in NOISE_PHRASES):
        return None
    if not _matches_query(text, query):
        return None

    matched_type: Optional[str] = None
    matched_phrase: Optional[str] = None
    base_score = 0

    # Check custom competitors first for switching/complaint intent
    comp_list = [c.strip().lower() for c in (competitors or []) if c.strip()]
    for comp in comp_list:
        if comp in low:
            matched_type = "competitor_complaint"
            matched_phrase = comp
            base_score = 42
            break

    if not matched_type:
        for bucket, weight, phrases in INTENT_BUCKETS:
            for phrase in phrases:
                if phrase in low:
                    matched_type = bucket
                    matched_phrase = phrase
                    base_score = weight
                    break
            if matched_type:
                break

    if not matched_type:
        if query and query.strip():
            # If user explicitly queried something, allow high-signal question posts
            if "?" in text or any(w in low for w in ("help", "need", "recommend", "looking", "issue", "problem")):
                matched_type = "pain_point"
                matched_phrase = query.strip()[:40]
                base_score = 26
            else:
                return None
        else:
            return None

    # Extract exact trigger sentence
    trigger_sentence = ""
    for sent in SENTENCE_SPLIT_RE.split(text or ""):
        s = sent.strip()
        if s and matched_phrase and matched_phrase.lower() in s.lower():
            trigger_sentence = s[:260]
            break
    if not trigger_sentence:
        trigger_sentence = (text or "").strip()[:220]

    score = base_score
    if query and query.strip():
        score += 18
    dt = _parse_iso(posted_at)
    if dt:
        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
        if age_hours <= 2:
            score += 22
        elif age_hours <= 24:
            score += 15
        elif age_hours <= 168:
            score += 7
    if reply_count <= 5:
        score += 10
    elif reply_count <= 15:
        score += 4
    if is_comment:
        score += 5
    score = max(15, min(100, score))

    return {
        "intent_type": matched_type,
        "intent_phrase": matched_phrase,
        "trigger_sentence": trigger_sentence,
        "intent_score": score,
    }


def _primary_search_term(query: Optional[str]) -> str:
    if not query or not query.strip():
        return "looking for agency OR developer OR redesign"
    cleaned = re.sub(r'[()"]', " ", query)
    cleaned = re.sub(r"\b(AND|OR)\b", " ", cleaned, flags=re.I)
    tokens = [t for t in cleaned.split() if len(t) > 1]
    return " ".join(tokens[:4]) if tokens else "agency"


class SocialIntentRadarConnector(BaseConnector):
    source_name = "social_radar"
    terms_url = "https://www.redditinc.com/policies/data-api-terms"
    automation_level = "L0"
    rate_limit_per_minute = 20
    max_fetch = 80

    def _build_item(
        self,
        *,
        source: str,
        external_id: str,
        title: str,
        description: str,
        url: str,
        posted_at: Optional[str],
        platform: str,
        author: str,
        community: str,
        reply_count: int,
        upvotes: int,
        is_comment: bool,
        intent: Dict[str, Any],
    ) -> OpportunityItem:
        ext_urls = extract_external_urls(f"{title} {description}")
        return OpportunityItem(
            type="social",
            source=source,
            external_id=str(external_id),
            title=title[:220] or description[:120],
            description=description[:1500],
            company_name=None,
            url=url,
            posted_at=posted_at,
            metadata={
                "platform": platform,
                "community": community,
                "author": author,
                "intent_phrase": intent["intent_phrase"],
                "intent_type": intent["intent_type"],
                "intent_score": intent["intent_score"],
                "trigger_sentence": intent["trigger_sentence"],
                "reply_count": reply_count,
                "upvotes": upvotes,
                "is_comment": is_comment,
                "external_urls": ext_urls,
            },
        )

    def fetch_hn_posts(
        self,
        query: Optional[str] = None,
        competitors: Optional[List[str]] = None,
        time_window: str = "all",
        limit: int = 15,
    ) -> Tuple[List[OpportunityItem], Dict[str, Any]]:
        items: List[OpportunityItem] = []
        try:
            q_param = f"&query={quote_plus(_primary_search_term(query))}" if query and query.strip() else ""
            cutoff = _window_cutoff_unix(time_window)
            nf_param = f"&numericFilters=created_at_i>={cutoff}" if cutoff else ""
            url = f"https://hn.algolia.com/api/v1/search_by_date?tags=(ask_hn,show_hn)&hitsPerPage=35{q_param}{nf_param}"
            status, text, _ = SafeFetcher.safe_get(url, timeout=8, headers=UA)
            if status != 200 or not text:
                return items, {"id": "hn_posts", "label": "HN Ask/Show", "status": "error", "hits": 0, "detail": f"HTTP {status}"}
            data = json.loads(text)
            for hit in data.get("hits", []):
                title = _strip_html_entities(hit.get("title") or "").strip()
                body = _strip_html_entities(hit.get("story_text") or "")
                reply_count = int(hit.get("num_comments") or 0)
                upvotes = int(hit.get("points") or 0)
                posted_at = hit.get("created_at")
                intent = classify_intent(
                    f"{title}. {body[:700]}",
                    query=query,
                    competitors=competitors,
                    posted_at=posted_at,
                    reply_count=reply_count,
                    is_comment=False,
                )
                if not intent:
                    continue
                oid = hit.get("objectID", "")
                items.append(
                    self._build_item(
                        source="hn_ask",
                        external_id=oid,
                        title=title,
                        description=body or title,
                        url=f"https://news.ycombinator.com/item?id={oid}",
                        posted_at=posted_at,
                        platform="Hacker News",
                        author=hit.get("author", ""),
                        community="Ask/Show HN",
                        reply_count=reply_count,
                        upvotes=upvotes,
                        is_comment=False,
                        intent=intent,
                    )
                )
                if len(items) >= limit:
                    break
            return items, {"id": "hn_posts", "label": "HN Ask/Show", "status": "ok", "hits": len(items), "detail": "Algolia API"}
        except Exception as exc:
            logger.debug(f"HN posts skipped: {exc}")
            return items, {"id": "hn_posts", "label": "HN Ask/Show", "status": "error", "hits": 0, "detail": str(exc)[:60]}

    def fetch_hn_comments(
        self,
        query: Optional[str] = None,
        competitors: Optional[List[str]] = None,
        time_window: str = "all",
        limit: int = 12,
    ) -> Tuple[List[OpportunityItem], Dict[str, Any]]:
        items: List[OpportunityItem] = []
        try:
            term = _primary_search_term(query) if (query and query.strip()) else "looking for agency"
            cutoff = _window_cutoff_unix(time_window)
            nf_param = f"&numericFilters=created_at_i>={cutoff}" if cutoff else ""
            url = f"https://hn.algolia.com/api/v1/search_by_date?tags=comment&query={quote_plus(term)}&hitsPerPage=30{nf_param}"
            status, text, _ = SafeFetcher.safe_get(url, timeout=8, headers=UA)
            if status != 200 or not text:
                return items, {"id": "hn_comments", "label": "HN Comments", "status": "error", "hits": 0, "detail": f"HTTP {status}"}
            data = json.loads(text)
            for hit in data.get("hits", []):
                body = _strip_html_entities(hit.get("comment_text") or "")
                story_title = _strip_html_entities(hit.get("story_title") or "HN Thread").strip()
                posted_at = hit.get("created_at")
                intent = classify_intent(
                    f"{story_title}. {body[:700]}",
                    query=query,
                    competitors=competitors,
                    posted_at=posted_at,
                    reply_count=2,
                    is_comment=True,
                )
                if not intent:
                    continue
                oid = hit.get("objectID", "")
                items.append(
                    self._build_item(
                        source="hn_comment",
                        external_id=oid,
                        title=f"Comment on: {story_title}",
                        description=body,
                        url=f"https://news.ycombinator.com/item?id={oid}",
                        posted_at=posted_at,
                        platform="Hacker News",
                        author=hit.get("author", ""),
                        community="HN Comments",
                        reply_count=2,
                        upvotes=int(hit.get("points") or 1),
                        is_comment=True,
                        intent=intent,
                    )
                )
                if len(items) >= limit:
                    break
            return items, {"id": "hn_comments", "label": "HN Comments", "status": "ok", "hits": len(items), "detail": "Comment Mining"}
        except Exception as exc:
            logger.debug(f"HN comments skipped: {exc}")
            return items, {"id": "hn_comments", "label": "HN Comments", "status": "error", "hits": 0, "detail": str(exc)[:60]}

    def fetch_bluesky(
        self, query: Optional[str] = None, competitors: Optional[List[str]] = None, limit: int = 15
    ) -> Tuple[List[OpportunityItem], Dict[str, Any]]:
        items: List[OpportunityItem] = []
        bsky_handle = os.getenv("BLUESKY_HANDLE", "").strip()
        bsky_pw = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
        if not bsky_handle or not bsky_pw:
            return items, {
                "id": "bluesky",
                "label": "Bluesky",
                "status": "auth_required",
                "hits": 0,
                "detail": "Set BLUESKY_HANDLE & BLUESKY_APP_PASSWORD",
            }
        try:
            sess_res = httpx.post(
                "https://bsky.social/xrpc/com.atproto.server.createSession",
                json={"identifier": bsky_handle, "password": bsky_pw},
                headers=UA,
                timeout=8.0,
            )
            if sess_res.status_code in (401, 403):
                return items, {"id": "bluesky", "label": "Bluesky", "status": "auth_required", "hits": 0, "detail": f"Session HTTP {sess_res.status_code}"}
            if sess_res.status_code != 200:
                return items, {"id": "bluesky", "label": "Bluesky", "status": "error", "hits": 0, "detail": f"Session HTTP {sess_res.status_code}"}
            access_jwt = (sess_res.json() or {}).get("accessJwt")
            if not access_jwt:
                return items, {"id": "bluesky", "label": "Bluesky", "status": "auth_required", "hits": 0, "detail": "Missing accessJwt"}

            term = _primary_search_term(query) if (query and query.strip()) else "looking for agency"
            url = f"https://bsky.social/xrpc/app.bsky.feed.searchPosts?q={quote_plus(term)}&limit=25"
            headers = {**UA, "Authorization": f"Bearer {access_jwt}"}
            status, text, _ = SafeFetcher.safe_get(url, timeout=8, headers=headers)
            if status in (401, 403):
                return items, {"id": "bluesky", "label": "Bluesky", "status": "auth_required", "hits": 0, "detail": f"HTTP {status}"}
            if status != 200 or not text:
                return items, {"id": "bluesky", "label": "Bluesky", "status": "rate_limited" if status == 429 else "error", "hits": 0, "detail": f"HTTP {status}"}
            data = json.loads(text)
            for post in data.get("posts", []):
                record = post.get("record") or {}
                body = (record.get("text") or "").strip()
                author_obj = post.get("author") or {}
                handle = author_obj.get("handle") or ""
                posted_at = record.get("createdAt")
                reply_count = int(post.get("replyCount") or 0)
                upvotes = int(post.get("likeCount") or 0)
                intent = classify_intent(
                    body,
                    query=query,
                    competitors=competitors,
                    posted_at=posted_at,
                    reply_count=reply_count,
                    is_comment=False,
                )
                if not intent:
                    continue
                uri = post.get("uri") or ""
                rkey = uri.rsplit("/", 1)[-1] if "/" in uri else ""
                web_url = f"https://bsky.app/profile/{handle}/post/{rkey}" if handle and rkey else "https://bsky.app"
                items.append(
                    self._build_item(
                        source="bluesky",
                        external_id=rkey or uri,
                        title=body.split("\n", 1)[0][:120],
                        description=body,
                        url=web_url,
                        posted_at=posted_at,
                        platform="Bluesky",
                        author=handle,
                        community="bsky.app",
                        reply_count=reply_count,
                        upvotes=upvotes,
                        is_comment=False,
                        intent=intent,
                    )
                )
                if len(items) >= limit:
                    break
            return items, {"id": "bluesky", "label": "Bluesky", "status": "ok", "hits": len(items), "detail": "ATProto Public API"}
        except Exception as exc:
            logger.debug(f"Bluesky skipped: {exc}")
            return items, {"id": "bluesky", "label": "Bluesky", "status": "error", "hits": 0, "detail": str(exc)[:60]}

    def fetch_reddit(
        self,
        query: Optional[str] = None,
        communities: Optional[List[str]] = None,
        competitors: Optional[List[str]] = None,
        limit: int = 15,
    ) -> Tuple[List[OpportunityItem], Dict[str, Any]]:
        items: List[OpportunityItem] = []
        subs = [c.strip().lstrip("r/").strip("/") for c in (communities or []) if c.strip()] or DEFAULT_REDDIT_FEEDS
        rate_limited = False
        auth_required = False

        # Try Reddit RSS feeds first
        for sub in subs[:6]:
            feed_url = f"https://www.reddit.com/r/{sub}/new.rss?limit=35"
            try:
                status, text, _ = SafeFetcher.safe_get(feed_url, timeout=8, headers=UA)
                if status in (401, 403):
                    auth_required = True
                    continue
                if status == 429:
                    rate_limited = True
                    continue
                if status != 200 or not text:
                    continue
                root = ET.fromstring(text)
                for e in root.findall("a:entry", NS):
                    title = (e.findtext("a:title", "", NS) or "").strip()
                    body = clean_html(e.findtext("a:content", "", NS) or "")
                    posted_at = e.findtext("a:updated", None, NS)
                    intent = classify_intent(
                        f"{title}. {body[:700]}",
                        query=query,
                        competitors=competitors,
                        posted_at=posted_at,
                        reply_count=0,
                        is_comment=False,
                    )
                    if not intent:
                        continue
                    link = e.find("a:link", NS).get("href") if e.find("a:link", NS) is not None else ""
                    author = (e.findtext("a:author/a:name", "", NS) or "").lstrip("/u/")
                    items.append(
                        self._build_item(
                            source=f"reddit:r/{sub}",
                            external_id=(e.findtext("a:id", "", NS) or link).rsplit("/", 1)[-1],
                            title=title,
                            description=body,
                            url=link,
                            posted_at=posted_at,
                            platform="Reddit",
                            author=author,
                            community=f"r/{sub}",
                            reply_count=0,
                            upvotes=1,
                            is_comment=False,
                            intent=intent,
                        )
                    )
                    if len(items) >= limit:
                        break
            except Exception as exc:
                logger.debug(f"Reddit feed r/{sub} skipped: {exc}")

        if items:
            return items, {"id": "reddit", "label": "Reddit", "status": "ok", "hits": len(items), "detail": f"{len(subs[:6])} subreddits"}

        # SERP Fallback (DuckDuckGo HTML) if Reddit RSS blocked or returned 0
        try:
            term = _primary_search_term(query)
            sub_q = " OR ".join(f"site:reddit.com/r/{s}" for s in subs[:3])
            ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus(f'({sub_q}) {term}')}"
            status, html, _ = SafeFetcher.safe_get(ddg_url, timeout=8, headers=UA)
            if status == 200 and html:
                for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
                    href = clean_html(m.group(1))
                    title = clean_html(m.group(2))
                    if "reddit.com/r/" not in href:
                        continue
                    sub_m = re.search(r"reddit\.com/(r/[^/]+)", href)
                    sub_name = sub_m.group(1) if sub_m else "r/reddit"
                    intent = classify_intent(title, query=query, competitors=competitors, is_comment=False) or {
                        "intent_type": "buying_request",
                        "intent_phrase": term[:32],
                        "trigger_sentence": title,
                        "intent_score": 55,
                    }
                    items.append(
                        self._build_item(
                            source=f"reddit:{sub_name}",
                            external_id=href.rsplit("/", 2)[-1] or title[:24],
                            title=title,
                            description=title,
                            url=href,
                            posted_at=None,
                            platform="Reddit",
                            author="",
                            community=sub_name,
                            reply_count=0,
                            upvotes=1,
                            is_comment=False,
                            intent=intent,
                        )
                    )
                    if len(items) >= limit:
                        break
                if items:
                    return items, {"id": "reddit", "label": "Reddit", "status": "ok", "hits": len(items), "detail": "SERP fallback"}
        except Exception as exc:
            logger.debug(f"Reddit SERP fallback skipped: {exc}")

        if auth_required and not os.getenv("REDDIT_CLIENT_ID"):
            return [], {"id": "reddit", "label": "Reddit", "status": "auth_required", "hits": 0, "detail": "OAuth / blocked"}
        if rate_limited:
            return [], {"id": "reddit", "label": "Reddit", "status": "rate_limited", "hits": 0, "detail": "429 rate-limited"}
        return [], {"id": "reddit", "label": "Reddit", "status": "ok", "hits": 0, "detail": "0 matches"}

    def fetch_github(
        self, query: Optional[str] = None, competitors: Optional[List[str]] = None, limit: int = 12
    ) -> Tuple[List[OpportunityItem], Dict[str, Any]]:
        items: List[OpportunityItem] = []
        try:
            term = _primary_search_term(query) if (query and query.strip()) else "looking for agency OR freelancer"
            url = f"https://api.github.com/search/issues?q={quote_plus(term)}&sort=updated&order=desc&per_page=20"
            headers = dict(UA)
            gh_tok = os.getenv("GITHUB_TOKEN", "").strip()
            if gh_tok:
                headers["Authorization"] = f"Bearer {gh_tok}"
            status, text, _ = SafeFetcher.safe_get(url, timeout=8, headers=headers)
            if status in (403, 429):
                return items, {"id": "github", "label": "GitHub", "status": "rate_limited", "hits": 0, "detail": f"HTTP {status}"}
            if status != 200 or not text:
                return items, {"id": "github", "label": "GitHub", "status": "error", "hits": 0, "detail": f"HTTP {status}"}
            data = json.loads(text)
            for issue in data.get("items", []):
                title = (issue.get("title") or "").strip()
                body = clean_html(issue.get("body") or "")
                posted_at = issue.get("created_at")
                reply_count = int(issue.get("comments") or 0)
                upvotes = int((issue.get("reactions") or {}).get("total_count") or 0)
                intent = classify_intent(
                    f"{title}. {body[:700]}",
                    query=query,
                    competitors=competitors,
                    posted_at=posted_at,
                    reply_count=reply_count,
                    is_comment=False,
                )
                if not intent:
                    continue
                user = (issue.get("user") or {}).get("login") or ""
                items.append(
                    self._build_item(
                        source="github",
                        external_id=str(issue.get("id") or issue.get("number")),
                        title=title,
                        description=body or title,
                        url=issue.get("html_url") or "",
                        posted_at=posted_at,
                        platform="GitHub",
                        author=user,
                        community="GitHub Issues",
                        reply_count=reply_count,
                        upvotes=upvotes,
                        is_comment=False,
                        intent=intent,
                    )
                )
                if len(items) >= limit:
                    break
            return items, {"id": "github", "label": "GitHub", "status": "ok", "hits": len(items), "detail": "Issues & Discussions"}
        except Exception as exc:
            logger.debug(f"GitHub skipped: {exc}")
            return items, {"id": "github", "label": "GitHub", "status": "error", "hits": 0, "detail": str(exc)[:60]}

    def fetch_devto(
        self, query: Optional[str] = None, competitors: Optional[List[str]] = None, limit: int = 10
    ) -> Tuple[List[OpportunityItem], Dict[str, Any]]:
        items: List[OpportunityItem] = []
        try:
            url = "https://dev.to/api/articles?per_page=30"
            status, text, _ = SafeFetcher.safe_get(url, timeout=8, headers=UA)
            if status != 200 or not text:
                return items, {"id": "devto", "label": "Dev.to", "status": "error", "hits": 0, "detail": f"HTTP {status}"}
            for art in json.loads(text):
                title = (art.get("title") or "").strip()
                desc = (art.get("description") or "").strip()
                posted_at = art.get("published_at")
                reply_count = int(art.get("comments_count") or 0)
                upvotes = int(art.get("positive_reactions_count") or 0)
                intent = classify_intent(
                    f"{title}. {desc}",
                    query=query,
                    competitors=competitors,
                    posted_at=posted_at,
                    reply_count=reply_count,
                    is_comment=False,
                )
                if not intent:
                    continue
                user = (art.get("user") or {}).get("username") or ""
                items.append(
                    self._build_item(
                        source="devto",
                        external_id=str(art.get("id")),
                        title=title,
                        description=desc or title,
                        url=art.get("url") or "",
                        posted_at=posted_at,
                        platform="Dev.to",
                        author=user,
                        community="dev.to",
                        reply_count=reply_count,
                        upvotes=upvotes,
                        is_comment=False,
                        intent=intent,
                    )
                )
                if len(items) >= limit:
                    break
            return items, {"id": "devto", "label": "Dev.to", "status": "ok", "hits": len(items), "detail": "Articles API"}
        except Exception as exc:
            logger.debug(f"Dev.to skipped: {exc}")
            return items, {"id": "devto", "label": "Dev.to", "status": "error", "hits": 0, "detail": str(exc)[:60]}

    def fetch_lobsters(
        self, query: Optional[str] = None, competitors: Optional[List[str]] = None, limit: int = 10
    ) -> Tuple[List[OpportunityItem], Dict[str, Any]]:
        items: List[OpportunityItem] = []
        try:
            url = "https://lobste.rs/newest.json"
            status, text, _ = SafeFetcher.safe_get(url, timeout=8, headers=UA)
            if status != 200 or not text:
                return items, {"id": "lobsters", "label": "Lobsters", "status": "error", "hits": 0, "detail": f"HTTP {status}"}
            for story in json.loads(text):
                title = (story.get("title") or "").strip()
                desc = clean_html(story.get("description") or "")
                posted_at = story.get("created_at")
                reply_count = int(story.get("comment_count") or 0)
                upvotes = int(story.get("score") or 0)
                intent = classify_intent(
                    f"{title}. {desc}",
                    query=query,
                    competitors=competitors,
                    posted_at=posted_at,
                    reply_count=reply_count,
                    is_comment=False,
                )
                if not intent:
                    continue
                items.append(
                    self._build_item(
                        source="lobsters",
                        external_id=str(story.get("short_id") or ""),
                        title=title,
                        description=desc or title,
                        url=story.get("comments_url") or story.get("url") or "",
                        posted_at=posted_at,
                        platform="Lobsters",
                        author=str(story.get("submitter_user") or ""),
                        community="lobste.rs",
                        reply_count=reply_count,
                        upvotes=upvotes,
                        is_comment=False,
                        intent=intent,
                    )
                )
                if len(items) >= limit:
                    break
            return items, {"id": "lobsters", "label": "Lobsters", "status": "ok", "hits": len(items), "detail": "Newest JSON"}
        except Exception as exc:
            logger.debug(f"Lobsters skipped: {exc}")
            return items, {"id": "lobsters", "label": "Lobsters", "status": "error", "hits": 0, "detail": str(exc)[:60]}

    def fetch_all_with_health(
        self,
        query: Optional[str] = None,
        limit: int = 40,
        time_window: str = "all",
        communities: Optional[List[str]] = None,
        competitors: Optional[List[str]] = None,
        include_comments: bool = True,
    ) -> Tuple[List[OpportunityItem], List[Dict[str, Any]]]:
        tasks = [
            lambda: self.fetch_hn_posts(query=query, competitors=competitors, time_window=time_window, limit=15),
            lambda: self.fetch_bluesky(query=query, competitors=competitors, limit=15),
            lambda: self.fetch_reddit(query=query, communities=communities, competitors=competitors, limit=15),
            lambda: self.fetch_github(query=query, competitors=competitors, limit=12),
            lambda: self.fetch_devto(query=query, competitors=competitors, limit=10),
            lambda: self.fetch_lobsters(query=query, competitors=competitors, limit=10),
        ]
        if include_comments:
            tasks.append(lambda: self.fetch_hn_comments(query=query, competitors=competitors, time_window=time_window, limit=12))

        all_items: List[OpportunityItem] = []
        health: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures = [pool.submit(fn) for fn in tasks]
            for fut in futures:
                try:
                    rows, h = fut.result(timeout=12)
                    all_items.extend(rows)
                    health.append(h)
                except Exception as exc:
                    logger.debug(f"Social worker failed: {exc}")

        filtered = [it for it in all_items if _within_window(it.posted_at, time_window)]
        # Deduplicate by (source, external_id), canonical URL, and normalized (title, author) hash
        seen_ids = set()
        seen_urls = set()
        seen_ta = set()
        deduped: List[OpportunityItem] = []
        for it in sorted(filtered, key=lambda x: x.metadata.get("intent_score", 0), reverse=True):
            k = (it.source, it.external_id)
            canon = _canonical_url(it.url)
            ta_hash = _title_author_hash(it.title, it.metadata.get("author", ""))
            if k in seen_ids or (canon and canon in seen_urls) or ta_hash in seen_ta:
                continue
            seen_ids.add(k)
            if canon:
                seen_urls.add(canon)
            seen_ta.add(ta_hash)
            deduped.append(it)
        return deduped[:limit], health

    def fetch(self, query: Optional[str] = None, limit: int = 30, org_id: Optional[str] = None) -> List[OpportunityItem]:
        items, _ = self.fetch_all_with_health(query=query, limit=limit)
        return items


def _serialize_item(it: OpportunityItem) -> Dict[str, Any]:
    return {
        "source": it.source,
        "type": it.type,
        "external_id": it.external_id,
        "title": it.title,
        "description": it.description,
        "url": it.url,
        "posted_at": it.posted_at,
        "platform": it.metadata.get("platform", it.source),
        "community": it.metadata.get("community", it.source),
        "author": it.metadata.get("author", ""),
        "intent_phrase": it.metadata.get("intent_phrase", ""),
        "intent_type": it.metadata.get("intent_type", "buying_request"),
        "intent_score": it.metadata.get("intent_score", 50),
        "trigger_sentence": it.metadata.get("trigger_sentence", ""),
        "reply_count": it.metadata.get("reply_count", 0),
        "upvotes": it.metadata.get("upvotes", 0),
        "is_comment": bool(it.metadata.get("is_comment", False)),
        "external_urls": it.metadata.get("external_urls", []),
    }


def scan_social_intent_rich(
    query: Optional[str] = None,
    limit: int = 40,
    time_window: str = "all",
    communities: Optional[List[str]] = None,
    competitors: Optional[List[str]] = None,
    include_comments: bool = True,
) -> Dict[str, Any]:
    connector = SocialIntentRadarConnector()
    items, health = connector.fetch_all_with_health(
        query=query,
        limit=limit,
        time_window=time_window,
        communities=communities,
        competitors=competitors,
        include_comments=include_comments,
    )
    return {
        "signals": [_serialize_item(it) for it in items],
        "source_health": health,
    }


def scan_social_intent(query: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    return scan_social_intent_rich(query=query, limit=limit)["signals"]
