import { useState } from 'react';
import type { FC } from 'react';
import { PageHeader, Tabs } from '../components/ui';
import { FindLocal } from '../components/find/FindLocal';
import type { LocalPreset } from '../components/find/FindLocal';
import { FindJobs } from '../components/find/FindJobs';
import type { JobsPreset } from '../components/find/FindJobs';
import { FindTenders } from '../components/find/FindTenders';
import { LeadFinder } from '../components/leadfinder/LeadFinder';
import { SmartSearch } from '../components/find/SmartSearch';
import type { SearchRun } from '../components/find/SmartSearch';
import { SocialIntentRadar } from '../components/find/SocialIntentRadar';
import { TabGuide } from '../components/find/TabGuide';
import type { Me } from '../lib/api';

const ALL_TABS = [
  { id: 'local', label: 'Local businesses' },
  { id: 'jobs', label: 'Jobs and projects' },
  { id: 'social', label: 'Social intent' },
  { id: 'tenders', label: 'Tenders' },
  { id: 'watch', label: 'Watching' },
];

export const Find: FC<{
  onOpenClient: (leadId: number) => void;
  onAddGoogleKey: () => void;
  seed?: { text: string; n: number } | null;
  onSendEmail?: (params: {
    recipient: string;
    recipientName?: string;
    companyName?: string;
    subject?: string;
    body?: string;
    leadId?: number;
  }) => void;
  identity?: Me | null;
  onOpenScraper?: (url: string, mode?: 'general' | 'client_audit' | 'job_spec' | 'local_audit', title?: string) => void;
}> = ({ onOpenClient, onAddGoogleKey, seed, onSendEmail, identity, onOpenScraper }) => {
  const [tab, setTab] = useState(() => (identity?.role === 'sdr_rep' ? 'jobs' : 'local'));
  const [local, setLocal] = useState<LocalPreset | null>(null);
  const [jobs, setJobs] = useState<JobsPreset | null>(null);
  const [tenders, setTenders] = useState<JobsPreset | null>(null);

  // Growth Lead role has Tenders scope removed completely
  const isGrowthLead = identity?.role === 'growth_lead';
  const tabs = isGrowthLead ? ALL_TABS.filter((t) => t.id !== 'tenders') : ALL_TABS;

  const run = (r: SearchRun) => {
    const nonce = Date.now();
    if (r.kind === 'local') {
      setLocal({ category: r.category ?? '', city: r.city ?? '', only_gaps: !!r.only_gaps, nonce });
      setTab('local');
    } else if (r.kind === 'jobs') {
      setJobs({ q: r.q ?? '', min_budget: r.min_budget, max_budget: r.max_budget, remote: r.remote, nonce });
      setTab('jobs');
    } else if (r.kind === 'tenders') {
      if (isGrowthLead) {
        // Fallback to jobs search for Growth Lead without tenders
        setJobs({ q: r.q ?? '', min_budget: r.min_budget, nonce });
        setTab('jobs');
      } else {
        setTenders({ q: r.q ?? '', min_budget: r.min_budget, nonce });
        setTab('tenders');
      }
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Find"
        subtitle="Describe who or what you are looking for in your own words. Spelling is corrected, and every result shows why it was ranked."
      />
      <SmartSearch onRun={run} seed={seed} />
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === 'local' && (
        <TabGuide
          id="local"
          title="Local businesses"
          note="Best for selling web redesigns, SEO & booking setups"
          steps={[
            'Enter a business type and city (or click a quick-start preset).',
            'Check "Hide businesses with a working site" to isolate easy wins.',
            'Scrape Site & Gaps or Save selected directly to Clients.',
          ]}
        />
      )}
      {tab === 'jobs' && (
        <TabGuide
          id="jobs"
          title="Jobs & projects"
          note="Live freelance, remote & engineering hiring signals"
          steps={[
            'Filter by Source, Minimum fit %, Budget, or Remote status.',
            'Click any row or "See Business Details" to resolve owner & company intel.',
            'Use "Scrape Job Specs" for deep tech-stack extraction or Draft Proposal.',
          ]}
        />
      )}
      {tab === 'social' && (
        <TabGuide
          id="social"
          title="Social intent"
          note="Multi-source buying-intent engine across HN, Bluesky, Reddit, GitHub, Dev.to & Lobsters"
          steps={[
            'Click an Offer-Aware Query chip or enter a boolean query, then Scan Social Intent.',
            'Filter by Intent Type (Buying Request, Competitor Pain, Pain Point, Launch) & Time Window.',
            'Resolve Author Identity for site audits or use the Human-First Reply Studio with anti-ban guardrails.',
          ]}
        />
      )}
      {!isGrowthLead && tab === 'tenders' && (
        <TabGuide
          id="tenders"
          title="Government & public tenders"
          note="Official procurement notices from TED (EU), UK Find a Tender, UK Contracts Finder & SAM.gov (US)"
          steps={[
            'Filter by Portal, Notice Stage (Pre-Market PIN, Live RFP, Framework, Award), CPV/NAICS & Value Tier.',
            'Click "Bid / No-Go Studio" for the 4-point Scorecard, Authority contacts & Mega-Tender Teaming strategy.',
            'Parse Tender Docs for the Compliance Matrix, generate a Bid Outline, or Watch Authority/CPV.',
          ]}
        />
      )}
      {tab === 'watch' && (
        <TabGuide
          id="watch"
          title="Automated signal monitors"
          note="Unified Signal Monitoring, Alert Routing & Triage Inbox across all 4 Find tabs"
          steps={[
            'Start with a 1-click Monitor Template (Local Territory, Hiring-Spree, Competitor Radar, or Tender/CPV).',
            'Enable Auto-Play or set Instant vs. Daily Digest alert thresholds to prevent notification fatigue.',
            'Triage stacked multi-signal accounts in the Unified Inbox with Inspect, Keep to CRM, or Bulk actions.',
          ]}
        />
      )}
      {tab === 'local' && (
        <FindLocal
          onSaved={onOpenClient}
          preset={local}
          onAddGoogleKey={onAddGoogleKey}
          onSendEmail={onSendEmail}
          onOpenScraper={onOpenScraper}
        />
      )}
      {tab === 'jobs' && (
        <FindJobs
          mode="jobs"
          types={['marketplace', 'hiring_signal', 'inbound', 'outbound']}
          preset={jobs}
          onSendEmail={onSendEmail}
          onOpenClient={onOpenClient}
          onOpenScraper={onOpenScraper}
        />
      )}
      {!isGrowthLead && tab === 'tenders' && (
        <FindTenders
          preset={tenders}
          onSendEmail={onSendEmail}
          onOpenClient={onOpenClient}
        />
      )}
      {tab === 'social' && <SocialIntentRadar onOpenScraper={onOpenScraper} />}
      {tab === 'watch' && <LeadFinder onOpenClient={onOpenClient} onAddKey={onAddGoogleKey} />}
    </div>
  );
};
