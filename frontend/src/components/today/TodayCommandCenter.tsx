import { useMemo, useState } from 'react';
import type { FC } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  Flame,
  ListChecks,
  Mail,
  Play,
  RefreshCw,
  Send,
  Sparkles,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react';
import { Badge, Button, Card, EmptyState, Select } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { useApi } from '../../lib/hooks';
import type { Surface } from '../../types';

interface CommandCenterData {
  briefing_bullets: string[];
  setup: {
    total: number;
    completed: number;
    required_missing: number;
    next_fix?: { key: string; label: string; fix?: string } | null;
  };
  kpis: {
    pipeline_value: number;
    weighted_forecast: number;
    replies_7d: number;
    reply_rate_pct: number;
    pending_approvals: number;
    open_tasks: number;
    sent_7d: number;
    sent_total: number;
    delivered_pct: number;
    bounce_pct: number;
  };
  action_queue: {
    replies_followups: Array<{ kind: string; id: number; title: string; detail: string; lead_id?: number }>;
    pending_approvals: Array<{ approval_id: number; draft_id?: number; lead_id?: number; subject?: string; body?: string; company_name?: string; created_at?: string }>;
    urgent_deadlines: Array<{ kind: string; id: number; title: string; company?: string; deadline?: string; url?: string }>;
    crm_tasks: Array<{ kind: string; id: number; title: string; detail: string; lead_id?: number }>;
    bottlenecks: Array<{ lead_id: number; company_name: string; deal_stage: string; deal_value: number; updated_at: string }>;
  };
  top_signals: Array<{ id: number; type: string; source: string; title: string; company_name?: string; url?: string; fit_score?: number; deadline?: string }>;
  velocity_series: Array<{ date: string; sent: number; replies: number }>;
  attribution_matrix: Array<{ channel: string; label: string; surface: Surface; signals_found: number; saved_to_crm: number; replied: number; pipeline_value: number }>;
}

const Sparkline: FC<{ values: number[]; stroke?: string }> = ({ values, stroke = 'currentColor' }) => {
  const pts = values.length >= 2 ? values : [0, 0, 0, 0, 0];
  const max = Math.max(1, ...pts);
  const w = 68;
  const h = 22;
  const path = pts
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${((i / (pts.length - 1)) * w).toFixed(1)},${(h - (v / max) * (h - 4) - 2).toFixed(1)}`)
    .join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="opacity-80 shrink-0" aria-hidden="true">
      <path d={path} fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

export const TodayCommandCenter: FC<{
  roleLabel: string;
  onGo: (s: Surface) => void;
  onOpenClient: (leadId: number) => void;
  onSettings: (section?: string) => void;
  onSendEmail?: (params: { recipient: string; recipientName?: string; companyName?: string; subject?: string; body?: string; leadId?: number }) => void;
}> = ({ roleLabel, onGo, onOpenClient, onSettings, onSendEmail }) => {
  const [period, setPeriod] = useState<'7' | '14' | '30' | '90'>('14');
  const cc = useApi<CommandCenterData>(`/api/today/command-center?days=${period}`);
  const d = cc.data;

  const [hideSetup, setHideSetup] = useState(() => localStorage.getItem('today_hide_setup') === '1');
  const [queueTab, setQueueTab] = useState<'replies' | 'approvals' | 'deadlines' | 'tasks'>('replies');
  const [focusOpen, setFocusOpen] = useState(false);
  const [focusIdx, setFocusIdx] = useState(0);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notice, setNotice] = useState('');
  const [slackBusy, setSlackBusy] = useState(false);

  const sentSeries = useMemo(() => (d?.velocity_series ?? []).slice(-7).map((x) => x.sent), [d?.velocity_series]);
  const replySeries = useMemo(() => (d?.velocity_series ?? []).slice(-7).map((x) => x.replies), [d?.velocity_series]);

  const decideApproval = async (approvalId: number, decision: 'approved' | 'rejected') => {
    setBusyId(approvalId);
    try {
      const res = await apiFetch(`/api/approvals/${approvalId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision }),
      });
      if (res.ok) {
        setNotice(`Draft ${decision}.`);
        cc.reload();
      }
    } finally {
      setBusyId(null);
    }
  };

  const saveOpportunity = async (oppId: number, title: string) => {
    setBusyId(oppId);
    try {
      const res = await apiFetch(`/api/opportunities/${oppId}/convert_to_lead`, { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      if (res.ok) {
        setNotice(`Saved "${title.slice(0, 40)}" to Clients.`);
        cc.reload();
        if (body.lead_id) onOpenClient(body.lead_id);
      }
    } finally {
      setBusyId(null);
    }
  };

  const postToSlack = async () => {
    setSlackBusy(true);
    try {
      const res = await apiFetch('/api/digest/send', { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      setNotice(res.ok && body.delivered ? 'Top signals posted to Slack.' : apiErrorMessage(res.status, body) || 'Configure Slack webhook in Settings.');
    } finally {
      setSlackBusy(false);
    }
  };

  // Focus Mode flattened actionable items
  const focusItems = useMemo(() => {
    if (!d) return [];
    const list: Array<{ kind: 'approval' | 'reply' | 'task'; id: number; title: string; body: string; lead_id?: number; company?: string }> = [];
    d.action_queue.pending_approvals.forEach((a) =>
      list.push({ kind: 'approval', id: a.approval_id, title: a.subject || `Draft for ${a.company_name || 'Lead'}`, body: a.body || '', lead_id: a.lead_id, company: a.company_name }),
    );
    d.action_queue.replies_followups.forEach((r) =>
      list.push({ kind: 'reply', id: r.id, title: r.title, body: r.detail, lead_id: r.lead_id }),
    );
    d.action_queue.crm_tasks.forEach((t) =>
      list.push({ kind: 'task', id: t.id, title: t.title, body: t.detail, lead_id: t.lead_id }),
    );
    return list.slice(0, 20);
  }, [d]);

  const scrollToQueue = (tab: 'replies' | 'approvals' | 'deadlines' | 'tasks') => {
    setQueueTab(tab);
    document.getElementById('today-action-queue')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const lowData = (d?.kpis.sent_total ?? 0) < 10;
  const maxVel = Math.max(1, ...(d?.velocity_series ?? []).map((v) => Math.max(v.sent, v.replies)));

  return (
    <div className="space-y-5">
      {/* Collapsible Setup Progress Bar */}
      {!hideSetup && d && d.setup.required_missing > 0 && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2 text-amber-300 font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>
              Workspace Setup: <strong>{d.setup.completed} of {d.setup.total} complete</strong>
              {d.setup.next_fix ? ` — Next: ${d.setup.next_fix.label}` : ''}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button small variant="primary" onClick={() => onSettings('setup')}>
              Fix now <ArrowRight className="h-3.5 w-3.5" />
            </Button>
            <button
              type="button"
              onClick={() => { setHideSetup(true); localStorage.setItem('today_hide_setup', '1'); }}
              className="text-slate-400 hover:text-white p-1"
              aria-label="Dismiss setup bar"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* AI Morning Briefing (3-Bullet Executive Pulse) */}
      <Card className="!p-5 ai-surface">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-400" />
            <h1 className="text-base font-semibold text-white">Executive Morning Briefing</h1>
            <Badge tone="ai">{roleLabel}</Badge>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-28">
              <Select
                small
                value={period}
                onChange={(v) => setPeriod(v as '7' | '14' | '30' | '90')}
                aria-label="Analytics period"
                options={[
                  { value: '7', label: 'Last 7d' },
                  { value: '14', label: 'Last 14d' },
                  { value: '30', label: 'Last 30d' },
                  { value: '90', label: 'Last 90d' },
                ]}
              />
            </div>
            <Button small variant="secondary" onClick={() => cc.reload()}>
              <RefreshCw className={`h-3.5 w-3.5 ${cc.loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
        <ul className="space-y-1.5 text-xs text-slate-300">
          {(d?.briefing_bullets ?? ['Loading live workspace intelligence…']).map((b, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
              <span>{b}</span>
            </li>
          ))}
        </ul>
        {notice && <p className="text-xs text-emerald-300 font-medium mt-2">{notice}</p>}
      </Card>

      {/* Upgraded Executive KPI Strip with Inline Sparklines */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <button type="button" onClick={() => onGo('clients')} className="text-left bento-tile rounded-2xl p-4 border border-slate-800 hover:border-indigo-500/40 transition">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-slate-400">Pipeline &amp; Weighted</span>
            <Sparkline values={[20, 28, 25, 34, 38, 40, Math.max(1, d?.kpis.pipeline_value ?? 40)]} stroke="#10b981" />
          </div>
          <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">
            ${Math.round(d?.kpis.pipeline_value ?? 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            ${Math.round(d?.kpis.weighted_forecast ?? 0).toLocaleString()} weighted forecast
          </div>
        </button>

        <button type="button" onClick={() => scrollToQueue('replies')} className="text-left bento-tile rounded-2xl p-4 border border-slate-800 hover:border-indigo-500/40 transition">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-slate-400">Replies (7d)</span>
            <Sparkline values={replySeries} stroke="#6366f1" />
          </div>
          <div className="text-2xl font-semibold text-white tabular mt-1">{d?.kpis.replies_7d ?? 0}</div>
          <div className="text-[11px] text-slate-400 mt-1">{d?.kpis.reply_rate_pct ?? 0}% reply rate</div>
        </button>

        <button type="button" onClick={() => scrollToQueue('approvals')} className="text-left bento-tile rounded-2xl p-4 border border-slate-800 hover:border-indigo-500/40 transition">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-slate-400">Approvals &amp; Tasks</span>
            <Sparkline values={[4, 6, 5, 8, 7, 6, Math.max(1, d?.kpis.open_tasks ?? 1)]} stroke="#f59e0b" />
          </div>
          <div className="text-2xl font-semibold text-amber-400 tabular mt-1">
            {(d?.kpis.pending_approvals ?? 0) + (d?.kpis.open_tasks ?? 0)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {d?.kpis.pending_approvals ?? 0} HITL approvals · {d?.kpis.open_tasks ?? 0} due tasks
          </div>
        </button>

        <button type="button" onClick={() => onGo('email')} className="text-left bento-tile rounded-2xl p-4 border border-slate-800 hover:border-indigo-500/40 transition">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-slate-400">Deliverability Health</span>
            <Sparkline values={sentSeries} stroke="#14b8a6" />
          </div>
          <div className="text-2xl font-semibold text-white tabular mt-1">{d?.kpis.delivered_pct ?? 100}%</div>
          <div className="text-[11px] text-slate-400 mt-1">
            {d?.kpis.sent_7d ?? 0} sent (7d) · {d?.kpis.bounce_pct ?? 0}% bounce
          </div>
        </button>
      </div>

      {/* Priority Action Queue (Above the Fold!) */}
      <div id="today-action-queue">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-indigo-400" />
              Today&apos;s Priority Action Queue
            </h2>
            <p className="text-xs text-slate-400">Execute your highest-leverage replies, HITL approvals, urgent deadlines &amp; idle deals.</p>
          </div>
          <Button
            small
            variant="primary"
            disabled={focusItems.length === 0}
            onClick={() => { setFocusIdx(0); setFocusOpen(true); }}
          >
            <Play className="h-3.5 w-3.5" />
            Start Focus Session ({focusItems.length})
          </Button>
        </div>

        {/* Queue Tabs */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {(
            [
              ['replies', `Replies & Follow-Ups (${d?.action_queue.replies_followups.length ?? 0})`],
              ['approvals', `Pending Approvals (${d?.action_queue.pending_approvals.length ?? 0})`],
              ['deadlines', `Urgent Deadlines (${d?.action_queue.urgent_deadlines.length ?? 0})`],
              ['tasks', `CRM Tasks & Bottlenecks (${(d?.action_queue.crm_tasks.length ?? 0) + (d?.action_queue.bottlenecks.length ?? 0)})`],
            ] as const
          ).map(([id, lbl]) => (
            <button
              key={id}
              type="button"
              onClick={() => setQueueTab(id)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                queueTab === id
                  ? 'bg-indigo-600 border-indigo-500 text-white'
                  : 'bg-slate-900/70 border-slate-800 text-slate-300 hover:border-slate-700'
              }`}
            >
              {lbl}
            </button>
          ))}
        </div>

        {queueTab === 'replies' && (
          <div className="space-y-2">
            {(d?.action_queue.replies_followups ?? []).length === 0 ? (
              <EmptyState title="Inbox zero on replies & follow-ups" hint="New client replies and due follow-ups appear here automatically." />
            ) : (
              d!.action_queue.replies_followups.map((item) => (
                <div key={`${item.kind}-${item.id}`} className="p-3 rounded-xl border border-slate-800 bg-slate-900/40 flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                      <Flame className="h-3.5 w-3.5 text-amber-400 shrink-0" />
                      {item.title}
                    </div>
                    <p className="text-[11px] text-slate-400 truncate mt-0.5">{item.detail}</p>
                  </div>
                  <div className="flex gap-1.5">
                    {item.lead_id ? (
                      <Button small variant="primary" onClick={() => onOpenClient(item.lead_id!)}>Open Client</Button>
                    ) : (
                      <Button small variant="primary" onClick={() => onGo('channels')}>Reply</Button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {queueTab === 'approvals' && (
          <div className="space-y-2">
            {(d?.action_queue.pending_approvals ?? []).length === 0 ? (
              <EmptyState title="No pending HITL approvals" hint="AI-drafted emails and proposals appear here for 1-click sign-off." />
            ) : (
              d!.action_queue.pending_approvals.map((a) => (
                <div key={a.approval_id} className="p-3 rounded-xl border border-slate-800 bg-slate-900/40 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-xs font-semibold text-white">{a.subject || `Draft for ${a.company_name || 'Prospect'}`}</div>
                      {a.company_name && <div className="text-[11px] text-slate-400">{a.company_name}</div>}
                    </div>
                    <div className="flex gap-1.5">
                      <Button small variant="primary" disabled={busyId === a.approval_id} onClick={() => decideApproval(a.approval_id, 'approved')}>
                        <Check className="h-3.5 w-3.5" /> Approve
                      </Button>
                      <Button small variant="secondary" disabled={busyId === a.approval_id} onClick={() => decideApproval(a.approval_id, 'rejected')}>
                        Reject
                      </Button>
                    </div>
                  </div>
                  {a.body && <p className="text-[11px] text-slate-300 line-clamp-2">{a.body}</p>}
                </div>
              ))
            )}
          </div>
        )}

        {queueTab === 'deadlines' && (
          <div className="space-y-2">
            {(d?.action_queue.urgent_deadlines ?? []).length === 0 ? (
              <EmptyState title="No urgent deadlines in next 7 days" hint="Tenders closing within 7 days and fresh Watching hits appear here." />
            ) : (
              d!.action_queue.urgent_deadlines.map((u) => (
                <div key={`${u.kind}-${u.id}`} className="p-3 rounded-xl border border-slate-800 bg-slate-900/40 flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <Badge tone={u.kind === 'tender' ? 'bad' : 'good'}>
                        <Clock className="h-3 w-3 mr-1 inline" />
                        {u.deadline ? u.deadline.slice(0, 10) : 'Act <24h'}
                      </Badge>
                      <span className="text-xs font-semibold text-white truncate">{u.title}</span>
                    </div>
                    {u.company && <div className="text-[11px] text-slate-400 mt-0.5">{u.company}</div>}
                  </div>
                  <Button small variant="secondary" onClick={() => onGo('find')}>Inspect in Find</Button>
                </div>
              ))
            )}
          </div>
        )}

        {queueTab === 'tasks' && (
          <div className="space-y-3">
            {(d?.action_queue.bottlenecks ?? []).length > 0 && (
              <div className="p-3 rounded-xl border border-amber-500/30 bg-amber-500/10 space-y-2">
                <div className="text-xs font-semibold text-amber-300 flex items-center gap-1.5">
                  <Zap className="h-3.5 w-3.5" />
                  Pipeline Bottleneck Detector ({d!.action_queue.bottlenecks.length} idle 7+ days)
                </div>
                {d!.action_queue.bottlenecks.map((b) => (
                  <div key={b.lead_id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="text-white">
                      <strong>{b.company_name}</strong> · {b.deal_stage} (${Math.round(b.deal_value).toLocaleString()})
                    </span>
                    <div className="flex gap-1.5">
                      {onSendEmail && (
                        <Button
                          small
                          variant="primary"
                          onClick={() => onSendEmail({
                            recipient: '',
                            companyName: b.company_name,
                            subject: `Quick follow-up — ${b.company_name}`,
                            body: `Hi team,\n\nWanted to bump this to the top of your inbox and see if you had any questions on our proposal.\n\nBest,`,
                            leadId: b.lead_id,
                          })}
                        >
                          <Mail className="h-3.5 w-3.5" /> Draft Bump Follow-Up
                        </Button>
                      )}
                      <Button small variant="secondary" onClick={() => onOpenClient(b.lead_id)}>Open</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {(d?.action_queue.crm_tasks ?? []).length === 0 ? (
              <EmptyState title="No open CRM tasks" hint="Tasks and quiet clients to chase will surface here." />
            ) : (
              d!.action_queue.crm_tasks.map((t) => (
                <div key={`${t.kind}-${t.id}`} className="p-3 rounded-xl border border-slate-800 bg-slate-900/40 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-xs font-semibold text-white">{t.title}</div>
                    <div className="text-[11px] text-slate-400">{t.detail}</div>
                  </div>
                  {t.lead_id && <Button small variant="secondary" onClick={() => onOpenClient(t.lead_id!)}>Open Client</Button>}
                </div>
              ))
            )}
          </div>
        )}
      </Card>
      </div>

      {/* Interactive Top Signals Across All 5 Find Tabs (replaces raw Slack <pre> digest) */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-indigo-400" />
              Top Signals Across All 5 Find Tabs
            </h2>
            <p className="text-xs text-slate-400">Highest-fit opportunities ready to inspect, save to CRM, or share with the team.</p>
          </div>
          <div className="flex gap-2">
            <Button small variant="secondary" disabled={slackBusy} onClick={postToSlack}>
              <Send className="h-3.5 w-3.5" />
              {slackBusy ? 'Posting…' : 'Post to Slack'}
            </Button>
            <Button small variant="ghost" onClick={() => onGo('find')}>Open Find</Button>
          </div>
        </div>
        {(d?.top_signals ?? []).length === 0 ? (
          <EmptyState title="No signals yet" hint="Run a scan in Find to populate top opportunities here." />
        ) : (
          <div className="divide-y divide-slate-800/80">
            {d!.top_signals.map((s) => (
              <div key={s.id} className="py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge tone="accent">{s.source}</Badge>
                    {s.fit_score != null && <Badge tone="good">{Math.round(s.fit_score * 100)}% fit</Badge>}
                    <span className="font-semibold text-white truncate">{s.title}</span>
                  </div>
                  {s.company_name && <div className="text-[11px] text-slate-400 mt-0.5">{s.company_name}</div>}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {s.url && (
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-indigo-300 hover:underline inline-flex items-center gap-1 px-2">
                      Open <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  <Button small variant="primary" disabled={busyId === s.id} onClick={() => saveOpportunity(s.id, s.title)}>
                    Save to CRM
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Compact Analytics Row: Outbound Velocity vs Replies + 5-Channel Attribution Matrix */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-indigo-400" />
              Outbound Velocity vs. Replies ({period}d)
            </h2>
            <span className="text-[11px] text-slate-400">Bars: Sent · Line: Replies</span>
          </div>
          <div className="relative h-36 flex items-end gap-1.5 pt-4">
            {(d?.velocity_series ?? []).map((pt) => {
              const barH = Math.round((pt.sent / maxVel) * 96);
              const repH = Math.round((pt.replies / maxVel) * 96);
              return (
                <div key={pt.date} className="flex-1 flex flex-col items-center gap-1 min-w-0" title={`${pt.date}: ${pt.sent} sent, ${pt.replies} replies`}>
                  <div className="w-full flex items-end justify-center gap-0.5 h-24">
                    <div className="w-2.5 rounded-t bg-indigo-500/40" style={{ height: `${Math.max(2, barH)}px` }} />
                    <div className="w-1.5 rounded-t bg-emerald-400" style={{ height: `${Math.max(0, repH)}px` }} />
                  </div>
                  <span className="text-[9px] text-slate-500 truncate w-full text-center">{pt.date}</span>
                </div>
              );
            })}
            {lowData && (
              <div className="absolute inset-0 bg-slate-950/75 backdrop-blur-xs flex items-center justify-center p-4 text-center rounded-xl">
                <p className="text-xs text-slate-300">
                  Send <strong>10+ emails</strong> or save <strong>5 leads</strong> to unlock live trend analytics.
                </p>
              </div>
            )}
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Pipeline &amp; Source Attribution Matrix</h2>
            <span className="text-[11px] text-slate-400">Click row to open channel</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 text-slate-400">
                <tr>
                  <th className="py-2 pr-2">Channel</th>
                  <th className="py-2 px-2 text-right">Signals</th>
                  <th className="py-2 px-2 text-right">Saved CRM</th>
                  <th className="py-2 pl-2 text-right">Pipeline</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {(d?.attribution_matrix ?? []).map((row) => (
                  <tr
                    key={row.channel}
                    onClick={() => onGo(row.surface)}
                    className="hover:bg-slate-900/50 cursor-pointer transition"
                  >
                    <td className="py-2 pr-2 font-medium text-white">{row.label}</td>
                    <td className="py-2 px-2 text-right tabular text-slate-300">{row.signals_found}</td>
                    <td className="py-2 px-2 text-right tabular text-indigo-300">{row.saved_to_crm}</td>
                    <td className="py-2 pl-2 text-right tabular font-semibold text-emerald-400">
                      ${Math.round(row.pipeline_value).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* 1-Click Focus Mode Stepper Modal */}
      {focusOpen && focusItems.length > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <Card className="w-full max-w-xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge tone="accent">Focus Mode</Badge>
                <span className="text-xs text-slate-400">Item {focusIdx + 1} of {focusItems.length}</span>
              </div>
              <button type="button" onClick={() => setFocusOpen(false)} className="text-slate-400 hover:text-white" aria-label="Exit focus mode">
                <X className="h-5 w-5" />
              </button>
            </div>
            {(() => {
              const cur = focusItems[focusIdx];
              if (!cur) return null;
              return (
                <>
                  <h3 className="text-base font-semibold text-white">{cur.title}</h3>
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 whitespace-pre-wrap max-h-56 overflow-y-auto">
                    {cur.body || 'No additional preview.'}
                  </div>
                  <div className="flex flex-wrap justify-between gap-2 pt-2 border-t border-slate-800">
                    <Button
                      small
                      variant="secondary"
                      onClick={() => {
                        if (focusIdx + 1 < focusItems.length) setFocusIdx((i) => i + 1);
                        else setFocusOpen(false);
                      }}
                    >
                      Skip / Next
                    </Button>
                    <div className="flex gap-2">
                      {cur.lead_id && (
                        <Button small variant="secondary" onClick={() => { setFocusOpen(false); onOpenClient(cur.lead_id!); }}>
                          Open Client
                        </Button>
                      )}
                      {cur.kind === 'approval' && (
                        <Button
                          small
                          variant="primary"
                          onClick={async () => {
                            await decideApproval(cur.id, 'approved');
                            if (focusIdx + 1 < focusItems.length) setFocusIdx((i) => i + 1);
                            else setFocusOpen(false);
                          }}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" /> Approve &amp; Next
                        </Button>
                      )}
                    </div>
                  </div>
                </>
              );
            })()}
          </Card>
        </div>
      )}
    </div>
  );
};
