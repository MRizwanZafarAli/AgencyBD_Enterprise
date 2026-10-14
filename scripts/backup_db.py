"""Online SQLite backup with integrity check and rotation.

    python scripts/backup_db.py [--dest data/backups] [--keep 14]

Uses SQLite's backup API, so it is safe while the API and scheduler are running.
Exit code 1 if the copy fails its integrity check.
"""
import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH, DATA_DIR  # noqa: E402


def backup(src: Path, dest_dir: Path, keep: int = 14) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = dest_dir / f"agency_bd-{stamp}.db"
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        copy = sqlite3.connect(target)
        try:
            source.backup(copy)
            result = copy.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            copy.close()
    finally:
        source.close()
    if result != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError(f"backup failed integrity check: {result}")
    target.chmod(0o600)
    for old in sorted(dest_dir.glob("agency_bd-*.db"))[:-keep]:
        old.unlink()
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(DATA_DIR / "backups"))
    ap.add_argument("--keep", type=int, default=14)
    args = ap.parse_args()
    try:
        print(backup(Path(DB_PATH), Path(args.dest), args.keep))
    except Exception as exc:  # noqa: BLE001
        print(f"backup failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
