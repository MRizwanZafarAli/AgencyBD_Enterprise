"""Input validation helpers for values that end up in network calls or subprocess arguments."""

import re

_LABEL = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


def is_valid_hostname(value: str) -> bool:
    """True for a plausible DNS name or IP literal. Rejects spaces, option-like strings ('-x'), and junk."""
    if not value or len(value) > 253 or value.startswith("-"):
        return False
    host = value.rstrip(".")
    if re.fullmatch(r"[0-9.]+", host) or ":" in host:  # IPv4 / IPv6 literal: let ipaddress validate elsewhere
        return bool(re.fullmatch(r"[0-9a-fA-F:.]+", host))
    return all(_LABEL.match(label) for label in host.split("."))


def clean_domain(raw: str) -> str:
    """Strips scheme, path and port from user input and validates the result."""
    value = (raw or "").strip().lower()
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.split("/")[0].split("?")[0].split("#")[0]
    if "@" in value:
        raise ValueError("Credentials in a domain are not allowed.")
    host = value.rsplit(":", 1)[0] if re.search(r":\d+$", value) else value
    if not is_valid_hostname(host):
        raise ValueError(f"Invalid domain: {raw!r}")
    return value
