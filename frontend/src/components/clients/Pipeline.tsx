import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Download, Plus } from 'lucide-react';
import { FollowupsPanel } from './FollowupsPanel';
import { ChasePanel } from './ChasePanel';
import { Badge, Button, Card, EmptyState, Skeletons, Stat, SuggestInput, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';

interface Deal { id: number; company_name: string; domain: string; deal_value: number | null; pitch_angle: string | null; source_channel: string | null; phone: string | null }
interface Pipeline {
  active_deals_count: number; won_deals_count: number; lost_deals_count: number; unvalued_deals_count: number; total_pipeline_value: number;
  weighted_projected_revenue: number; win_rate_percent: number | null; projection_note: string;
  stages: Record<string, { count: number; leads: Deal[] }>;
}

const STAGES: Array<{ id: string; label: string }> = [
  { id: 'sourced', label: 'New' }, { id: 'audited', label: 'Audited' }, { id: 'sequence_active', label: 'In outreach' },
  { id: 'meeting_booked', label: 'Meeting' }, { id: 'proposal_sent', label: 'Proposal sent' }, { id: 'won', label: 'Won' }, { id: 'lost', label: 'Lost' },
];

export const PipelineBoard: FC<{ onOpen: (leadId: number) => void }> = ({ onOpen }) => {
  const pipe = useApi<Pipeline>('/api/pipeline/deals');
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ company_name: '', domain: '', deal_value: '', notes: '' });

  const move = async (id: number, stage: string) => {
    setError('');
    try { await send('/api/pipeline/deals/stage', 'POST', { lead_id: id, new_stage: stage }); pipe.reload(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not move the client'); }
  };
  const add = async (e: FormEvent) => {
    e.preventDefault(); setError('');
    try {
      await send('/api/pipeline/deals/create', 'POST', { company_name: form.company_name, domain: form.domain, notes: form.notes || undefined, ...(form.deal_value ? { deal_value: Number(form.deal_value) } : {}) });
      setForm({ company_name: '', domain: '', deal_value: '', notes: '' }); setAdding(false); pipe.reload();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not add the client'); }
  };
  const d = pipe.data;
  const [find, setFind] = useState('');
  const names = d ? Object.values(d.stages).flatMap((s) => s.leads.map((l) => l.company_name)) : [];
  const [sort, setSort] = useState<'recent' | 'value' | 'name'>('recent');
  const match = (l: Deal) => !find.trim() || `${l.company_name} ${l.domain}`.toLowerCase().includes(find.trim().toLowerCase());
  const ordered = (leads: Deal[]) => leads.filter(match).sort((a, b) => sort === 'value' ? (b.deal_value ?? 0) - (a.deal_value ?? 0) : sort === 'name' ? a.company_name.localeCompare(b.company_name) : 0);
  const exportCsv = () => {
    if (!d) return;
    const q = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const rows = [['company', 'website', 'stage', 'value', 'phone'], ...STAGES.flatMap((s) => (d.stages[s.id]?.leads ?? []).map((l) => [l.company_name, l.domain, s.label, l.deal_value, l.phone]))];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([rows.map((r) => r.map(q).join(',')).join('\n')], { type: 'text/csv' }));
    a.download = 'clients.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
        <Stat label="Active clients" value={d?.active_deals_count ?? '–'} />
        <Stat label="Valued pipeline" value={d ? (d.total_pipeline_value ? `$${d.total_pipeline_value.toLocaleString()}` : '–') : '–'} hint={d?.unvalued_deals_count ? `${d.unvalued_deals_count} client(s) have no value entered` : 'Only values you entered'} />
        <Stat label="Won / lost" value={d ? `${d.won_deals_count} / ${d.lost_deals_count}` : '–'} />
        <Stat label="Win rate" value={d ? (d.win_rate_percent === null ? 'n/a' : `${d.win_rate_percent}%`) : '–'} hint="Won ÷ (won + lost); n/a until something closes" />
      </div>
      <ChasePanel onOpenClient={onOpen} />
      <FollowupsPanel onOpenClient={onOpen} />
      <div className="flex flex-wrap justify-between items-center gap-2">
        <p className="text-xs text-slate-500 max-w-2xl">{d?.projection_note}</p>
        <div className="flex flex-wrap items-center gap-2">
          <SuggestInput className="w-48" label="Search clients" placeholder="Search clients" value={find} onChange={setFind} options={names} />
          <select className={`${field} !w-auto`} aria-label="Sort cards" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}><option value="recent">Newest first</option><option value="value">Highest value</option><option value="name">Name</option></select>
          <Button small onClick={exportCsv} disabled={!d}><Download className="h-3.5 w-3.5" />CSV</Button>
        <Button small variant="primary" onClick={() => setAdding((v) => !v)}><Plus className="h-3.5 w-3.5" />Add client</Button>
        </div>
      </div>
      {adding && (
        <Card>
          <form onSubmit={add} className="grid gap-3 sm:grid-cols-4 items-end">
            <label className="text-xs text-slate-400 space-y-1">Company<input className={field} required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} /></label>
            <label className="text-xs text-slate-400 space-y-1">Website<input className={field} required placeholder="example.com" value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} /></label>
            <label className="text-xs text-slate-400 space-y-1">Deal value, optional (USD)<input className={field} inputMode="numeric" value={form.deal_value} onChange={(e) => setForm({ ...form, deal_value: e.target.value.replace(/[^0-9]/g, '') })} /></label>
            <Button variant="primary">Save</Button>
          </form>
        </Card>
      )}
      <ErrorBanner message={error || pipe.error} />
      {pipe.loading && !d ? <Skeletons rows={3} /> : d && d.active_deals_count + d.lost_deals_count === 0 ? (
        <EmptyState title="No clients yet" hint="Save businesses from Find, or add one by hand. Each one gets a page with its audit, contacts and drafts." />
      ) : d && (
        <div className="overflow-x-auto pb-2">
          <div className="grid grid-flow-col auto-cols-[minmax(220px,1fr)] gap-3 min-w-max">
            {STAGES.map((s) => (
              <div key={s.id} className="rounded-xl bg-slate-900/50 border border-slate-800 p-2.5 w-60">
                <div className="flex items-center justify-between px-1 pb-2 text-xs font-medium text-slate-300">{s.label}<span className="text-slate-500 tabular">{d.stages[s.id]?.count ?? 0}</span></div>
                <div className="space-y-2">
                  {ordered([...(d.stages[s.id]?.leads ?? [])]).map((l) => (
                    <div key={l.id} className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5 space-y-1.5">
                      <button className="text-left w-full" onClick={() => onOpen(l.id)}>
                        <div className="text-sm text-slate-100 font-medium line-clamp-1">{l.company_name}</div>
                        <div className="text-[11px] text-slate-500 font-mono truncate">{l.domain.endsWith('.invalid') ? 'no website' : l.domain}</div>
                      </button>
                      <div className="flex items-center justify-between gap-2">
                        {l.deal_value ? <Badge tone="accent">${l.deal_value.toLocaleString()}</Badge> : <span className="text-[11px] text-slate-600">no value</span>}
                        <select aria-label={`Move ${l.company_name}`} className="bg-slate-900 border border-slate-800 rounded text-[11px] text-slate-300 px-1 py-0.5" value={s.id} onChange={(e) => move(l.id, e.target.value)}>
                          {STAGES.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                        </select>
                      </div>
                    </div>))}
                </div>
              </div>))}
          </div>
        </div>
      )}
    </div>
  );
};
