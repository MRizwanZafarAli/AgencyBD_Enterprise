import { useState } from 'react';
import type { FC } from 'react';
import { PageHeader, Tabs } from '../components/ui';
import { FindLocal } from '../components/find/FindLocal';
import type { LocalPreset } from '../components/find/FindLocal';
import { FindJobs } from '../components/find/FindJobs';
import type { JobsPreset } from '../components/find/FindJobs';
import { LeadFinder } from '../components/leadfinder/LeadFinder';
import { SmartSearch } from '../components/find/SmartSearch';
import type { SearchRun } from '../components/find/SmartSearch';

const TABS = [
  { id: 'local', label: 'Local businesses' },
  { id: 'jobs', label: 'Jobs and projects' },
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
}> = ({ onOpenClient, onAddGoogleKey, seed, onSendEmail }) => {
  const [tab, setTab] = useState('local');
  const [local, setLocal] = useState<LocalPreset | null>(null);
  const [jobs, setJobs] = useState<JobsPreset | null>(null);
  const [tenders, setTenders] = useState<JobsPreset | null>(null);

  const run = (r: SearchRun) => {
    const nonce = Date.now();
    if (r.kind === 'local') {
      setLocal({ category: r.category ?? '', city: r.city ?? '', only_gaps: !!r.only_gaps, nonce });
      setTab('local');
    } else if (r.kind === 'jobs') {
      setJobs({ q: r.q ?? '', min_budget: r.min_budget, max_budget: r.max_budget, remote: r.remote, nonce });
      setTab('jobs');
    } else if (r.kind === 'tenders') {
      setTenders({ q: r.q ?? '', min_budget: r.min_budget, nonce });
      setTab('tenders');
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Find"
        subtitle="Describe who or what you are looking for in your own words. Spelling is corrected, and every result shows why it was ranked."
      />
      <SmartSearch onRun={run} seed={seed} />
      <Tabs tabs={TABS} active={tab} onChange={setTab} />
      {tab === 'local' && (
        <FindLocal
          onSaved={onOpenClient}
          preset={local}
          onAddGoogleKey={onAddGoogleKey}
          onSendEmail={onSendEmail}
        />
      )}
      {tab === 'jobs' && (
        <FindJobs
          types={['marketplace', 'hiring_signal', 'inbound', 'outbound']}
          preset={jobs}
          onSendEmail={onSendEmail}
        />
      )}
      {tab === 'tenders' && (
        <FindJobs
          types={['tender']}
          preset={tenders}
          onSendEmail={onSendEmail}
        />
      )}
      {tab === 'watch' && <LeadFinder onOpenClient={onOpenClient} onAddKey={onAddGoogleKey} />}
    </div>
  );
};
