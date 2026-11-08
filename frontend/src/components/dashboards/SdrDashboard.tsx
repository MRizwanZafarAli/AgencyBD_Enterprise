import { useMemo, useState } from 'react';
import type { FC } from 'react';
import { Target, Search, Sparkles, Radio, ArrowRight, RefreshCw, CheckCircle2, Clock } from 'lucide-react';
import { Badge, Card, Skeletons, Button } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useApi } from '../../lib/hooks';
import type { Surface } from '../../types';
import type { Me } from '../../lib/api';
import type { TodaySummary } from '../today/TodayOverview';
import { FollowupsPanel } from '../clients/FollowupsPanel';

interface Opp {
  id: number;
  title: string;
  source: string;
  type: string;
  fit_score: number | null;
  budget_max: number | null;
  currency?: string;
  company_name?: string;
}

export const SdrDashboard: FC<{
  identity: Me;
  onGo: (s: Surface) => void;
  onOpenClient: (leadId: number) => void;
  onSearch?: (q: string) => void;
}> = ({ identity, onGo, onOpenClient, onSearch }) => {
  const sum = useApi<TodaySummary>('/api/today/summary');
  const opps = useApi<Opp[]>('/api/opportunities');
  const d = sum.data;

  const [searchQuery, setSearchQuery] = useState('');

  const handleQuickSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (q) {
      if (onSearch) onSearch(q);
      else onGo('find');
    } else {
      onGo('find');
    }
  };

  const oppsList = useMemo(() => (Array.isArray(opps.data) ? opps.data : []), [opps.data]);
  const channelList = useMemo(() => (Array.isArray(d?.channels) ? d.channels : []), [d?.channels]);
  const attention = useMemo(() => channelList.filter((c) => c.followups_due || c.unanswered), [channelList]);
  const topOpps = useMemo(
    () => oppsList.filter((o) => (o.fit_score ?? 0) >= 0.5).slice(0, 4),
    [oppsList]
  );

  return (
    <div className="space-y-6">
      {/* Role Identity Banner */}
      <div className="rounded-2xl border border-indigo-500/30 bg-gradient-to-r from-indigo-950/40 to-slate-900/60 p-5 backdrop-blur-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold">
              <Target className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold text-white">Prospecting & Proposal Studio</h1>
                <Badge tone="accent">SDR Representative</Badge>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Logged in as <strong className="text-slate-200">{identity.user_id}</strong> ({identity.org_id}).
                Find high-converting client signals, generate strategic proposal drafts, and close communication loops.
              </p>
            </div>
          </div>
          <Button small onClick={() => { sum.reload(); opps.reload(); }}>
            <RefreshCw className={`h-3.5 w-3.5 ${sum.loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </div>

      <ErrorBanner message={sum.error} />

      {/* Quick Search Hunter Bar */}
      <Card>
        <form onSubmit={handleQuickSearch} className="flex flex-wrap items-center gap-2.5">
          <div className="relative flex-1 min-w-64">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search leads, jobs & tenders (e.g. react, remote operations, tender, dubai)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
            />
          </div>
          <Button variant="primary" onClick={() => (searchQuery.trim() && onSearch ? onSearch(searchQuery.trim()) : onGo('find'))}>
            <Search className="h-3.5 w-3.5" /> Hunt Prospects
          </Button>
          <Button onClick={() => onGo('channels')}>
            <Radio className="h-3.5 w-3.5" /> Open Channels
          </Button>
        </form>
      </Card>

      {/* 4 Clean, Focused SDR Metric Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Total Opportunities</div>
          <div className="text-2xl font-semibold text-white tabular mt-1">{oppsList.length}</div>
          <div className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" /> Job & tender signals
          </div>
          <div className="text-[11px] text-slate-500">Live feeds monitored</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Hot Prospects (≥70%)</div>
          <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">{d?.kpis.hot_leads ?? 0}</div>
          <div className="text-[11px] text-slate-400 mt-1">High qualification score</div>
          <div className="text-[11px] text-slate-500">Highest pitch conversion</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Sites Audited</div>
          <div className="text-2xl font-semibold text-white tabular mt-1">{d?.kpis.audits.now ?? 0}</div>
          <div className="text-[11px] text-slate-400 mt-1">Technical evaluations</div>
          <div className="text-[11px] text-slate-500">Used for grounded pitches</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Channels Needing Action</div>
          <div className="text-2xl font-semibold text-amber-400 tabular mt-1">{attention.length}</div>
          <div className="text-[11px] text-slate-400 mt-1">Upwork / LinkedIn queues</div>
          <div className="text-[11px] text-slate-500">Follow-ups & replies due</div>
        </div>
      </div>

      {/* Hot Opportunities: 1-Click Proposal Generator */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-400" /> Hot Opportunities Ready for Proposals
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              High commercial alignment. Open any opportunity to analyze fit or draft a dual-variant proposal.
            </p>
          </div>
          <Button small onClick={() => onGo('find')}>
            View All ({oppsList.length}) <ArrowRight className="h-3 w-3" />
          </Button>
        </div>

        {opps.loading && !opps.data ? (
          <Skeletons rows={3} />
        ) : topOpps.length === 0 ? (
          <p className="text-xs text-slate-400">Click &quot;Hunt Prospects&quot; to scan for fresh job signals.</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {topOpps.map((o) => (
              <div
                key={o.id}
                onClick={() => onGo('find')}
                className="p-3.5 rounded-xl border border-slate-800 hover:border-indigo-500/60 bg-slate-900/40 hover:bg-slate-900/80 cursor-pointer transition flex flex-col justify-between space-y-2 group"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <Badge tone="good">{Math.round((o.fit_score ?? 0) * 100)}% Fit</Badge>
                    <span className="text-[11px] text-slate-400 uppercase font-mono">{o.source}</span>
                  </div>
                  <h3 className="text-xs font-semibold text-slate-100 group-hover:text-white mt-2 line-clamp-1">
                    {o.title}
                  </h3>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    {o.company_name ? `${o.company_name} · ` : ''}
                    {o.budget_max ? `$${Math.round(o.budget_max).toLocaleString()}` : 'Project Scope'}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-indigo-400">
                  <span className="inline-flex items-center gap-1">
                    <Sparkles className="h-3 w-3" /> Draft Proposal
                  </span>
                  <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Follow-ups Due Panel */}
      <FollowupsPanel onOpenClient={onOpenClient} />

      {/* Channel Queue */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Radio className="h-4 w-4 text-indigo-400" /> Active Communication Channels
          </h2>
          <Button small onClick={() => onGo('channels')}>
            Open Channels Hub
          </Button>
        </div>

        {attention.length === 0 ? (
          <div className="text-xs text-slate-400 flex items-center gap-2 py-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" /> All channel follow-ups and messages are caught up!
          </div>
        ) : (
          <ul className="divide-y divide-slate-800">
            {attention.map((c) => (
              <li key={c.platform} className="py-2.5 flex items-center justify-between">
                <div>
                  <span className="text-xs font-medium text-slate-200">{c.label}</span>
                  <div className="text-[11px] text-slate-500">
                    {c.routine.done_today}/{c.routine.total} routine items completed today
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {c.unanswered > 0 && <Badge tone="warn">{c.unanswered} waiting</Badge>}
                  {c.followups_due > 0 && (
                    <Badge tone="warn">
                      <Clock className="h-3 w-3 inline mr-1" />
                      {c.followups_due} follow-up
                    </Badge>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
};
