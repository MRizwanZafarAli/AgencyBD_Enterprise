"""
Base connector framework for opportunity sources.

A connector only fetches and normalises. It never scores (radar/fit.py does that from the agency's own profile) and it
never swallows errors: failures are raised so the radar can record them in connector_runs and show them to the user.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ConnectorNotConfigured(RuntimeError):
    """Credentials or setup are missing (not an error in the source itself)."""


@dataclass
class OpportunityItem:
    """Normalized opportunity model across all platforms and sources."""
    type: str                     # marketplace | tender | hiring_signal | outbound | inbound
    source: str                   # upwork | freelancer | remoteok | wwr | hn | sam_gov | ted | uk_fts
    external_id: str
    title: str
    description: str
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: str = "USD"
    url: Optional[str] = None
    posted_at: Optional[str] = None
    deadline: Optional[str] = None
    skills_required: List[str] = field(default_factory=list)
    fit_score: Optional[float] = None
    risk_flags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


class BaseConnector(ABC):
    source_name: str = "base"
    terms_url: str = ""
    automation_level: str = "L0"       # L0 = ingest only; L1 = AI drafts, human submits
    rate_limit_per_minute: int = 30
    requires_api_key: bool = False
    max_fetch: int = 100               # how many items to read per scan (the radar keeps the best few)

    @abstractmethod
    def fetch(self, query: Optional[str] = None, limit: int = 20, org_id: Optional[str] = None) -> List[OpportunityItem]:
        """Returns normalised items. Raise ConnectorNotConfigured when set-up is missing; let other errors propagate."""

    def check_health(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        return {"source": self.source_name, "terms_url": self.terms_url, "automation_level": self.automation_level,
                "requires_api_key": self.requires_api_key}
