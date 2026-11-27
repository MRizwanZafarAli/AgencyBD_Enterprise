import { useMemo, useState } from 'react';
import type { FC, FormEvent } from 'react';
import {
  AlertTriangle,
  Archive,
  ArrowRight,
  Check,
  CheckSquare,
  Download,
  Globe,
  Inbox,
  LayoutGrid,
  LayoutList,
  Mail,
  Plus,
  Sparkles,
  Trash2,
  Trophy,
  User,
  X,
  XCircle,
} from 'lucide-react';
import { FollowupsPanel } from './FollowupsPanel';
import { ChasePanel } from './ChasePanel';
import { Badge, Button, Card, EmptyState, Select, Skeletons, Stat, SuggestInput, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { apiFetch } from '../../lib/api';
import { send, useApi } from '../../lib/hooks';

interface Deal {
  id: number;
  company_name: string;
  domain: string;
  deal_value: number | null;
  pitch_angle: string | null;
  source_channel: string | null;
  phone: string | null;
  primary_contact?: string | null;
  contact_email?: string | null;
  stage_id?: string;
  days_idle?: number;
  is_rotting?: boolean;
  deal_stage?: string;
}

interface Pipeline {
  active_deals_count: number;
  won_deals_count: number;
  lost_deals_count: number;
  unvalued_deals_count: number;
  total_pipeline_value: number;
  weighted_projected_revenue: number;
  win_rate_percent: number | null;
  projection_note: string;
  stages: Record<string, { count: number; value?: number; win_rate?: number; leads: Deal[]; truncated?: boolean }>;
}

interface HygieneReport {
  duplicates: Array<{ domain: string; records: Array<{ id: number; company_name: string; domain: string; status: string }> }>;
  junk: Array<{ id: number; company_name: string; domain: string; reason: string }>;
  unvalued_count: number;
}

const ACTIVE_STAGES: Array<{ id: string; label: string; prob: number; tone: 'neutral' | 'info' | 'accent' | 'warn' | 'ai' | 'good' | 'bad' }> = [
  { id: 'audited', label: 'Audited', prob: 25, tone: 'info' },
  { id: 'sequence_active', label: 'In outreach', prob: 40, tone: 'accent' },
  { id: 'meeting_booked', label: 'Meeting', prob: 65, tone: 'warn' },
  { id: 'proposal_sent', label: 'Proposal sent', prob: 80, tone: 'ai' },
  { id: 'won', label: 'Won', prob: 100, tone: 'good' },
];

const ALL_STAGES = [
  { id: 'sourced', label: 'Leads Inbox', prob: 10, tone: 'neutral' as const },
  ...ACTIVE_STAGES,
  { id: 'lost', label: 'Lost', prob: 0, tone: 'bad' as const },
];

const SOURCE_LABELS: Record<string, { label: string; tone: 'good' | 'warn' | 'accent' | 'info' | 'neutral' }> = {
  map_osm: { label: 'Local Maps', tone: 'good' },
  local: { label: 'Local Maps', tone: 'good' },
  local_hunt: { label: 'Local Maps', tone: 'good' },
  social_hacker_news: { label: 'Hacker News', tone: 'warn' },
  social_reddit: { label: 'Reddit', tone: 'warn' },
  social_bluesky: { label: 'Bluesky', tone: 'info' },
  social_bulk_radar: { label: 'Social Intent', tone: 'warn' },
  sales_nav_companion: { label: 'LinkedIn', tone: 'accent' },
  hiring_intent: { label: 'Job Signal', tone: 'info' },
  opportunity: { label: 'Job Signal', tone: 'info' },
  inbound_webhook: { label: 'Inbound', tone: 'good' },
  lead_finder: { label: 'Watching', tone: 'accent' },
  tender: { label: 'Public Tender', tone: 'neutral' },
  crm_pipeline: { label: 'Manual', tone: 'neutral' },
};

function formatSource(ch?: string | null) {
  if (!ch) return { label: 'Direct', tone: 'neutral' as const };
  const exact = SOURCE_LABELS[ch.toLowerCase()];
  if (exact) return exact;
  if (ch.startsWith('social_')) return { label: ch.replace('social_', '').replace(/_/g, ' '), tone: 'warn' as const };
  return { label: ch.replace(/_/g, ' '), tone: 'neutral' as const };
}

export const PipelineBoard: FC<{
  onOpen: (leadId: number) => void;
  onSendEmail?: (params: { recipient: string; recipientName?: string; companyName?: string; subject?: string; body?: string; leadId?: number }) => void;
}> = ({ onOpen, onSendEmail }) => {
  const pipe = useApi<Pipeline>('/api/pipeline/deals');
  const [view, setView] = useState<'board' | 'table' | 'inbox'>('board');
  const [savedFilter, setSavedFilter] = useState<'all' | 'rotting' | 'unvalued' | 'high' | 'closed'>('all');
  const [channelFilter, setChannelFilter] = useState('all');
  const [find, setFind] = useState('');
  const [sort, setSort] = useState<'recent' | 'value' | 'name'>('recent');

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ company_name: '', domain: '', deal_value: '', notes: '' });

  // Inline Value Editing
  const [editingValId, setEditingValId] = useState<number | null>(null);
  const [editingValText, setEditingValText] = useState('');

  // Drag & Drop state
  const [draggingId, setDraggingId] = useState<number | null>(null);

  // Bulk Selection state
  const [selectedIds, setSelectedIds] = useState<Record<number, boolean>>({});
  const [bulkStage, setBulkStage] = useState('audited');

  // Smart Clean Data Modal
  const [hygieneOpen, setHygieneOpen] = useState(false);
  const [hygiene, setHygiene] = useState<HygieneReport | null>(null);
  const [hygieneLoading, setHygieneLoading] = useState(false);

  const d = pipe.data;
  const inboxLeads = d?.stages?.sourced?.leads ?? [];

  const move = async (id: number, stage: string) => {
    setError('');
    try {
      await send('/api/pipeline/deals/stage', 'POST', { lead_id: id, new_stage: stage });
      pipe.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not move client');
    }
  };

  const saveInlineValue = async (id: number) => {
    const num = editingValText.trim() ? Number(editingValText.replace(/[^0-9.]/g, '')) : null;
    setEditingValId(null);
    if (num !== null && Number.isNaN(num)) return;
    try {
      await send(`/api/pipeline/deals/${id}/value`, 'POST', { deal_value: num });
      pipe.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update deal value');
    }
  };

  const deleteLead = async (id: number, name: string) => {
    if (!window.confirm(`Remove "${name}" from your CRM?`)) return;
    try {
      await send(`/api/pipeline/deals/${id}`, 'DELETE');
      setSuccess(`Removed "${name}".`);
      pipe.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete lead');
    }
  };

  const openHygieneModal = async () => {
    setHygieneOpen(true);
    setHygieneLoading(true);
    try {
      const res = await apiFetch('/api/pipeline/deals/hygiene');
      if (res.ok) setHygiene(await res.json());
    } finally {
      setHygieneLoading(false);
    }
  };

  const purgeJunk = async () => {
    const res = await send<{ deleted_count: number }>('/api/pipeline/deals/clean_junk', 'POST');
    setSuccess(`Purged ${res.deleted_count} synthetic/junk records.`);
    pipe.reload();
    openHygieneModal();
  };

  const mergeDuplicate = async (keepId: number, removeId: number) => {
    await send('/api/pipeline/deals/merge', 'POST', { keep_id: keepId, remove_id: removeId });
    setSuccess('Merged duplicate records.');
    pipe.reload();
    openHygieneModal();
  };

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await send('/api/pipeline/deals/create', 'POST', {
        company_name: form.company_name,
        domain: form.domain,
        notes: form.notes || undefined,
        stage: 'audited',
        ...(form.deal_value ? { deal_value: Number(form.deal_value) } : {}),
      });
      setForm({ company_name: '', domain: '', deal_value: '', notes: '' });
      setAdding(false);
      pipe.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add client');
    }
  };

  const checkedList = Object.entries(selectedIds).filter(([, v]) => v).map(([k]) => Number(k));

  const runBulkAction = async (action: 'stage' | 'delete') => {
    if (!checkedList.length) return;
    if (action === 'delete' && !window.confirm(`Delete ${checkedList.length} selected leads?`)) return;
    await send('/api/pipeline/deals/bulk', 'POST', {
      lead_ids: checkedList,
      action,
      stage: action === 'stage' ? bulkStage : undefined,
    });
    setSelectedIds({});
    setSuccess(action === 'delete' ? `Deleted ${checkedList.length} leads.` : `Moved ${checkedList.length} leads.`);
    pipe.reload();
  };

  const matchDeal = (l: Deal) => {
    if (channelFilter !== 'all' && formatSource(l.source_channel).label !== channelFilter) return false;
    if (!find.trim()) return true;
    return `${l.company_name} ${l.domain} ${l.primary_contact || ''}`.toLowerCase().includes(find.trim().toLowerCase());
  };

  const sortDeals = (arr: Deal[]) =>
    [...arr].sort((a, b) =>
      sort === 'value' ? (b.deal_value ?? 0) - (a.deal_value ?? 0) : sort === 'name' ? a.company_name.localeCompare(b.company_name) : 0,
    );

  const allTableLeads = useMemo(() => {
    if (!d) return [];
    const list = ALL_STAGES.flatMap((s) => (d.stages[s.id]?.leads ?? []).map((l) => ({ ...l, stage_id: s.id, stage_label: s.label })));
    return sortDeals(
      list.filter((l) => {
        if (!matchDeal(l)) return false;
        if (savedFilter === 'rotting') return !!l.is_rotting;
        if (savedFilter === 'unvalued') return l.deal_value == null;
        if (savedFilter === 'high') return (l.deal_value ?? 0) >= 5000;
        if (savedFilter === 'closed') return l.stage_id === 'won' || l.stage_id === 'lost';
        return l.stage_id !== 'lost' && l.stage_id !== 'won';
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d, savedFilter, channelFilter, find, sort]);

  const channelsList = useMemo(() => {
    if (!d) return [];
    const set = new Set<string>();
    Object.values(d.stages).forEach((s) => s.leads.forEach((l) => set.add(formatSource(l.source_channel).label)));
    return Array.from(set).sort();
  }, [d]);

  const names = d ? Object.values(d.stages).flatMap((s) => s.leads.map((l) => l.company_name)) : [];

  const exportCsv = () => {
    if (!d) return;
    const q = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const rows = [
      ['Company', 'Website', 'Contact', 'Stage', 'Value', 'Source', 'DaysIdle'],
      ...ALL_STAGES.flatMap((s) =>
        (d.stages[s.id]?.leads ?? []).map((l) => [
          l.company_name,
          l.domain,
          l.primary_contact || '',
          s.label,
          l.deal_value,
          formatSource(l.source_channel).label,
          l.days_idle ?? 0,
        ]),
      ),
    ];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([rows.map((r) => r.map(q).join(',')).join('\n')], { type: 'text/csv' }));
    a.download = 'clients-pipeline.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="space-y-4">
      {/* Top KPI Bar */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
        <Stat label="Active Pipeline" value={d ? `$${Math.round(d.total_pipeline_value).toLocaleString()}` : '…'} hint={`${d?.active_deals_count ?? 0} total records`} />
        <Stat label="Weighted Forecast" value={d ? `$${Math.round(d.weighted_projected_revenue).toLocaleString()}` : '…'} hint="Stage-probability adjusted" />
        <Stat label="Leads Inbox" value={inboxLeads.length} hint="Unqualified scrapes to triage" />
        <Stat label="Missing Value" value={d?.unvalued_deals_count ?? '…'} hint="Click any deal value to edit inline" />
      </div>

      {/* Single-Row Enterprise Toolbar */}
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex items-center bg-slate-900 border border-slate-800 rounded-xl p-1">
          <button
            type="button"
            onClick={() => setView('board')}
            className={`px-3 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${view === 'board' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            <LayoutGrid className="h-3.5 w-3.5" /> Kanban
          </button>
          <button
            type="button"
            onClick={() => setView('table')}
            className={`px-3 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${view === 'table' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            <LayoutList className="h-3.5 w-3.5" /> List
          </button>
          <button
            type="button"
            onClick={() => setView('inbox')}
            className={`px-3 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${view === 'inbox' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            <Inbox className="h-3.5 w-3.5" /> Leads Inbox ({inboxLeads.length})
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2 flex-1 max-w-2xl">
          <div className="flex-1 min-w-44">
            <SuggestInput
              value={find}
              onChange={setFind}
              options={names}
              placeholder="Search company, domain, or contact…"
              aria-label="Search clients"
            />
          </div>
          <div className="w-36">
            <Select
              small
              value={channelFilter}
              onChange={setChannelFilter}
              aria-label="Filter by source"
              options={[{ value: 'all', label: 'All Sources' }, ...channelsList.map((c) => ({ value: c, label: c }))]}
            />
          </div>
          <div className="w-32">
            <Select
              small
              value={sort}
              onChange={(v) => setSort(v as 'recent' | 'value' | 'name')}
              aria-label="Sort deals"
              options={[
                { value: 'recent', label: 'Newest' },
                { value: 'value', label: 'Value ($)' },
                { value: 'name', label: 'Name (A-Z)' },
              ]}
            />
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button small variant="secondary" onClick={openHygieneModal}>
            <Sparkles className="h-3.5 w-3.5 text-purple-400" />
            Smart Clean Data
          </Button>
          <Button small variant="secondary" onClick={exportCsv}>
            <Download className="h-3.5 w-3.5" />
            CSV
          </Button>
          <Button small variant="primary" onClick={() => setAdding((v) => !v)}>
            <Plus className="h-3.5 w-3.5" />
            Add Client
          </Button>
        </div>
      </div>

      <ErrorBanner message={error || pipe.error} />
      {success && <p className="text-xs text-emerald-300 font-medium">{success}</p>}

      {adding && (
        <Card>
          <form onSubmit={add} className="grid gap-3 sm:grid-cols-4 items-end">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Company *</label>
              <input className={field} required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} placeholder="Acme Dental" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Website *</label>
              <input className={field} required value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} placeholder="acmedental.com" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Deal Value ($)</label>
              <input className={field} type="number" min={0} value={form.deal_value} onChange={(e) => setForm({ ...form, deal_value: e.target.value })} placeholder="5000" />
            </div>
            <div className="flex gap-2">
              <Button variant="primary" type="submit">Create Deal</Button>
              <Button variant="ghost" type="button" onClick={() => setAdding(false)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {pipe.loading && !d ? (
        <Skeletons rows={6} />
      ) : !d || d.active_deals_count === 0 ? (
        <Card><EmptyState title="No deals in pipeline" hint="Save prospects from Find or click Add Client above." /></Card>
      ) : view === 'inbox' ? (
        /* Leads Inbox (Separated from Active Revenue Pipeline) */
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Leads Triage Inbox ({inboxLeads.length})</h2>
              <p className="text-xs text-slate-400">Newly scraped prospects sit here before entering your revenue forecast. Qualify real buyers to move them into Audited.</p>
            </div>
          </div>
          {inboxLeads.length === 0 ? (
            <EmptyState title="Leads Inbox is clear" hint="New leads captured from Find or Browser Sidepanel appear here." />
          ) : (
            <div className="divide-y divide-slate-800/80">
              {sortDeals(inboxLeads.filter(matchDeal)).map((l) => {
                const src = formatSource(l.source_channel);
                return (
                  <div key={l.id} className="py-3 flex flex-wrap items-center justify-between gap-3 text-xs">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <button type="button" onClick={() => onOpen(l.id)} className="font-semibold text-white hover:text-indigo-300 text-left">
                          {l.company_name}
                        </button>
                        <Badge tone={src.tone}>{src.label}</Badge>
                        {l.is_rotting && <Badge tone="bad">Idle {l.days_idle}d</Badge>}
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5 flex flex-wrap gap-2">
                        <span>{l.domain}</span>
                        {l.primary_contact ? <span className="text-slate-300">· {l.primary_contact}</span> : <span className="text-amber-300">· No contact yet</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button small variant="primary" onClick={() => move(l.id, 'audited')}>
                        <Check className="h-3.5 w-3.5" /> Qualify to Deal
                      </Button>
                      <Button small variant="ghost" onClick={() => deleteLead(l.id, l.company_name)} aria-label={`Delete ${l.company_name}`}>
                        <Trash2 className="h-3.5 w-3.5 text-rose-400" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      ) : view === 'board' ? (
        /* Kanban Board with Independent Column Scrolling + Sticky Headers + Drag-and-Drop */
        <div className="relative">
          <div className="grid gap-3 grid-cols-1 md:grid-cols-3 lg:grid-cols-5 h-[calc(100vh-330px)] min-h-[460px]">
            {ACTIVE_STAGES.map((st) => {
              const bucket = d.stages[st.id] ?? { count: 0, leads: [] };
              const leads = sortDeals(bucket.leads.filter(matchDeal));
              const colTotal = leads.reduce((sum, x) => sum + (x.deal_value || 0), 0);
              return (
                <div
                  key={st.id}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => {
                    if (draggingId) {
                      move(draggingId, st.id);
                      setDraggingId(null);
                    }
                  }}
                  className="bento-tile rounded-2xl flex flex-col min-h-0 overflow-hidden border border-slate-800"
                >
                  {/* Sticky Column Header */}
                  <div className="p-3 border-b border-slate-800/80 bg-slate-900/95 sticky top-0 z-10 shrink-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-xs font-semibold text-white">{st.label}</span>
                      <Badge tone={st.tone}>{leads.length}</Badge>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between">
                      <span className="font-semibold text-emerald-400">${Math.round(colTotal).toLocaleString()}</span>
                      <span>{st.prob}% prob</span>
                    </div>
                  </div>

                  {/* Independent Scrollable Cards */}
                  <div className="p-2.5 space-y-2 overflow-y-auto flex-1">
                    {leads.length === 0 ? (
                      <p className="text-[11px] text-slate-500 text-center py-6">Drop deals here</p>
                    ) : (
                      leads.map((l) => {
                        const src = formatSource(l.source_channel);
                        return (
                          <div
                            key={l.id}
                            draggable
                            onDragStart={() => setDraggingId(l.id)}
                            onDragEnd={() => setDraggingId(null)}
                            className={`p-3 rounded-xl border bg-slate-950/60 hover:border-indigo-500/40 cursor-grab active:cursor-grabbing transition space-y-1.5 ${
                              l.is_rotting ? 'border-rose-500/40' : 'border-slate-800'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-1.5">
                              <button type="button" onClick={() => onOpen(l.id)} className="text-xs font-semibold text-white hover:text-indigo-300 text-left line-clamp-1">
                                {l.company_name}
                              </button>
                              <Badge tone={src.tone}>{src.label}</Badge>
                            </div>
                            <div className="text-[11px] text-slate-400 flex items-center gap-1 truncate">
                              <Globe className="h-3 w-3 shrink-0" />
                              <span className="truncate">{l.domain}</span>
                            </div>
                            <div className="text-[11px] flex items-center gap-1 text-slate-300">
                              <User className="h-3 w-3 text-slate-400 shrink-0" />
                              {l.primary_contact ? (
                                <span className="truncate">{l.primary_contact}</span>
                              ) : (
                                <button type="button" onClick={() => onOpen(l.id)} className="text-amber-300 hover:underline">
                                  No contact — Enrich
                                </button>
                              )}
                            </div>

                            <div className="flex items-center justify-between gap-2 pt-1 border-t border-slate-800/70">
                              {editingValId === l.id ? (
                                <input
                                  autoFocus
                                  className="w-24 bg-slate-900 border border-indigo-500 rounded px-1.5 py-0.5 text-xs text-white"
                                  value={editingValText}
                                  onChange={(e) => setEditingValText(e.target.value)}
                                  onBlur={() => saveInlineValue(l.id)}
                                  onKeyDown={(e) => e.key === 'Enter' && saveInlineValue(l.id)}
                                />
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => { setEditingValId(l.id); setEditingValText(l.deal_value ? String(l.deal_value) : ''); }}
                                  className="text-xs font-semibold text-emerald-400 hover:underline"
                                  title="Click to edit deal value"
                                >
                                  {l.deal_value ? `$${l.deal_value.toLocaleString()}` : '+ Set $ Value'}
                                </button>
                              )}

                              {l.is_rotting ? (
                                <span className="text-[10px] font-medium text-rose-300 flex items-center gap-0.5">
                                  <AlertTriangle className="h-3 w-3" /> Rotting {l.days_idle}d
                                </span>
                              ) : (
                                <span className="text-[10px] text-slate-500">Idle {l.days_idle ?? 0}d</span>
                              )}
                            </div>

                            {l.is_rotting && onSendEmail && (
                              <button
                                type="button"
                                onClick={() => onSendEmail({
                                  recipient: l.contact_email || '',
                                  recipientName: l.primary_contact || '',
                                  companyName: l.company_name,
                                  subject: `Quick follow-up — ${l.company_name}`,
                                  leadId: l.id,
                                })}
                                className="w-full text-[11px] py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/25 font-medium"
                              >
                                Draft Bump Follow-Up
                              </button>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Bottom Won / Lost / Delete Drop Zones when dragging */}
          {draggingId && (
            <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 p-2.5 rounded-2xl bg-slate-950/95 border border-slate-700 shadow-2xl">
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => { move(draggingId, 'won'); setDraggingId(null); }}
                className="px-5 py-2.5 rounded-xl border-2 border-dashed border-emerald-500/60 bg-emerald-500/15 text-emerald-300 text-xs font-semibold flex items-center gap-1.5"
              >
                <Trophy className="h-4 w-4" /> Drop to Mark Won
              </div>
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => { move(draggingId, 'lost'); setDraggingId(null); }}
                className="px-5 py-2.5 rounded-xl border-2 border-dashed border-amber-500/60 bg-amber-500/15 text-amber-300 text-xs font-semibold flex items-center gap-1.5"
              >
                <XCircle className="h-4 w-4" /> Drop to Mark Lost
              </div>
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => { deleteLead(draggingId, 'selected deal'); setDraggingId(null); }}
                className="px-5 py-2.5 rounded-xl border-2 border-dashed border-rose-500/60 bg-rose-500/15 text-rose-300 text-xs font-semibold flex items-center gap-1.5"
              >
                <Archive className="h-4 w-4" /> Drop to Delete
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Upgraded List View with Saved Views, Bulk Actions & Inline Value Edit */
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex flex-wrap gap-1.5">
              {(
                [
                  ['all', 'All Active'],
                  ['rotting', 'Rotting (7d+)'],
                  ['unvalued', 'Missing Value'],
                  ['high', 'High Value ($5k+)'],
                  ['closed', 'Won / Lost'],
                ] as const
              ).map(([id, lbl]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setSavedFilter(id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                    savedFilter === id ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-slate-900/70 border-slate-800 text-slate-300'
                  }`}
                >
                  {lbl}
                </button>
              ))}
            </div>

            {checkedList.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <div className="w-36">
                  <Select
                    small
                    value={bulkStage}
                    onChange={setBulkStage}
                    aria-label="Bulk target stage"
                    options={ALL_STAGES.map((s) => ({ value: s.id, label: s.label }))}
                  />
                </div>
                <Button small variant="primary" onClick={() => runBulkAction('stage')}>
                  <CheckSquare className="h-3.5 w-3.5" /> Move ({checkedList.length})
                </Button>
                <Button small variant="danger" onClick={() => runBulkAction('delete')}>
                  Delete ({checkedList.length})
                </Button>
              </div>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 text-slate-400">
                <tr>
                  <th className="py-2 pr-2 w-8">
                    <input
                      type="checkbox"
                      checked={allTableLeads.length > 0 && checkedList.length === allTableLeads.length}
                      onChange={(e) => {
                        const next: Record<number, boolean> = {};
                        if (e.target.checked) allTableLeads.forEach((l) => { next[l.id] = true; });
                        setSelectedIds(next);
                      }}
                      aria-label="Select all deals"
                    />
                  </th>
                  <th className="py-2 px-2">Company &amp; Domain</th>
                  <th className="py-2 px-2">Primary Contact</th>
                  <th className="py-2 px-2">Stage</th>
                  <th className="py-2 px-2">Deal Value</th>
                  <th className="py-2 px-2">Activity</th>
                  <th className="py-2 px-2">Source</th>
                  <th className="py-2 pl-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {allTableLeads.map((l) => {
                  const src = formatSource(l.source_channel);
                  return (
                    <tr key={l.id} className="hover:bg-slate-900/40">
                      <td className="py-2.5 pr-2">
                        <input
                          type="checkbox"
                          checked={!!selectedIds[l.id]}
                          onChange={(e) => setSelectedIds((p) => ({ ...p, [l.id]: e.target.checked }))}
                          aria-label={`Select ${l.company_name}`}
                        />
                      </td>
                      <td className="py-2.5 px-2">
                        <button type="button" onClick={() => onOpen(l.id)} className="font-semibold text-white hover:text-indigo-300 text-left">
                          {l.company_name}
                        </button>
                        <div className="text-[11px] text-slate-400">{l.domain}</div>
                      </td>
                      <td className="py-2.5 px-2">
                        {l.primary_contact ? (
                          <div>
                            <div className="text-slate-200">{l.primary_contact}</div>
                            {l.contact_email && <div className="text-[11px] text-slate-400">{l.contact_email}</div>}
                          </div>
                        ) : (
                          <span className="text-amber-300">No contact</span>
                        )}
                      </td>
                      <td className="py-2.5 px-2">
                        <div className="w-32">
                          <Select
                            small
                            value={l.stage_id ?? 'sourced'}
                            onChange={(v) => move(l.id, v)}
                            aria-label={`Stage for ${l.company_name}`}
                            options={ALL_STAGES.map((s) => ({ value: s.id, label: s.label }))}
                          />
                        </div>
                      </td>
                      <td className="py-2.5 px-2 whitespace-nowrap">
                        {editingValId === l.id ? (
                          <input
                            autoFocus
                            className="w-24 bg-slate-900 border border-indigo-500 rounded px-2 py-1 text-xs text-white"
                            value={editingValText}
                            onChange={(e) => setEditingValText(e.target.value)}
                            onBlur={() => saveInlineValue(l.id)}
                            onKeyDown={(e) => e.key === 'Enter' && saveInlineValue(l.id)}
                          />
                        ) : (
                          <button
                            type="button"
                            onClick={() => { setEditingValId(l.id); setEditingValText(l.deal_value ? String(l.deal_value) : ''); }}
                            className="font-semibold text-emerald-400 hover:underline"
                          >
                            {l.deal_value ? `$${l.deal_value.toLocaleString()}` : '+ Set Value'}
                          </button>
                        )}
                      </td>
                      <td className="py-2.5 px-2 whitespace-nowrap">
                        {l.is_rotting ? (
                          <Badge tone="bad">Rotting {l.days_idle}d</Badge>
                        ) : (
                          <span className="text-slate-400">Idle {l.days_idle ?? 0}d</span>
                        )}
                      </td>
                      <td className="py-2.5 px-2 whitespace-nowrap">
                        <Badge tone={src.tone}>{src.label}</Badge>
                      </td>
                      <td className="py-2.5 pl-2 text-right whitespace-nowrap">
                        <div className="inline-flex items-center gap-1">
                          <Button small variant="secondary" onClick={() => onOpen(l.id)}>
                            Dossier <ArrowRight className="h-3 w-3" />
                          </Button>
                          {onSendEmail && l.contact_email && (
                            <Button
                              small
                              variant="ghost"
                              onClick={() => onSendEmail({ recipient: l.contact_email!, recipientName: l.primary_contact || '', companyName: l.company_name, leadId: l.id })}
                              aria-label={`Email ${l.company_name}`}
                            >
                              <Mail className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <FollowupsPanel onOpenClient={onOpen} />
        <ChasePanel onOpenClient={onOpen} />
      </div>

      {/* Smart Clean Data (AI Hygiene & Dedupe Modal) */}
      {hygieneOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <Card className="w-full max-w-2xl max-h-[85vh] overflow-y-auto space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-purple-400" />
                Smart Clean Data &amp; CRM Hygiene
              </h3>
              <button type="button" onClick={() => setHygieneOpen(false)} className="text-slate-400 hover:text-white" aria-label="Close hygiene modal">
                <X className="h-5 w-5" />
              </button>
            </div>
            {hygieneLoading ? (
              <p className="text-xs text-slate-400">Scanning CRM for duplicates, synthetic domains &amp; missing deal values…</p>
            ) : hygiene ? (
              <div className="space-y-4 text-xs">
                <div className="p-3 rounded-xl border border-slate-800 bg-slate-900/60 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white">Non-Company / Test Records ({hygiene.junk.length})</span>
                    {hygiene.junk.length > 0 && (
                      <Button small variant="danger" onClick={purgeJunk}>Purge All Junk</Button>
                    )}
                  </div>
                  {hygiene.junk.length === 0 ? (
                    <p className="text-slate-400">No synthetic `.local` domains or raw social questions found.</p>
                  ) : (
                    hygiene.junk.slice(0, 8).map((j) => (
                      <div key={j.id} className="text-slate-300 flex justify-between gap-2">
                        <span className="truncate">{j.company_name} ({j.domain})</span>
                        <Badge tone="bad">{j.reason}</Badge>
                      </div>
                    ))
                  )}
                </div>

                <div className="p-3 rounded-xl border border-slate-800 bg-slate-900/60 space-y-2">
                  <span className="font-semibold text-white block">Duplicate Domains ({hygiene.duplicates.length})</span>
                  {hygiene.duplicates.length === 0 ? (
                    <p className="text-slate-400">No duplicate domains detected.</p>
                  ) : (
                    hygiene.duplicates.map((dup) => (
                      <div key={dup.domain} className="flex items-center justify-between gap-2 border-t border-slate-800 pt-2">
                        <span className="text-white">{dup.domain} ({dup.records.length} records)</span>
                        <Button small variant="primary" onClick={() => mergeDuplicate(dup.records[0].id, dup.records[1].id)}>
                          Merge into #{dup.records[0].id}
                        </Button>
                      </div>
                    ))
                  )}
                </div>

                <div className="p-3 rounded-xl border border-slate-800 bg-slate-900/60">
                  <span className="font-semibold text-white block">Missing Deal Values: {hygiene.unvalued_count}</span>
                  <p className="text-slate-400 mt-0.5">Use the inline <strong>+ Set Value</strong> button on any Kanban card or List row to populate deal values in seconds.</p>
                </div>
              </div>
            ) : null}
          </Card>
        </div>
      )}
    </div>
  );
};
