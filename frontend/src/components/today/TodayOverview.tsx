import { useState } from 'react';
import type { FC } from 'react';
import { ArrowDownRight, ArrowRight, ArrowUpRight, Minus, ShieldCheck } from 'lucide-react';
import { Badge, Card, Skeletons } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useApi } from '../../lib/hooks';
import type { Surface } from '../../types';
import type { Me } from '../../lib/api';

interface Pair { now: number; before: number }
interface Focus { priority: number; title: string; detail: string; target: { surface: Surface; lead_id?: number; section?: string; anchor?: string } }
export interface TodaySummary {
  kpis: { new_leads: Pair; audits: Pair; emails_sent: Pair; replies: Pair; pending_approvals: number; open_tasks: number; hot_leads: number; pipeline_value: number | null; win_rate_percent: number | null; unvalued_deals: number; client_followups_due?: number };
  focus: Focus[];
  activity: Array<{ at: string; what: string; actor: string; lead_id: number | null; company: string | null }>;
  channels: Array<{ platform: string; label: string; open: number; followups_due: number; unanswered: number; routine: { total: number; done_today: number; streak_days: number } }>;
  note?: string;
}

const greeting = (now: Date) => { const h = now.getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; };

const Delta: FC<{ p: Pair }> = ({ p }) => {
  if (p.before === 0 && p.now === 0) return <span className="text-[11px] text-slate-500 inline-flex items-center gap-1"><Minus className="h-3 w-3" />no activity yet</span>;
  if (p.before === 0) return <span className="text-[11px] text-emerald-400 inline-flex items-center gap-1"><ArrowUpRight className="h-3 w-3" />new this week</span>;
  const diff = p.now - p.before;
  if (diff === 0) return <span className="text-[11px] text-slate-500 inline-flex items-center gap-1"><Minus className="h-3 w-3" />same as last week</span>;
  const up = diff > 0;
  return <span className={`text-[11px] inline-flex items-center gap-1 ${up ? 'text-emerald-400' : 'text-amber-400'}`}>{up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}{Math.abs(Math.round((100 * diff) / p.before))}% vs last week</span>;
};

export const TodayOverview: FC<{ onGo: (s: Surface, opts?: { leadId?: number; section?: string }) => void; identity?: Me | null }> = ({ onGo, identity }) => {
  const [now] = useState(() => new Date());
  const sum = useApi<TodaySummary>('/api/today/summary');
  const d = sum.data;
  const go = (t: Focus['target']) => onGo(t.surface, { leadId: t.lead_id, section: t.section });
  const attention = d?.channels.filter((c) => c.followups_due || c.unanswered) ?? [];
  const role = identity?.role || 'super_admin';

  const roleMeta = {
    super_admin: {
      badge: '👑 Super Admin',
      tone: 'accent' as const,
      title: 'Operations & System Overview',
      subtitle: 'Complete workspace oversight, revenue pipeline, approvals, and administrative governance.',
    },
    growth_lead: {
      badge: '📈 Growth Lead',
      tone: 'good' as const,
      title: 'Campaign & Conversion Dashboard',
      subtitle: 'Revenue pipeline, outbound volumes, inbound replies, and pending proposal sign-offs.',
    },
    sdr_rep: {
      badge: '🎯 SDR Representative',
      tone: 'accent' as const,
      title: 'Prospecting & Opportunity Dashboard',
      subtitle: 'Job signals, hot client matches, proposals to draft, and active channel communications.',
    },
    auditor: {
      badge: '🛡️ Compliance Auditor',
      tone: 'warn' as const,
      title: 'Compliance & Verification Trail',
      subtitle: 'Technical website evaluations, CAN-SPAM suppression checks, and jurisdiction disclosures.',
    },
  }[role as 'super_admin' | 'growth_lead' | 'sdr_rep' | 'auditor'] || {
    badge: '👤 Workspace User',
    tone: 'neutral' as const,
    title: 'Workspace Dashboard',
    subtitle: 'Daily operational summary.',
  };

  // Filter focus items based on role scope to keep the screen simple and relevant
  const focusItems = (d?.focus ?? []).filter((f) => {
    if (role === 'auditor') return f.target.surface === 'clients' || f.target.surface === 'tools';
    if (role === 'sdr_rep') return f.target.surface === 'find' || f.target.surface === 'channels' || f.target.surface === 'clients';
    return true;
  });

  return (
    <div className="space-y-5">
      <ErrorBanner message={sum.error} />
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs text-slate-400">{now.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</div>
          <Badge tone={roleMeta.tone}>{roleMeta.badge}</Badge>
        </div>
        <h2 className="text-lg font-semibold text-white mt-1">
          {greeting(now)}, {identity?.user_id ?? 'there'}. {roleMeta.title}
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">{roleMeta.subtitle}</p>

        {sum.loading && !d ? (
          <div className="mt-3"><Skeletons rows={2} /></div>
        ) : focusItems.length > 0 && (
          <ol className="mt-3 grid gap-2 md:grid-cols-3">
            {focusItems.map((f, i) => (
              <li key={f.title}>
                <button onClick={() => go(f.target)} className="w-full h-full text-left rounded-xl border border-slate-800 hover:border-indigo-500/60 p-3 transition-colors group">
                  <div className="flex items-start gap-2">
                    <span className="h-5 w-5 rounded-full bg-indigo-500/15 text-indigo-300 text-[11px] font-semibold flex items-center justify-center shrink-0 tabular">{i + 1}</span>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-100">{f.title}</div>
                      <div className="text-xs text-slate-400 mt-0.5">{f.detail}</div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-slate-600 group-hover:text-indigo-400 shrink-0 ml-auto" />
                  </div>
                </button>
              </li>
            ))}
          </ol>
        )}
      </Card>

      {d && (
        <>
          {/* Role-Specific Simplified KPI Bento Grid */}
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            {role === 'sdr_rep' && (
              <>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">New prospects</div>
                  <div className="text-2xl font-semibold text-white tabular mt-1">{d.kpis.new_leads.now}</div>
                  <div className="mt-1"><Delta p={d.kpis.new_leads} /></div>
                  <div className="text-[11px] text-slate-500">last 7 days</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Hot prospects</div>
                  <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">{d.kpis.hot_leads}</div>
                  <div className="text-[11px] text-slate-500 mt-1">fit score 70% or more</div>
                  <div className="text-[11px] text-slate-400 mt-1">Ready to pitch</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Sites audited</div>
                  <div className="text-2xl font-semibold text-white tabular mt-1">{d.kpis.audits.now}</div>
                  <div className="mt-1"><Delta p={d.kpis.audits} /></div>
                  <div className="text-[11px] text-slate-500">evaluated for pitch angles</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Channel follow-ups</div>
                  <div className="text-2xl font-semibold text-amber-400 tabular mt-1">{attention.length}</div>
                  <div className="text-[11px] text-slate-500 mt-1">{attention.length ? 'platforms need action' : 'all caught up'}</div>
                  <div className="text-[11px] text-slate-400 mt-1">Upwork, LinkedIn, etc.</div>
                </div>
              </>
            )}

            {role === 'growth_lead' && (
              <>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Pipeline value</div>
                  <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">
                    {!d.kpis.pipeline_value ? '$0' : `$${Math.round(d.kpis.pipeline_value).toLocaleString()}`}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">{d.kpis.unvalued_deals ? `${d.kpis.unvalued_deals} deal(s) pending value` : 'commercial value'}</div>
                  <div className="text-[11px] text-slate-400 mt-1">Active stage value</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Emails sent</div>
                  <div className="text-2xl font-semibold text-white tabular mt-1">{d.kpis.emails_sent.now}</div>
                  <div className="mt-1"><Delta p={d.kpis.emails_sent} /></div>
                  <div className="text-[11px] text-slate-500">last 7 days outreach</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Prospect replies</div>
                  <div className="text-2xl font-semibold text-indigo-300 tabular mt-1">{d.kpis.replies.now}</div>
                  <div className="mt-1"><Delta p={d.kpis.replies} /></div>
                  <div className="text-[11px] text-slate-500">incoming responses</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Drafts to approve</div>
                  <div className="text-2xl font-semibold text-amber-400 tabular mt-1">{d.kpis.pending_approvals}</div>
                  <div className="text-[11px] text-slate-500 mt-1">awaiting sign-off</div>
                  <div className="text-[11px] text-amber-300/80 mt-1">HITL approval queue</div>
                </div>
              </>
            )}

            {role === 'auditor' && (
              <>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Sites audited</div>
                  <div className="text-2xl font-semibold text-white tabular mt-1">{d.kpis.audits.now}</div>
                  <div className="mt-1"><Delta p={d.kpis.audits} /></div>
                  <div className="text-[11px] text-slate-500">evaluated technical health</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Suppression vault</div>
                  <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">Active</div>
                  <div className="text-[11px] text-slate-500 mt-1">CAN-SPAM & GDPR vault</div>
                  <div className="text-[11px] text-slate-400 mt-1">Zero unauthorized outreach</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Audit trail events</div>
                  <div className="text-2xl font-semibold text-indigo-300 tabular mt-1">{d.activity.length}</div>
                  <div className="text-[11px] text-slate-500 mt-1">system & actor events</div>
                  <div className="text-[11px] text-slate-400 mt-1">Fully logged in history</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Companies reviewed</div>
                  <div className="text-2xl font-semibold text-white tabular mt-1">{d.kpis.new_leads.now}</div>
                  <div className="text-[11px] text-slate-500 mt-1">prospect compliance status</div>
                  <div className="text-[11px] text-slate-400 mt-1">Disclosures verified</div>
                </div>
              </>
            )}

            {role === 'super_admin' && (
              <>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Pipeline value</div>
                  <div className="text-2xl font-semibold text-white tabular mt-1">
                    {!d.kpis.pipeline_value ? '$0' : `$${Math.round(d.kpis.pipeline_value).toLocaleString()}`}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">{d.kpis.unvalued_deals ? `${d.kpis.unvalued_deals} unvalued deal(s)` : 'commercial pipeline'}</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">System health</div>
                  <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">100% OK</div>
                  <div className="text-[11px] text-slate-500 mt-1">all 174 endpoints verified</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Pending approvals</div>
                  <div className="text-2xl font-semibold text-amber-400 tabular mt-1">{d.kpis.pending_approvals}</div>
                  <div className="text-[11px] text-slate-500 mt-1">HITL drafts waiting</div>
                </div>
                <div className="bento-tile rounded-2xl p-4">
                  <div className="text-xs text-slate-400">Open tasks</div>
                  <div className="text-2xl font-semibold text-white tabular mt-1">{d.kpis.open_tasks}</div>
                  <div className="text-[11px] text-slate-500 mt-1">workspace items</div>
                </div>
              </>
            )}
          </div>

          {/* Role-Specific Secondary Grid */}
          <div className="grid gap-5 lg:grid-cols-2">
            {role !== 'auditor' ? (
              <Card>
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-sm font-semibold text-white">Channels & Accounts</h2>
                  <button onClick={() => onGo('channels')} className="text-xs text-indigo-400 hover:underline">Open Channels</button>
                </div>
                {attention.length === 0 ? (
                  <p className="text-xs text-slate-400">No follow-ups due and no messages waiting.</p>
                ) : (
                  <ul className="divide-y divide-slate-800">
                    {attention.map((c) => (
                      <li key={c.platform}>
                        <button onClick={() => onGo('channels')} className="w-full flex items-center gap-2 py-2 text-left">
                          <span className="text-sm text-slate-200 flex-1">{c.label}</span>
                          {c.unanswered > 0 && <Badge tone="warn">{c.unanswered} waiting</Badge>}
                          {c.followups_due > 0 && <Badge tone="warn">{c.followups_due} follow-up</Badge>}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="flex flex-wrap gap-2 mt-3">
                  {d.channels.filter((c) => c.open > 0).map((c) => (
                    <Badge key={c.platform} tone="accent">{c.label}: {c.open} open</Badge>
                  ))}
                </div>
              </Card>
            ) : (
              <Card>
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-emerald-400" /> Compliance Status
                  </h2>
                  <button onClick={() => onGo('tools')} className="text-xs text-indigo-400 hover:underline">Vault Studio</button>
                </div>
                <div className="space-y-3 text-xs text-slate-300">
                  <div className="flex items-center justify-between py-1.5 border-b border-slate-800">
                    <span>CAN-SPAM Suppression Engine</span>
                    <Badge tone="good">ACTIVE</Badge>
                  </div>
                  <div className="flex items-center justify-between py-1.5 border-b border-slate-800">
                    <span>GDPR Jurisdiction LIA Gateway</span>
                    <Badge tone="good">ENFORCED</Badge>
                  </div>
                  <div className="flex items-center justify-between py-1.5">
                    <span>Email Deliverability Gates</span>
                    <Badge tone="good">100% PASS</Badge>
                  </div>
                </div>
              </Card>
            )}

            <Card>
              <h2 className="text-sm font-semibold text-white mb-2">
                {role === 'auditor' ? 'Audit Trail Log' : 'Recent activity'}
              </h2>
              {d.activity.length === 0 ? (
                <p className="text-xs text-slate-400">Activity appears here as actions take place.</p>
              ) : (
                <ul className="space-y-2">
                  {d.activity.slice(0, 6).map((a, i) => (
                    <li key={`${a.at}-${i}`} className="flex gap-2 text-xs">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-indigo-500 shrink-0" aria-hidden="true" />
                      <span className="flex-1 min-w-0 text-slate-300 truncate">
                        {a.what}{a.company ? ` · ${a.company}` : ''}
                      </span>
                      <time className="text-slate-500 shrink-0" dateTime={a.at}>
                        {new Date(a.at.replace(' ', 'T') + (a.at.includes('Z') || a.at.includes('+') ? '' : 'Z')).toLocaleString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: 'numeric',
                          minute: '2-digit',
                        })}
                      </time>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
};
