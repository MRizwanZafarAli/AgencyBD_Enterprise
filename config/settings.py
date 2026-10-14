"""
Global Configuration and Settings for AgencyBD_Enterprise.
Defines agency positioning, outreach guardrails, and operational thresholds.
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field

from config.env import BASE_DIR, environment

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# DB_PATH may be overridden (containers, tests); relative paths resolve from the project root.
_db_override = os.getenv("DB_PATH")
if _db_override:
    DB_PATH = Path(_db_override)
    if not DB_PATH.is_absolute():
        DB_PATH = BASE_DIR / DB_PATH
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
else:
    DB_PATH = DATA_DIR / "agency_bd.db"

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class AgencyProfile(BaseModel):
    """Who the agency is. Everything comes from the environment; nothing is invented."""
    name: str = Field(default_factory=lambda: _env("AGENCYBD_SENDER_COMPANY", "Our Agency"))
    tagline: str = Field(default_factory=lambda: _env("AGENCYBD_AGENCY_TAGLINE"))
    founder_name: str = Field(default_factory=lambda: _env("AGENCYBD_SENDER_NAME", "The team"))
    founder_title: str = Field(default_factory=lambda: _env("AGENCYBD_SENDER_TITLE"))
    booking_link: str = Field(default_factory=lambda: _env("AGENCYBD_BOOKING_LINK"))
    primary_domain: str = Field(default_factory=lambda: _env("AGENCYBD_AGENCY_DOMAIN"))
    # Only set this to a result you can prove; it is quoted to prospects verbatim.
    case_study_metric: str = Field(default_factory=lambda: _env("AGENCYBD_CASE_STUDY"))
    core_services: list[str] = Field(default_factory=lambda: [
        s.strip() for s in os.getenv("AGENCYBD_CORE_SERVICES", "").split(",") if s.strip()])

class ThresholdSettings(BaseModel):
    max_emails_per_inbox_daily: int = 35
    warmup_min_delay_seconds: int = 180
    warmup_max_delay_seconds: int = 420
    lcp_critical_threshold_ms: int = 2500
    ttfb_critical_threshold_ms: int = 800
    spam_score_max_allowed: float = 2.5
    min_email_deliverability_score: float = 0.85

class Settings(BaseModel):
    agency: AgencyProfile = Field(default_factory=AgencyProfile)
    thresholds: ThresholdSettings = Field(default_factory=ThresholdSettings)
    db_url: str = f"sqlite:///{DB_PATH}"
    environment: str = environment()
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

settings = Settings()

def get_settings() -> Settings:
    return settings

