import { useState } from 'react';
import type { FC } from 'react';
import { ExternalLink, ShieldCheck } from 'lucide-react';
import { Card, Skeletons, Stat, Tabs } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { apiFetch } from '../../lib/api';
import { send, useApi } from '../../lib/hooks';
import {
  Activity,
  Availability,
  Experiments,
  Features,
  FeeCalculator,
  Funnel,
  Pacing,
  Messages,
  OpenInBrowser,
  Performance,
  Pipeline,
  ProfileHealth,
  QuickActivityBar,
  QuickPages,
  Routine,
  Templates,
} from './ChannelSections';
import {
  BiddingMarketplaceView,
  InboundStorefrontView,
  ReviewDirectoryView,
  SocialOutboundView,
  VettedNetworkView,
} from './ArchetypeWorkspaces';
import { localDay } from './types';
import type { Catalog, Platform, Rec, Summary } from './types';
import type { Run } from './shared';
import type { ScraperMode } from '../browser/InteractiveBrowserSidepanel';

/** Runs one action, shows its error, then refreshes what is on screen. */
function useAction(reload: () => void): { error: string; run: Run } {
  const [error, setError] = useState('');
  const run: Run = async (fn: () => Promise<unknown>) => {
    try {
      setError('');
      await fn();
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return { error, run };
}

export const ChannelPanel: FC<{
  platform: Platform;
  catalog: Catalog;
  onOpenScraper?: (url: string, mode?: ScraperMode, title?: string) => void;
  onOverviewDirty?: () => void;
}> = ({ platform, catalog, onOpenScraper, onOverviewDirty }) => {
  const id = platform.id;
  const [subTab, setSubTab] = useState<'daily' | 'pipeline' | 'analytics' | 'playbook'>('daily');
  const summary = useApi<Summary>(`/api/channels/${id}/summary`);
  const records = useApi<{ records: Rec[] }>(`/api/channels/${id}/records`);
  const routines = useApi<{ records: Rec[] }>(`/api/channels/${id}/records?type=routine`);
  const reload = () => {
    summary.reload();
    records.reload();
    routines.reload();
    onOverviewDirty?.();
  };
  const { error, run } = useAction(reload);
  const all = records.data?.records ?? [];
  const of = (t: string) => all.filter((r) => r.type === t);
  const s = summary.data;
  const today = localDay();
  const doneToday = new Map(of('done').filter((d) => d.day === today).map((d) => [d.routine_id, d.id]));
  const post = (type: string, data: Record<string, unknown>) => send(`/api/channels/${id}/records`, 'POST', { type, data });
  const update = (rid: number, data: Record<string, unknown>) =>
    run(async () => {
      const res = await apiFetch(`/api/channels/${id}/records/${rid}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Could not save');
    });
  const remove = (rid: number) => run(() => send(`/api/channels/${id}/records/${rid}`, 'DELETE'));
  const promote = (rid: number) => run(() => send(`/api/channels/${id}/records/${rid}/promote`, 'POST', {}));
  const loading = (records.loading && !records.data) || (summary.loading && !summary.data);

  const arch = platform.archetype;

  return (
    <div className="space-y-5">
      <ErrorBanner message={error || summary.error || records.error} />

      <Card className="!border-emerald-500/30">
        <div className="flex gap-3">
          <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-white">Account Safety &amp; Pacing Shield — {platform.label}</h2>
            <ul className="mt-1.5 space-y-1 text-xs text-slate-300 list-disc pl-4">
              {platform.rules.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            {platform.terms && (
              <a
                href={platform.terms}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:underline mt-2"
              >
                Read their terms <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
      </Card>

      {/* Archetype-Native Top 5 KPI Strip */}
      {loading ? (
        <Skeletons rows={3} />
      ) : (
        s?.kpis && (
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-5">
            {s.kpis.map((k) => (
              <Stat key={k.id} label={k.label} value={k.value} hint={k.hint} />
            ))}
          </div>
        )
      )}

      <Tabs
        tabs={[
          { id: 'daily', label: 'Workspace' },
          { id: 'pipeline', label: 'Pipeline & templates', count: of('pipeline').length || undefined },
          { id: 'analytics', label: 'Analytics & activity' },
          { id: 'playbook', label: 'Playbook & profile health' },
        ]}
        active={subTab}
        onChange={(t) => setSubTab(t as typeof subTab)}
      />

      {subTab === 'daily' && (
        <div className="space-y-5">
          <QuickPages platform={platform} onOpenScraper={onOpenScraper} />

          {/* Platform-Native Archetype Workspace Module */}
          {arch === 'social_outbound' && <SocialOutboundView platform={platform} s={s ?? null} run={run} onOpenScraper={onOpenScraper} />}
          {arch === 'bidding_marketplace' && <BiddingMarketplaceView platform={platform} s={s ?? null} run={run} onOpenScraper={onOpenScraper} />}
          {arch === 'inbound_storefront' && <InboundStorefrontView platform={platform} s={s ?? null} run={run} onOpenScraper={onOpenScraper} />}
          {arch === 'vetted_network' && <VettedNetworkView platform={platform} s={s ?? null} run={run} onOpenScraper={onOpenScraper} />}
          {arch === 'review_directory' && <ReviewDirectoryView platform={platform} s={s ?? null} run={run} onOpenScraper={onOpenScraper} />}
          {arch === 'custom' && <BiddingMarketplaceView platform={platform} s={s ?? null} run={run} onOpenScraper={onOpenScraper} />}

          <Pacing s={s ?? null} />
          <QuickActivityBar platform={platform} s={s ?? null} today={today} run={run} post={post} />

          <div className="grid gap-5 lg:grid-cols-2">
            <Routine id={id} routines={routines.data?.records ?? []} doneToday={doneToday} today={today} run={run} post={post} remove={remove} />
            <OpenInBrowser platform={platform} links={of('link')} run={run} post={post} remove={remove} onOpenScraper={onOpenScraper} />
          </div>
        </div>
      )}

      {subTab === 'pipeline' && (
        <div className="space-y-5">
          <Pipeline platformId={id} statuses={catalog.statuses} items={of('pipeline')} run={run} post={post} update={update} remove={remove} promote={promote} />
          <div className="grid gap-5 lg:grid-cols-2">
            <Templates platform={platform} items={of('template')} run={run} post={post} update={update} remove={remove} />
            <Messages items={of('message')} s={s ?? null} run={run} post={post} update={update} remove={remove} />
          </div>
        </div>
      )}

      {subTab === 'analytics' && (
        <div className="space-y-5">
          <Funnel s={s ?? null} />
          <div className="grid gap-5 lg:grid-cols-2">
            <Activity platformId={id} kinds={catalog.activity_kinds} s={s ?? null} today={today} run={run} post={post} />
            <Performance platform={platform} s={s ?? null} />
          </div>
          <Experiments platform={platform} items={of('experiment')} s={s ?? null} run={run} post={post} update={update} remove={remove} />
        </div>
      )}

      {subTab === 'playbook' && (
        <div className="space-y-5">
          <Features platform={platform} />
          <div className="grid gap-5 lg:grid-cols-2">
            <ProfileHealth platform={platform} />
            <FeeCalculator platform={platform} />
          </div>
          {platform.kind === 'marketplace' && (
            <Availability platform={platform} setting={s?.setting ?? null} s={s ?? null} run={run} post={post} />
          )}
        </div>
      )}
    </div>
  );
};
