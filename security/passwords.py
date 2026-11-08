"""
Tier passwords: the only way into the app.

Each tier (role) has its own secret password. Only a salted PBKDF2-HMAC-SHA256 hash is stored (table ``access_passwords``), never the password.
Rules that protect the secrets:

  * every tier's password must be different from every other tier's, so a leaked low-tier password never opens a higher tier
  * length and mix are checked, and obvious choices are refused
  * checking a password does the same work whether or not the tier has one set, so timing does not reveal which tiers exist
  * 5 wrong tries from one address lock that address out for 15 minutes (and 100 across all addresses slow everyone down, which still caps online guessing at under 10,000 a day)
  * changing a tier's password ends every session of that tier that started earlier
  * a password never appears in a response, a log line or an error message
"""

import hashlib
import hmac
import os
import re
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from database.db import get_db
from security.auth import DEFAULT_ORG_ID, ROLE_PERMISSIONS

TIER_ORDER = ["super_admin", "growth_lead", "sdr_rep", "auditor"]
TIER_LABEL = {"super_admin": "Super admin", "growth_lead": "Growth lead", "sdr_rep": "Sales rep", "auditor": "Auditor"}
MIN_LENGTH, MAX_LENGTH = 12, 128
FAILS_PER_IP, FAILS_GLOBAL, WINDOW_SECONDS = 5, 100, 15 * 60
_COMMON_WORDS = ("password", "passw0rd", "qwerty", "123456", "letmein", "welcome", "changeme", "iloveyou", "admin1234", "abc123")
_DUMMY_SALT = "0" * 32


def _iterations() -> int:
    return 2_000 if os.getenv("AGENCYBD_ENV") == "test" else 600_000       # tests stay fast; real installs use the recommended work factor


def _hash(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()


def org_id() -> str:
    return (os.getenv("AGENCYBD_LOGIN_ORG") or DEFAULT_ORG_ID).strip() or DEFAULT_ORG_ID


def generate() -> str:
    """A strong random password for a tier: 20 characters from an unambiguous alphabet."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789-_"
    return "".join(secrets.choice(alphabet) for _ in range(20))


def check_policy(password: Any, role: str) -> None:
    """Raises ValueError with a sentence a person can act on."""
    if not isinstance(password, str) or not password.strip():
        raise ValueError("Type a password.")
    if len(password) < MIN_LENGTH:
        raise ValueError(f"Use at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        raise ValueError(f"Use at most {MAX_LENGTH} characters.")
    if password != password.strip():
        raise ValueError("Remove the spaces at the start or end.")
    if len(set(password)) < 5:
        raise ValueError("That password repeats too much. Mix different characters.")
    classes = sum(bool(re.search(p, password)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if len(password) < 16 and classes < 3:
        raise ValueError("Use at least 16 characters, or mix upper case, lower case, numbers and symbols.")
    low = password.lower()
    squashed = re.sub(r"[^a-z0-9]", "", low)
    if any(w in squashed for w in _COMMON_WORDS) or role.replace("_", "") in squashed or "agencybd" in squashed:
        raise ValueError("That is too easy to guess. Avoid common words, the tier name and the product name.")


def _row(db, org: str, role: str):
    return db.execute("SELECT * FROM access_passwords WHERE org_id = ? AND role = ?", (org, role)).fetchone()


def is_set(role: str, org: Optional[str] = None) -> bool:
    with get_db() as db:
        return _row(db, org or org_id(), role) is not None


def updated_at(role: str, org: str) -> Optional[float]:
    with get_db() as db:
        r = _row(db, org, role)
    return float(r["updated_at"]) if r else None


def status(org: Optional[str] = None) -> List[Dict[str, Any]]:
    org = org or org_id()
    with get_db() as db:
        rows = {r["role"]: r for r in db.execute("SELECT role, updated_at, updated_by FROM access_passwords WHERE org_id = ?", (org,))}
    return [{"role": r, "label": TIER_LABEL[r], "is_set": r in rows, "updated_at": rows[r]["updated_at"] if r in rows else None,
             "updated_by": rows[r]["updated_by"] if r in rows else None} for r in TIER_ORDER]


def set_password(role: str, password: str, by: str, org: Optional[str] = None) -> None:
    """Sets or replaces a tier's password. Refuses a weak password and one already used by another tier."""
    org = org or org_id()
    if role not in ROLE_PERMISSIONS:
        raise ValueError("Unknown tier.")
    check_policy(password, role)
    with get_db() as db:
        for other in db.execute("SELECT * FROM access_passwords WHERE org_id = ? AND role != ?", (org, role)).fetchall():
            if hmac.compare_digest(_hash(password, other["salt"], other["iterations"]), other["pw_hash"]):
                raise ValueError("Another tier already uses this password. Every tier needs its own.")
        salt, n = secrets.token_hex(16), _iterations()
        db.execute("""INSERT INTO access_passwords (org_id, role, pw_hash, salt, iterations, updated_at, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?)
                      ON CONFLICT(org_id, role) DO UPDATE SET pw_hash = excluded.pw_hash, salt = excluded.salt, iterations = excluded.iterations,
                      updated_at = excluded.updated_at, updated_by = excluded.updated_by""", (org, role, _hash(password, salt, n), salt, n, time.time(), by[:80]))
        db.commit()


def verify(role: str, password: str, org: Optional[str] = None) -> bool:
    """True only for the right password of that tier. Does the same work whether or not the tier has a password."""
    org = org or org_id()
    with get_db() as db:
        r = _row(db, org, role) if role in ROLE_PERMISSIONS else None
    salt, n, stored = (r["salt"], r["iterations"], r["pw_hash"]) if r else (_DUMMY_SALT, _iterations(), "0" * 64)
    ok = hmac.compare_digest(_hash(password or "", salt, n), stored)
    return bool(ok and r)


# ------------------------------------------------------------------ lockout

def retry_after(ip: str, now: Optional[float] = None) -> int:
    """Seconds until this address may try again, or 0."""
    now = now or time.time()
    since = now - WINDOW_SECONDS
    with get_db() as db:
        mine = [r[0] for r in db.execute("SELECT at FROM login_attempts WHERE ip = ? AND ok = 0 AND at > ? ORDER BY at", (ip, since))]
        total = [r[0] for r in db.execute("SELECT at FROM login_attempts WHERE ok = 0 AND at > ? ORDER BY at", (since,))]
    waits = []
    if len(mine) >= FAILS_PER_IP:                                   # wait until the oldest of the last few mistakes leaves the window
        waits.append(int(mine[-FAILS_PER_IP] + WINDOW_SECONDS - now) + 1)
    if len(total) >= FAILS_GLOBAL:
        waits.append(int(total[-FAILS_GLOBAL] + WINDOW_SECONDS - now) + 1)
    return max(waits, default=0)


def record(ip: str, role: Optional[str], ok: bool, now: Optional[float] = None) -> None:
    now = now or time.time()
    with get_db() as db:
        db.execute("INSERT INTO login_attempts (ip, role, ok, at) VALUES (?, ?, ?, ?)", (ip[:64], (role or "")[:32], int(ok), now))
        db.execute("DELETE FROM login_attempts WHERE at < ?", (now - 86400,))
        if ok:                                                   # a good sign-in clears that address's failures
            db.execute("DELETE FROM login_attempts WHERE ip = ? AND ok = 0", (ip[:64],))
        db.commit()
