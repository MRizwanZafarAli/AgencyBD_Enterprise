"""Background loop that re-runs saved searches when they are due. Safe to run in the API process or as its own worker."""

import logging
import threading
from typing import Optional

from leadfinder import engine

logger = logging.getLogger("AgencyBD.leadfinder")


class LeadWorker(threading.Thread):
    def __init__(self, interval: int = 300):
        super().__init__(daemon=True, name="lead-finder")
        self.interval = interval
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        while not self._halt.wait(self.interval):
            try:
                engine.cycle()
            except Exception:
                logger.exception("lead finder cycle failed")      # never let one bad pass end the loop
            try:
                from workflows import rescan
                rescan.run_if_due()                               # at most once a day; also done by the scheduler when that is on
            except Exception:
                logger.exception("nightly re-check failed")


_worker: Optional[LeadWorker] = None


def start() -> LeadWorker:
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = LeadWorker()
        _worker.start()
    return _worker


def stop() -> None:
    if _worker:
        _worker.stop()
