"""Platform-Native Safeguards & Official Connectors (Fiverr Shield, Upwork MCP, Clutch Qualifier)."""

import re
from typing import Any, Dict, List

FIVERR_RISKY_PATTERNS = [
    (r"\b(whatsapp|telegram|skype|zoom|google meet|calendly|paypal|wise|payoneer|stripe)\b", "Off-platform contact/payment tool"),
    (r"\b(email me|my email|outside fiverr|off platform|direct payment|phone number)\b", "Off-platform solicitation phrase"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "Email address detected"),
    (r"\+?\d[\d\s\-]{8,}\d", "Phone number detected"),
]


def check_fiverr_compliance(text: str) -> Dict[str, Any]:
    """Scans drafted Fiverr replies for off-platform contact/payment terms before copying."""
    warnings: List[Dict[str, str]] = []
    seen = set()
    for pattern, reason in FIVERR_RISKY_PATTERNS:
        for m in re.finditer(pattern, text or "", flags=re.IGNORECASE):
            token = m.group(0).strip()
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            warnings.append({"term": token, "reason": reason})

    suggestions: List[str] = []
    if warnings:
        suggestions.append("Keep all messages, files, and payments inside Fiverr Order/Inbox chat.")
        if any("zoom" in w["term"].lower() or "meet" in w["term"].lower() or "calendly" in w["term"].lower() for w in warnings):
            suggestions.append("Use Fiverr's built-in Zoom video call button inside the Fiverr inbox instead of external links.")
        if any("paypal" in w["term"].lower() or "stripe" in w["term"].lower() or "wise" in w["term"].lower() for w in warnings):
            suggestions.append("Send a Fiverr Custom Offer instead of mentioning external payment methods.")

    return {
        "safe": len(warnings) == 0,
        "warnings": warnings,
        "suggestions": suggestions,
    }


def qualify_clutch_inquiry(
    service_fit: int = 20,
    budget: float = 0,
    min_project_size: float = 10000,
    specificity: int = 20,
    timeline_weeks: int = 4,
) -> Dict[str, Any]:
    """4-Point Clutch Inquiry Qualifier (0-100) + <30m SLA guidance."""
    fit_pts = max(0, min(25, int(service_fit)))
    if min_project_size <= 0:
        budget_pts = 25
    elif budget >= min_project_size:
        budget_pts = 25
    elif budget >= min_project_size * 0.6:
        budget_pts = 15
    else:
        budget_pts = 5

    spec_pts = max(0, min(25, int(specificity)))
    if 1 <= timeline_weeks <= 12:
        time_pts = 25
    elif timeline_weeks <= 24:
        time_pts = 15
    else:
        time_pts = 10

    score = fit_pts + budget_pts + spec_pts + time_pts
    band = "High Intent" if score >= 75 else ("Qualified" if score >= 50 else "Price Shopper / Low Fit")
    return {
        "score": score,
        "band": band,
        "sla_minutes": 30,
        "flags": [f"Budget ${budget:,.0f} is below min project size ${min_project_size:,.0f}"] if budget and budget < min_project_size else [],
    }


def get_upwork_mcp_spec() -> Dict[str, Any]:
    """Official Upwork MCP server metadata (free, OAuth 2.1 dynamic client registration, human-confirmed)."""
    return {
        "server_url": "https://mcp.upwork.com/mcp",
        "auth_flow": "OAuth 2.1 (Dynamic Client Registration)",
        "capabilities": ["job_search", "connects_balance", "unread_messages", "human_confirmed_proposal_drafts"],
        "safety_note": "100% human-in-the-loop confirmation; Connects are never spent automatically.",
    }
