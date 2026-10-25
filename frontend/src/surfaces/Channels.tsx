import type { FC } from 'react';
import { useState } from 'react';
import { Card, PageHeader, Skeletons, Tabs } from '../components/ui';
import { ErrorBanner } from '../components/shared/ErrorBanner';
import { ChannelPanel } from '../components/channels/ChannelPanel';
import { QuickLog } from '../components/channels/QuickLog';
import type { Catalog } from '../components/channels/types';
import { useApi } from '../lib/hooks';

interface Overview { platforms: Array<{ platform: string; open: number; followups_due: number; unanswered: number }> }

export const Channels: FC<{ active: string; onActive: (id: string) => void; quick?: { text: string; n: number } | null }> = ({ active, onActive: setActive, quick }) => {
  const [version, setVersion] = useState(0);
  const catalog = useApi<Catalog>('/api/channels/platforms');
  const overview = useApi<Overview>('/api/channels/overview');
  const platforms = catalog.data?.platforms ?? [];
  const current = platforms.find((p) => p.id === active) ?? platforms[0];
  const attention = (id: string) => { const o = overview.data?.platforms.find((p) => p.platform === id); return o ? o.followups_due + o.unanswered : undefined; };

  return (
    <div className="space-y-5">
      <PageHeader title="Channels" subtitle="Your control centre for LinkedIn and freelance sites. You work on each site in your own browser. This page keeps your pipeline, routine, templates and response times." />
      <ErrorBanner message={catalog.error} />
      {catalog.loading && !catalog.data ? <Skeletons rows={3} /> : current && catalog.data && (
        <>
          <QuickLog catalog={catalog.data} seed={quick} onSaved={(id) => { setActive(id); setVersion((v) => v + 1); overview.reload(); }} />
          <Tabs tabs={platforms.map((p) => ({ id: p.id, label: p.label, count: attention(p.id) || undefined }))} active={current.id} onChange={(id) => { setActive(id); overview.reload(); }} />
          <ChannelPanel key={`${current.id}-${version}`} platform={current} catalog={catalog.data} />
        </>)}
      {!catalog.loading && !catalog.error && platforms.length === 0 && <Card><p className="text-sm text-slate-400">No channels available.</p></Card>}
    </div>
  );
};
