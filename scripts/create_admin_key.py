#!/usr/bin/env python3
"""
Creates an API key and prints it ONCE. Only its SHA-256 hash is stored.

    python scripts/create_admin_key.py                              # super_admin for org_default
    python scripts/create_admin_key.py --role growth_lead --org org_acme --user jane --name "Jane (Acme)"

Run this on the host or inside the container (`docker compose exec api python scripts/create_admin_key.py`).
There are no default credentials; this is the supported way to obtain the first key.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import init_db, create_api_key_record  # noqa: E402
from security.auth import ROLE_PERMISSIONS  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--role", default="super_admin", choices=sorted(ROLE_PERMISSIONS))
    parser.add_argument("--org", default="org_default")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--name", default="Bootstrap admin key")
    args = parser.parse_args()

    init_db()
    key = create_api_key_record(name=args.name, user_id=args.user, role=args.role, org_id=args.org)
    print(f"role={args.role} org={args.org} user={args.user}")
    print(f"API key (shown once, store it in a password manager): {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
