"""
Google PageSpeed Insights (Lighthouse + Chrome UX Report) auditor.

Gives what a single HTTP request cannot: Largest Contentful Paint, layout shift, blocking time, and Lighthouse's
accessibility audits (axe-core rules run in a real browser). Real-user (field) data from CrUX is preferred over lab
data whenever Google has enough traffic data for the site.

Requires PAGESPEED_API_KEY (free from Google Cloud). Without it the engine reports the check as SKIPPED. Fixed vendor host.
"""

import os
from typing import Any, Dict, List, Optional

import requests

from auditors.base import AuditFinding

URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
# Core Web Vitals thresholds published by Google (web.dev/vitals)
LCP_GOOD, LCP_POOR = 2500, 4000          # ms
CLS_GOOD, CLS_POOR = 0.1, 0.25
INP_GOOD, INP_POOR = 200, 500            # ms
TBT_GOOD, TBT_POOR = 200, 600            # ms (lab proxy for interactivity)


def configured() -> bool:
    key = os.getenv("PAGESPEED_API_KEY", "")
    return bool(key and not key.startswith("your_"))


def run_pagespeed(url: str, strategy: str = "mobile") -> Dict[str, Any]:
    resp = requests.get(URL, params=[("url", url), ("strategy", strategy), ("category", "performance"), ("category", "accessibility"),
                                      ("category", "seo"), ("category", "best-practices"), ("key", os.environ["PAGESPEED_API_KEY"])], timeout=90)
    resp.raise_for_status()
    return resp.json()


def _grade(value: float, good: float, poor: float) -> Optional[str]:
    if value <= good:
        return None
    return "poor" if value > poor else "needs improvement"


def parse_psi(data: Dict[str, Any], url: str) -> List[AuditFinding]:
    """Pure function: PSI response -> findings. Only metrics present in the response are used."""
    out: List[AuditFinding] = []
    lh = data.get("lighthouseResult", {})
    audits, cats = lh.get("audits", {}), lh.get("categories", {})
    fetched = lh.get("fetchTime", "")
    field = (data.get("loadingExperience") or {}).get("metrics", {})

    def metric(audit_id: str) -> Optional[float]:
        a = audits.get(audit_id)
        return a.get("numericValue") if a and a.get("numericValue") is not None else None

    # --- LCP: real-user data first, lab second
    lcp_field = (field.get("LARGEST_CONTENTFUL_PAINT_MS") or {}).get("percentile")
    lcp_lab = metric("largest-contentful-paint")
    for source, lcp in (("Chrome real-user data (75th percentile)", lcp_field), ("Lighthouse lab test, mobile", lcp_lab)):
        if lcp is None:
            continue
        grade = _grade(lcp, LCP_GOOD, LCP_POOR)
        if grade:
            out.append(AuditFinding("performance", "slow_lcp", "high" if grade == "poor" else "medium",
                                    f"Largest Contentful Paint is {lcp / 1000:.1f}s ({grade}; Google: good <= 2.5s).",
                                    "Optimise the largest above-the-fold element: compress/preload the hero image, cut render-blocking CSS/JS, speed up the server.",
                                    "Slow main-content load affects Google's page-experience signals and how fast the page feels.",
                                    "performance_engineering", f"LCP {lcp:.0f} ms. Source: {source}. Tested {fetched}.",
                                    confidence=0.95 if "real-user" in source else 0.8))
        break  # field beats lab; report one LCP finding

    cls_field = (field.get("CUMULATIVE_LAYOUT_SHIFT_SCORE") or {}).get("percentile")
    cls_val = (cls_field / 100.0) if cls_field is not None else metric("cumulative-layout-shift")
    if cls_val is not None and cls_val > CLS_GOOD:
        out.append(AuditFinding("performance", "layout_shift", "high" if cls_val > CLS_POOR else "medium",
                                f"Cumulative Layout Shift is {cls_val:.2f} (Google: good <= 0.1).",
                                "Reserve space for images, ads and embeds; avoid inserting content above existing content.",
                                "Content jumping while loading causes mis-taps and a poor experience.", "performance_engineering",
                                f"CLS {cls_val:.3f} ({'real-user' if cls_field is not None else 'lab'}). Tested {fetched}.", confidence=0.9))

    inp_field = (field.get("INTERACTION_TO_NEXT_PAINT") or {}).get("percentile")
    if inp_field is not None and inp_field > INP_GOOD:
        out.append(AuditFinding("performance", "slow_inp", "high" if inp_field > INP_POOR else "medium",
                                f"Interaction to Next Paint is {inp_field} ms (Google: good <= 200 ms).",
                                "Break up long JavaScript tasks, defer non-critical scripts, reduce main-thread work.",
                                "The page feels sluggish when people tap or type.", "performance_engineering",
                                f"INP {inp_field} ms from real-user data. Tested {fetched}.", confidence=0.95))
    else:
        tbt = metric("total-blocking-time")
        if inp_field is None and tbt is not None and tbt > TBT_GOOD:
            out.append(AuditFinding("performance", "high_blocking_time", "high" if tbt > TBT_POOR else "medium",
                                    f"Main-thread blocking time is {tbt:.0f} ms in the lab test (good <= 200 ms).",
                                    "Reduce and split JavaScript; remove unused third-party scripts.",
                                    "Heavy scripts delay when the page responds to taps.", "performance_engineering",
                                    f"Total Blocking Time {tbt:.0f} ms (Lighthouse mobile). Tested {fetched}.", confidence=0.8))

    perf = (cats.get("performance") or {}).get("score")
    if perf is not None and perf < 0.5:
        out.append(AuditFinding("performance", "low_lighthouse_score", "high",
                                f"Lighthouse mobile performance score is {round(perf * 100)}/100.",
                                "Work through the Lighthouse opportunities: images, JavaScript, render-blocking resources.",
                                "A low score reflects slow loading and responsiveness on a mid-range phone.", "performance_engineering",
                                f"Lighthouse performance score {perf:.2f}. Tested {fetched}.", confidence=0.8))

    blocking = audits.get("render-blocking-resources", {})
    savings = (blocking.get("details") or {}).get("overallSavingsMs") or 0
    if savings >= 500:
        out.append(AuditFinding("performance", "render_blocking_savings", "medium",
                                f"Render-blocking CSS/JS delays first paint by an estimated {savings:.0f} ms.",
                                "Inline critical CSS and defer the rest.", "Visitors stare at a blank screen longer.", "performance_engineering",
                                f"Lighthouse 'render-blocking-resources' potential savings: {savings:.0f} ms.", confidence=0.8))

    # --- accessibility: Lighthouse runs axe-core in a real browser
    acc = (cats.get("accessibility") or {})
    if acc.get("score") is not None and acc["score"] < 0.9:
        failing = []
        for ref in acc.get("auditRefs", []):
            a = audits.get(ref.get("id"), {})
            if a.get("score") == 0 and a.get("scoreDisplayMode") == "binary":
                items = len((a.get("details") or {}).get("items", []))
                failing.append(f"{a.get('title')} ({items})")
        out.append(AuditFinding("a11y", "lighthouse_accessibility", "high" if acc["score"] < 0.7 else "medium",
                                f"Lighthouse accessibility score is {round(acc['score'] * 100)}/100 with {len(failing)} failing rule(s).",
                                "Fix the failing rules, starting with contrast, labels and names.",
                                "Barriers for keyboard and screen-reader users; relevant to accessibility regulations.", "a11y_compliance",
                                "Failing: " + "; ".join(failing[:6]) + f". Tested {fetched}.", confidence=0.9))
    return out


class PageSpeedAuditor:
    @staticmethod
    def audit(url: str) -> List[AuditFinding]:
        return parse_psi(run_pagespeed(url), url)
