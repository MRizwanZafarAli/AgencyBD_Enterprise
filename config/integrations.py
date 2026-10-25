"""
Integration keys managed from Settings.

A super-admin can add, replace, test and remove the API keys of the products this app talks to. Values are encrypted at rest (Fernet,
key derived from AGENCYBD_HMAC_VAULT_KEY), never returned by the API (only "set" and the last four characters), and never logged.

How they take effect: the app reads every key from the process environment at the moment it needs it, so saving a key sets that variable
immediately and `apply_all()` re-applies stored keys at startup. A key saved here overrides the same variable from .env; removing it
restores the .env value. Keys are workspace-wide (shared by every tenant on this installation), which is why only a super-admin may change them.
"""

import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from database.db import get_db
from net.fetcher import SafeFetcher
from security.crypto import decrypt_secret, encrypt_secret

MAX_LEN = 512
_original: Dict[str, Optional[str]] = {}          # value of the variable before the UI overrode it (None = it was unset)


@dataclass(frozen=True)
class Provider:
    name: str                 # environment variable
    label: str
    group: str
    purpose: str
    get_url: str
    cost: str                 # stated conservatively; pricing changes, so each entry points to the vendor page
    secret: bool = True
    check: Optional[Callable[[str], Optional[str]]] = None       # returns an error message, or None when the format is acceptable


def _starts(prefix: str, what: str) -> Callable[[str], Optional[str]]:
    return lambda v: None if v.startswith(prefix) else f"{what} must start with {prefix}"


PROVIDERS: List[Provider] = [
    Provider("ANTHROPIC_API_KEY", "Anthropic (Claude)", "AI", "Proposals, 'Should we chase this?', plain-language advice, assistant.", "https://console.anthropic.com/settings/keys", "Paid, per use"),
    Provider("OLLAMA_HOST", "Ollama (local model address)", "AI", "A local model instead of a paid one, e.g. http://localhost:11434.", "https://ollama.com", "Free; runs on your machine", False, _starts("http", "The address")),
    Provider("GOOGLE_PLACES_API_KEY", "Google Places", "Finding prospects", "Google Maps search with ratings, review counts, phone and a verified 'no website'.", "https://console.cloud.google.com/google/maps-apis", "Small free monthly allowance per request type, then paid; needs a billing account"),
    Provider("BRAVE_SEARCH_API_KEY", "Brave Search", "Finding prospects", "Better company-name to website matching.", "https://brave.com/search/api/", "Free plan with limits, then paid"),
    Provider("SAM_GOV_API_KEY", "SAM.gov", "Finding prospects", "US federal tenders.", "https://sam.gov/content/home", "Free"),
    Provider("GITHUB_TOKEN", "GitHub token", "Finding prospects", "Higher rate limit for the GitHub bounty feed.", "https://github.com/settings/tokens", "Free"),
    Provider("UPWORK_CLIENT_ID", "Upwork client ID", "Finding prospects", "Upwork job feed (needs API access approved by Upwork).", "https://www.upwork.com/developer/keys/apply", "Free, by approval", False),
    Provider("UPWORK_CLIENT_SECRET", "Upwork client secret", "Finding prospects", "Pairs with the client ID.", "https://www.upwork.com/developer/keys/apply", "Free, by approval"),
    Provider("UPWORK_REDIRECT_URI", "Upwork redirect URL", "Finding prospects", "The callback address you registered with Upwork.", "https://www.upwork.com/developer/keys/apply", "n/a", False, _starts("http", "The URL")),
    Provider("PAGESPEED_API_KEY", "Google PageSpeed", "Website checks", "Real Core Web Vitals and the browser accessibility audit.", "https://developers.google.com/speed/docs/insights/v5/get-started", "Free within quota"),
    Provider("NVD_API_KEY", "NVD (vulnerability database)", "Website checks", "Higher rate limit for vulnerability lookups.", "https://nvd.nist.gov/developers/request-an-api-key", "Free"),
    Provider("ZEROBOUNCE_API_KEY", "ZeroBounce", "Email", "Confirms an address accepts mail. Without a verifier nothing can be emailed.", "https://www.zerobounce.net/members/apikey", "Paid, with a small free trial"),
    Provider("MILLIONVERIFIER_API_KEY", "MillionVerifier", "Email", "Alternative email verifier.", "https://app.millionverifier.com/", "Paid, with a small free trial"),
    Provider("HUNTER_API_KEY", "Hunter", "Email", "Looks up emails for a company domain.", "https://hunter.io/api-keys", "Free tier, then paid"),
    Provider("APOLLO_API_KEY", "Apollo", "Email", "People and company data.", "https://developer.apollo.io/", "Free tier, then paid"),
    Provider("RESEND_API_KEY", "Resend", "Sending", "Email delivery provider.", "https://resend.com/api-keys", "Free tier, then paid"),
    Provider("SENDGRID_API_KEY", "SendGrid", "Sending", "Email delivery provider.", "https://app.sendgrid.com/settings/api_keys", "Free tier, then paid"),
    Provider("SLACK_WEBHOOK_URL", "Slack webhook", "Notifications", "Daily digest and new-vulnerability alerts.", "https://api.slack.com/messaging/webhooks", "Free", True, _starts("https://hooks.slack.com/", "A Slack webhook")),
    Provider("HUBSPOT_ACCESS_TOKEN", "HubSpot", "CRM", "Sync deals to HubSpot.", "https://developers.hubspot.com/docs/api/private-apps", "Free CRM available"),
]
BY_NAME = {p.name: p for p in PROVIDERS}


def _mask(provider: Provider, value: str) -> str:
    if not provider.secret:
        return value if len(value) <= 60 else value[:57] + "…"
    return "••••" + value[-4:] if len(value) > 8 else "••••"


def validate(name: str, value: str) -> str:
    if name not in BY_NAME:
        raise ValueError(f"'{name}' is not a supported integration.")
    value = (value or "").strip()
    if not value:
        raise ValueError("The value is empty.")
    if len(value) > MAX_LEN or re.search(r"[\x00-\x1f\x7f\s]", value):
        raise ValueError("The value must be a single line with no spaces or control characters (max 512 characters).")
    error = BY_NAME[name].check(value) if BY_NAME[name].check else None
    if error:
        raise ValueError(error)
    return value


def _apply(name: str, value: str) -> None:
    if name not in _original:
        _original[name] = os.environ.get(name)
    os.environ[name] = value


def set_key(name: str, value: str, user: str) -> Dict[str, Any]:
    value = validate(name, value)
    with get_db() as db:
        db.execute("INSERT INTO integration_keys (name, value_enc, set_by, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
                   "ON CONFLICT(name) DO UPDATE SET value_enc = excluded.value_enc, set_by = excluded.set_by, updated_at = CURRENT_TIMESTAMP",
                   (name, encrypt_secret(value), user))
        db.commit()
    _apply(name, value)
    return status_of(name)


def clear_key(name: str) -> bool:
    if name not in BY_NAME:
        raise ValueError(f"'{name}' is not a supported integration.")
    with get_db() as db:
        removed = db.execute("DELETE FROM integration_keys WHERE name = ?", (name,)).rowcount
        db.commit()
    if name in _original:                                  # restore whatever .env had, or unset
        previous = _original.pop(name)
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous
    return removed > 0


def apply_all() -> int:
    """Re-applies every stored key to the process environment (call at startup). Returns how many were applied."""
    with get_db() as db:
        rows = db.execute("SELECT name, value_enc FROM integration_keys").fetchall()
    n = 0
    for r in rows:
        if r["name"] in BY_NAME:
            try:
                _apply(r["name"], decrypt_secret(r["value_enc"]))
                n += 1
            except Exception:                              # a key sealed under a different vault key cannot be read; leave it unset
                continue
    return n


def status_of(name: str) -> Dict[str, Any]:
    p = BY_NAME[name]
    with get_db() as db:
        row = db.execute("SELECT value_enc, set_by, updated_at FROM integration_keys WHERE name = ?", (name,)).fetchone()
    current = os.environ.get(name, "").strip()
    if row:
        try:
            shown = _mask(p, decrypt_secret(row["value_enc"]))
        except Exception:
            shown = "unreadable (re-enter it)"
        return {"name": name, "label": p.label, "group": p.group, "purpose": p.purpose, "get_url": p.get_url, "cost": p.cost, "secret": p.secret,
                "set": True, "source": "settings", "display": shown, "set_by": row["set_by"], "updated_at": row["updated_at"],
                "testable": name in TESTS}
    return {"name": name, "label": p.label, "group": p.group, "purpose": p.purpose, "get_url": p.get_url, "cost": p.cost, "secret": p.secret,
            "set": bool(current and not current.startswith(("your_", "replace"))), "source": "env" if current else None,
            "display": _mask(p, current) if current else None, "set_by": None, "updated_at": None, "testable": name in TESTS}


def list_status() -> List[Dict[str, Any]]:
    return [status_of(p.name) for p in PROVIDERS]


# ------------------------------------------------------------------ connection tests (cheap, read-only calls to the vendor's own host)

def _result(res_status: int, ok_codes=(200,), bad_codes=(400, 401, 403)) -> Tuple[Optional[bool], str]:
    if res_status in ok_codes:
        return True, "The key works."
    if res_status in bad_codes:
        return False, f"The provider rejected the key (HTTP {res_status})."
    return None, f"The provider answered HTTP {res_status}; try again later."


def _get(url: str, headers: Optional[dict] = None, method: str = "GET", body: Optional[dict] = None) -> int:
    return SafeFetcher.safe_fetch(url, timeout=20, headers=headers, method=method, json_body=body, max_bytes=300_000).status_code


def _t_places(k: str):
    return _result(_get("https://places.googleapis.com/v1/places:searchText", {"X-Goog-Api-Key": k, "X-Goog-FieldMask": "places.id", "Content-Type": "application/json"},
                        "POST", {"textQuery": "cafe in Leeds", "pageSize": 1}))


TESTS: Dict[str, Callable[[str], Tuple[Optional[bool], str]]] = {
    "GOOGLE_PLACES_API_KEY": _t_places,
    "PAGESPEED_API_KEY": lambda k: _result(_get(f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=https%3A%2F%2Fexample.com&strategy=mobile&category=performance&key={k}")),
    "BRAVE_SEARCH_API_KEY": lambda k: _result(_get("https://api.search.brave.com/res/v1/web/search?q=test&count=1", {"X-Subscription-Token": k, "Accept": "application/json"}), bad_codes=(401, 403, 422)),
    "NVD_API_KEY": lambda k: _result(_get("https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1", {"apiKey": k})),
    "GITHUB_TOKEN": lambda k: _result(_get("https://api.github.com/rate_limit", {"Authorization": f"Bearer {k}", "User-Agent": "AgencyBD", "Accept": "application/vnd.github+json"}), bad_codes=(401, 403)),
    "ANTHROPIC_API_KEY": lambda k: _result(_get("https://api.anthropic.com/v1/models", {"x-api-key": k, "anthropic-version": "2023-06-01"})),
}


def test_key(name: str) -> Dict[str, Any]:
    if name not in BY_NAME:
        raise ValueError(f"'{name}' is not a supported integration.")
    value = os.environ.get(name, "").strip()
    if not value:
        return {"ok": False, "message": "No key is set."}
    if name not in TESTS:
        return {"ok": None, "message": "This integration can only be tested by using it (a test call would have side effects or cost money)."}
    try:
        ok, message = TESTS[name](value)
    except Exception as exc:                               # network problems are not a verdict on the key
        return {"ok": None, "message": f"Could not reach the provider: {str(exc)[:80]}"}
    return {"ok": ok, "message": message}
