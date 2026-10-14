"""
Enterprise Structured JSON Logger.
Formats all application events into standardized JSON objects for ELK/Datadog/CloudWatch ingestion.
"""

import sys
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "AgencyBD_Enterprise",
        }
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id
        if hasattr(record, "org_id"):
            log_entry["org_id"] = record.org_id
        if hasattr(record, "event"):
            log_entry["event"] = record.event
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry.update(record.extra_data)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def get_enterprise_logger(name: str = "AgencyBD") -> logging.Logger:
    """Configures and returns a structured JSON logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = get_enterprise_logger()
