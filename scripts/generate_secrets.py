#!/usr/bin/env python3
"""
Generates strong random values for the application secrets and writes them to .env.

    python scripts/generate_secrets.py            # fill placeholders / missing values only
    python scripts/generate_secrets.py --rotate   # replace ALL three secrets (invalidates sessions, signatures)

Values are never printed. Creates .env from .env.example if it does not exist (mode 600).
"""

import argparse
import os
import re
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.env import KNOWN_COMPROMISED_SECRETS, MIN_SECRET_LENGTH  # noqa: E402

SECRET_NAMES = ["AGENCYBD_JWT_SECRET", "AGENCYBD_WEBHOOK_SECRET", "AGENCYBD_HMAC_VAULT_KEY"]
PLACEHOLDER_PREFIXES = ("replace", "change", "your", "example", "todo")


def needs_value(current: str) -> bool:
    current = current.strip()
    return (
        not current
        or current in KNOWN_COMPROMISED_SECRETS
        or current.lower().startswith(PLACEHOLDER_PREFIXES)
        or len(current) < MIN_SECRET_LENGTH
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rotate", action="store_true", help="replace secrets that are already set")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if not env_path.exists():
        example = ROOT / ".env.example"
        if example.exists():
            shutil.copyfile(example, env_path)
        else:
            env_path.write_text("")
    os.chmod(env_path, 0o600)

    lines = env_path.read_text().splitlines()
    present = {}
    for idx, line in enumerate(lines):
        m = re.match(r"\s*([A-Z0-9_]+)\s*=(.*)$", line)
        if m and m.group(1) in SECRET_NAMES:
            present[m.group(1)] = (idx, m.group(2))

    changed = []
    for name in SECRET_NAMES:
        new_value = secrets.token_urlsafe(48)
        if name in present:
            idx, current = present[name]
            if args.rotate or needs_value(current):
                lines[idx] = f"{name}={new_value}"
                changed.append(name)
        else:
            lines.append(f"{name}={new_value}")
            changed.append(name)

    env_path.write_text("\n".join(lines) + "\n")
    os.chmod(env_path, 0o600)

    if changed:
        print(f"Wrote {len(changed)} secret(s) to {env_path}: {', '.join(changed)}")
    else:
        print("All secrets already set; nothing changed (use --rotate to replace them).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
