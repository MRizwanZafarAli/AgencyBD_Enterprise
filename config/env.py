"""
Environment loading and secret management for AgencyBD_Enterprise.

Single source of truth for:
  * loading ``.env`` (without overriding variables already set in the process)
  * the runtime environment name (development / test / production)
  * fetching secrets with strict validation

Behaviour by environment
  production   a missing, short, placeholder or known-leaked secret aborts startup.
  development  a missing secret is replaced by a random per-process value and a warning
  / test       is logged. Tokens signed with it stop working after a restart, which is
               the safe failure mode. Run ``python scripts/generate_secrets.py`` to
               persist real values into ``.env``.
"""

import logging
import os
import secrets as _secrets
from pathlib import Path
from typing import Dict, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
_log = logging.getLogger("AgencyBD.config")

MIN_SECRET_LENGTH = 32

# Values that previously shipped in source control or in the example env file.
# They are public knowledge, so they are rejected everywhere, in every environment.
KNOWN_COMPROMISED_SECRETS = frozenset({
    "super-secret-enterprise-jwt-key-change-in-prod-999",
    "super-secret-enterprise-jwt-key-prod-999",
    "agy_enterprise_webhook_secret_998811",
    "apexcore_enterprise_secret_vault_seed_98234710239",
})
_PLACEHOLDER_PREFIXES = ("replace", "change", "changeme", "your_", "your-", "example", "todo")


def _parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        elif val.startswith("#"):
            val = ""
        elif " #" in val:
            val = val.split(" #", 1)[0].rstrip()
        values[key] = val
    return values


def load_env_file(path: Optional[Path] = None) -> None:
    """Loads KEY=VALUE pairs from ``.env``. Variables already in the process win."""
    for key, val in _parse_env_file(path or (BASE_DIR / ".env")).items():
        os.environ.setdefault(key, val)


if not os.getenv("AGENCYBD_SKIP_DOTENV"):
    load_env_file()


def environment() -> str:
    """Returns 'production', 'test' or 'development'."""
    raw = (os.getenv("AGENCYBD_ENV") or os.getenv("APP_ENV") or "development").strip().lower()
    if raw in ("prod", "production"):
        return "production"
    if raw == "test":
        return "test"
    return "development"


def is_production() -> bool:
    return environment() == "production"


class SecretConfigError(RuntimeError):
    """Raised when a required secret is missing or unsafe in production."""


def _problem_with(value: str, min_length: int) -> Optional[str]:
    if value in KNOWN_COMPROMISED_SECRETS:
        return "is a value that was published in source control"
    if value.lower().startswith(_PLACEHOLDER_PREFIXES):
        return "is still a placeholder"
    if len(value) < min_length:
        return f"is shorter than {min_length} characters"
    return None


_ephemeral: Dict[str, str] = {}


def get_secret(name: str, *aliases: str, min_length: int = MIN_SECRET_LENGTH) -> str:
    """
    Returns the secret stored in env var ``name`` (or one of ``aliases``).

    Known-compromised values are rejected in every environment. Production also rejects
    missing, placeholder and short values. Elsewhere a missing or placeholder value is
    replaced with a random per-process secret.
    """
    for candidate in (name, *aliases):
        value = (os.getenv(candidate) or "").strip()
        if not value:
            continue
        problem = _problem_with(value, min_length)
        if problem is None:
            return value
        if is_production() or value in KNOWN_COMPROMISED_SECRETS:
            raise SecretConfigError(f"{candidate} {problem}. Run `python scripts/generate_secrets.py`.")
        _log.warning("%s %s; using an ephemeral development secret instead.", candidate, problem)
        break
    else:
        if is_production():
            raise SecretConfigError(
                f"{name} is not set. Refusing to start in production. "
                "Run `python scripts/generate_secrets.py` or inject it from your secret manager."
            )
        _log.warning("%s is not set; using an ephemeral development secret.", name)

    if name not in _ephemeral:
        _ephemeral[name] = _secrets.token_urlsafe(48)
    return _ephemeral[name]


def get_list(name: str, default: str = "") -> list:
    """Parses a comma-separated env var into a clean list."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]
