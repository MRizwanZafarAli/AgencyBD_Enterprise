import type { FC } from 'react';
import { useState } from 'react';
import { BarChart3, ChevronDown, ChevronUp } from 'lucide-react';
import { Badge, Button, Card, PageHeader, Skeletons, Stat, Tabs } from '../components/ui';
import { ErrorBanner } from '../components/shared/ErrorBanner';
import { ChannelPanel } from '../components/channels/ChannelPanel';
import { QuickLog } from '../components/channels/QuickLog';
import { ClientMessages } from '../components/alerts/ClientMessages';
import type { Catalog } from '../components/channels/types';
import { fmtMinutes } from '../components/channels/types';
import type { ScraperMode } from '../components/browser/InteractiveBrowserSidepanel';
import { useApi } from '../lib/hooks';

interface OverviewRow {
  platform: string;
  label: string;
  kind?: string;
  open: number;
  followups_due: number;
  value_open?: number;
  value_won?: number;
  win_rate_percent?: number | null;
  applications?: number;
  cost_total?: number;
  unanswered: number;
  average_minutes?: number | null;
}
interface Overview { platforms: OverviewRow[] }

const usd = (n: number) => `$${Math.round(n).toLocaleString()}`;

export const Channels: FC<{
  active: string;
  onActive: (id: string) => void;
  quick?: { text: string; n: number } | null;
  onOpenAlerts?: () => void;
  onOpenScraper?: (url: string, mode?: ScraperMode, title?: string) => void;
}> = ({ active, onActive: setActive, quick, onOpenAlerts, onOpenScraper }) => {
  const [version, setVersion] = useState(0);
  const [showCompare, setShowCompare] = useState(false);
  const catalog = useApi<Catalog>('/api/channels/platforms');
  const overview = useApi<Overview>('/api/channels/overview');
  const platforms = catalog.data?.platforms ?? [];
  const current = platforms.find((p) => p.id === active) ?? platforms[0];
  const rows = overview.data?.platforms ?? [];
  const attention = (id: string) => { const o = rows.find((p) => p.platform === id); return o ? o.followups_due + o.unanswered : undefined; };

  const totals = rows.reduce(
    (acc, r) => ({
      open: acc.open + (r.open || 0),
      valueOpen: acc.valueOpen + (r.value_open || 0),
      valueWon: acc.valueWon + (r.value_won || 0),
      due: acc.due + (r.followups_due || 0),
      waiting: acc.waiting + (r.unanswered || 0),
    }),
    { open: 0, valueOpen: 0, valueWon: 0, due: 0, waiting: 0 },
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Channels"
        subtitle="Your control centre for LinkedIn, Clutch, and freelance marketplaces. Launch sites in the built-in Side Panel or your own browser while tracking pipeline, templates, ROI, and SLAs."
        actions={
          rows.length > 0 ? (
            <Button small onClick={() => setShowCompare((v) => !v)}>
              <BarChart3 className="h-3.5 w-3.5" />
              All-channels rollup
              {showCompare ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </Button>
          ) : undefined
        }
      />
      <ClientMessages onOpenAlerts={onOpenAlerts} />
      <ErrorBanner message={catalog.error} />

      {rows.length > 0 && showCompare && (
        <Card className="space-y-4">
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-5">
            <Stat label="Total open deals" value={totals.open} hint="across all channels" />
            <Stat label="Pipeline in play" value={usd(totals.valueOpen)} hint="open deal value" />
            <Stat label="Total won revenue" value={usd(totals.valueWon)} hint="closed won across channels" />
            <Stat label="Follow-ups due" value={totals.due} hint={totals.due > 0 ? 'needs outreach today' : 'all caught up'} />
            <Stat label="Messages waiting" value={totals.waiting} hint={totals.waiting > 0 ? 'reply to protect SLA' : 'inbox clear'} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 pr-3 font-medium">Channel</th>
                  <th className="py-2 px-3 font-medium">Open</th>
                  <th className="py-2 px-3 font-medium">In play</th>
                  <th className="py-2 px-3 font-medium">Won</th>
                  <th className="py-2 px-3 font-medium">Win rate</th>
                  <th className="py-2 px-3 font-medium">Due</th>
                  <th className="py-2 px-3 font-medium">Waiting</th>
                  <th className="py-2 pl-3 font-medium">Avg reply</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {rows.map((r) => (
                  <tr
                    key={r.platform}
                    onClick={() => { setActive(r.platform); setShowCompare(false); }}
                    className={`cursor-pointer transition-colors hover:bg-slate-800/40 ${r.platform === current?.id ? 'bg-indigo-500/10' : ''}`}
                  >
                    <td className="py-2 pr-3 font-medium text-slate-200 flex items-center gap-2">
                      {r.label}
                      {r.platform === current?.id && <Badge tone="accent">Active</Badge>}
                    </td>
                    <td className="py-2 px-3 tabular text-slate-300">{r.open}</td>
                    <td className="py-2 px-3 tabular text-slate-300">{r.value_open ? usd(r.value_open) : '—'}</td>
                    <td className="py-2 px-3 tabular text-emerald-300">{r.value_won ? usd(r.value_won) : '—'}</td>
                    <td className="py-2 px-3 tabular text-slate-300">{r.win_rate_percent != null ? `${r.win_rate_percent}%` : '—'}</td>
                    <td className="py-2 px-3 tabular">{r.followups_due > 0 ? <Badge tone="warn">{r.followups_due}</Badge> : <span className="text-slate-500">0</span>}</td>
                    <td className="py-2 px-3 tabular">{r.unanswered > 0 ? <Badge tone="warn">{r.unanswered}</Badge> : <span className="text-slate-500">0</span>}</td>
                    <td className="py-2 pl-3 tabular text-slate-400">{fmtMinutes(r.average_minutes ?? null)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {catalog.loading && !catalog.data ? <Skeletons rows={3} /> : current && catalog.data && (
        <>
          <QuickLog catalog={catalog.data} seed={quick} onSaved={(id) => { setActive(id); setVersion((v) => v + 1); overview.reload(); }} />
          <Tabs tabs={platforms.map((p) => ({ id: p.id, label: p.label, count: attention(p.id) || undefined }))} active={current.id} onChange={(id) => { setActive(id); overview.reload(); }} />
          <ChannelPanel
            key={`${current.id}-${version}`}
            platform={current}
            catalog={catalog.data}
            onOpenScraper={onOpenScraper}
            onOverviewDirty={overview.reload}
          />
        </>)}
      {!catalog.loading && !catalog.error && platforms.length === 0 && <Card><p className="text-sm text-slate-400">No channels available.</p></Card>}
    </div>
  );
};
