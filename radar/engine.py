"""
Opportunity Radar.

For every source: fetch -> score against the agency's own profile -> keep the best N -> record the outcome.
Failures are never swallowed: each scan writes a row per source to `connector_runs` (ok | empty | error | not_configured |
not_connected) with the reason, and /api/radar/sources shows it.
"""

import logging
from typing import Any, Dict, List, Optional


from connectors.base import BaseConnector, ConnectorNotConfigured, OpportunityItem
from connectors.hn import HackerNewsConnector
from connectors.github_bounties import GitHubBountyConnector
from connectors.reddit import RedditConnector
from connectors.remoteok import RemoteOKConnector
from connectors.sam_gov import SamGovConnector
from connectors.ted import TedConnector
from connectors.uk_fts import UkFindATenderConnector
from connectors.upwork import UpworkConnector
from connectors.wwr import WeWorkRemotelyConnector
from database.db import get_db
from database.models import OpportunityRepository
from radar.fit import agency_profile_terms, score_opportunity

logger = logging.getLogger("AgencyBD.radar")

UPWORK_CACHE_HOURS = 24  # Upwork API terms: do not cache API data longer than this


def default_connectors() -> List[BaseConnector]:
    return [UpworkConnector(), HackerNewsConnector(), RemoteOKConnector(), WeWorkRemotelyConnector(), TedConnector(),
            UkFindATenderConnector(), SamGovConnector(), RedditConnector(), GitHubBountyConnector()]


def purge_expired(org_id: str) -> int:
    """Deletes undecided Upwork rows older than the permitted cache window."""
    with get_db() as db:
        cur = db.execute("DELETE FROM opportunities WHERE org_id = ? AND source = 'upwork' AND status = 'discovered' "
                         "AND created_at < datetime('now', ?)", (org_id, f"-{UPWORK_CACHE_HOURS} hours"))
        db.commit()
        return cur.rowcount


def _log_run(org_id: str, source: str, status: str, fetched: int = 0, stored: int = 0, detail: Optional[str] = None) -> None:
    with get_db() as db:
        db.execute("INSERT INTO connector_runs (org_id, source, status, fetched, stored, detail) VALUES (?,?,?,?,?,?)",
                   (org_id, source, status, fetched, stored, (detail or "")[:300]))
        db.commit()


class OpportunityRadarEngine:
    def __init__(self, connectors: Optional[List[BaseConnector]] = None):
        self.connectors = connectors if connectors is not None else default_connectors()

    def scan_all_sources(self, limit_per_source: int = 10, org_id: str = "org_default", progress=None) -> List[Dict[str, Any]]:
        """Reads every source IN PARALLEL (the slowest one sets the time, not the sum), then scores and stores the results in source order."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        profile = agency_profile_terms(org_id)
        collected: List[Dict[str, Any]] = []

        def read(conn):
            name = getattr(conn, "source_name", type(conn).__name__)
            try:
                return name, conn.fetch(limit=getattr(conn, "max_fetch", 100), org_id=org_id), None
            except Exception as exc:
                return name, None, exc

        results: Dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=min(9, max(1, len(self.connectors)))) as pool:
            futures = [pool.submit(read, c) for c in self.connectors]
            for f in as_completed(futures):
                name, items, exc = f.result()
                results[name] = (items, exc)
                if progress:
                    progress({"log": [{"step": "source", "message": f"{name}: " + (f"{len(items)} read" if exc is None else "problem")}], "processed": len(results),
                              "total": len(self.connectors)})

        for conn in self.connectors:
            name = getattr(conn, "source_name", type(conn).__name__)
            items, exc = results[name]
            if isinstance(exc, ConnectorNotConfigured):
                _log_run(org_id, name, "not_connected" if "not connected" in str(exc).lower() or "reconnect" in str(exc).lower() else "not_configured", detail=str(exc))
                continue
            if exc is not None:
                logger.warning("Radar connector %s failed: %s", name, str(exc)[:160])
                _log_run(org_id, name, "error", detail=f"{type(exc).__name__}: {exc}")
                continue

            scored = []
            for it in items:
                fit = score_opportunity(it.title, it.description, it.type, it.budget_max, profile)
                scored.append((fit, it))
            # best fit first; unscored items (no profile) keep source order, which is newest-first
            scored.sort(key=lambda p: (p[0].score is None, -(p[0].score or 0.0)))
            stored = 0
            for fit, it in scored[:limit_per_source]:
                opp = OpportunityRepository.create_opportunity(
                    opp_type=it.type, source=it.source, title=it.title, description=it.description, external_id=it.external_id,
                    budget_min=it.budget_min, budget_max=it.budget_max, currency=it.currency, fit_score=fit.score,
                    risk_flags=sorted(set(fit.risk_flags) | set(it.risk_flags)), org_id=org_id, url=it.url,
                    company_name=it.company_name, skills=it.skills_required, fit_reasons=fit.reasons, posted_at=it.posted_at)
                collected.append(opp)
                stored += 1
            _log_run(org_id, name, "ok" if items else "empty", fetched=len(items), stored=stored,
                     detail=None if items else "The source returned no items.")

        purge_expired(org_id)

        return collected

    @staticmethod
    def source_status(org_id: str, connectors: Optional[List[BaseConnector]] = None) -> List[Dict[str, Any]]:
        """Connector health plus the outcome of the most recent scan for this tenant."""
        out = []
        with get_db() as db:
            for conn in (connectors or default_connectors()):
                health = conn.check_health(org_id)
                last = db.execute("SELECT status, fetched, stored, detail, ran_at FROM connector_runs WHERE org_id = ? AND source = ? "
                                  "ORDER BY id DESC LIMIT 1", (org_id, conn.source_name)).fetchone()
                out.append({**health, "last_run": dict(last) if last else None})
        return out

    @staticmethod
    def list_radar_feed(source: Optional[str] = None, limit: int = 50, org_id: str = "org_default") -> List[Dict[str, Any]]:
        return OpportunityRepository.list_opportunities(source=source, limit=limit, org_id=org_id)
