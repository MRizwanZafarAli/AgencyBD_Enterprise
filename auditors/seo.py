"""
SEO auditor: indexability, metadata, structure and structured data. HTML is parsed with a real parser (attribute order
and quoting do not matter) and site-level files come from the shared SiteContext.
"""

import json
import re
from typing import List
from urllib.robotparser import RobotFileParser

from auditors.base import AuditFinding
from auditors.context import SiteContext


def robots_allows(robots_txt: str, agent: str, path: str = "/") -> bool:
    rp = RobotFileParser()
    rp.parse(robots_txt.splitlines())
    return rp.can_fetch(agent, path)


class SEOAuditor:
    @staticmethod
    def audit(ctx: SiteContext) -> List[AuditFinding]:
        f: List[AuditFinding] = []
        soup, h = ctx.soup, ctx.lower_headers

        def meta(**attrs):
            tag = soup.find("meta", attrs=attrs)
            return (tag.get("content") or "").strip() if tag else ""

        # --- can search engines index it at all?
        robots_meta = meta(name="robots").lower() + " " + h.get("x-robots-tag", "").lower()
        if "noindex" in robots_meta:
            f.append(AuditFinding("seo", "noindex_set", "critical", "The homepage tells search engines NOT to index it (noindex).",
                                  "Remove the noindex directive (meta robots or X-Robots-Tag) unless this is intentional.",
                                  "The page will not appear in search results.", "seo_optimization", f"robots directive: {robots_meta.strip()}"))
        if ctx.robots_txt is not None:
            if ctx.robots_txt and not robots_allows(ctx.robots_txt, "*"):
                f.append(AuditFinding("seo", "robots_blocks_all", "critical", "robots.txt blocks all crawlers from the whole site.",
                                      "Remove 'Disallow: /' for User-agent: * unless the site is meant to be private.",
                                      "Search engines are told not to crawl any page.", "seo_optimization", "robots.txt disallows '/' for '*'."))
            elif ctx.robots_txt == "":
                f.append(AuditFinding("seo", "missing_robots_txt", "low", "No robots.txt file.",
                                      "Publish a robots.txt that references your sitemap.", "Crawlers get no guidance and no sitemap pointer.",
                                      "seo_optimization", "GET /robots.txt returned 404."))
        if ctx.sitemap_found is False:
            f.append(AuditFinding("seo", "missing_sitemap", "medium", "No XML sitemap found (checked robots.txt and /sitemap.xml).",
                                  "Generate sitemap.xml and list it in robots.txt.", "New and deep pages are discovered more slowly.",
                                  "seo_optimization", "No Sitemap: line in robots.txt and /sitemap.xml missing."))

        # --- metadata
        title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
        if not title:
            f.append(AuditFinding("seo", "missing_meta_title", "high", "The homepage has no <title>.",
                                  "Add a unique title of roughly 50-60 characters describing the business.",
                                  "Search results will show a generic or auto-generated title.", "seo_optimization", "No non-empty <title> tag."))
        elif len(title) > 65:
            f.append(AuditFinding("seo", "title_too_long", "low", f"The title is {len(title)} characters and may be truncated in results.",
                                  "Shorten to about 60 characters.", "Google truncates long titles by pixel width.", "seo_optimization",
                                  f"Title ({len(title)} chars): {title[:80]}", confidence=0.8))
        if not meta(name="description"):
            f.append(AuditFinding("seo", "missing_meta_description", "medium", "The homepage has no meta description.",
                                  "Write a 120-155 character description with a clear call to action.",
                                  "Google will pick its own snippet, which is often a poor summary.", "seo_optimization", "No meta name='description' with content."))
        if not meta(name="viewport"):
            f.append(AuditFinding("seo", "missing_viewport_tag", "high", "No mobile viewport meta tag.",
                                  "Add <meta name='viewport' content='width=device-width, initial-scale=1'>.",
                                  "Google indexes the mobile version first; without this the page renders desktop-sized on phones.",
                                  "mobile_optimization", "No meta name='viewport'."))
        if not soup.find("link", rel=lambda r: r and "canonical" in (r if isinstance(r, list) else [r])):
            f.append(AuditFinding("seo", "missing_canonical_url", "low", "No rel=canonical link.", "Declare the preferred URL with <link rel='canonical'>.",
                                  "Duplicate URL variants can split ranking signals.", "seo_optimization", "No <link rel='canonical'>."))
        h1s = soup.find_all("h1")
        if len(h1s) != 1:
            f.append(AuditFinding("seo", "h1_structure", "low", "The homepage has no H1 heading." if not h1s else f"The homepage has {len(h1s)} H1 headings.",
                                  "Use exactly one H1 that states what the business does.", "A clear single H1 helps search engines and screen readers.",
                                  "seo_optimization", f"{len(h1s)} <h1> element(s)."))
        words = len(soup.get_text(" ", strip=True).split())
        from intel.site_profile import looks_js_rendered
        if words < 150 and not looks_js_rendered(soup, words):             # an app shell's words are not in the HTML, so a low count proves nothing
            f.append(AuditFinding("seo", "thin_content", "low", f"The homepage has only about {words} words of text.",
                                  "Add useful copy: services, location, proof, FAQs.", "Little text gives search engines little to rank.",
                                  "seo_optimization", f"~{words} words of visible text.", confidence=0.7))
        if not (meta(property="og:title") and meta(property="og:image")):
            f.append(AuditFinding("seo", "missing_open_graph", "info", "Open Graph tags (title/image) are missing.",
                                  "Add og:title, og:description and og:image.", "Links shared on social networks and chat apps show no preview card.",
                                  "seo_optimization", "og:title or og:image absent."))

        # --- structured data
        blocks = soup.find_all("script", attrs={"type": "application/ld+json"})
        if not blocks:
            f.append(AuditFinding("seo", "missing_structured_data", "medium", "No schema.org (JSON-LD) structured data.",
                                  "Add Organization/LocalBusiness JSON-LD (plus FAQ or Product where relevant).",
                                  "No eligibility for rich results; weaker entity understanding.", "seo_optimization", "0 application/ld+json blocks."))
        else:
            bad = 0
            for b in blocks:
                try:
                    json.loads(b.string or b.get_text() or "")
                except ValueError:
                    bad += 1
            if bad:
                f.append(AuditFinding("seo", "invalid_structured_data", "medium", f"{bad} JSON-LD block(s) contain invalid JSON and are ignored by search engines.",
                                      "Fix the JSON syntax (validate with Google's Rich Results Test).", "Invalid markup earns no rich results.",
                                      "seo_optimization", f"{bad} of {len(blocks)} JSON-LD blocks failed to parse."))
        return f
