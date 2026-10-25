"""Restore the database from a backup made by scripts/backup_db.py.

    python scripts/restore_db.py data/backups/agency_bd-<stamp>.db [--yes]

Safety: the backup is integrity-checked first, the current database is copied aside (never deleted), and the app must be stopped.
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH  # noqa: E402


def restore(backup: Path, target: Path) -> Path:
    check = sqlite3.connect(f"file:{backup}?mode=ro", uri=True)
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
        tables = check.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
    finally:
        check.close()
    if result != "ok" or tables == 0:
        raise RuntimeError(f"backup is not usable (integrity: {result}, tables: {tables})")
    aside = target.with_name(f"{target.stem}.before-restore-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}{target.suffix}")
    if target.exists():
        shutil.copy2(target, aside)
    for suffix in ("-wal", "-shm"):                      # stale WAL files would be replayed over the restored data
        Path(str(target) + suffix).unlink(missing_ok=True)
    shutil.copy2(backup, target)
    return aside


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("backup")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    args = ap.parse_args()
    if not args.yes and input(f"Replace {DB_PATH} with {args.backup}? The API must be stopped. Type 'restore' to continue: ") != "restore":
        return 1
    try:
        aside = restore(Path(args.backup), Path(DB_PATH))
    except Exception as exc:  # noqa: BLE001
        print(f"restore failed: {exc}", file=sys.stderr)
        return 1
    print(f"restored. previous database kept at {aside}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
