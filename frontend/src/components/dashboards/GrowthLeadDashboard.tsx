import { useMemo, useState } from 'react';
import type { FC } from 'react';
import { TrendingUp, CheckCircle, XCircle, Send, ArrowRight, RefreshCw, Sparkles, Mail, Building2, ExternalLink, UserPlus, CheckCircle2, Radar } from 'lucide-react';
import { Badge, Card, Skeletons, Button, Drawer, ScoreBar } from '../ui';
import type { RelatedReadData } from '../find/FindJobs';
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

interface Opp {
  id: number;
  type: string;
  source: string;
  title: string;
  description: string | null;
  company_name: string | null;
  budget_min: number | null;
  budget_max: number | null;
  currency: string | null;
  url: string | null;
  posted_at: string | null;
  fit_score: number | null;
  fit_reasons: string[];
  risk_flags: string[];
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
  const opps = useApi<Opp[]>('/api/opportunities?limit=50');
  const d = sum.data;

  const [actingId, setActingId] = useState<number | null>(null);
  const [actionSuccess, setActionSuccess] = useState('');
  const [actionError, setActionError] = useState('');

  // Jobs & Projects Detection + Related Read state
  const [selectedOpp, setSelectedOpp] = useState<Opp | null>(null);
  const [relatedRead, setRelatedRead] = useState<RelatedReadData | null>(null);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedError, setRelatedError] = useState('');
  const [convertSuccess, setConvertSuccess] = useState('');
  const [converting, setConverting] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState('');

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

  const detectedJobs: Opp[] = useMemo(() => {
    return (opps.data ?? [])
      .filter((o) => o.type !== 'tender')
      .slice(0, 5);
  }, [opps.data]);

  const getCompanyName = (o: Opp) => {
    if (o.company_name && o.company_name.trim() && o.company_name.toLowerCase() !== 'unknown') {
      return o.company_name.trim();
    }
    const match = o.title.match(/(?:at|for|with)\s+([A-Z][A-Za-z0-9&.,'\s]{1,30}?)(?:\s+is|\s+looking|\s+hiring|[-–—|(\[\n]|$)/i)
      || o.title.match(/^\[?([A-Z][A-Za-z0-9&.,'\s]{1,30}?)\]?\s*[-–—:|]/i);
    return match ? match[1].trim() : 'Company detected';
  };

  const handleOpenOpp = (o: Opp) => {
    setSelectedOpp(o);
    setRelatedRead(null);
    setRelatedLoading(false);
    setRelatedError('');
    setConvertSuccess('');
    handleRelatedRead(o.id);
  };

  const handleRelatedRead = async (oppId: number) => {
    setRelatedLoading(true);
    setRelatedError('');
    try {
      const res = await apiFetch(`/api/opportunities/${oppId}/related_read`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Failed to resolve business owner details');
      setRelatedRead(data as RelatedReadData);
    } catch (e) {
      setRelatedError(e instanceof Error ? e.message : 'Error reading owner details');
    } finally {
      setRelatedLoading(false);
    }
  };

  const handleConvertToLead = async (oppId: number) => {
    setConverting(true);
    setRelatedError('');
    try {
      const res = await apiFetch(`/api/opportunities/${oppId}/convert_to_lead`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Failed to convert to lead');
      setConvertSuccess(data.message || `✓ Added to CRM pipeline!`);
      deals.reload();
      opps.reload();
      sum.reload();
    } catch (e) {
      setRelatedError(e instanceof Error ? e.message : 'Failed to convert');
    } finally {
      setConverting(false);
    }
  };

  const handleScanNow = async () => {
    setScanning(true);
    setScanMsg('Scanning feeds…');
    try {
      const res = await apiFetch('/api/radar/scan', { method: 'POST' });
      if (res.ok) {
        opps.reload();
        setScanMsg('✓ Scan complete! Newly detected jobs added.');
      } else {
        setScanMsg('Scan encountered an issue.');
      }
    } catch {
      setScanMsg('Scan failed.');
    } finally {
      setScanning(false);
      setTimeout(() => setScanMsg(''), 4000);
    }
  };

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

      {/* Jobs & Projects Detection: Inbound Market Signals Radar */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Radar className="h-4 w-4 text-teal-400" /> Jobs & Projects Detection Feed
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Live commercial intent signals detected across HackerNews, RemoteOK, WWR, Reddit, and GitHub.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {scanMsg && <span className="text-xs text-teal-300 font-medium">{scanMsg}</span>}
            <Button small onClick={handleScanNow} disabled={scanning}>
              <RefreshCw className={`h-3.5 w-3.5 ${scanning ? 'animate-spin' : ''}`} />
              {scanning ? 'Detecting…' : 'Scan Signals'}
            </Button>
            <Button small variant="primary" onClick={() => onGo('find')}>
              Explore All Jobs <ArrowRight className="h-3 w-3" />
            </Button>
          </div>
        </div>

        {opps.loading && !opps.data ? (
          <Skeletons rows={3} />
        ) : detectedJobs.length === 0 ? (
          <div className="p-4 rounded-xl border border-slate-800/80 bg-slate-900/30 text-center space-y-1">
            <div className="text-xs font-medium text-slate-200">No signals detected yet</div>
            <p className="text-[11px] text-slate-500">Click &apos;Scan Signals&apos; to detect live client hiring posts and projects.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-800 pb-2">
                  <th className="py-2 pr-3 w-20">Fit Score</th>
                  <th className="py-2 pr-3">Detected Job / Project</th>
                  <th className="py-2 pr-3">Organization</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {detectedJobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-900/60 transition group cursor-pointer" onClick={() => handleOpenOpp(job)}>
                    <td className="py-2.5 pr-3">
                      <div className="font-mono tabular font-semibold text-emerald-400">
                        {job.fit_score != null ? `${Math.round(job.fit_score * 100)}%` : '–'}
                      </div>
                      {job.fit_score != null && <ScoreBar value={job.fit_score * 100} />}
                    </td>
                    <td className="py-2.5 pr-3">
                      <div className="font-medium text-slate-200 group-hover:text-white line-clamp-1">
                        {job.title}
                      </div>
                      <div className="text-[11px] text-slate-500 line-clamp-1">
                        {job.description ? job.description.slice(0, 90) + '…' : 'Signal post'}
                      </div>
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className="font-medium text-slate-300 flex items-center gap-1">
                        <Building2 className="h-3 w-3 text-slate-500" />
                        {getCompanyName(job)}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3">
                      <Badge tone="accent">{job.source}</Badge>
                    </td>
                    <td className="py-2.5 text-right">
                      <Button
                        small
                        variant="primary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenOpp(job);
                        }}
                      >
                        <Building2 className="h-3 w-3" />
                        See Business Details
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
    
      {/* Opportunity Inspection & Related Read Drawer */}
      <Drawer
        open={selectedOpp !== null}
        title={selectedOpp?.title ?? ''}
        onClose={() => setSelectedOpp(null)}
        wide
      >
        {selectedOpp && (
          <div className="space-y-4 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent">{selectedOpp.source}</Badge>
              <Badge>{selectedOpp.type}</Badge>
              {selectedOpp.fit_score != null && (
                <Badge tone="good">Fit {Math.round(selectedOpp.fit_score * 100)}%</Badge>
              )}
              {selectedOpp.url && (
                <a
                  href={selectedOpp.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-indigo-400 hover:underline ml-auto"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Source Link
                </a>
              )}
            </div>

            <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 leading-relaxed max-h-40 overflow-auto whitespace-pre-wrap">
              {selectedOpp.description || 'No job description provided.'}
            </div>

            {/* Actions Row */}
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800">
              <Button
                variant="primary"
                disabled={relatedLoading}
                onClick={() => handleRelatedRead(selectedOpp.id)}
              >
                <Building2 className="h-4 w-4" />
                {relatedLoading ? 'Reading Business Details…' : relatedRead ? 'Refresh Business Details' : '🏢 See Business Details'}
              </Button>
            </div>

            {/* Related Read Surface */}
            {relatedError && <ErrorBanner message={relatedError} />}
            {relatedRead && (
              <div className="rounded-xl border border-teal-800/60 bg-slate-900/90 p-4 space-y-3 animate-fade-up">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-teal-400" />
                    <span className="font-semibold text-white text-xs">{relatedRead.company_name}</span>
                    {relatedRead.domain && !relatedRead.domain.endsWith('.invalid') && (
                      <Badge tone="good">🌐 {relatedRead.domain}</Badge>
                    )}
                  </div>
                  <Badge tone="accent">Related Read: Verified Leadership</Badge>
                </div>

                {convertSuccess && (
                  <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/40 text-xs text-emerald-200 flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5">
                      <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                      {convertSuccess}
                    </span>
                  </div>
                )}

                {/* Primary Business Owner Card */}
                <div className="rounded-lg bg-slate-950 border border-slate-800/80 p-3 space-y-2">
                  <div className="text-[11px] font-semibold text-teal-300 uppercase tracking-wider flex items-center justify-between">
                    <span>Key Decision Maker / Business Owner</span>
                    <Badge tone={relatedRead.business_owner.verification_status === 'published_on_site' ? 'good' : 'neutral'}>
                      {relatedRead.business_owner.verification_status?.replace(/_/g, ' ') || 'detected'}
                    </Badge>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2 text-xs">
                    <div>
                      <div className="text-slate-400 text-[11px]">Contact Name</div>
                      <div className="font-semibold text-white">{relatedRead.business_owner.name}</div>
                    </div>
                    <div>
                      <div className="text-slate-400 text-[11px]">Role / Title</div>
                      <div className="text-slate-200">{relatedRead.business_owner.title}</div>
                    </div>
                    {relatedRead.business_owner.email && (
                      <div>
                        <div className="text-slate-400 text-[11px]">Direct Email</div>
                        <div className="font-mono text-teal-300 flex items-center gap-1.5">
                          {relatedRead.business_owner.email}
                        </div>
                      </div>
                    )}
                    {relatedRead.business_owner.linkedin_url && (
                      <div>
                        <div className="text-slate-400 text-[11px]">LinkedIn Profile</div>
                        <a
                          href={relatedRead.business_owner.linkedin_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-teal-400 hover:underline flex items-center gap-1"
                        >
                          View Profile <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                {/* Additional Leadership Contacts */}
                {relatedRead.contacts.length > 1 && (
                  <div className="space-y-1">
                    <div className="text-[11px] font-semibold text-slate-400">Other Organization Contacts Detected:</div>
                    <div className="grid gap-1.5 sm:grid-cols-2">
                      {relatedRead.contacts.slice(1, 4).map((ct, idx) => (
                        <div key={idx} className="p-2 rounded bg-slate-950/60 border border-slate-800 text-[11px] space-y-0.5">
                          <div className="font-medium text-slate-200">{ct.name}</div>
                          <div className="text-slate-400">{ct.title}</div>
                          {ct.email && <div className="text-teal-300 font-mono">{ct.email}</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Conversion Button */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800">
                  <span className="text-[11px] text-slate-400 italic">{relatedRead.summary}</span>
                  {!convertSuccess && (
                    <Button small variant="primary" disabled={converting} onClick={() => handleConvertToLead(selectedOpp.id)}>
                      <UserPlus className="h-3.5 w-3.5" />
                      {converting ? 'Adding…' : 'Add to Pipeline'}
                    </Button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
};