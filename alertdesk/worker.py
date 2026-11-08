"""Background loop that runs the Alert Desk for every workspace that switched it on. Safe to run in the API process or as its own worker."""

import logging
import threading
from typing import Optional

from alertdesk import engine
from database.db import get_db

logger = logging.getLogger("AgencyBD.alertdesk")


def enabled_orgs() -> list:
    with get_db() as db:
        rows = db.execute("SELECT org_id, data_json FROM alert_settings").fetchall()
    import json
    return [r["org_id"] for r in rows if json.loads(r["data_json"]).get("enabled")]


class AlertWorker(threading.Thread):
    def __init__(self, interval: int = 30):
        super().__init__(daemon=True, name="alert-desk")
        self.interval = interval
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        while not self._halt.wait(self.interval):
            try:
                for org in enabled_orgs():
                    engine.cycle(org)
            except Exception:
                logger.exception("alert desk cycle failed")        # never let one bad pass end the loop


_worker: Optional[AlertWorker] = None


def start() -> AlertWorker:
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = AlertWorker()
        _worker.start()
    return _worker


def stop() -> None:
    if _worker:
        _worker.stop()
