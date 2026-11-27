export interface OppItem {
  id: number;
  type: string;
  source: string;
  title: string;
  description: string | null;
  company_name: string | null;
  budget_min: number | null;
  budget_max: number | null;
  currency: string | null;
  url: string | null;
  posted_at: string | null;
  fit_score: number | null;
  fit_reasons: string[];
  risk_flags: string[];
  user_vote?: 'up' | 'down' | null;
  crm_status?: { lead_id: number; deal_stage: string } | null;
}

export type EngagementFilter = 'all' | 'direct_project' | 'contract_c2c' | 'full_time';
export type CompanyStageFilter = 'all' | 'startup_smb' | 'agency_partner' | 'enterprise';
export type PitchAngle = 'staff_aug' | 'fixed_scope' | 'white_label';

const TECH_PATTERNS: Array<[RegExp, string]> = [
  [/\breact(\.js)?\b/i, 'React'],
  [/\bnext\.?js\b/i, 'Next.js'],
  [/\btypescript\b/i, 'TypeScript'],
  [/\bpython\b/i, 'Python'],
  [/\bfastapi\b/i, 'FastAPI'],
  [/\bdjango\b/i, 'Django'],
  [/\bnode\.?js\b/i, 'Node.js'],
  [/\bplaywright\b/i, 'Playwright'],
  [/\bselenium\b/i, 'Selenium'],
  [/\bcypress\b/i, 'Cypress'],
  [/\bwordpress\b/i, 'WordPress'],
  [/\bwebflow\b/i, 'Webflow'],
  [/\bshopify\b/i, 'Shopify'],
  [/\bhubspot\b/i, 'HubSpot'],
  [/\bsalesforce\b/i, 'Salesforce'],
  [/\baws\b/i, 'AWS'],
  [/\bkubernetes\b/i, 'Kubernetes'],
  [/\bdocker\b/i, 'Docker'],
  [/\bpostgres(ql)?\b/i, 'PostgreSQL'],
  [/\bgraphql\b/i, 'GraphQL'],
  [/\bseo\b/i, 'SEO'],
];

export function detectEngagementType(o: OppItem): Exclude<EngagementFilter, 'all'> {
  const txt = `${o.title} ${o.description || ''}`.toLowerCase();
  if (o.type === 'marketplace' || ['upwork', 'reddit', 'github'].includes(o.source)) {
    return 'direct_project';
  }
  if (/\b(contractor|contract|c2c|freelance|fractional|agency|1099|3-6 months|6 months)\b/.test(txt)) {
    return 'contract_c2c';
  }
  return 'full_time';
}

export function detectCompanyStage(o: OppItem): Exclude<CompanyStageFilter, 'all'> {
  const txt = `${o.company_name || ''} ${o.title} ${o.description || ''}`.toLowerCase();
  if (/\b(agency|digital agency|seo agency|webflow agency|white[- ]label|marketing agency|consultancy|studio)\b/.test(txt)) {
    return 'agency_partner';
  }
  if (/(\$\d+(\.\d+)?[bm]\b|billion|million customers|fortune 500|enterprise|publicly traded|series [cdef]|1,?000\+ employees)/i.test(txt)) {
    return 'enterprise';
  }
  return 'startup_smb';
}

export function detectNoAgenciesRedFlag(o: OppItem): string | null {
  if (o.risk_flags?.includes('no_agencies_red_flag')) {
    return 'No Agencies / Direct Hire Only';
  }
  const txt = `${o.title} ${o.description || ''}`;
  const m = txt.match(/\b(no agencies|no staffing|direct hire only|w2 only|no c2c|no third[- ]party|no recruiters|us citizens? only|security clearance)\b/i);
  return m ? `Red Flag: "${m[0]}"` : null;
}

export function getFreshness(postedAt: string | null): { label: string; isStale: boolean; days: number | null } {
  if (!postedAt) return { label: 'Recent', isStale: false, days: null };
  const ts = Date.parse(postedAt);
  if (Number.isNaN(ts)) return { label: 'Recent', isStale: false, days: null };
  const diffMs = Math.max(0, Date.now() - ts);
  const hours = Math.floor(diffMs / 3600000);
  if (hours < 1) return { label: 'Just now', isStale: false, days: 0 };
  if (hours < 24) return { label: `${hours}h ago`, isStale: false, days: 0 };
  const days = Math.floor(hours / 24);
  if (days >= 30) return { label: `Stale (${days}d)`, isStale: true, days };
  return { label: `${days}d ago`, isStale: false, days };
}

export function formatBudgetOrEstimate(o: OppItem): { text: string; estimated: boolean } {
  if (o.budget_max) {
    return {
      text: `${o.currency ?? 'USD'} ${Math.round(o.budget_max).toLocaleString()}${o.type === 'hiring_signal' ? '/yr' : ''}`,
      estimated: false,
    };
  }
  const txt = `${o.title} ${o.description || ''}`.toLowerCase();
  if (o.type === 'hiring_signal') {
    if (/\b(principal|staff|lead|architect|director|vp|senior|sr\.?)\b/.test(txt)) {
      return { text: 'Est. $8k–$14k/mo pod', estimated: true };
    }
    return { text: 'Est. $5k–$9k/mo pod', estimated: true };
  }
  if (o.type === 'tender') return { text: 'Est. $25k+ RFP', estimated: true };
  return { text: 'Est. $2k–$5k', estimated: true };
}

export function extractCompanyIntel(o: OppItem, openRolesCount: number) {
  const txt = `${o.title}\n${o.description || ''}`;
  const techStack = TECH_PATTERNS.filter(([re]) => re.test(txt)).map(([, label]) => label);
  const scaleMatch = txt.match(/(\$[0-9.]+\s?[BMbm](?:\+)?|[0-9.]+\s?million\s+customers|[0-9,]+\+?\s+employees)/i);
  return {
    techStack,
    scaleSignal: scaleMatch ? scaleMatch[0] : null,
    hiringVelocity: openRolesCount > 1 ? `Hiring ${openRolesCount} roles simultaneously` : null,
  };
}

export function buildLoomScript(o: OppItem, company: string, angle: PitchAngle): string {
  const freshness = getFreshness(o.posted_at);
  const staleLine = freshness.isStale
    ? `I noticed your "${o.title}" role has been open for ${freshness.days} days — `
    : `I saw your "${o.title}" post — `;
  const angleBody =
    angle === 'white_label'
      ? `since ${company} is an agency, we work strictly white-label as an overflow engineering/SEO pod so you keep 100% of the client relationship.`
      : angle === 'staff_aug'
        ? `we can embed a senior pod within 5 days to clear the immediate backlog while you keep interviewing full-time.`
        : `we can scope this as a fixed-milestone deliverable with clear weekly demos and zero overhead.`;

  return [
    `[0:00-0:15 Hook] "Hi team at ${company}, quick 60s Loom for your ${o.title} search. ${staleLine}${angleBody}"`,
    `[0:15-0:40 Proof & Fit] Walk through 1 relevant architecture/audit sample matching ${(extractCompanyIntel(o, 1).techStack.slice(0, 3).join(', ') || 'your stack')}.`,
    `[0:40-0:60 CTA] "Happy to send a 2-week sprint plan or jump on a 10-min alignment call this week."`,
  ].join('\n');
}
