"""
Accessibility auditor (static HTML checks against common WCAG 2.2 failures).

Limits: it reads the server-sent HTML, so content built by JavaScript is not covered. When PAGESPEED_API_KEY is set the
Lighthouse accessibility audit (axe-core rules, run in a real browser) is added by the PageSpeed auditor.
"""

import re
from typing import List

from auditors.base import AuditFinding
from auditors.context import SiteContext


def _name(tag) -> str:
    return " ".join(filter(None, [tag.get_text(" ", strip=True), tag.get("aria-label", ""), tag.get("title", ""),
                                  *[i.get("alt", "") for i in tag.find_all("img")]])).strip()


class A11yAuditor:
    @staticmethod
    def audit(ctx: SiteContext) -> List[AuditFinding]:
        f: List[AuditFinding] = []
        soup = ctx.soup

        def add(check, severity, finding, fix, impact, evidence, wcag):
            f.append(AuditFinding("a11y", check, severity, f"{finding} (WCAG {wcag}).", fix, impact, "a11y_compliance", evidence))

        html_tag = soup.find("html")
        if not (html_tag and re.fullmatch(r"[a-zA-Z]{2,3}(-[a-zA-Z0-9]+)*", html_tag.get("lang", "") or "")):
            add("missing_html_lang", "medium", "The <html> element has no valid lang attribute", "Add lang='en' (or the page language).",
                "Screen readers may use the wrong pronunciation.", "<html> lang attribute missing or invalid.", "3.1.1")

        no_alt = [i for i in soup.find_all("img") if not i.has_attr("alt")]
        if no_alt:
            add("images_missing_alt", "high" if len(no_alt) > 3 else "medium", f"{len(no_alt)} image(s) have no alt attribute",
                "Give informative images descriptive alt text and decorative ones alt=''.",
                "Screen-reader users get no description; also relevant to accessibility regulations.",
                f"{len(no_alt)} <img> without alt, e.g. {no_alt[0].get('src', '')[:60]}", "1.1.1")

        unlabeled = []
        for inp in soup.find_all("input"):
            if (inp.get("type") or "text").lower() in ("hidden", "submit", "button", "image", "reset"):
                continue
            iid = inp.get("id")
            if inp.get("aria-label") or inp.get("aria-labelledby") or inp.get("title") or inp.find_parent("label") \
                    or (iid and soup.find("label", attrs={"for": iid})):
                continue
            unlabeled.append(inp)
        unlabeled += [t for t in soup.find_all(["select", "textarea"]) if not (t.get("aria-label") or t.get("aria-labelledby") or t.find_parent("label")
                                                                               or (t.get("id") and soup.find("label", attrs={"for": t.get("id")})))]
        if unlabeled:
            add("form_fields_unlabeled", "high" if len(unlabeled) > 2 else "medium", f"{len(unlabeled)} form field(s) have no label",
                "Associate each field with a <label for=...> or aria-label.", "Assistive technology cannot tell users what to enter.",
                f"{len(unlabeled)} unlabeled controls, e.g. name='{unlabeled[0].get('name', '')}'", "1.3.1 / 3.3.2")

        empty_buttons = [b for b in soup.find_all("button") if not _name(b) and not b.get("value")]
        if empty_buttons:
            add("buttons_without_name", "medium", f"{len(empty_buttons)} button(s) have no accessible name", "Add visible text or aria-label.",
                "Screen-reader users hear only 'button'.", f"{len(empty_buttons)} empty <button> elements.", "4.1.2")
        empty_links = [a for a in soup.find_all("a", href=True) if not _name(a)]
        if empty_links:
            add("links_without_name", "medium", f"{len(empty_links)} link(s) have no text or accessible name", "Add link text or aria-label.",
                "Users cannot tell where the link goes.", f"{len(empty_links)} empty <a>, e.g. href={empty_links[0]['href'][:60]}", "2.4.4")
        frames = [i for i in soup.find_all("iframe") if not i.get("title")]
        if frames:
            add("iframes_without_title", "low", f"{len(frames)} iframe(s) have no title", "Add a title describing each frame.",
                "Frames are announced without context.", f"{len(frames)} <iframe> without title.", "4.1.2")

        viewport = (soup.find("meta", attrs={"name": "viewport"}) or {}).get("content", "") if soup.find("meta", attrs={"name": "viewport"}) else ""
        if re.search(r"user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b", viewport, re.IGNORECASE):
            add("zoom_disabled", "medium", "Pinch-zoom is disabled by the viewport tag", "Remove user-scalable=no and maximum-scale limits.",
                "Low-vision users cannot enlarge the page.", f"viewport: {viewport}", "1.4.4")

        levels = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
        if any(b - a > 1 for a, b in zip(levels, levels[1:])):
            add("heading_levels_skipped", "low", "Heading levels skip (e.g. H2 followed by H4)", "Use headings in order without gaps.",
                "Screen-reader users navigate by heading structure.", f"Heading sequence: {levels[:12]}", "1.3.1")
        if [t for t in soup.find_all(attrs={"tabindex": True}) if (t.get("tabindex") or "0").lstrip("-").isdigit() and int(t["tabindex"]) > 0]:
            add("positive_tabindex", "low", "Elements use a positive tabindex", "Remove positive tabindex values; use DOM order.",
                "Keyboard focus order becomes unpredictable.", "tabindex > 0 present.", "2.4.3")
        return f
