import { useMemo, useState } from 'react';
import type { FC } from 'react';
import {
  Activity,
  Bell,
  Check,
  CheckSquare,
  Download,
  ExternalLink,
  Flame,
  Globe,
  Pause,
  Play,
  Plus,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Trash2,
  X,
  Zap,
} from 'lucide-react';
import { Badge, Button, Card, EmptyState, Pager, Select, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';

interface Search {
  id: number;
  name: string;
  source: string;
  params: Record<string, unknown>;
  notify: boolean;
  active: boolean;
  every_hours: number;
  last_run_at: string | null;
  last_status: string | null;
  last_detail: string | null;
  new_hits: number;
  total_hits?: number;
  kept_hits?: number;
  hit_rate_pct?: number;
  auto_play?: boolean;
  min_score_alert?: number;
  alert_mode?: 'instant' | 'digest';
  channels?: string[];
}

interface Hit {
  id: number;
  search_id?: number;
  search_name: string;
  search_source?: string;
  title: string;
  detail: string;
  url: string | null;
  status: 'new' | 'saved' | 'dismissed';
  lead_id: number | null;
  first_seen_at: string;
  score?: number;
  auto_domain?: string;
  company_name?: string;
  action_window?: string;
  multi_signal_count?: number;
}

interface Source {
  id: string;
  label: string;
  about: string;
  needs_key: string | null;
  ready: boolean;
}

interface Signal {
  id: string;
  label: string;
}

const CADENCE_OPTIONS = [
  { value: '1', label: 'Hourly' },
  { value: '6', label: 'Every 6h' },
  { value: '24', label: 'Daily' },
  { value: '72', label: 'Every 3d' },
  { value: '168', label: 'Weekly' },
];

const SOURCE_META: Record<string, { label: string; category: 'local' | 'jobs' | 'social' | 'tenders'; tone: 'accent' | 'good' | 'warn' | 'neutral' }> = {
  site_signals: { label: 'Local Territory', category: 'local', tone: 'warn' },
  new_companies: { label: 'Local / UK Reg', category: 'local', tone: 'warn' },
  new_companies_ie: { label: 'Local / IE Reg', category: 'local', tone: 'warn' },
  hiring: { label: 'Job Signal', category: 'jobs', tone: 'accent' },
  social_intent: { label: 'Social Intent', category: 'social', tone: 'good' },
  tender_cpv: { label: 'Tender / CPV', category: 'tenders', tone: 'neutral' },
};

const TEMPLATES = [
  {
    id: 'local_territory',
    label: 'Local Territory Monitor',
    desc: 'Expired SSLs, slow sites, missing mobile layout',
    source: 'site_signals',
    name: 'Local Site Pain Monitor',
    signals: ['certificate', 'slow', 'not_mobile'],
    every: 24,
  },
  {
    id: 'hiring_spree',
    label: 'Hiring-Spree & Stale Role Monitor',
    desc: 'Companies hiring React, Shopify, or Python pods',
    source: 'hiring',
    name: 'High-Intent Engineering Hiring',
    keywords: 'react, shopify, python, redesign',
    every: 6,
  },
  {
    id: 'competitor_radar',
    label: 'Competitor Complaint Radar',
    desc: 'Real-time social switching intent on HN, Reddit & Bluesky',
    source: 'social_intent',
    name: 'Competitor Switching Intent',
    q: '("wix" OR "webflow" OR "shopify") AND ("agency" OR "redesign" OR "slow")',
    every: 6,
  },
  {
    id: 'tender_cpv',
    label: 'Pre-Market Tender & CPV Watch',
    desc: 'New RFPs & PINs in IT / Digital Services',
    source: 'tender_cpv',
    name: 'Public IT & Digital Tenders',
    q: 'software',
    every: 24,
  },
];

const ago = (at: string | null) => {
  if (!at) return 'Pending first run';
  const m = Math.max(0, Math.round((Date.now() - new Date(at.replace(' ', 'T') + 'Z').getTime()) / 60000));
  return m < 1 ? 'Just now' : m < 60 ? `${m}m ago` : m < 1440 ? `${Math.round(m / 60)}h ago` : `${Math.round(m / 1440)}d ago`;
};

const nextScanIn = (at: string | null, everyHours: number) => {
  if (!at) return 'Ready now';
  const nextMs = new Date(at.replace(' ', 'T') + 'Z').getTime() + everyHours * 3_600_000;
  const mins = Math.round((nextMs - Date.now()) / 60000);
  if (mins <= 0) return 'Due now';
  if (mins < 60) return `Next in ${mins}m`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return `Next in ${hrs}h ${rem}m`;
};

const words = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);

export const LeadFinder: FC<{ onOpenClient: (leadId: number) => void; onAddKey: () => void }> = ({ onOpenClient, onAddKey }) => {
  const [inboxStatus, setInboxStatus] = useState<'new' | 'saved' | 'dismissed'>('new');
  const searches = useApi<{ searches: Search[] }>('/api/leadfinder/searches');
  const hits = useApi<{ hits: Hit[] }>(`/api/leadfinder/hits?status=${inboxStatus}`);
  const meta = useApi<{ sources: Source[]; signals: Signal[] }>('/api/leadfinder/sources');

  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [adding, setAdding] = useState(false);

  const [f, setF] = useState({
    source: 'hiring',
    name: '',
    keywords: '',
    q: '',
    days: '7',
    sic: '',
    location: '',
    signals: [] as string[],
    every: 6,
    notify: true,
    auto_play: false,
    min_score_alert: 85,
    alert_mode: 'instant' as 'instant' | 'digest',
  });

  // Inbox filters
  const [monitorFilter, setMonitorFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState<'all' | 'local' | 'jobs' | 'social' | 'tenders'>('all');
  const [minScore, setMinScore] = useState('0');
  const [checkedIds, setCheckedIds] = useState<Record<number, boolean>>({});
  const [hitsPage, setHitsPage] = useState(0);
  const HITS_PAGE_SIZE = 12;

  // Inspect slide-out drawer
  const [inspectHit, setInspectHit] = useState<Hit | null>(null);
  const [overrideSite, setOverrideSite] = useState('');

  const all = () => {
    searches.reload();
    hits.reload();
    setCheckedIds({});
  };

  const run = async (fn: () => Promise<unknown>) => {
    setError('');
    setNote('');
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const source = meta.data?.sources.find((s) => s.id === f.source);

  const buildParams = () => {
    const common = {
      auto_play: f.auto_play,
      min_score_alert: f.min_score_alert,
      alert_mode: f.alert_mode,
      channels: f.alert_mode === 'instant' ? ['Slack', 'Telegram', 'Email Digest'] : ['Daily 8:00 AM Digest'],
    };
    if (f.source === 'hiring') return { keywords: words(f.keywords), ...common };
    if (f.source === 'social_intent' || f.source === 'tender_cpv') return { q: f.q, ...common };
    if (f.source === 'new_companies' || f.source === 'new_companies_ie') {
      return { days: Number(f.days), sic_codes: words(f.sic), location: f.location, ...common };
    }
    return { signals: f.signals, ...common };
  };

  const applyTemplate = (tpl: (typeof TEMPLATES)[number]) => {
    setAdding(true);
    setF((prev) => ({
      ...prev,
      source: tpl.source,
      name: tpl.name,
      keywords: tpl.keywords || '',
      q: tpl.q || '',
      signals: tpl.signals || [],
      every: tpl.every,
    }));
  };

  const create = () =>
    run(async () => {
      const made = await send<Search>('/api/leadfinder/searches', 'POST', {
        name: f.name,
        source: f.source,
        params: buildParams(),
        notify: f.notify,
        every_hours: f.every,
      });
      const r = await send<{ total: number; new: number; auto_played?: number; status: string; detail: string }>(`/api/leadfinder/searches/${made.id}/run`);
      setNote(
        r.status === 'ok'
          ? `Monitor "${f.name}" active: ${r.total} matches (${r.new} new${r.auto_played ? `, ${r.auto_played} auto-played to CRM` : ''}).`
          : `Saved, but initial scan returned: ${r.detail}`,
      );
      setAdding(false);
      setF({ ...f, name: '', keywords: '', q: '', sic: '', location: '', signals: [] });
      all();
    });

  const runNow = (s: Search) =>
    run(async () => {
      const r = await send<{ total: number; new: number; auto_played?: number; status: string; detail: string }>(`/api/leadfinder/searches/${s.id}/run`);
      setNote(
        r.status === 'ok'
          ? `${s.name}: ${r.new} new, ${r.total} total${r.auto_played ? ` (${r.auto_played} auto-played)` : ''}.`
          : `${s.name}: ${r.detail}`,
      );
      all();
    });

  const saveHit = (h: Hit, manualWebsite?: string) =>
    run(async () => {
      const w = (manualWebsite || h.auto_domain || '').trim();
      const r = await send<{ lead_id: number | null }>(`/api/leadfinder/hits/${h.id}/save`, 'POST', w ? { website: w } : {});
      setNote(r.lead_id ? `${h.title} saved to Clients CRM.` : `${h.title} marked Kept.`);
      setInspectHit(null);
      setOverrideSite('');
      all();
    });

  const filteredHits = useMemo(() => {
    const raw = hits.data?.hits ?? [];
    const minS = Number(minScore || 0);
    return raw.filter((h) => {
      if (monitorFilter !== 'all' && h.search_name !== monitorFilter) return false;
      const cat = SOURCE_META[h.search_source || 'hiring']?.category || 'jobs';
      if (typeFilter !== 'all' && cat !== typeFilter) return false;
      if ((h.score ?? 0) < minS) return false;
      return true;
    });
  }, [hits.data?.hits, monitorFilter, typeFilter, minScore]);

  const selectedIds = Object.entries(checkedIds)
    .filter(([, v]) => v)
    .map(([k]) => Number(k));

  const bulkSave = () =>
    run(async () => {
      if (!selectedIds.length) return;
      const r = await send<{ saved: number }>('/api/leadfinder/hits/bulk-save', 'POST', { hit_ids: selectedIds });
      setNote(`Saved ${r.saved} selected signal(s) to Clients CRM.`);
      all();
    });

  const bulkDismiss = () =>
    run(async () => {
      if (!selectedIds.length) return;
      const r = await send<{ dismissed: number }>('/api/leadfinder/hits/bulk-dismiss', 'POST', { hit_ids: selectedIds });
      setNote(`Dismissed ${r.dismissed} selected signal(s).`);
      all();
    });

  const exportCsv = () => {
    const rows = selectedIds.length ? filteredHits.filter((h) => checkedIds[h.id]) : filteredHits;
    const header = ['Score', 'Monitor', 'Title', 'Company', 'Domain', 'ActionWindow', 'URL'];
    const lines = [header.join(',')].concat(
      rows.map((h) => [
        String(h.score ?? ''),
        `"${(h.search_name || '').replace(/"/g, '""')}"`,
        `"${(h.title || '').replace(/"/g, '""')}"`,
        `"${(h.company_name || '').replace(/"/g, '""')}"`,
        h.auto_domain || '',
        h.action_window || '',
        h.url || '',
      ].join(',')),
    );
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `signal-triage-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const searchList = searches.data?.searches ?? [];

  return (
    <div className="space-y-5">
      <ErrorBanner message={error || searches.error || hits.error} />
      {note && <p role="status" className="text-xs text-emerald-300 font-medium">{note}</p>}

      {/* Top Section: Active Signal Monitors Command Center */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Activity className="h-4 w-4 text-indigo-400" />
              Active Signal Monitors
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Automated Signal Monitors across Local Territory, Jobs, Social Intent &amp; Public Tenders with Alert Routing &amp; Auto-Play rules.
            </p>
          </div>
          <Button small variant="primary" onClick={() => setAdding((v) => !v)}>
            <Plus className="h-3.5 w-3.5" />
            New Monitor
          </Button>
        </div>

        {/* 1-Click Starter Templates */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2 mb-4">
          {TEMPLATES.map((tpl) => (
            <button
              key={tpl.id}
              type="button"
              onClick={() => applyTemplate(tpl)}
              className="text-left p-2.5 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-indigo-500/40 transition"
            >
              <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                <span className="truncate">{tpl.label}</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-1">{tpl.desc}</p>
            </button>
          ))}
        </div>

        {adding && (
          <form className="grid gap-3 mb-4 p-4 rounded-2xl border border-slate-800 bg-slate-900/40" onSubmit={(e) => { e.preventDefault(); create(); }}>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Monitor Source</label>
                <Select
                  value={f.source}
                  onChange={(v) => setF({ ...f, source: v })}
                  aria-label="Monitor source"
                  options={(meta.data?.sources ?? []).map((s) => ({ value: s.id, label: s.label }))}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Monitor Name</label>
                <input
                  className={field}
                  required
                  maxLength={80}
                  value={f.name}
                  onChange={(e) => setF({ ...f, name: e.target.value })}
                  placeholder="e.g. Shopify Redesign & Migration Signals"
                />
              </div>
            </div>

            {source && (
              <p className="text-xs text-slate-400">
                {source.about}
                {source.needs_key && !source.ready && (
                  <> Requires API key. <button type="button" className="text-indigo-400 hover:underline" onClick={onAddKey}>Configure in Settings</button>.</>
                )}
              </p>
            )}

            {f.source === 'hiring' && (
              <div>
                <label className="block text-xs text-slate-400 mb-1">Keywords (comma-separated)</label>
                <input className={field} required value={f.keywords} onChange={(e) => setF({ ...f, keywords: e.target.value })} placeholder="shopify, react, wordpress" />
              </div>
            )}

            {(f.source === 'social_intent' || f.source === 'tender_cpv') && (
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  {f.source === 'tender_cpv' ? 'CPV Code, Authority, or Keyword' : 'Boolean Query or Topic'}
                </label>
                <input
                  className={field}
                  value={f.q}
                  onChange={(e) => setF({ ...f, q: e.target.value })}
                  placeholder={f.source === 'tender_cpv' ? '72200000 or NHS' : '("shopify" OR "webflow") AND ("agency" OR "redesign")'}
                />
              </div>
            )}

            {(f.source === 'new_companies' || f.source === 'new_companies_ie') && (
              <div className="grid gap-2 sm:grid-cols-3">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Registered in last (days)</label>
                  <input className={field} type="number" min={1} max={30} value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">City / Region (optional)</label>
                  <input className={field} value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} placeholder="London" />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">SIC / NACE codes (optional)</label>
                  <input className={field} value={f.sic} onChange={(e) => setF({ ...f, sic: e.target.value })} placeholder="6201, 4791" />
                </div>
              </div>
            )}

            {f.source === 'site_signals' && (
              <fieldset className="grid gap-1.5 sm:grid-cols-2">
                <legend className="text-xs text-slate-400 mb-1">Trigger when audited site has:</legend>
                {(meta.data?.signals ?? []).map((s) => (
                  <label key={s.id} className="flex items-center gap-2 text-xs text-slate-200">
                    <input
                      type="checkbox"
                      checked={f.signals.includes(s.id)}
                      onChange={(e) => setF({ ...f, signals: e.target.checked ? [...f.signals, s.id] : f.signals.filter((v) => v !== s.id) })}
                    />
                    {s.label}
                  </label>
                ))}
              </fieldset>
            )}

            {/* Cadence, Alert Fatigue Threshold & Auto-Play Controls */}
            <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-800">
              <div className="w-36">
                <Select
                  small
                  value={String(f.every)}
                  onChange={(v) => setF({ ...f, every: Number(v) })}
                  aria-label="Scan cadence"
                  options={CADENCE_OPTIONS}
                />
              </div>
              <div className="w-48">
                <Select
                  small
                  value={f.alert_mode}
                  onChange={(v) => setF({ ...f, alert_mode: v as 'instant' | 'digest' })}
                  aria-label="Alert delivery mode"
                  options={[
                    { value: 'instant', label: `Instant if Score ≥ ${f.min_score_alert}` },
                    { value: 'digest', label: 'Daily 8:00 AM Digest' },
                  ]}
                />
              </div>
              <label className="flex items-center gap-1.5 text-xs text-slate-200 cursor-pointer">
                <input type="checkbox" checked={f.auto_play} onChange={(e) => setF({ ...f, auto_play: e.target.checked })} />
                <Zap className="h-3.5 w-3.5 text-amber-400" />
                Auto-Play: Save Score ≥ {f.min_score_alert} to Clients
              </label>
              <Button variant="primary" small type="submit" className="ml-auto">
                Activate &amp; Scan Now
              </Button>
            </div>
          </form>
        )}

        {searchList.length === 0 ? (
          <EmptyState title="No active monitors" hint="Pick a 1-click monitor template above to start automated signal tracking." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 text-slate-400">
                <tr>
                  <th className="py-2 pr-3">Monitor &amp; Source</th>
                  <th className="py-2 px-3">Cadence &amp; Next Run</th>
                  <th className="py-2 px-3">Alert Routing &amp; Play</th>
                  <th className="py-2 px-3">Signal Quality</th>
                  <th className="py-2 pl-3 text-right">Controls</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {searchList.map((s) => {
                  const sm = SOURCE_META[s.source] || { label: s.source, category: 'jobs', tone: 'neutral' as const };
                  return (
                    <tr key={s.id} className="hover:bg-slate-900/40">
                      <td className="py-2.5 pr-3">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-semibold text-white">{s.name}</span>
                          <Badge tone={sm.tone}>{sm.label}</Badge>
                          <Badge tone={s.active ? 'good' : 'neutral'}>{s.active ? 'Active' : 'Paused'}</Badge>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          Last scan: {ago(s.last_run_at)} {s.last_detail ? `· ${s.last_detail}` : ''}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <div className="w-28">
                          <Select
                            small
                            value={String(s.every_hours)}
                            onChange={(v) => run(async () => { await send(`/api/leadfinder/searches/${s.id}`, 'PUT', { every_hours: Number(v) }); searches.reload(); })}
                            aria-label={`Cadence for ${s.name}`}
                            options={CADENCE_OPTIONS}
                          />
                        </div>
                        <div className="text-[11px] text-slate-400 mt-1">{nextScanIn(s.last_run_at, s.every_hours)}</div>
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="flex flex-wrap items-center gap-1">
                          <Badge tone={s.alert_mode === 'instant' ? 'accent' : 'neutral'}>
                            <Bell className="h-3 w-3 mr-1 inline" />
                            {s.alert_mode === 'instant' ? `Instant ≥ ${s.min_score_alert ?? 80}` : 'Daily Digest'}
                          </Badge>
                          {s.auto_play && (
                            <Badge tone="good">
                              <Zap className="h-3 w-3 mr-0.5 inline" />
                              Auto-Play
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <div className="text-slate-200 font-medium">
                          {s.total_hits ?? 0} found · {s.kept_hits ?? 0} kept
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {s.hit_rate_pct ?? 0}% fit · {s.new_hits} unread
                        </div>
                      </td>
                      <td className="py-2.5 pl-3 text-right whitespace-nowrap">
                        <span className="inline-flex gap-1">
                          <Button small variant="ghost" onClick={() => runNow(s)} aria-label={`Scan now: ${s.name}`}>
                            <RefreshCw className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            small
                            variant="ghost"
                            onClick={() => run(async () => { await send(`/api/leadfinder/searches/${s.id}`, 'PUT', { active: !s.active }); searches.reload(); })}
                            aria-label={`${s.active ? 'Pause' : 'Resume'} ${s.name}`}
                          >
                            {s.active ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                          </Button>
                          <Button
                            small
                            variant="ghost"
                            onClick={() => run(async () => { await send(`/api/leadfinder/searches/${s.id}`, 'DELETE'); all(); })}
                            aria-label={`Delete ${s.name}`}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Main Section: Unified Signal Triage Inbox */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white">
              Unified Signal Triage Inbox ({filteredHits.length})
            </h2>
            <p className="text-xs text-slate-400">
              Cross-channel signals deduplicated and enriched with auto-resolved domains, decay windows &amp; multi-signal account stacking.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {selectedIds.length > 0 && (
              <>
                <Button small variant="primary" onClick={bulkSave}>
                  <CheckSquare className="h-3.5 w-3.5" />
                  Keep {selectedIds.length} to CRM
                </Button>
                <Button small variant="secondary" onClick={bulkDismiss}>
                  Dismiss {selectedIds.length}
                </Button>
              </>
            )}
            <Button small variant="secondary" onClick={exportCsv}>
              <Download className="h-3.5 w-3.5" />
              Export CSV
            </Button>
          </div>
        </div>

        {/* Inbox Filter & Triage Bar */}
        <div className="grid gap-2 sm:grid-cols-4 mb-4">
          <Select
            small
            value={inboxStatus}
            onChange={(v) => { setInboxStatus(v as 'new' | 'saved' | 'dismissed'); setHitsPage(0); }}
            aria-label="Triage status"
            options={[
              { value: 'new', label: 'Status: Unread' },
              { value: 'saved', label: 'Status: Kept to CRM' },
              { value: 'dismissed', label: 'Status: Dismissed' },
            ]}
          />
          <Select
            small
            value={typeFilter}
            onChange={(v) => { setTypeFilter(v as 'all' | 'local' | 'jobs' | 'social' | 'tenders'); setHitsPage(0); }}
            aria-label="Signal type"
            options={[
              { value: 'all', label: 'All Signal Types' },
              { value: 'local', label: 'Local Territory' },
              { value: 'jobs', label: 'Job Signals' },
              { value: 'social', label: 'Social Intent' },
              { value: 'tenders', label: 'Tenders / CPV' },
            ]}
          />
          <Select
            small
            value={monitorFilter}
            onChange={(v) => { setMonitorFilter(v); setHitsPage(0); }}
            aria-label="Filter by monitor"
            options={[
              { value: 'all', label: 'All Monitors' },
              ...searchList.map((s) => ({ value: s.name, label: s.name })),
            ]}
          />
          <Select
            small
            value={minScore}
            onChange={(v) => { setMinScore(v); setHitsPage(0); }}
            aria-label="Minimum score"
            options={[
              { value: '0', label: 'Score: All' },
              { value: '60', label: 'Score: 60+' },
              { value: '75', label: 'Score: 75+' },
              { value: '85', label: 'Score: 85+ (High Priority)' },
            ]}
          />
        </div>

        {filteredHits.length === 0 ? (
          <EmptyState title="No signals in this view" hint="Run a monitor above or adjust your status/score filters." />
        ) : (
          <>
            <div className="divide-y divide-slate-800/80">
              {filteredHits.slice(hitsPage * HITS_PAGE_SIZE, (hitsPage + 1) * HITS_PAGE_SIZE).map((h) => {
                const sm = SOURCE_META[h.search_source || 'hiring'] || { label: h.search_name, category: 'jobs', tone: 'neutral' as const };
                return (
                  <div key={h.id} className="py-3 flex flex-wrap items-start gap-3">
                    <input
                      type="checkbox"
                      checked={!!checkedIds[h.id]}
                      onChange={(e) => setCheckedIds((p) => ({ ...p, [h.id]: e.target.checked }))}
                      className="mt-1 rounded border-slate-700"
                      aria-label={`Select ${h.title}`}
                    />
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge tone={(h.score ?? 0) >= 80 ? 'good' : 'accent'}>{h.score ?? 72}/100</Badge>
                        <Badge tone={sm.tone}>{sm.label}</Badge>
                        {h.action_window && <Badge tone="neutral">{h.action_window}</Badge>}
                        {(h.multi_signal_count ?? 1) > 1 && (
                          <Badge tone="warn">
                            <Flame className="h-3 w-3 mr-0.5 inline" />
                            Multi-Signal Account ({h.multi_signal_count} triggers)
                          </Badge>
                        )}
                      </div>
                      <div className="text-sm font-semibold text-white">{h.title}</div>
                      <div className="text-xs text-slate-400 flex flex-wrap items-center gap-2">
                        {h.company_name && <span>{h.company_name}</span>}
                        {h.auto_domain && (
                          <span className="inline-flex items-center gap-1 text-indigo-300 font-medium">
                            <Globe className="h-3 w-3" />
                            {h.auto_domain}
                          </span>
                        )}
                        <span>· {h.search_name}</span>
                      </div>
                      <p className="text-xs text-slate-400 line-clamp-2">{h.detail}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                      <Button
                        small
                        variant="secondary"
                        onClick={() => { setInspectHit(h); setOverrideSite(h.auto_domain || ''); }}
                      >
                        Inspect
                      </Button>
                      {h.status !== 'saved' ? (
                        <Button small variant="primary" onClick={() => saveHit(h)}>
                          <Check className="h-3.5 w-3.5" />
                          Keep to CRM
                        </Button>
                      ) : h.lead_id ? (
                        <Button small variant="secondary" onClick={() => onOpenClient(h.lead_id!)}>
                          Open Client
                        </Button>
                      ) : null}
                      {h.status === 'new' && (
                        <Button
                          small
                          variant="ghost"
                          onClick={() => run(async () => { await send(`/api/leadfinder/hits/${h.id}/dismiss`); all(); })}
                          aria-label={`Dismiss ${h.title}`}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            <Pager page={hitsPage} pageSize={HITS_PAGE_SIZE} total={filteredHits.length} onPage={setHitsPage} />
          </>
        )}
      </Card>

      {/* Signal Inspection Slide-Out Drawer */}
      {inspectHit && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-slate-950 border-l border-slate-800 h-full overflow-y-auto p-6 space-y-4 shadow-2xl">
            <div className="flex items-start justify-between gap-2">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone="good">{inspectHit.score ?? 72}/100</Badge>
                  <Badge>{inspectHit.search_name}</Badge>
                  {inspectHit.action_window && <Badge tone="warn">{inspectHit.action_window}</Badge>}
                </div>
                <h3 className="text-base font-semibold text-white">{inspectHit.title}</h3>
              </div>
              <button
                type="button"
                onClick={() => setInspectHit(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white"
                aria-label="Close inspector"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
              {inspectHit.detail}
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Auto-Resolved Company Domain (optional override)</label>
              <input
                className={field}
                value={overrideSite}
                onChange={(e) => setOverrideSite(e.target.value)}
                placeholder="example.com"
              />
            </div>

            {(inspectHit.multi_signal_count ?? 1) > 1 && (
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 flex items-start gap-2">
                <ShieldAlert className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <span>
                  <strong>Multi-Signal Account:</strong> This company triggered {inspectHit.multi_signal_count} separate signals in your inbox. Prioritize outreach immediately.
                </span>
              </div>
            )}

            <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
              {inspectHit.url && (
                <a
                  href={inspectHit.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-800 hover:bg-slate-700 text-white"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  Open Source
                </a>
              )}
              <Button small variant="primary" onClick={() => saveHit(inspectHit, overrideSite)}>
                <Check className="h-3.5 w-3.5" />
                Keep to Clients CRM
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
