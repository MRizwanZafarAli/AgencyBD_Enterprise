"""
AI-search readiness (GEO). Reports what the site actually allows and publishes:
  * which AI crawlers its robots.txt blocks (parsed with a real robots parser)
  * whether /llms.txt exists (low-cost; there is no evidence yet that AI engines rely on it)
  * whether it publishes entity data (schema.org Organization / LocalBusiness)
Checks whose inputs we could not observe are skipped, never guessed.
"""

from typing import List

from auditors.base import AuditFinding
from auditors.context import SiteContext
from auditors.seo import robots_allows
from intel.site_profile import extract_profile

SEARCH_BOTS = ["OAI-SearchBot", "PerplexityBot", "Claude-SearchBot"]
TRAINING_BOTS = ["GPTBot", "ClaudeBot", "CCBot", "Google-Extended", "anthropic-ai", "cohere-ai"]


class GEOAuditor:
    @staticmethod
    def audit(ctx: SiteContext) -> List[AuditFinding]:
        f: List[AuditFinding] = []
        if ctx.robots_txt:
            blocked_search = [b for b in SEARCH_BOTS if not robots_allows(ctx.robots_txt, b)]
            blocked_training = [b for b in TRAINING_BOTS if not robots_allows(ctx.robots_txt, b)]
            if blocked_search:
                f.append(AuditFinding("geo", "ai_search_crawlers_blocked", "medium",
                                      f"robots.txt blocks AI search crawlers: {', '.join(blocked_search)}.",
                                      "Allow these crawlers if you want the business cited in ChatGPT search, Perplexity or Claude answers.",
                                      "The site cannot be retrieved for AI-generated answers from those engines.", "geo_ai_readiness",
                                      f"robots.txt disallows: {blocked_search}"))
            if blocked_training:
                f.append(AuditFinding("geo", "ai_training_crawlers_blocked", "info",
                                      f"robots.txt blocks AI training crawlers: {', '.join(blocked_training)}.",
                                      "This is often a deliberate choice. Confirm it matches the owner's intent.",
                                      "Content is excluded from model training; this does not necessarily affect AI search citations.",
                                      "geo_ai_readiness", f"robots.txt disallows: {blocked_training}", confidence=0.9))
        if ctx.llms_txt is False:
            f.append(AuditFinding("geo", "missing_llms_txt", "info", "No /llms.txt file.",
                                  "Optional: publish a short /llms.txt summarising the business for AI tools.",
                                  "A cheap, optional addition. There is no evidence yet that major AI engines depend on it.",
                                  "geo_ai_readiness", "GET /llms.txt returned 404 (or non-text).", confidence=0.6))
        types = set(extract_profile(ctx.html, ctx.url)["schema_types"])
        if not (types & {"Organization", "LocalBusiness", "Corporation", "ProfessionalService"} or any("Business" in t for t in types)):
            f.append(AuditFinding("geo", "missing_entity_schema", "medium", "No Organization/LocalBusiness schema on the homepage.",
                                  "Add JSON-LD with name, logo, address/contact and sameAs links to official profiles.",
                                  "Machines cannot reliably tie the site to a verified business identity.", "geo_ai_readiness",
                                  f"JSON-LD types found: {sorted(types) or 'none'}"))
        return f
