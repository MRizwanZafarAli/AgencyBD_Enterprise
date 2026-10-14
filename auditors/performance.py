"""
Performance auditor (measured from one real request; lab metrics come from PageSpeed when configured).

Thresholds follow Google's published guidance (web.dev): TTFB good <=800 ms, poor >1800 ms. Impact statements are
deliberately qualitative: no invented conversion statistics.
"""

import re
from typing import List
from urllib.parse import urlparse

from auditors.base import AuditFinding
from auditors.context import SiteContext


class PerformanceAuditor:
    @staticmethod
    def audit(ctx: SiteContext) -> List[AuditFinding]:
        f: List[AuditFinding] = []
        h, soup = ctx.lower_headers, ctx.soup
        size_kb = round(len(ctx.html.encode("utf-8")) / 1024, 1)

        if ctx.ttfb_ms > 800:
            poor = ctx.ttfb_ms > 1800
            f.append(AuditFinding(
                "performance", "slow_ttfb", "high" if poor else "medium",
                f"Server took {ctx.ttfb_ms} ms to start responding (Google: good <= 800 ms, poor > 1800 ms).",
                "Add full-page or edge caching (CDN), check database queries and hosting capacity.",
                "A slow first byte delays everything that follows and counts against Google's loading metrics (LCP).",
                "performance_engineering", f"Time to response headers: {ctx.ttfb_ms} ms (single request from our server).",
                confidence=0.7))  # one sample from one location

        if "content-encoding" not in h and len(ctx.html) > 10_000:
            f.append(AuditFinding(
                "performance", "no_text_compression", "medium",
                f"The HTML ({size_kb} KB) was served without gzip/brotli compression.",
                "Enable gzip or brotli on the web server or CDN for HTML, CSS and JavaScript.",
                "Larger transfers on slow mobile connections.", "performance_engineering",
                f"No Content-Encoding header on a {size_kb} KB response."))

        head = soup.head or soup
        blocking = [s for s in head.find_all("script", src=True)
                    if not s.has_attr("async") and not s.has_attr("defer") and (s.get("type") or "").lower() != "module"]
        if len(blocking) >= 3:
            f.append(AuditFinding(
                "performance", "render_blocking_scripts", "medium",
                f"{len(blocking)} scripts in <head> block rendering (no async/defer).",
                "Add defer/async, or move non-critical scripts to the end of the body.",
                "The browser cannot paint the page until blocking scripts have downloaded and run.", "performance_engineering",
                f"{len(blocking)} blocking <script src> tags in <head>: " + ", ".join(urlparse(s['src']).netloc or 'inline-host' for s in blocking[:4])))

        third = {urlparse(t.get("src") or t.get("href") or "").netloc for t in soup.find_all(["script", "link"])}
        third = {d for d in third if d and d.replace("www.", "") != ctx.domain.replace("www.", "")}
        if len(third) >= 12:
            f.append(AuditFinding(
                "performance", "many_third_party_hosts", "low",
                f"The page loads code or styles from {len(third)} other domains.",
                "Audit third-party tags and remove those that are unused.",
                "Each third-party host adds connection overhead and a dependency outside your control.", "performance_engineering",
                f"{len(third)} external hosts: " + ", ".join(sorted(third)[:6]) + " ..."))

        no_dims = [i for i in soup.find_all("img") if not (i.get("width") and i.get("height"))]
        if len(no_dims) >= 6:
            f.append(AuditFinding(
                "performance", "images_without_dimensions", "low",
                f"{len(no_dims)} images have no width/height attributes.",
                "Declare width and height (or CSS aspect-ratio) so the browser reserves space.",
                "Images that pop in can shift the layout (Cumulative Layout Shift).", "performance_engineering",
                f"{len(no_dims)} of {len(soup.find_all('img'))} <img> tags lack explicit dimensions.", confidence=0.8))

        if size_kb > 300:
            f.append(AuditFinding(
                "performance", "bloated_dom_size", "medium", f"The HTML document alone is {size_kb} KB.",
                "Trim inline data, split large pages, and lazy-load below-the-fold sections.",
                "Large documents take longer to parse on phones.", "performance_engineering", f"HTML size: {size_kb} KB."))

        if "cache-control" not in h and "expires" not in h:
            f.append(AuditFinding(
                "performance", "missing_cache_control", "low", "The HTML response has no caching headers.",
                "Send Cache-Control (e.g. short s-maxage with stale-while-revalidate) so CDNs can serve repeat requests.",
                "Every visit hits the origin server.", "performance_engineering", "Neither Cache-Control nor Expires present."))
        return f
