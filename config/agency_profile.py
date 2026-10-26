"""
Agency identity managed from Settings.

Who the agency is (name, sender, booking link, website, services), the legal details every commercial email must carry (postal address and the
public address unsubscribe links point to) and the one result you are willing to quote to prospects. Previously all of this lived only in .env,
so none of it could be fixed from the app.

How it takes effect (same pattern as integration keys): a value saved here is applied to the live settings object and to the environment
variable the rest of the app reads, immediately and again at startup. A saved value overrides .env; "reset" deletes it and restores .env.
It is shared by this whole installation, so only a super-admin may change it.

Honesty rule: the result quoted to prospects is sent verbatim in outreach, so it cannot be saved without a note saying where it is proven, and
clearing that note withdraws the result.
"""

import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from compliance.content_guard import check_outreach_text
from config.settings import settings
from database.db import get_db


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    group: str
    help: str
    env: Optional[str] = None          # environment variable the rest of the app reads
    attr: Optional[str] = None         # attribute on settings.agency
    required: bool = False             # may not be saved blank (reset to .env instead)
    needed_to_send: bool = False       # required before any commercial email may be sent
    multiline: bool = False
    placeholder: str = ""


FIELDS: List[Field] = [
    Field("name", "Agency name", "Identity", "Shown in emails, reports and proposals.", "AGENCYBD_SENDER_COMPANY", "name", required=True, placeholder="Acme Web Studio"),
    Field("sender_name", "Sender name", "Identity", "Who emails and replies are signed by.", "AGENCYBD_SENDER_NAME", "founder_name", required=True, placeholder="Sam Rivera"),
    Field("sender_title", "Sender title", "Identity", "Optional, for example Founder.", "AGENCYBD_SENDER_TITLE", "founder_title", placeholder="Founder"),
    Field("tagline", "Tagline", "Identity", "One line about what you do. Optional.", "AGENCYBD_AGENCY_TAGLINE", "tagline", placeholder="Fast, accessible websites for local businesses"),
    Field("primary_domain", "Agency website", "Identity", "Your own domain, without https://.", "AGENCYBD_AGENCY_DOMAIN", "primary_domain", placeholder="acmeweb.studio"),
    Field("booking_link", "Booking link", "Identity", "Where a prospect books a call. Optional.", "AGENCYBD_BOOKING_LINK", "booking_link", placeholder="https://cal.com/you/intro"),
    Field("core_services", "Core services", "Identity", "Comma separated, up to 12. Used so proposals only offer what you do.", "AGENCYBD_CORE_SERVICES", "core_services", placeholder="Web design, SEO, Accessibility audits"),
    Field("sender_address", "Postal address", "Legal footer", "A real postal address. Commercial email must carry one (CAN-SPAM), so nothing can be sent without it.",
          "AGENCYBD_SENDER_ADDRESS", needed_to_send=True, multiline=True, placeholder="12 High Street, Leeds LS1 4AB, United Kingdom"),
    Field("public_base_url", "Public address of this app", "Legal footer", "Where unsubscribe links point. Must be reachable by recipients, so it cannot be localhost in production.",
          "AGENCYBD_PUBLIC_BASE_URL", needed_to_send=True, placeholder="https://bd.acmeweb.studio"),
    Field("case_study_metric", "Result you quote", "Proof", "One sentence about a result, sent to prospects word for word. Leave empty unless you can prove it.",
          "AGENCYBD_CASE_STUDY", "case_study_metric", placeholder="Cut page load from 4.1 s to 1.3 s for Brightside Dental"),
    Field("case_study_proof", "Where it is proven", "Proof", "A link or a note that shows the result is real (a case study page, a signed testimonial). Required to quote a result.", placeholder="https://acmeweb.studio/work/brightside"),
]
BY_KEY = {f.key: f for f in FIELDS}
_original_env: Dict[str, Optional[str]] = {}
_original_attr: Dict[str, Any] = {}


def _clean_text(v: Any, label: str, lo: int, hi: int, multiline: bool = False) -> str:
    v = (v or "").strip() if isinstance(v, str) or v is None else str(v).strip()
    if not multiline and ("\n" in v or "\r" in v):
        raise ValueError(f"{label} must be a single line.")
    v = re.sub(r"[ \t]+", " ", v)
    if len(v) < lo:
        raise ValueError(f"{label} is required." if lo else f"{label} is too short.")
    if len(v) > hi:
        raise ValueError(f"{label} is too long (max {hi} characters).")
    return v


def _url(v: str, label: str, https_only: bool = False) -> str:
    p = urlparse(v if "://" in v else f"https://{v}")
    host = p.hostname or ""
    local = host in ("localhost", "127.0.0.1") or host.endswith(".localhost")
    if p.scheme not in ("http", "https") or "." not in host and not local:
        raise ValueError(f"{label} must be a web address such as https://example.com")
    if https_only and p.scheme != "https" and not local:
        raise ValueError(f"{label} must start with https://")
    return (v if "://" in v else f"https://{v}").rstrip("/")


def validate(key: str, value: Any, stored: Optional[Dict[str, str]] = None) -> str:
    f = BY_KEY.get(key)
    if not f:
        raise ValueError(f"'{key}' is not a profile field.")
    stored = stored if stored is not None else _stored()
    blank = value is None or (isinstance(value, str) and not value.strip())
    if blank:
        if f.required:
            raise ValueError(f"{f.label} cannot be blank. Use Reset to go back to the value in .env.")
        return ""
    if key == "name":
        return _clean_text(value, f.label, 2, 80)
    if key == "sender_name":
        return _clean_text(value, f.label, 2, 60)
    if key in ("sender_title", "tagline"):
        text = _clean_text(value, f.label, 0, 60 if key == "sender_title" else 120)
        reason = check_outreach_text("", text) if key == "tagline" else None
        if reason:
            raise ValueError(reason)
        return text
    if key == "primary_domain":
        host = urlparse(value if "://" in value else f"https://{value}").hostname or ""
        if "." not in host or not re.fullmatch(r"[a-z0-9.-]+", host.lower()):
            raise ValueError("Agency website must be a domain such as acmeweb.studio")
        return host.lower().removeprefix("www.")
    if key == "booking_link":
        return _url(_clean_text(value, f.label, 0, 300), f.label)
    if key == "core_services":
        items = [s.strip() for s in re.split(r"[,\n]", str(value)) if s.strip()]
        items = list(dict.fromkeys(items))
        if len(items) > 12 or any(len(s) > 40 for s in items):
            raise ValueError("Core services: up to 12 items, each at most 40 characters.")
        return ", ".join(items)
    if key == "sender_address":
        text = _clean_text(value, f.label, 10, 200, multiline=True)
        if not re.search(r"\d", text) or not re.search(r"[A-Za-z]", text):
            raise ValueError("Postal address must include a street number and a place name.")
        return text
    if key == "public_base_url":
        return _url(_clean_text(value, f.label, 0, 200), f.label, https_only=True)
    if key == "case_study_metric":
        text = _clean_text(value, f.label, 0, 200)
        if reason := check_outreach_text("", text):
            raise ValueError(reason)
        if len((stored.get("case_study_proof") or "").strip()) < 8:
            raise ValueError("Say where this result is proven first (the proof field). It is sent to prospects word for word.")
        return text
    if key == "case_study_proof":
        return _clean_text(value, f.label, 8, 300)
    raise ValueError(f"'{key}' cannot be edited.")


def _stored() -> Dict[str, str]:
    with get_db() as db:
        return {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM agency_profile").fetchall()}


def _apply(key: str, value: str, stored: Dict[str, str]) -> None:
    f = BY_KEY[key]
    if key == "case_study_metric" and len((stored.get("case_study_proof") or "").strip()) < 8:
        value = ""                                           # no proof on file: the result is not quoted
    if f.attr:
        if key not in _original_attr:
            _original_attr[key] = getattr(settings.agency, f.attr)
        setattr(settings.agency, f.attr, [s.strip() for s in value.split(",") if s.strip()] if key == "core_services" else value)
    if f.env:
        if key not in _original_env:
            _original_env[key] = os.environ.get(f.env)
        os.environ[f.env] = value


def _restore(key: str) -> None:
    f = BY_KEY[key]
    if key in _original_attr and f.attr:
        setattr(settings.agency, f.attr, _original_attr.pop(key))
    if key in _original_env and f.env:
        previous = _original_env.pop(key)
        if previous is None:
            os.environ.pop(f.env, None)
        else:
            os.environ[f.env] = previous


def set_field(key: str, value: Any, user: str) -> Dict[str, Any]:
    stored = _stored()
    value = validate(key, value, stored)
    with get_db() as db:
        db.execute("INSERT INTO agency_profile (key, value, set_by, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
                   "ON CONFLICT(key) DO UPDATE SET value = excluded.value, set_by = excluded.set_by, updated_at = CURRENT_TIMESTAMP", (key, value, user))
        db.commit()
    stored[key] = value
    if key == "case_study_proof":                              # the proof gates the quoted result: re-evaluate it
        if "case_study_metric" in stored:
            _apply("case_study_metric", stored["case_study_metric"], stored)
    else:
        _apply(key, value, stored)
    return field_status(key)


def reset_field(key: str) -> bool:
    """Delete the saved value and go back to what .env says."""
    if key not in BY_KEY:
        raise ValueError(f"'{key}' is not a profile field.")
    with get_db() as db:
        removed = db.execute("DELETE FROM agency_profile WHERE key = ?", (key,)).rowcount
        db.commit()
    if key == "case_study_proof":
        stored = _stored()
        if "case_study_metric" in stored:
            _apply("case_study_metric", stored["case_study_metric"], stored)       # no proof now, so it stops being quoted
    else:
        _restore(key)
    return removed > 0


def apply_all() -> int:
    stored = _stored()
    n = 0
    for key, value in stored.items():
        if key in BY_KEY and key != "case_study_proof":
            _apply(key, value, stored)
            n += 1
    return n


def _current(f: Field) -> str:
    if f.attr:
        v = getattr(settings.agency, f.attr)
        return ", ".join(v) if isinstance(v, list) else (v or "")
    if f.env:
        return os.environ.get(f.env, "") or ""
    return _stored().get(f.key, "")


def field_status(key: str, stored: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    f = BY_KEY[key]
    stored = stored if stored is not None else _stored()
    value = _current(f) if f.key != "case_study_proof" else stored.get("case_study_proof", "")
    placeholder_default = value in ("Our Agency", "The team") or value.startswith("your_")
    in_db = key in stored
    from_env = bool(f.env and (_original_env.get(key, os.environ.get(f.env)) or "").strip()) if not in_db else False
    source = "settings" if in_db else ("env" if from_env else "default")
    warning = None
    if key == "case_study_metric" and value and not (stored.get("case_study_proof") or "").strip():
        warning = "This result has no proof on file. It is quoted to prospects word for word, so keep it only if you can show it is true."
    return {"key": key, "label": f.label, "group": f.group, "help": f.help, "value": "" if placeholder_default else value, "set": bool(value) and not placeholder_default,
            "source": source, "env": f.env, "needed_to_send": f.needed_to_send, "required": f.required, "multiline": f.multiline, "placeholder": f.placeholder, "warning": warning}


def list_status() -> List[Dict[str, Any]]:
    stored = _stored()
    return [field_status(f.key, stored) for f in FIELDS]
