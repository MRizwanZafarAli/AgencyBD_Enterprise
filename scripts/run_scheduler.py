#!/usr/bin/env python3
"""Standalone sequence worker: `python scripts/run_scheduler.py` (or `--once`). Use instead of AGENCYBD_SCHEDULER=on
when you want the scheduler in its own process/container."""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import init_db  # noqa: E402
from workflows.scheduler import SequenceScheduler  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    init_db()
    while True:
        outcomes = SequenceScheduler.run_due()
        logging.info("processed %d enrollment(s)", len(outcomes))
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
