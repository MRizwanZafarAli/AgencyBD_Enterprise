#!/usr/bin/env python3
"""
Sets the secret password of each tier. Only a salted hash is stored; the password cannot be read back, only replaced.

    python scripts/set_passwords.py                        # asks for every tier, typing is hidden
    python scripts/set_passwords.py --role auditor         # only one tier
    python scripts/set_passwords.py --generate             # makes strong random passwords and shows them ONCE
    python scripts/set_passwords.py --generate --out FILE  # writes them to FILE (owner-only) instead of the screen

Run it on the host, or inside the container: `docker compose exec api python scripts/set_passwords.py`.
Every tier needs a different password. Changing a tier's password signs out everyone in that tier.
There are no default passwords: until you run this, nobody can sign in.
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import init_db  # noqa: E402
from security import passwords  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--role", choices=passwords.TIER_ORDER, help="only this tier (default: all four)")
    ap.add_argument("--generate", action="store_true", help="create strong random passwords instead of asking")
    ap.add_argument("--out", help="with --generate: write the passwords to this file (mode 600) instead of printing them")
    args = ap.parse_args()
    init_db()
    roles = [args.role] if args.role else passwords.TIER_ORDER
    made = {}
    for role in roles:
        label = passwords.TIER_LABEL[role]
        if args.generate:
            pw = passwords.generate()
        else:
            while True:
                pw = getpass.getpass(f"New password for {label} ({role}): ")
                if pw != getpass.getpass("Type it again: "):
                    print("  They did not match. Try again.")
                    continue
                try:
                    passwords.check_policy(pw, role)
                except ValueError as exc:
                    print(f"  {exc}")
                    continue
                break
        try:
            passwords.set_password(role, pw, by="set_passwords.py")
        except ValueError as exc:
            print(f"{label}: {exc}", file=sys.stderr)
            return 1
        made[role] = pw
        print(f"  {label}: password set")
    if args.generate:
        if args.out:
            fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(made, f, indent=2)
            print(f"Passwords written to {args.out} (readable only by you). Move them to a password manager, then delete the file.")
        else:
            print("\nShown once. Store them in a password manager:")
            for role, pw in made.items():
                print(f"  {passwords.TIER_LABEL[role]:<12} {pw}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
