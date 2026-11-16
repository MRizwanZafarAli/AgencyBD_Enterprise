import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { 
  Download, Plus, LayoutGrid, LayoutList, Trash2, ArrowRight, 
  Sparkles, Globe, CheckCircle2 
} from 'lucide-react';
import { FollowupsPanel } from './FollowupsPanel';
import { ChasePanel } from './ChasePanel';
import { Button, Card, EmptyState, Skeletons, Stat, SuggestInput, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';

interface Deal { 
  id: number; 
  company_name: string; 
  domain: string; 
  deal_value: number | null; 
  pitch_angle: string | null; 
  source_channel: string | null; 
  phone: string | null;
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
  stages: Record<string, { count: number; leads: Deal[]; truncated?: boolean }>;
}

const STAGES: Array<{ id: string; label: string; color: string }> = [
  { id: 'sourced', label: 'New', color: 'border-slate-500/40 text-slate-300' }, 
  { id: 'audited', label: 'Audited', color: 'border-cyan-500/40 text-cyan-300' }, 
  { id: 'sequence_active', label: 'In outreach', color: 'border-indigo-500/40 text-indigo-300' },
  { id: 'meeting_booked', label: 'Meeting', color: 'border-amber-500/40 text-amber-300' }, 
  { id: 'proposal_sent', label: 'Proposal sent', color: 'border-purple-500/40 text-purple-300' }, 
  { id: 'won', label: 'Won', color: 'border-emerald-500/40 text-emerald-300' }, 
  { id: 'lost', label: 'Lost', color: 'border-rose-500/40 text-rose-300' },
];

export const PipelineBoard: FC<{ onOpen: (leadId: number) => void }> = ({ onOpen }) => {
  const pipe = useApi<Pipeline>('/api/pipeline/deals');
  const [view, setView] = useState<'board' | 'table'>('board');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ company_name: '', domain: '', deal_value: '', notes: '' });

  const move = async (id: number, stage: string) => {
    setError('');
    try { 
      await send('/api/pipeline/deals/stage', 'POST', { lead_id: id, new_stage: stage }); 
      pipe.reload(); 
    } catch (e) { 
      setError(e instanceof Error ? e.message : 'Could not move the client'); 
    }
  };

  const advanceStage = (id: number, currentStage: string) => {
    const stageIds = STAGES.map(s => s.id);
    const currIdx = stageIds.indexOf(currentStage);
    if (currIdx >= 0 && currIdx < stageIds.length - 2) {
      move(id, stageIds[currIdx + 1]);
    }
  };

  const deleteLead = async (id: number, name: string) => {
    if (!window.confirm(`Are you sure you want to remove "${name}" from your client pipeline?`)) return;
    setError('');
    try {
      await send(`/api/pipeline/deals/${id}`, 'DELETE');
      setSuccess(`Removed "${name}" from pipeline.`);
      setTimeout(() => setSuccess(''), 3000);
      pipe.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the lead');
    }
  };

  const cleanJunk = async () => {
    if (!window.confirm('Clean up synthetic test scrapings (such as sec-edgar filings and placeholder domains)?')) return;
    setError('');
    try {
      const res = await send<{ deleted_count: number }>('/api/pipeline/deals/clean_junk', 'POST');
      setSuccess(`Cleaned ${res.deleted_count} synthetic scrapings.`);
      setTimeout(() => setSuccess(''), 3000);
      pipe.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not clean test scrapings');
    }
  };

  const add = async (e: FormEvent) => {
    e.preventDefault(); 
    setError('');
    try {
      await send('/api/pipeline/deals/create', 'POST', { 
        company_name: form.company_name, 
        domain: form.domain, 
        notes: form.notes || undefined, 
        ...(form.deal_value ? { deal_value: Number(form.deal_value) } : {}) 
      });
      setForm({ company_name: '', domain: '', deal_value: '', notes: '' }); 
      setAdding(false); 
      pipe.reload();
    } catch (err) { 
      setError(err instanceof Error ? err.message : 'Could not add the client'); 
    }
  };

  const d = pipe.data;
  const [find, setFind] = useState('');
  const names = d ? Object.values(d.stages).flatMap((s) => s.leads.map((l) => l.company_name)) : [];
  const [sort, setSort] = useState<'recent' | 'value' | 'name'>('recent');
  
  const match = (l: Deal) => !find.trim() || `${l.company_name} ${l.domain}`.toLowerCase().includes(find.trim().toLowerCase());
  const ordered = (leads: Deal[]) => leads.filter(match).sort((a, b) => sort === 'value' ? (b.deal_value ?? 0) - (a.deal_value ?? 0) : sort === 'name' ? a.company_name.localeCompare(b.company_name) : 0);
  
  const allLeads = d ? STAGES.flatMap(s => (d.stages[s.id]?.leads ?? []).map(l => ({ ...l, stage_id: s.id, stage_label: s.label }))) : [];
  const filteredAllLeads = allLeads.filter(match).sort((a, b) => sort === 'value' ? (b.deal_value ?? 0) - (a.deal_value ?? 0) : sort === 'name' ? a.company_name.localeCompare(b.company_name) : 0);

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
    <div className="space-y-5 animate-fadeIn">
      {/* Top Professional KPI Bar */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
        <Stat 
          label="Active Pipeline Deals" 
          value={d?.active_deals_count ?? '–'} 
          hint="Total clients currently being worked"
        />
        <Stat 
          label="Total Pipeline Value" 
          value={d ? (d.total_pipeline_value ? `$${d.total_pipeline_value.toLocaleString()}` : '$0') : '–'} 
          hint={d?.unvalued_deals_count ? `${d.unvalued_deals_count} unassigned deal values` : 'Estimated value of active deals'} 
        />
        <Stat 
          label="Weighted Forecast" 
          value={d ? (d.weighted_projected_revenue ? `$${Math.round(d.weighted_projected_revenue).toLocaleString()}` : '$0') : '–'} 
          hint="Stage probability weighted projection"
        />
        <Stat 
          label="Win / Loss Record" 
          value={d ? `${d.won_deals_count} Won • ${d.lost_deals_count} Lost` : '–'} 
          hint={d?.win_rate_percent !== null ? `Win Rate: ${d?.win_rate_percent}%` : 'Historical deal conversions'}
        />
      </div>

      <ChasePanel onOpenClient={onOpen} />
      <FollowupsPanel onOpenClient={onOpen} />

      {/* Control Bar: View Switcher, Search, Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-slate-900/60 rounded-2xl border border-slate-800 backdrop-blur-md">
        <div className="flex items-center gap-2">
          {/* View Mode Toggle */}
          <div className="inline-flex rounded-xl bg-slate-950 p-1 border border-slate-800">
            <button
              onClick={() => setView('board')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                view === 'board' 
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              <span>Kanban Board</span>
            </button>
            <button
              onClick={() => setView('table')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                view === 'table' 
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LayoutList className="h-3.5 w-3.5" />
              <span>List / Table</span>
            </button>
          </div>

          <p className="hidden md:block text-xs text-slate-400 font-medium pl-2">
            {d?.projection_note || 'Stage-weighted pipeline revenue models.'}
          </p>
        </div>

        {/* Right Tools */}
        <div className="flex flex-wrap items-center gap-2">
          <SuggestInput 
            className="w-44" 
            label="Search clients" 
            placeholder="Search company or domain..." 
            value={find} 
            onChange={setFind} 
            options={names} 
          />
          <select 
            className={`${field} !w-auto text-xs`} 
            aria-label="Sort cards" 
            value={sort} 
            onChange={(e) => setSort(e.target.value as typeof sort)}
          >
            <option value="recent">Newest first</option>
            <option value="value">Highest value</option>
            <option value="name">Company Name</option>
          </select>
          <Button small onClick={exportCsv} disabled={!d}>
            <Download className="h-3.5 w-3.5" />CSV
          </Button>
          <Button small onClick={cleanJunk} variant="ghost" title="Clean synthetic test scrapings">
            <Sparkles className="h-3.5 w-3.5 text-amber-400" />Clean Data
          </Button>
          <Button small variant="primary" onClick={() => setAdding((v) => !v)}>
            <Plus className="h-3.5 w-3.5" />Add client
          </Button>
        </div>
      </div>

      {/* Add Client Form */}
      {adding && (
        <Card className="animate-fadeIn border border-indigo-500/30 bg-slate-900/80">
          <form onSubmit={add} className="grid gap-3 sm:grid-cols-4 items-end">
            <label className="text-xs text-slate-300 space-y-1 font-medium">
              Company Name
              <input className={field} required placeholder="Acme Software" value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} />
            </label>
            <label className="text-xs text-slate-300 space-y-1 font-medium">
              Website Domain
              <input className={field} required placeholder="acme.com" value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} />
            </label>
            <label className="text-xs text-slate-300 space-y-1 font-medium">
              Deal Value, USD (Optional)
              <input className={field} inputMode="numeric" placeholder="5000" value={form.deal_value} onChange={(e) => setForm({ ...form, deal_value: e.target.value.replace(/[^0-9]/g, '') })} />
            </label>
            <div className="flex gap-2">
              <Button variant="primary" className="flex-1">Save Client</Button>
              <Button onClick={() => setAdding(false)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {success && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4" />
          <span>{success}</span>
        </div>
      )}

      <ErrorBanner message={error || pipe.error} />

      {/* Main Content Area: Kanban Board vs Table View */}
      {pipe.loading && !d ? (
        <Skeletons rows={3} />
      ) : d && d.active_deals_count + d.lost_deals_count === 0 ? (
        <EmptyState 
          title="No clients in pipeline yet" 
          hint="Convert high-fit opportunities from 'Find', or add a prospect manually using the 'Add client' button above." 
        />
      ) : view === 'board' ? (
        /* KANBAN BOARD VIEW */
        <div className="overflow-x-auto pb-4">
          <div className="grid grid-flow-col auto-cols-[minmax(250px,280px)] gap-3.5 min-w-max">
            {STAGES.map((s) => {
              const stageLeads = ordered([...(d?.stages[s.id]?.leads ?? [])]);
              return (
                <div key={s.id} className="rounded-2xl bg-slate-900/60 border border-slate-800 p-3.5 flex flex-col min-h-[500px]">
                  {/* Column Header */}
                  <div className="flex items-center justify-between px-1 pb-3 mb-2 border-b border-slate-800/80">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${s.id === 'won' ? 'bg-emerald-400' : s.id === 'sequence_active' ? 'bg-indigo-400' : 'bg-slate-400'}`} />
                      <span className="text-xs font-semibold text-slate-200">{s.label}</span>
                    </div>
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-bold bg-slate-800 text-slate-400">
                      {d?.stages[s.id]?.count ?? 0}
                    </span>
                  </div>

                  {/* Column Cards */}
                  <div className="space-y-2.5 flex-1">
                    {stageLeads.length === 0 ? (
                      <div className="h-28 rounded-xl border border-dashed border-slate-800/80 flex items-center justify-center p-4 text-center">
                        <span className="text-xs text-slate-600 font-medium">No deals in {s.label.toLowerCase()}</span>
                      </div>
                    ) : (
                      stageLeads.map((l) => (
                        <div 
                          key={l.id} 
                          className="group relative rounded-xl border border-slate-800 bg-slate-950/80 hover:border-indigo-500/40 hover:bg-slate-900/90 p-3.5 transition-all shadow-sm hover:shadow-md space-y-2.5"
                        >
                          {/* Card Header & Title */}
                          <div className="flex items-start justify-between gap-2">
                            <button 
                              className="text-left flex-1 min-w-0" 
                              onClick={() => onOpen(l.id)}
                              title="Click to open client dossier"
                            >
                              <div className="text-sm font-semibold text-white group-hover:text-indigo-300 transition-colors truncate">
                                {l.company_name}
                              </div>
                              <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono mt-0.5 truncate">
                                <Globe className="h-3 w-3 text-slate-500 shrink-0" />
                                <span className="truncate">{l.domain.endsWith('.invalid') ? 'No website linked' : l.domain}</span>
                              </div>
                            </button>

                            {/* Delete button */}
                            <button
                              onClick={(e) => { e.stopPropagation(); deleteLead(l.id, l.company_name); }}
                              className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 transition-all rounded hover:bg-rose-500/10"
                              title="Delete lead"
                              aria-label={`Delete ${l.company_name}`}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>

                          {/* Value & Actions Footer */}
                          <div className="flex items-center justify-between pt-1 border-t border-slate-900/90 gap-2">
                            <div>
                              {l.deal_value ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                  ${l.deal_value.toLocaleString()}
                                </span>
                              ) : (
                                <span className="text-[11px] text-slate-500 font-mono">Unassigned</span>
                              )}
                            </div>

                            <div className="flex items-center gap-1">
                              {/* Stage Selector */}
                              <select 
                                aria-label={`Move ${l.company_name}`} 
                                className="bg-slate-900 border border-slate-700/80 rounded-lg text-[11px] text-slate-200 px-2 py-1 font-medium focus:border-indigo-500 focus:outline-none" 
                                value={s.id} 
                                onChange={(e) => move(l.id, e.target.value)}
                              >
                                {STAGES.map((o) => (
                                  <option key={o.id} value={o.id}>{o.label}</option>
                                ))}
                              </select>

                              {/* Advance shortcut */}
                              {s.id !== 'won' && s.id !== 'lost' && (
                                <button
                                  onClick={() => advanceStage(l.id, s.id)}
                                  className="p-1 rounded-lg bg-slate-800 hover:bg-indigo-600 text-slate-300 hover:text-white transition-colors"
                                  title="Advance to next stage"
                                >
                                  <ArrowRight className="h-3 w-3" />
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* TABLE / LIST VIEW */
        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400 font-mono uppercase text-[10px]">
                  <th className="py-3 px-4 font-semibold">Company & Domain</th>
                  <th className="py-3 px-4 font-semibold">Stage</th>
                  <th className="py-3 px-4 font-semibold">Deal Value</th>
                  <th className="py-3 px-4 font-semibold">Channel</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {filteredAllLeads.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-500">
                      No matching clients found.
                    </td>
                  </tr>
                ) : (
                  filteredAllLeads.map((l) => (
                    <tr key={l.id} className="hover:bg-slate-800/40 transition-colors group">
                      <td className="py-3 px-4">
                        <button 
                          onClick={() => onOpen(l.id)}
                          className="text-left group-hover:text-indigo-400 transition-colors"
                        >
                          <div className="font-semibold text-white text-sm">{l.company_name}</div>
                          <div className="text-slate-400 font-mono text-[11px] flex items-center gap-1 mt-0.5">
                            <Globe className="h-3 w-3 text-slate-500" />
                            <span>{l.domain.endsWith('.invalid') ? 'No website' : l.domain}</span>
                          </div>
                        </button>
                      </td>
                      <td className="py-3 px-4">
                        <select 
                          value={l.stage_id} 
                          onChange={(e) => move(l.id, e.target.value)}
                          className="bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-2 py-1 text-xs font-medium focus:border-indigo-500 focus:outline-none"
                        >
                          {STAGES.map((s) => (
                            <option key={s.id} value={s.id}>{s.label}</option>
                          ))}
                        </select>
                      </td>
                      <td className="py-3 px-4 font-mono font-medium">
                        {l.deal_value ? (
                          <span className="text-emerald-400 font-bold">${l.deal_value.toLocaleString()}</span>
                        ) : (
                          <span className="text-slate-500">Unassigned</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300">
                          {l.source_channel || 'Direct'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                        <Button small onClick={() => onOpen(l.id)}>
                          View Dossier
                        </Button>
                        <button
                          onClick={() => deleteLead(l.id, l.company_name)}
                          className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors inline-flex items-center"
                          title="Delete Client"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
