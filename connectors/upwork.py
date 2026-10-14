"""
Upwork connector: official OAuth2 + GraphQL API, read-only job search, human submits.

  * Each tenant connects its OWN approved Upwork API app (UPWORK_CLIENT_ID / UPWORK_CLIENT_SECRET / UPWORK_REDIRECT_URI)
    through the authorization-code flow; tokens are stored encrypted and refreshed automatically.
  * No scraping, no automated submission. Upwork's terms limit caching of API data to 24 hours, so the radar purges
    Upwork rows older than that (see radar.engine.purge_expired).

HONESTY NOTE: the OAuth endpoints are Upwork's documented ones, but the GraphQL query below follows the published schema
from memory and could NOT be run against the live API here (it needs an approved key). If Upwork rejects it, the GraphQL
error text is surfaced in the connector status instead of being hidden. Verify with a real key before relying on it.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from connectors.base import BaseConnector, ConnectorNotConfigured, OpportunityItem
from connectors.oauth import TokenStore, sign_state
from net.fetcher import SafeFetcher

AUTH_URL = "https://www.upwork.com/ab/account-security/oauth2/authorize"
TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
GRAPHQL_URL = "https://api.upwork.com/graphql"
CACHE_HOURS = 24

QUERY = """
query Jobs($q: String!) {
  marketplaceJobPostingsSearch(
    marketPlaceJobFilter: { searchExpression_eq: $q }
    searchType: USER_JOBS_SEARCH
    sortAttributes: [{ field: RECENCY }]
  ) {
    edges { node { id title description createdDateTime ciphertext
                   amount { rawValue currency } skills { name } } }
  }
}
"""


def _client() -> Dict[str, str]:
    cid, secret, redirect = (os.getenv("UPWORK_CLIENT_ID", ""), os.getenv("UPWORK_CLIENT_SECRET", ""), os.getenv("UPWORK_REDIRECT_URI", ""))
    if not (cid and secret and redirect) or cid.startswith("your_"):
        raise ConnectorNotConfigured("Set UPWORK_CLIENT_ID, UPWORK_CLIENT_SECRET and UPWORK_REDIRECT_URI (apply for API access at upwork.com/developer).")
    return {"id": cid, "secret": secret, "redirect": redirect}


def parse_graphql(data: Dict[str, Any]) -> List[OpportunityItem]:
    if data.get("errors"):
        raise RuntimeError("Upwork GraphQL error: " + "; ".join(str(e.get("message", e))[:150] for e in data["errors"][:3]))
    edges = (((data.get("data") or {}).get("marketplaceJobPostingsSearch")) or {}).get("edges") or []
    items = []
    for edge in edges:
        n = edge.get("node") or {}
        amount = (n.get("amount") or {})
        raw = amount.get("rawValue")
        items.append(OpportunityItem(
            type="marketplace", source="upwork", external_id=str(n.get("id")), title=n.get("title") or "Upwork job",
            description=n.get("description") or "", url=f"https://www.upwork.com/jobs/{n.get('ciphertext')}" if n.get("ciphertext") else None,
            posted_at=n.get("createdDateTime"), budget_max=float(raw) if raw not in (None, "") else None, currency=amount.get("currency") or "USD",
            skills_required=[s.get("name") for s in (n.get("skills") or []) if s.get("name")][:10]))
    return items


class UpworkConnector(BaseConnector):
    source_name = "upwork"
    terms_url = "https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly"
    automation_level = "L1"            # AI drafts, a human reviews and submits
    rate_limit_per_minute = 15
    requires_api_key = True
    max_fetch = 50

    # -- OAuth ------------------------------------------------------------------------------------
    @staticmethod
    def authorize_url(org_id: str) -> str:
        c = _client()
        return f"{AUTH_URL}?{urlencode({'response_type': 'code', 'client_id': c['id'], 'redirect_uri': c['redirect'], 'state': sign_state(org_id, 'upwork')})}"

    @staticmethod
    def _token_request(form: Dict[str, str]) -> Dict[str, Any]:
        res = SafeFetcher.safe_fetch(TOKEN_URL, method="POST", form_body=form, timeout=20)
        if res.status_code != 200:
            raise RuntimeError(f"Upwork token endpoint returned HTTP {res.status_code}: {res.text[:150]}")
        return json.loads(res.text)

    @classmethod
    def exchange_code(cls, org_id: str, code: str) -> None:
        c = _client()
        tok = cls._token_request({"grant_type": "authorization_code", "client_id": c["id"], "client_secret": c["secret"],
                                  "code": code, "redirect_uri": c["redirect"]})
        TokenStore.save(org_id, "upwork", tok["access_token"], tok.get("refresh_token"), tok.get("expires_in"), tok.get("scope", ""))

    @classmethod
    def access_token(cls, org_id: str) -> str:
        stored = TokenStore.load(org_id, "upwork")
        if not stored:
            raise ConnectorNotConfigured("Upwork is not connected for this workspace. Use Connect Upwork in the Radar.")
        if stored["expires_at"] - datetime.now(timezone.utc) > timedelta(seconds=60):
            return stored["access"]
        if not stored["refresh"]:
            raise ConnectorNotConfigured("The Upwork connection expired. Reconnect Upwork.")
        c = _client()
        tok = cls._token_request({"grant_type": "refresh_token", "client_id": c["id"], "client_secret": c["secret"], "refresh_token": stored["refresh"]})
        TokenStore.save(org_id, "upwork", tok["access_token"], tok.get("refresh_token"), tok.get("expires_in"), tok.get("scope", ""))
        return tok["access_token"]

    # -- fetching ---------------------------------------------------------------------------------
    def fetch(self, query: Optional[str] = None, limit: int = 50, org_id: Optional[str] = None) -> List[OpportunityItem]:
        _client()
        if not org_id:
            raise ConnectorNotConfigured("Upwork needs a workspace context.")
        token = self.access_token(org_id)
        if not query:
            from radar.fit import agency_profile_terms
            terms = sorted(agency_profile_terms(org_id))[:5]
            query = os.getenv("AGENCYBD_UPWORK_QUERY") or " ".join(terms)
        if not query.strip():
            raise ConnectorNotConfigured("No search terms: add services/portfolio (or set AGENCYBD_UPWORK_QUERY).")
        res = SafeFetcher.safe_fetch(GRAPHQL_URL, method="POST", json_body={"query": QUERY, "variables": {"q": query}},
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=30)
        if res.status_code == 401:
            raise ConnectorNotConfigured("Upwork rejected the token. Reconnect Upwork.")
        if res.status_code != 200:
            raise RuntimeError(f"Upwork GraphQL returned HTTP {res.status_code}: {res.text[:150]}")
        return parse_graphql(json.loads(res.text))[:limit]

    def check_health(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        base = super().check_health(org_id)
        try:
            _client()
        except ConnectorNotConfigured as exc:
            return {**base, "status": "not_configured", "detail": str(exc)}
        connected = bool(org_id and TokenStore.load(org_id, "upwork"))
        return {**base, "status": "connected" if connected else "not_connected",
                "detail": None if connected else "Authorize Upwork to start ingesting jobs."}
