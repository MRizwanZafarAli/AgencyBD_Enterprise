import { useMemo, useState } from 'react';
import type { FC } from 'react';
import { TrendingUp, CheckCircle, XCircle, Send, ArrowRight, RefreshCw, Sparkles, Mail } from 'lucide-react';
import { Badge, Card, Skeletons, Button } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useApi } from '../../lib/hooks';
import type { Surface } from '../../types';
import type { Me } from '../../lib/api';
import { apiFetch } from '../../lib/api';
import type { TodaySummary } from '../today/TodayOverview';

interface PendingApproval {
  id: number;
  subject_type: string;
  subject_id: number;
  requested_by: string;
  decision: string;
  proposal_body?: string;
  opportunity_id?: number;
  draft_subject?: string;
  draft_body?: string;
}

interface Deal {
  id: number;
  title: string;
  stage: string;
  value: number | null;
  company_name?: string;
}

interface PipelineResponse {
  stages?: Record<string, Deal[]>;
  total_pipeline_value?: number;
  weighted_projected_revenue?: number;
  active_deals?: number;
  unvalued_deals?: number;
  won_deals?: number;
  lost_deals?: number;
  total_deals?: number;
}

export const GrowthLeadDashboard: FC<{
  identity: Me;
  onGo: (s: Surface) => void;
  onOpenClient: (leadId: number) => void;
  onSettings: (section?: string) => void;
}> = ({ identity, onGo }) => {
  const sum = useApi<TodaySummary>('/api/today/summary');
  const approvals = useApi<PendingApproval[]>('/api/approvals/pending');
  const deals = useApi<PipelineResponse | Deal[]>('/api/pipeline/deals');
  const d = sum.data;

  const [actingId, setActingId] = useState<number | null>(null);
  const [actionSuccess, setActionSuccess] = useState('');
  const [actionError, setActionError] = useState('');

  const handleDecision = async (approvalId: number, decision: 'approve' | 'reject') => {
    setActingId(approvalId);
    setActionError('');
    setActionSuccess('');
    try {
      const res = await apiFetch(`/api/approvals/${approvalId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || 'Decision failed');
      setActionSuccess(`Successfully ${decision}d approval #${approvalId}!`);
      approvals.reload();
      sum.reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setActingId(null);
    }
  };

  const pendingItems = Array.isArray(approvals.data) ? approvals.data : [];

  const dealList: Deal[] = useMemo(() => {
    if (!deals.data) return [];
    if (Array.isArray(deals.data)) return deals.data;
    if (typeof deals.data === 'object' && deals.data.stages && typeof deals.data.stages === 'object') {
      const stagesObj = deals.data.stages as Record<string, Deal[]>;
      return Object.values(stagesObj).flat();
    }
    return [];
  }, [deals.data]);

  return (
    <div className="space-y-6">
      {/* Role Identity Banner */}
      <div className="bento-tile rounded-3xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-teal-500/20 text-teal-400 flex items-center justify-center font-bold">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold text-white">Pipeline & Campaign Command Center</h1>
                <Badge tone="good">Growth Lead</Badge>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Logged in as <strong className="text-slate-200">{identity.user_id}</strong> ({identity.org_id}).
                Oversees commercial pipeline velocity, sequence outreach, inbound triage, and outbound draft sign-offs.
              </p>
            </div>
          </div>
          <Button small onClick={() => { sum.reload(); approvals.reload(); deals.reload(); }}>
            <RefreshCw className={`h-3.5 w-3.5 ${sum.loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </div>

      <ErrorBanner message={sum.error} />

      {/* 4 Clean, Focused Growth Lead Metric Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Pipeline Deal Value</div>
          <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">
            {!d?.kpis.pipeline_value ? '$0' : `$${Math.round(d.kpis.pipeline_value).toLocaleString()}`}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {d?.kpis.unvalued_deals ? `${d.kpis.unvalued_deals} deal(s) pending value` : 'Active commercial stages'}
          </div>
          <div className="text-[11px] text-slate-500">Total pipeline under management</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Emails Dispatched</div>
          <div className="text-2xl font-semibold text-white tabular mt-1">{d?.kpis.emails_sent.now ?? 0}</div>
          <div className="text-[11px] text-slate-400 mt-1">Last 7 days volume</div>
          <div className="text-[11px] text-slate-500">Automated sequence sends</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Prospect Inbound Replies</div>
          <div className="text-2xl font-semibold text-indigo-300 tabular mt-1">{d?.kpis.replies.now ?? 0}</div>
          <div className="text-[11px] text-slate-400 mt-1">Responses to triage</div>
          <div className="text-[11px] text-slate-500">Replies waiting to be read</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Drafts Needing Approval</div>
          <div className={`text-2xl font-semibold tabular mt-1 ${pendingItems.length > 0 ? 'text-amber-400' : 'text-slate-300'}`}>
            {pendingItems.length}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Human-in-the-loop queue</div>
          <div className="text-[11px] text-amber-300/80">Requires your sign-off</div>
        </div>
      </div>

      {/* Hero Section: Pending Approvals Sign-off Desk */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-400" /> Outbound Sign-off & Approvals Desk
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Review proposals and sequence drafts prepared by SDRs before they are dispatched.
            </p>
          </div>
          <Badge tone={pendingItems.length > 0 ? 'warn' : 'good'}>
            {pendingItems.length} Pending Sign-offs
          </Badge>
        </div>

        {actionSuccess && (
          <div className="mb-3 p-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-xs text-emerald-300 flex items-center gap-2">
            <CheckCircle className="h-4 w-4 shrink-0" /> {actionSuccess}
          </div>
        )}
        <ErrorBanner message={actionError} />

        {approvals.loading && !approvals.data ? (
          <Skeletons rows={2} />
        ) : pendingItems.length === 0 ? (
          <div className="p-4 rounded-xl border border-slate-800/80 bg-slate-900/30 text-center space-y-1">
            <div className="text-xs font-medium text-slate-200">Approval queue is completely clear</div>
            <p className="text-[11px] text-slate-500">All outbound drafts have been reviewed or signed off.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {pendingItems.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3 hover:border-slate-700 transition"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800/60">
                  <div className="flex items-center gap-2">
                    <Badge tone="accent">Opportunity #{item.opportunity_id || item.subject_id}</Badge>
                    <span className="text-xs text-slate-400">Requested by: <strong>{item.requested_by}</strong></span>
                  </div>
                  <Badge tone="warn">Awaiting Your Decision</Badge>
                </div>

                <div className="text-xs text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800/80 leading-relaxed font-mono whitespace-pre-wrap max-h-36 overflow-auto">
                  {item.proposal_body || item.draft_body || 'No proposal content preview available.'}
                </div>

                <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                  <Button
                    small
                    disabled={actingId === item.id}
                    onClick={() => handleDecision(item.id, 'reject')}
                  >
                    <XCircle className="h-3.5 w-3.5 text-rose-400" /> Reject
                  </Button>
                  <Button
                    small
                    variant="primary"
                    disabled={actingId === item.id}
                    onClick={() => handleDecision(item.id, 'approve')}
                  >
                    <CheckCircle className="h-3.5 w-3.5" /> Approve & Dispatch
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Commercial Deals & Stage Velocity */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" /> Active Deals Pipeline
            </h2>
            <Button small onClick={() => onGo('clients')}>
              Manage Deals <ArrowRight className="h-3 w-3" />
            </Button>
          </div>

          {deals.loading && !deals.data ? (
            <Skeletons rows={3} />
          ) : dealList.length === 0 ? (
            <p className="text-xs text-slate-400">No active commercial deals in pipeline.</p>
          ) : (
            <ul className="divide-y divide-slate-800">
              {dealList.slice(0, 5).map((deal) => (
                <li key={deal.id} className="py-2.5 flex items-center justify-between text-xs">
                  <div>
                    <div className="font-medium text-slate-200">{deal.title}</div>
                    <div className="text-[11px] text-slate-500">{deal.company_name || 'Prospect Company'}</div>
                  </div>
                  <div className="text-right">
                    <Badge tone="accent">{(deal.stage || 'sourced').replace('_', ' ')}</Badge>
                    <div className="font-mono text-emerald-400 font-semibold mt-0.5">
                      {deal.value ? `$${Math.round(deal.value).toLocaleString()}` : 'Unvalued'}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Quick Growth Actions */}
        <Card>
          <h2 className="text-sm font-semibold text-white mb-3">Growth Workflow Shortcuts</h2>
          <div className="grid gap-2.5 sm:grid-cols-2 text-xs">
            <button
              onClick={() => onGo('clients')}
              className="p-3 text-left rounded-xl border border-slate-800 hover:border-teal-500/60 bg-slate-900/40 hover:bg-slate-900/80 transition space-y-1"
            >
              <div className="font-medium text-white flex items-center justify-between">
                <span>Manage Deals</span>
                <ArrowRight className="h-3.5 w-3.5 text-teal-400" />
              </div>
              <p className="text-[11px] text-slate-400">Move pipeline stages and record commercial values.</p>
            </button>

            <button
              onClick={() => onGo('find')}
              className="p-3 text-left rounded-xl border border-slate-800 hover:border-teal-500/60 bg-slate-900/40 hover:bg-slate-900/80 transition space-y-1"
            >
              <div className="font-medium text-white flex items-center justify-between">
                <span>Radar Scan</span>
                <ArrowRight className="h-3.5 w-3.5 text-teal-400" />
              </div>
              <p className="text-[11px] text-slate-400">Scan freelance and job signals across web feeds.</p>
            </button>

            <button
              onClick={() => onGo('channels')}
              className="p-3 text-left rounded-xl border border-slate-800 hover:border-teal-500/60 bg-slate-900/40 hover:bg-slate-900/80 transition space-y-1"
            >
              <div className="font-medium text-white flex items-center justify-between">
                <span>Channels Hub</span>
                <ArrowRight className="h-3.5 w-3.5 text-teal-400" />
              </div>
              <p className="text-[11px] text-slate-400">Monitor multi-channel response rates & routines.</p>
            </button>

            <button
              onClick={() => onGo('email' as any)}
              className="p-3 text-left rounded-xl border border-slate-800 hover:border-teal-500/60 bg-slate-900/40 hover:bg-slate-900/80 transition space-y-1"
            >
              <div className="font-medium text-white flex items-center justify-between">
                <span>Email Dispatch Hub</span>
                <Mail className="h-3.5 w-3.5 text-teal-400" />
              </div>
              <p className="text-[11px] text-slate-400">Pre-flight MX verification, composer & mailbox fleet.</p>
            </button>

            <button
              onClick={() => onGo('tools')}
              className="p-3 text-left rounded-xl border border-slate-800 hover:border-teal-500/60 bg-slate-900/40 hover:bg-slate-900/80 transition space-y-1"
            >
              <div className="font-medium text-white flex items-center justify-between">
                <span>Sequence Studio</span>
                <Send className="h-3.5 w-3.5 text-teal-400" />
              </div>
              <p className="text-[11px] text-slate-400">Inspect automated spintax and sequence steps.</p>
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
};
