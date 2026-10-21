import { useEffect, useState, useMemo } from 'react';
import type { FC, FormEvent } from 'react';
import {
  BookOpen, Trash2, Plus, DollarSign, TrendingUp,
  CheckCircle2, ArrowRight, ArrowLeft, Trophy,
  Kanban, RefreshCw, Globe, Building2,
  Sparkles, Filter, X
} from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ExternalLink, CopyablePhone } from '../shared/ClickableContact';

// ==================== Interfaces ====================

interface Asset {
  id: number;
  title: string;
  industry?: string;
  services: string[];
  tech: string[];
  body: string;
}

const split = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);

interface Service {
  service_key: string;
  name: string;
  offer: string;
  price_band: string | null;
}

const SERVICE_KEYS: Record<string, string> = {
  performance_engineering: 'Performance engineering',
  seo_optimization: 'SEO optimization',
  security_hardening: 'Security hardening',
  a11y_compliance: 'Accessibility compliance',
  geo_ai_readiness: 'AI-search readiness (GEO)',
  mobile_optimization: 'Mobile optimization',
  devops_sre: 'DevOps / SRE',
  presence_rescue: 'Digital presence build (site + Google profile)'
};

interface PipelineDeal {
  id: number;
  company_name: string;
  domain: string | null;
  phone: string | null;
  address: string | null;
  deal_stage: string;
  deal_value: number;
  weighted_value: number;
  win_rate: number;
  source_channel: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface StageData {
  count: number;
  value: number;
  win_rate: number;
  leads: PipelineDeal[];
}

interface PipelineResponse {
  total_deals: number;
  total_value: number;
  weighted_value: number;
  stages: Record<string, StageData>;
}

const STAGES: Array<{ id: string; label: string; rate: number; color: string; border: string; bg: string }> = [
  { id: 'sourced', label: '1. Sourced', rate: 0.10, color: 'text-slate-300', border: 'border-slate-700/60', bg: 'bg-slate-900/40' },
  { id: 'audited', label: '2. Audited', rate: 0.25, color: 'text-sky-300', border: 'border-sky-500/40', bg: 'bg-sky-500/5' },
  { id: 'outreach_active', label: '3. Outreach Active', rate: 0.40, color: 'text-purple-300', border: 'border-purple-500/40', bg: 'bg-purple-500/5' },
  { id: 'meeting_booked', label: '4. Meeting Booked', rate: 0.65, color: 'text-amber-300', border: 'border-amber-500/40', bg: 'bg-amber-500/5' },
  { id: 'proposal_sent', label: '5. Proposal Sent', rate: 0.80, color: 'text-indigo-300', border: 'border-indigo-500/40', bg: 'bg-indigo-500/5' },
  { id: 'closed_won', label: '6. Closed Won', rate: 1.00, color: 'text-emerald-300', border: 'border-emerald-500/40', bg: 'bg-emerald-500/10' },
];

// ==================== Services Section ====================

const ServicesSection: FC = () => {
  const [services, setServices] = useState<Service[]>([]);
  const [form, setForm] = useState({ service_key: 'performance_engineering', offer: '', price_band: '' });
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiFetch('/api/services').then(async (res) => {
      if (active && res.ok) setServices(await res.json());
    });
    return () => {
      active = false;
    };
  }, []);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    const res = await apiFetch('/api/services', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_key: form.service_key, name: SERVICE_KEYS[form.service_key], offer: form.offer, price_band: form.price_band || null })
    });
    const data = await res.json();
    if (!res.ok) {
      setError(apiErrorMessage(res.status, data));
      return;
    }
    setServices((prev) => [...prev.filter((s) => s.service_key !== data.service_key), data]);
    setForm({ ...form, offer: '', price_band: '' });
  };

  const remove = async (key: string) => {
    await apiFetch(`/api/services/${key}`, { method: 'DELETE' });
    setServices((prev) => prev.filter((s) => s.service_key !== key));
  };

  const input = 'w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500 text-slate-100 placeholder:text-slate-500';
  return (
    <div className="space-y-4 pt-4 border-t border-slate-800/80">
      <div>
        <h2 className="text-lg font-bold text-white tracking-tight">Services &amp; Price Bands</h2>
        <p className="text-xs text-slate-400 mt-0.5">Briefs and presence offers quote only the price bands you enter here. Nothing is estimated for you.</p>
      </div>
      <form onSubmit={save} className="bento-tile specular-border rounded-2xl p-5 grid sm:grid-cols-3 gap-3">
        <select className={input} value={form.service_key} onChange={(e) => setForm({ ...form, service_key: e.target.value })}>
          {Object.entries(SERVICE_KEYS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input className={input} placeholder="What you deliver (items separated by ;)" value={form.offer} onChange={(e) => setForm({ ...form, offer: e.target.value })} required />
        <input className={input} placeholder="Price band, e.g. $4,000 - $9,000" value={form.price_band} onChange={(e) => setForm({ ...form, price_band: e.target.value })} />
        {error && <div role="alert" className="sm:col-span-3 text-xs text-rose-300">{error}</div>}
        <button className="sm:col-span-3 justify-self-start rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-sm font-semibold text-white transition">Save service</button>
      </form>
      <div className="grid sm:grid-cols-2 gap-3">
        {services.map((s) => (
          <div key={s.service_key} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3.5 text-sm flex justify-between gap-3 items-start">
            <div>
              <div className="font-semibold text-white">{s.name} <span className="text-emerald-400 font-mono text-xs ml-1">{s.price_band || 'no price band'}</span></div>
              <div className="text-slate-400 text-xs mt-1 leading-relaxed">{s.offer}</div>
            </div>
            <button onClick={() => remove(s.service_key)} aria-label={`Delete ${s.name}`} className="text-slate-500 hover:text-rose-400 p-1"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
      </div>
    </div>
  );
};

// ==================== Kanban CRM Section ====================

const KanbanPipelineSection: FC = () => {
  const [pipeline, setPipeline] = useState<PipelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [updating, setUpdating] = useState<Record<number, boolean>>({});
  const [showAddModal, setShowAddModal] = useState(false);
  const [newDeal, setNewDeal] = useState({
    company_name: '',
    domain: '',
    phone: '',
    address: '',
    deal_value: 4500,
    stage: 'sourced',
    notes: ''
  });
  const [addBusy, setAddBusy] = useState(false);
  const [addError, setAddError] = useState('');

  const loadPipeline = async () => {
    try {
      const res = await apiFetch('/api/pipeline/deals');
      if (res.ok) {
        const data = await res.json();
        setPipeline(data);
      }
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    apiFetch('/api/pipeline/deals')
      .then(async (res) => {
        if (active && res.ok) {
          const data = await res.json();
          setPipeline(data);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const moveStage = async (leadId: number, newStage: string) => {
    setUpdating((prev) => ({ ...prev, [leadId]: true }));
    try {
      const res = await apiFetch('/api/pipeline/deals/stage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_id: leadId, new_stage: newStage })
      });
      if (res.ok) {
        await loadPipeline();
      }
    } catch {
      // Ignore
    } finally {
      setUpdating((prev) => ({ ...prev, [leadId]: false }));
    }
  };

  const getNextStage = (curr: string) => {
    const idx = STAGES.findIndex((s) => s.id === curr);
    if (idx >= 0 && idx < STAGES.length - 1) return STAGES[idx + 1].id;
    return null;
  };

  const getPrevStage = (curr: string) => {
    const idx = STAGES.findIndex((s) => s.id === curr);
    if (idx > 0) return STAGES[idx - 1].id;
    return null;
  };

  const handleCreateDeal = async (e: FormEvent) => {
    e.preventDefault();
    setAddBusy(true);
    setAddError('');
    try {
      const res = await apiFetch('/api/pipeline/deals/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: newDeal.company_name,
          domain: newDeal.domain || null,
          phone: newDeal.phone || null,
          address: newDeal.address || null,
          deal_value: Number(newDeal.deal_value) || 4500,
          stage: newDeal.stage,
          notes: newDeal.notes || null,
        })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setAddError(errData.detail || 'Failed to create deal');
        return;
      }
      setShowAddModal(false);
      setNewDeal({ company_name: '', domain: '', phone: '', address: '', deal_value: 4500, stage: 'sourced', notes: '' });
      await loadPipeline();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Failed to create deal');
    } finally {
      setAddBusy(false);
    }
  };

  const wonTotal = useMemo(() => {
    return pipeline?.stages?.closed_won?.value || 0;
  }, [pipeline]);

  const wonCount = useMemo(() => {
    return pipeline?.stages?.closed_won?.count || 0;
  }, [pipeline]);

  const inputStyle = 'w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500 text-slate-100 placeholder:text-slate-500';

  return (
    <div className="space-y-6">
      {/* Metrics Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bento-tile specular-border rounded-2xl p-4 border border-indigo-500/20 bg-indigo-500/5">
          <div className="flex items-center justify-between text-xs text-indigo-300 font-medium">
            <span>Total Pipeline Value</span>
            <DollarSign className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-black text-white mt-2 font-mono">
            ${(pipeline?.total_value || 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
            <span>{pipeline?.total_deals || 0} active opportunities</span>
          </div>
        </div>

        <div className="bento-tile specular-border rounded-2xl p-4 border border-cyan-500/20 bg-cyan-500/5">
          <div className="flex items-center justify-between text-xs text-cyan-300 font-medium">
            <span>Weighted Revenue</span>
            <TrendingUp className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-black text-cyan-300 mt-2 font-mono">
            ${(pipeline?.weighted_value || 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            Expected revenue via stage win-rates
          </div>
        </div>

        <div className="bento-tile specular-border rounded-2xl p-4 border border-emerald-500/20 bg-emerald-500/5">
          <div className="flex items-center justify-between text-xs text-emerald-300 font-medium">
            <span>Closed Won Revenue</span>
            <Trophy className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-black text-emerald-400 mt-2 font-mono">
            ${wonTotal.toLocaleString()}
          </div>
          <div className="text-[11px] text-emerald-400/80 mt-1">
            🏆 {wonCount} deals secured
          </div>
        </div>

        <div className="bento-tile specular-border rounded-2xl p-4 border border-purple-500/20 bg-purple-500/5 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-purple-300 font-medium">
            <span>CRM Operations</span>
            <Sparkles className="h-4 w-4 text-purple-400" />
          </div>
          <div className="flex items-center gap-2 mt-2">
            <button
              onClick={() => setShowAddModal(true)}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 transition"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Deal</span>
            </button>
            <button
              onClick={loadPipeline}
              className="p-2 rounded-xl border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white transition"
              title="Refresh CRM Pipeline"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="Filter opportunities by name or domain…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
          />
          <Filter className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-3 top-2.5 text-slate-500 hover:text-slate-300"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <div className="text-xs text-slate-400 font-mono hidden sm:block">
          Sovereign CRM · 100% In-House SQLite Pipeline
        </div>
      </div>

      {/* Kanban Board Container */}
      <div className="overflow-x-auto pb-4 pt-1">
        <div className="flex gap-4 min-w-[1280px]">
          {STAGES.map((st) => {
            const stageData = pipeline?.stages?.[st.id] || { count: 0, value: 0, win_rate: st.rate, leads: [] };
            const leads = stageData.leads.filter((l) =>
              !search ||
              l.company_name.toLowerCase().includes(search.toLowerCase()) ||
              (l.domain && l.domain.toLowerCase().includes(search.toLowerCase()))
            );

            return (
              <div
                key={st.id}
                className={`flex-1 rounded-2xl border ${st.border} ${st.bg} flex flex-col p-3.5 min-w-[210px] max-w-[240px]`}
              >
                {/* Column Header */}
                <div className="pb-3 border-b border-slate-800/80">
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-bold uppercase tracking-wider ${st.color}`}>
                      {st.label}
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800/80 text-slate-300">
                      {leads.length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-1.5 text-[11px] font-mono text-slate-400">
                    <span className="font-semibold text-white">${stageData.value.toLocaleString()}</span>
                    <span>{Math.round(st.rate * 100)}% Win Rate</span>
                  </div>
                </div>

                {/* Column Cards List */}
                <div className="flex-1 space-y-2.5 pt-3 min-h-[360px] overflow-y-auto max-h-[640px] pr-1">
                  {leads.length === 0 ? (
                    <div className="text-center py-8 text-xs text-slate-600 italic">
                      No deals in this stage
                    </div>
                  ) : (
                    leads.map((deal) => {
                      const next = getNextStage(deal.deal_stage);
                      const prev = getPrevStage(deal.deal_stage);
                      const isBusy = updating[deal.id];

                      return (
                        <div
                          key={deal.id}
                          className="bento-tile-interactive rounded-xl p-3 border border-slate-800/90 hover:border-slate-700 bg-slate-950/70 shadow-sm space-y-2 group transition"
                        >
                          <div className="flex items-start justify-between gap-1.5">
                            <h4 className="text-xs font-bold text-slate-100 group-hover:text-indigo-300 transition truncate" title={deal.company_name}>
                              {deal.company_name}
                            </h4>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 shrink-0">
                              ${(deal.deal_value || 4500).toLocaleString()}
                            </span>
                          </div>

                          {/* Domain / Phone details */}
                          <div className="space-y-1 text-[11px] text-slate-400">
                            {deal.domain ? (
                              <div className="flex items-center gap-1 truncate text-indigo-400">
                                <Globe className="h-3 w-3 shrink-0" />
                                <ExternalLink href={deal.domain} className="text-xs truncate" />
                              </div>
                            ) : (
                              <div className="flex items-center gap-1 text-amber-400/90 text-[10px]">
                                <Sparkles className="h-3 w-3 shrink-0" />
                                <span>Digital Presence Lead</span>
                              </div>
                            )}

                            {deal.phone && (
                              <div className="pt-0.5">
                                <CopyablePhone phone={deal.phone} />
                              </div>
                            )}
                          </div>

                          {/* Stage Transition Actions */}
                          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between gap-1">
                            {prev ? (
                              <button
                                onClick={() => moveStage(deal.id, prev)}
                                disabled={isBusy}
                                className="p-1 rounded-md bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition"
                                title="Move back to previous stage"
                              >
                                <ArrowLeft className="h-3 w-3" />
                              </button>
                            ) : (
                              <div className="w-5" />
                            )}

                            {deal.deal_stage !== 'closed_won' && (
                              <button
                                onClick={() => moveStage(deal.id, 'closed_won')}
                                disabled={isBusy}
                                className="px-1.5 py-0.5 rounded-md bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold flex items-center gap-1 transition"
                                title="1-Click Mark as Won!"
                              >
                                <Trophy className="h-2.5 w-2.5" />
                                <span>Won</span>
                              </button>
                            )}

                            {next ? (
                              <button
                                onClick={() => moveStage(deal.id, next)}
                                disabled={isBusy}
                                className="p-1 rounded-md bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-200 border border-indigo-500/40 transition"
                                title="Advance to next pipeline stage"
                              >
                                <ArrowRight className="h-3 w-3" />
                              </button>
                            ) : (
                              <div className="w-5 flex justify-end">
                                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* New Deal Creation Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
          <div className="bento-tile specular-border w-full max-w-lg rounded-2xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <DollarSign className="h-5 w-5 text-indigo-400" />
                <h3 className="text-base font-bold text-white">Create New CRM Deal</h3>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="p-1.5 rounded-lg border border-slate-800 text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleCreateDeal} className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Company / Business Name *</label>
                <input
                  className={inputStyle}
                  placeholder="e.g. Acme Logistics or Bay Dental"
                  value={newDeal.company_name}
                  onChange={(e) => setNewDeal({ ...newDeal, company_name: e.target.value })}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Domain / Website</label>
                  <input
                    className={inputStyle}
                    placeholder="e.g. acme.com (optional)"
                    value={newDeal.domain}
                    onChange={(e) => setNewDeal({ ...newDeal, domain: e.target.value })}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Estimated Deal Value ($) *</label>
                  <input
                    type="number"
                    className={inputStyle}
                    value={newDeal.deal_value}
                    onChange={(e) => setNewDeal({ ...newDeal, deal_value: Number(e.target.value) })}
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Phone</label>
                  <input
                    className={inputStyle}
                    placeholder="e.g. +1 555-0199"
                    value={newDeal.phone}
                    onChange={(e) => setNewDeal({ ...newDeal, phone: e.target.value })}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Initial Stage</label>
                  <select
                    className={inputStyle}
                    value={newDeal.stage}
                    onChange={(e) => setNewDeal({ ...newDeal, stage: e.target.value })}
                  >
                    {STAGES.map((s) => (
                      <option key={s.id} value={s.id}>{s.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Notes / Pitch Scope</label>
                <textarea
                  rows={2}
                  className={inputStyle}
                  placeholder="e.g. High urgency SEO rescue, broken DNS on mobile"
                  value={newDeal.notes}
                  onChange={(e) => setNewDeal({ ...newDeal, notes: e.target.value })}
                />
              </div>

              {addError && <div className="text-xs text-rose-400">{addError}</div>}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-xl border border-slate-800 hover:bg-slate-800 text-xs text-slate-300 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addBusy}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs text-white font-semibold shadow-md shadow-indigo-600/30"
                >
                  {addBusy ? 'Creating…' : 'Create Deal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

// ==================== Main Portfolio & CRM Component ====================

export const PortfolioManager: FC = () => {
  const [activeTab, setActiveTab] = useState<'pipeline' | 'proof' | 'services'>('pipeline');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [form, setForm] = useState({ title: '', industry: '', services: '', tech: '', body: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const res = await apiFetch('/api/portfolio/assets');
    if (res.ok) setAssets(await res.json());
  };

  useEffect(() => {
    let active = true;
    apiFetch('/api/portfolio/assets').then(async (res) => {
      if (active && res.ok) setAssets(await res.json());
    });
    return () => {
      active = false;
    };
  }, []);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await apiFetch('/api/portfolio/assets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: form.title,
          industry: form.industry || null,
          services: split(form.services),
          tech: split(form.tech),
          body: form.body
        })
      });
      const data = await res.json();
      if (!res.ok) {
        setError(apiErrorMessage(res.status, data));
        return;
      }
      setForm({ title: '', industry: '', services: '', tech: '', body: '' });
      await load();
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    await apiFetch(`/api/portfolio/assets/${id}`, { method: 'DELETE' });
    await load();
  };

  const input = 'w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500 text-slate-100 placeholder:text-slate-500';

  return (
    <div className="space-y-6">
      {/* Top Header & Sub-Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <Kanban className="h-6 w-6 text-indigo-400" />
            <span>Revenue Pipeline &amp; Sovereign CRM</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Enterprise deal staging, revenue forecasting, verifiable case studies, and structured agency service offerings.
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-900/90 border border-slate-800 self-start sm:self-auto">
          <button
            onClick={() => setActiveTab('pipeline')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeTab === 'pipeline'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Kanban className="h-3.5 w-3.5" />
            <span>Deal Pipeline</span>
          </button>
          <button
            onClick={() => setActiveTab('proof')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeTab === 'proof'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>Proof &amp; Case Studies</span>
          </button>
          <button
            onClick={() => setActiveTab('services')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
              activeTab === 'services'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Building2 className="h-3.5 w-3.5" />
            <span>Service Catalog</span>
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      {activeTab === 'pipeline' && <KanbanPipelineSection />}

      {activeTab === 'proof' && (
        <div className="space-y-6">
          <form onSubmit={add} className="bento-tile specular-border rounded-2xl p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Add Verifiable Proof Case Study</h2>
              <span className="text-xs text-amber-400 font-mono">Verifier Enforced</span>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              <input className={input} placeholder="Title, e.g. Logistics booking rebuild" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
              <input className={input} placeholder="Industry, e.g. Healthcare, Dental, E-Commerce" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} />
              <input className={input} placeholder="Services (comma separated, e.g. SEO, Speed)" value={form.services} onChange={(e) => setForm({ ...form, services: e.target.value })} />
              <input className={input} placeholder="Tech (comma separated, e.g. Next.js, Postgres)" value={form.tech} onChange={(e) => setForm({ ...form, tech: e.target.value })} />
            </div>
            <textarea className={input} rows={4} placeholder="What you built for whom, and the measured result (15+ words)." value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} required />
            {error && <div role="alert" className="text-xs text-rose-300">{error}</div>}
            <button disabled={busy} className="flex items-center space-x-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 px-4 py-2.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/25 transition">
              <Plus className="h-4 w-4" />
              <span>{busy ? 'Saving…' : 'Add Case Study'}</span>
            </button>
          </form>

          <div className="space-y-3">
            {assets.length === 0 && (
              <div className="text-sm text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-2xl p-5">
                No case studies yet. Proposal drafting is blocked until you add at least one real one.
              </div>
            )}
            {assets.map((a) => (
              <div key={a.id} className="bento-tile-interactive specular-border rounded-2xl p-5 text-sm">
                <div className="flex justify-between items-start gap-3">
                  <div>
                    <div className="font-bold text-white text-base">{a.title}</div>
                    <div className="text-xs text-slate-400 font-mono mt-0.5">
                      {[a.industry, ...a.services, ...a.tech].filter(Boolean).join(' · ')}
                    </div>
                  </div>
                  <button onClick={() => remove(a.id)} aria-label={`Delete ${a.title}`} className="p-1 rounded-lg text-slate-500 hover:text-rose-400 transition">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                <p className="text-slate-300 mt-2.5 leading-relaxed whitespace-pre-wrap text-xs">{a.body}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'services' && <ServicesSection />}
    </div>
  );
};
