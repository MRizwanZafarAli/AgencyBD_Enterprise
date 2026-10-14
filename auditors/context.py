"""
Shared, real observations about a site, gathered once and handed to every auditor.

Each optional field is tri-state: a value when we observed it, and None when we could NOT observe it. Auditors must
never turn "unknown" into a finding.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from auditors.tls import inspect_tls
from net.fetcher import SafeFetcher, SSRFSecurityError


@dataclass
class SiteContext:
    domain: str
    url: str                       # final URL after redirects
    scheme: str                    # https | http
    status_code: int
    headers: Dict[str, str]
    html: str
    soup: BeautifulSoup
    ttfb_ms: int                   # time to response headers (what Google calls TTFB)
    total_ms: int                  # time to download the page body
    robots_txt: Optional[str] = None     # None = unknown, "" = no robots.txt
    llms_txt: Optional[bool] = None
    sitemap_found: Optional[bool] = None
    http_to_https: Optional[bool] = None
    tls: Optional[Dict[str, Any]] = None
    notes: List[str] = field(default_factory=list)

    @property
    def lower_headers(self) -> Dict[str, str]:
        return {k.lower(): v for k, v in self.headers.items()}


def _optional(url: str):
    """(status, text, headers, final_url) or None when the fetch itself failed. SSRF blocks are not swallowed."""
    try:
        r = SafeFetcher.safe_fetch(url, timeout=6, max_bytes=300_000)
        return r.status_code, r.text, r.headers, r.final_url
    except SSRFSecurityError:
        raise
    except Exception:
        return None


def _looks_like_html(text: str) -> bool:
    head = text.lstrip()[:200].lower()
    return head.startswith("<!doctype") or head.startswith("<html")


def fetch_site(domain: str) -> SiteContext:
    """Fetches the homepage (https first, then http) plus the supporting files. Raises if the homepage cannot be read."""
    import time
    scheme, result, started = "https", None, time.time()
    try:
        result = SafeFetcher.safe_fetch(f"https://{domain}", timeout=10)
    except SSRFSecurityError:
        raise
    except Exception as first:
        try:
            scheme, started = "http", time.time()
            result = SafeFetcher.safe_fetch(f"http://{domain}", timeout=8)
        except SSRFSecurityError:
            raise
        except Exception as second:
            raise ConnectionError(f"{type(first).__name__}: {str(first)[:100]}; http fallback: {str(second)[:100]}")
    total_ms = int((time.time() - started) * 1000)
    final_scheme = "https" if result.final_url.startswith("https") else "http"
    ctx = SiteContext(domain=domain, url=result.final_url, scheme=final_scheme, status_code=result.status_code,
                      headers=result.headers, html=result.text, soup=BeautifulSoup(result.text, "html.parser"),
                      ttfb_ms=result.elapsed_ms, total_ms=total_ms)

    base = f"{final_scheme}://{domain}"
    with ThreadPoolExecutor(max_workers=5) as pool:
        f_robots = pool.submit(_optional, f"{base}/robots.txt")
        f_llms = pool.submit(_optional, f"{base}/llms.txt")
        f_http = pool.submit(_optional, f"http://{domain}/") if final_scheme == "https" else None
        f_tls = pool.submit(inspect_tls, domain) if final_scheme == "https" else None

        robots = f_robots.result()
        if robots:
            status, text = robots[0], robots[1]
            if status == 200 and not _looks_like_html(text):
                ctx.robots_txt = text
            elif status in (404, 410) or (status == 200 and _looks_like_html(text)):
                ctx.robots_txt = ""
        llms = f_llms.result()
        if llms:
            status, text = llms[0], llms[1]
            ctx.llms_txt = status == 200 and bool(text.strip()) and not _looks_like_html(text)
        if f_http is not None:
            http = f_http.result()
            if http is not None:
                ctx.http_to_https = http[3].startswith("https")
        if f_tls is not None:
            try:
                ctx.tls = f_tls.result()
            except SSRFSecurityError:
                raise
            except Exception as exc:
                ctx.notes.append(f"TLS inspection failed: {str(exc)[:80]}")

    sitemap_lines = [l.split(":", 1)[1].strip() for l in (ctx.robots_txt or "").splitlines() if l.lower().startswith("sitemap:")]
    if sitemap_lines:
        ctx.sitemap_found = True
    else:
        sm = _optional(f"{base}/sitemap.xml")
        if sm:
            status, text = sm[0], sm[1]
            ctx.sitemap_found = True if (status == 200 and ("<urlset" in text or "<sitemapindex" in text)) else (False if status in (404, 410) or status == 200 else None)
    return ctx
