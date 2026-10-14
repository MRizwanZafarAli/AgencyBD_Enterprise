"""Post the daily digest to Slack (cron it: `0 8 * * * python scripts/send_digest.py [org_id]`)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import init_db  # noqa: E402
from workflows.digest import build_digest, send_to_slack  # noqa: E402

if __name__ == "__main__":
    init_db()
    digest = build_digest(sys.argv[1] if len(sys.argv) > 1 else "org_default")
    print(digest["text"])
    sys.exit(0 if send_to_slack(digest["text"]) else 1)
