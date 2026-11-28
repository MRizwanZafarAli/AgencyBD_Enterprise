import type { FC } from 'react';
import { useState } from 'react';
import { AlertTriangle, BarChart3, Check, CheckCircle2, Copy, ExternalLink, Plus, Settings2, Sparkles, X } from 'lucide-react';
import { Badge, Button, Card, PageHeader, Skeletons, Stat } from '../components/ui';
import { ErrorBanner } from '../components/shared/ErrorBanner';
import { ChannelPanel } from '../components/channels/ChannelPanel';
import { QuickLog } from '../components/channels/QuickLog';
import { ClientMessages } from '../components/alerts/ClientMessages';
import type { Catalog } from '../components/channels/types';
import { fmtMinutes } from '../components/channels/types';
import type { ScraperMode } from '../components/browser/InteractiveBrowserSidepanel';
import { send, useApi } from '../lib/hooks';
import { apiFetch } from '../lib/api';

interface MarketplaceEvent {
  id: number;
  platform: string;
  event_type: string;
  buyer_name: string;
  title: string;
  snippet: string;
  deep_link: string;
  ai_draft_reply: string;
  status: string;
  escalation_stage: number;
}

interface OverviewRow {
  platform: string;
  label: string;
  kind?: string;
  archetype?: string;
  archetype_label?: string;
  category?: string;
  native_currency?: { name: string; unit_cost_usd: number } | null;
  open: number;
  followups_due: number;
  value_open?: number;
  value_won?: number;
  spend_usd?: number;
  net_roi_pct?: number | null;
  win_rate_percent?: number | null;
  applications?: number;
  cost_total?: number;
  unanswered: number;
  average_minutes?: number | null;
  sla_target_mins?: number;
}

interface OverviewAlert {
  platform: string;
  label: string;
  tone: 'bad' | 'warn' | 'info' | 'accent';
  text: string;
}

interface Overview {
  platforms: OverviewRow[];
  alerts?: OverviewAlert[];
}

const usd = (n: number) => `$${Math.round(n).toLocaleString()}`;

const CATEGORY_ORDER = [
  'Social & Outbound',
  'Bidding Marketplaces',
  'Inbound Storefronts',
  'Vetted Networks',
  'B2B Directories',
  'Custom',
];

export const Channels: FC<{
  active: string;
  onActive: (id: string) => void;
  quick?: { text: string; n: number } | null;
  onOpenAlerts?: () => void;
  onOpenScraper?: (url: string, mode?: ScraperMode, title?: string) => void;
}> = ({ active, onActive: setActive, quick, onOpenAlerts, onOpenScraper }) => {
  const [version, setVersion] = useState(0);
  const [manageOpen, setManageOpen] = useState(false);
  const [customForm, setCustomForm] = useState({ label: '', archetype: 'custom', home_url: '', sender_pattern: '' });
  const [savingPref, setSavingPref] = useState(false);
  const [copiedEvId, setCopiedEvId] = useState<number | null>(null);

  const catalog = useApi<Catalog>('/api/channels/platforms');
  const overview = useApi<Overview>('/api/channels/overview');
  const urgentEvents = useApi<{ events: MarketplaceEvent[] }>('/api/alerts/events?status=pending');
  const allPlatforms = catalog.data?.platforms ?? [];
  const hiddenSet = new Set(catalog.data?.hidden_platforms ?? []);
  const visiblePlatforms = allPlatforms.filter((p) => !hiddenSet.has(p.id));
  const current = active === 'all' ? null : (allPlatforms.find((p) => p.id === active) ?? visiblePlatforms[0] ?? null);

  const rows = overview.data?.platforms ?? [];
  const alerts = overview.data?.alerts ?? [];
  const attention = (id: string) => {
    const o = rows.find((p) => p.platform === id);
    return o ? o.followups_due + o.unanswered : undefined;
  };

  const totals = rows.reduce(
    (acc, r) => ({
      open: acc.open + (r.open || 0),
      valueOpen: acc.valueOpen + (r.value_open || 0),
      valueWon: acc.valueWon + (r.value_won || 0),
      spend: acc.spend + (r.spend_usd || 0),
      due: acc.due + (r.followups_due || 0),
      waiting: acc.waiting + (r.unanswered || 0),
    }),
    { open: 0, valueOpen: 0, valueWon: 0, spend: 0, due: 0, waiting: 0 },
  );

  const toggleHidePlatform = async (id: string) => {
    setSavingPref(true);
    try {
      const next = new Set(hiddenSet);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      await send('/api/channels/preferences', 'POST', { hidden_platforms: Array.from(next) });
      catalog.reload();
      overview.reload();
      if (active === id && next.has(id)) setActive('all');
    } finally {
      setSavingPref(false);
    }
  };

  const createCustom = async () => {
    if (!customForm.label.trim()) return;
    setSavingPref(true);
    try {
      const res = await send<{ slug: string }>('/api/channels/custom', 'POST', customForm);
      setCustomForm({ label: '', archetype: 'custom', home_url: '', sender_pattern: '' });
      catalog.reload();
      overview.reload();
      if (res?.slug) setActive(res.slug);
    } finally {
      setSavingPref(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Channels"
        subtitle="Archetype-native operating system for LinkedIn, Clutch, marketplaces, and storefronts. Capture opportunities in 1 click from the Side Panel while protecting account safety."
        actions={
          <Button small variant={manageOpen ? 'primary' : 'secondary'} onClick={() => setManageOpen((v) => !v)}>
            <Settings2 className="h-3.5 w-3.5" />
            Manage Active Channels
          </Button>
        }
      />
      <ClientMessages onOpenAlerts={onOpenAlerts} />
      <ErrorBanner message={catalog.error || overview.error} />

      {/* Live Urgent Inquiries Bar (Zero-Ban-Risk Email Ingestion + Wake-Up Engine) */}
      {(urgentEvents.data?.events?.length ?? 0) > 0 && (
        <Card className="!border-rose-500/40 bg-rose-950/20 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-300 flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4" /> Urgent Marketplace Inquiries ({urgentEvents.data!.events.length} awaiting ACK)
            </span>
            <Badge tone="bad">Wake-Up Escalation Active</Badge>
          </div>
          <div className="space-y-2">
            {urgentEvents.data!.events.slice(0, 3).map((ev) => (
              <div key={ev.id} className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge tone="warn">{ev.platform.toUpperCase()}</Badge>
                    <span className="font-semibold text-white">{ev.buyer_name}</span>
                    <span className="text-slate-400 truncate">{ev.title}</span>
                  </div>
                  <p className="text-slate-300 line-clamp-1">&quot;{ev.snippet}&quot;</p>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                  <Button
                    small
                    variant="secondary"
                    onClick={() => {
                      navigator.clipboard?.writeText(ev.ai_draft_reply);
                      setCopiedEvId(ev.id);
                      setTimeout(() => setCopiedEvId(null), 1500);
                    }}
                  >
                    {copiedEvId === ev.id ? <CheckCircle2 className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                    {copiedEvId === ev.id ? 'Copied AI Reply' : 'Copy AI Reply'}
                  </Button>
                  {ev.deep_link && (
                    <a href={ev.deep_link} target="_blank" rel="noopener noreferrer" className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-700 text-indigo-300 hover:text-white inline-flex items-center gap-1">
                      Open <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  <Button
                    small
                    variant="primary"
                    onClick={async () => {
                      await apiFetch(`/api/alerts/events/${ev.id}/ack`, { method: 'POST' });
                      urgentEvents.reload();
                    }}
                  >
                    <Check className="h-3 w-3" /> I&apos;m on it
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Manage Active Channels & Custom Channel Builder Drawer */}
      {manageOpen && (
        <Card className="space-y-4 !border-indigo-500/30">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white">Manage Active Channels</h3>
              <p className="text-xs text-slate-400">Hide marketplaces your agency doesn&apos;t use or add a custom channel (Bark, DesignRush, Wellfound, Dribbble).</p>
            </div>
            <button type="button" onClick={() => setManageOpen(false)} aria-label="Close channel manager">
              <X className="h-4 w-4 text-slate-400 hover:text-white" />
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {allPlatforms.map((p) => {
              const isVisible = !hiddenSet.has(p.id);
              return (
                <button
                  key={p.id}
                  type="button"
                  disabled={savingPref}
                  onClick={() => toggleHidePlatform(p.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition ${
                    isVisible
                      ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                      : 'bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {isVisible && <Check className="h-3 w-3" />}
                  {p.label}
                  <span className="text-[10px] opacity-70">({p.category})</span>
                </button>
              );
            })}
          </div>
          <div className="pt-3 border-t border-slate-800 grid gap-2 sm:grid-cols-4 items-end">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Custom Platform Name</label>
              <input
                value={customForm.label}
                onChange={(e) => setCustomForm((f) => ({ ...f, label: e.target.value }))}
                placeholder="e.g. Bark, DesignRush, Wellfound"
                className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Archetype Preset</label>
              <select
                value={customForm.archetype}
                onChange={(e) => setCustomForm((f) => ({ ...f, archetype: e.target.value }))}
                className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white"
              >
                {(catalog.data?.archetypes ?? []).map((a) => (
                  <option key={a.id} value={a.id}>{a.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Home URL (optional)</label>
              <input
                value={customForm.home_url}
                onChange={(e) => setCustomForm((f) => ({ ...f, home_url: e.target.value }))}
                placeholder="https://www.designrush.com"
                className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Notification Sender (e.g. *@bark.com)</label>
              <input
                value={customForm.sender_pattern}
                onChange={(e) => setCustomForm((f) => ({ ...f, sender_pattern: e.target.value }))}
                placeholder="*@bark.com"
                className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white"
              />
            </div>
            <Button small variant="primary" onClick={createCustom} disabled={savingPref || !customForm.label.trim()}>
              <Plus className="h-3.5 w-3.5" /> Add Custom Channel
            </Button>
          </div>
        </Card>
      )}

      {/* Grouped Channel Navigation Bar */}
      {catalog.loading && !catalog.data ? (
        <Skeletons rows={2} />
      ) : (
        <div className="flex flex-wrap items-center gap-1.5 p-1.5 rounded-2xl bg-slate-900/70 border border-slate-800">
          <button
            type="button"
            onClick={() => setActive('all')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition ${
              active === 'all' ? 'bg-emerald-600 text-white shadow' : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            All Channels
            {alerts.length > 0 && <Badge tone="warn">{alerts.length}</Badge>}
          </button>

          {CATEGORY_ORDER.map((cat) => {
            const catPlatforms = visiblePlatforms.filter((p) => p.category === cat);
            if (!catPlatforms.length) return null;
            return (
              <div key={cat} className="flex items-center gap-1 pl-2 border-l border-slate-800">
                {catPlatforms.map((p) => {
                  const att = attention(p.id);
                  const isActive = active === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setActive(p.id)}
                      className={`px-2.5 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1.5 transition ${
                        isActive ? 'bg-indigo-600 text-white shadow' : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <span>{p.label}</span>
                      {att !== undefined && att > 0 && <Badge tone="warn">{att}</Badge>}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {/* Default View: All Channels Cross-Channel ROI & Alerts */}
      {active === 'all' && (
        <div className="space-y-5">
          {alerts.length > 0 && (
            <Card className="!border-amber-500/30 space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                <AlertTriangle className="h-4 w-4" /> Today&apos;s Cross-Channel Alerts
              </div>
              <div className="flex flex-wrap gap-2">
                {alerts.map((al, idx) => (
                  <button
                    key={`${al.platform}-${idx}`}
                    type="button"
                    onClick={() => setActive(al.platform)}
                    className="text-left"
                  >
                    <Badge tone={al.tone}>{al.text}</Badge>
                  </button>
                ))}
              </div>
            </Card>
          )}

          <div className="grid gap-3 grid-cols-2 lg:grid-cols-5">
            <Stat label="Active Pipeline" value={usd(totals.valueOpen)} hint={`${totals.open} open across channels`} />
            <Stat label="Won Revenue" value={usd(totals.valueWon)} hint="closed won across channels" />
            <Stat label="Bid / Ad Spend" value={usd(totals.spend)} hint="Connects, Bids, Credits, Quotes" />
            <Stat label="Follow-ups Due" value={totals.due} hint={totals.due > 0 ? 'needs outreach today' : 'all caught up'} />
            <Stat label="Messages Waiting" value={totals.waiting} hint={totals.waiting > 0 ? 'reply to protect SLA' : 'inbox clear'} />
          </div>

          <Card className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Cross-Channel ROI Matrix</h3>
                <p className="text-xs text-slate-400">Click any channel row to open its native archetype workspace.</p>
              </div>
              <Badge tone="info">{rows.length} active channels</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-2 pr-3 font-medium">Channel</th>
                    <th className="py-2 px-3 font-medium">Archetype</th>
                    <th className="py-2 px-3 font-medium">Open</th>
                    <th className="py-2 px-3 font-medium">Active Pipeline</th>
                    <th className="py-2 px-3 font-medium">Won Revenue</th>
                    <th className="py-2 px-3 font-medium">Bid Spend</th>
                    <th className="py-2 px-3 font-medium">Net ROI %</th>
                    <th className="py-2 px-3 font-medium">Win Rate</th>
                    <th className="py-2 pl-3 font-medium">Avg Reply</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {rows.map((r) => (
                    <tr
                      key={r.platform}
                      onClick={() => setActive(r.platform)}
                      className="cursor-pointer transition-colors hover:bg-slate-800/50"
                    >
                      <td className="py-2.5 pr-3 font-semibold text-white">{r.label}</td>
                      <td className="py-2.5 px-3"><Badge tone="neutral">{r.archetype_label || r.kind}</Badge></td>
                      <td className="py-2.5 px-3 tabular text-slate-300">{r.open}</td>
                      <td className="py-2.5 px-3 tabular text-slate-200">{r.value_open ? usd(r.value_open) : '—'}</td>
                      <td className="py-2.5 px-3 tabular font-semibold text-emerald-400">{r.value_won ? usd(r.value_won) : '—'}</td>
                      <td className="py-2.5 px-3 tabular text-slate-300">{r.spend_usd ? `$${r.spend_usd.toFixed(2)}` : '—'}</td>
                      <td className="py-2.5 px-3 tabular">
                        {r.net_roi_pct != null && Number.isFinite(r.net_roi_pct) ? (
                          <Badge tone={r.net_roi_pct >= 0 ? 'good' : 'bad'}>{r.net_roi_pct}%</Badge>
                        ) : (r.value_won ?? 0) > 0 && !(r.spend_usd ?? 0) ? (
                          <Badge tone="good">Organic</Badge>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-2.5 px-3 tabular text-slate-300">{r.win_rate_percent != null ? `${r.win_rate_percent}%` : '—'}</td>
                      <td className="py-2.5 pl-3 tabular text-slate-400">{fmtMinutes(r.average_minutes ?? null)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {catalog.data && (
            <QuickLog
              key={quick ? `${quick.n}:${quick.text}` : 'empty'}
              catalog={catalog.data}
              onSaved={(p) => { setActive(p); setVersion((v) => v + 1); overview.reload(); }}
              seed={quick}
            />
          )}
        </div>
      )}

      {/* Specific Platform Archetype Workspace */}
      {active !== 'all' && current && catalog.data && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge tone="accent">{current.archetype_label}</Badge>
              {current.native_currency && (
                <Badge tone="info">
                  <Sparkles className="h-3 w-3 mr-1 inline" />
                  Currency: {current.native_currency.name} (${current.native_currency.unit_cost_usd.toFixed(2)}/unit)
                </Badge>
              )}
            </div>
            <Button small variant="ghost" onClick={() => setActive('all')}>
              ← Back to All Channels
            </Button>
          </div>
          <ChannelPanel
            key={`${current.id}:${version}`}
            platform={current}
            catalog={catalog.data}
            onOpenScraper={onOpenScraper}
            onOverviewDirty={overview.reload}
          />
        </div>
      )}
    </div>
  );
};
