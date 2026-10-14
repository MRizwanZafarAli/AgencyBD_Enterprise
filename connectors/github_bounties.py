"""GitHub paid-bounty connector (public search API; GITHUB_TOKEN optional, raises the rate limit).

Only open issues carrying an Algora "💎 Bounty" label AND a dollar-amount label (e.g. "$50") are kept, so every item has a
stated reward. Rewards are small and need a human to claim them on the issue; this is a source of paid engineering tasks and
of companies actively funding work, not of agency-sized projects."""

import json
import os
import re
from typing import List, Optional
from urllib.parse import quote

from connectors.base import BaseConnector, OpportunityItem
from connectors.text import clean_html
from net.fetcher import SafeFetcher

QUERY = 'label:"💎 Bounty" state:open type:issue'
AMOUNT = re.compile(r"^\$\s?(\d[\d,]*)$")


def parse_issues(data: dict) -> List[OpportunityItem]:
    items: List[OpportunityItem] = []
    for i in data.get("items", []):
        labels = [l.get("name", "") for l in i.get("labels", [])]
        amounts = [float(m.group(1).replace(",", "")) for l in labels if (m := AMOUNT.match(l.strip()))]
        if not amounts:
            continue
        repo = i["repository_url"].split("/repos/")[-1]
        items.append(OpportunityItem(
            type="marketplace", source="github", external_id=str(i["id"]), title=i["title"][:200], description=clean_html(i.get("body") or "", 3000),
            company_name=repo.split("/")[0], url=i["html_url"], posted_at=i.get("created_at"), budget_min=max(amounts), budget_max=max(amounts),
            currency="USD", skills_required=[l for l in labels if l and not l.startswith(("$", "💎", "💰"))][:8],
            metadata={"repo": repo, "comments": i.get("comments"), "attribution": "Source: GitHub issue"}))
    return items


class GitHubBountyConnector(BaseConnector):
    source_name = "github"
    terms_url = "https://docs.github.com/en/site-policy/github-terms/github-terms-of-service"
    automation_level = "L0"
    rate_limit_per_minute = 8
    max_fetch = 50

    def fetch(self, query: Optional[str] = None, limit: int = 50, org_id: Optional[str] = None) -> List[OpportunityItem]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "AgencyBD-Enterprise/1.0"}
        if os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
        url = f"https://api.github.com/search/issues?q={quote(QUERY)}&sort=created&order=desc&per_page=50"
        status, text, _ = SafeFetcher.safe_get(url, timeout=15, headers=headers)
        if status != 200:
            raise RuntimeError(f"GitHub returned HTTP {status}")
        return parse_issues(json.loads(text))[:limit]
