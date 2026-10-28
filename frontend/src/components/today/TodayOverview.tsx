import { useState } from 'react';
import type { FC } from 'react';
import { ArrowDownRight, ArrowRight, ArrowUpRight, Check, ChevronDown, ChevronUp, Copy, Minus, Sparkles } from 'lucide-react';
import { Badge, Card, Skeletons } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useApi } from '../../lib/hooks';
import type { Surface } from '../../types';

interface Pair { now: number; before: number }
interface Focus { priority: number; title: string; detail: string; target: { surface: Surface; lead_id?: number; section?: string; anchor?: string } }
export interface TodaySummary {
  kpis: { new_leads: Pair; audits: Pair; emails_sent: Pair; replies: Pair; pending_approvals: number; open_tasks: number; hot_leads: number; pipeline_value: number | null; win_rate_percent: number | null; unvalued_deals: number; client_followups_due?: number };
  focus: Focus[];
  activity: Array<{ at: string; what: string; actor: string; lead_id: number | null; company: string | null }>;
  channels: Array<{ platform: string; label: string; open: number; followups_due: number; unanswered: number; routine: { total: number; done_today: number; streak_days: number } }>;
  note?: string;
}

interface BriefingData {
  headline: string;
  date: string;
  pipeline_value_str: string;
  followups_due: number;
  pending_approvals: number;
  overnight_visitors: number;
  focus_items: Focus[];
  markdown: string;
}

const greeting = (now: Date) => { const h = now.getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; };

/** Week-over-week change. With no earlier activity there is nothing honest to compare against, so it says so instead of a percentage. */
const Delta: FC<{ p: Pair }> = ({ p }) => {
  if (p.before === 0 && p.now === 0) return <span className="text-[11px] text-slate-500 inline-flex items-center gap-1"><Minus className="h-3 w-3" />no activity yet</span>;
  if (p.before === 0) return <span className="text-[11px] text-emerald-400 inline-flex items-center gap-1"><ArrowUpRight className="h-3 w-3" />new this week</span>;
  const diff = p.now - p.before;
  if (diff === 0) return <span className="text-[11px] text-slate-500 inline-flex items-center gap-1"><Minus className="h-3 w-3" />same as last week</span>;
  const up = diff > 0;
  return <span className={`text-[11px] inline-flex items-center gap-1 ${up ? 'text-emerald-400' : 'text-amber-400'}`}>{up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}{Math.abs(Math.round((100 * diff) / p.before))}% vs last week</span>;
};

const Kpi: FC<{ label: string; p: Pair }> = ({ label, p }) => (
  <div className="bento-tile rounded-2xl p-4">
    <div className="text-xs text-slate-400">{label}</div>
    <div className="text-2xl font-semibold text-white tabular mt-1">{p.now}</div>
    <div className="mt-1"><Delta p={p} /></div>
    <div className="text-[11px] text-slate-500">last 7 days</div>
  </div>
);

export const TodayOverview: FC<{ onGo: (s: Surface, opts?: { leadId?: number; section?: string }) => void }> = ({ onGo }) => {
  const [now] = useState(() => new Date());
  const sum = useApi<TodaySummary>('/api/today/summary');
  const briefing = useApi<BriefingData>('/api/today/briefing');
  const [showBriefingMarkdown, setShowBriefingMarkdown] = useState(false);
  const [copiedBriefing, setCopiedBriefing] = useState(false);

  const copyBriefing = () => {
    if (briefing.data?.markdown) {
      navigator.clipboard.writeText(briefing.data.markdown);
      setCopiedBriefing(true);
      setTimeout(() => setCopiedBriefing(false), 2000);
    }
  };

  const d = sum.data;
  const go = (t: Focus['target']) => onGo(t.surface, { leadId: t.lead_id, section: t.section });
  const attention = d?.channels.filter((c) => c.followups_due || c.unanswered) ?? [];

  return (
    <div className="space-y-5">
      <ErrorBanner message={sum.error} />
      <Card>
        <div className="text-xs text-slate-400">{now.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</div>
        <h2 className="text-lg font-semibold text-white mt-0.5">{greeting(now)}. {d && d.focus.length === 0 ? 'Nothing is urgent.' : 'Here is what matters most.'}</h2>

        {briefing.data && (
          <div className="mt-3.5 mb-1 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/90 flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded-lg bg-amber-500/20 text-amber-400 shrink-0">
                <Sparkles className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="font-semibold text-white text-xs sm:text-sm flex items-center gap-2 flex-wrap">
                  Executive Morning Briefing
                  <Badge tone="accent">Live Radar</Badge>
                </div>
                <p className="text-slate-400 text-xs mt-0.5">
                  <span className="text-slate-200 font-medium">{briefing.data.pipeline_value_str}</span> active pipeline · <span className="text-slate-200 font-medium">{briefing.data.followups_due}</span> client follow-ups due · <span className="text-slate-200 font-medium">{briefing.data.overnight_visitors}</span> corporate visits detected
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setShowBriefingMarkdown(!showBriefingMarkdown)}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs transition-colors"
              >
                {showBriefingMarkdown ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                {showBriefingMarkdown ? 'Hide full text' : 'Read full text'}
              </button>
              <button
                onClick={copyBriefing}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-xs transition-colors font-medium"
                title="Copy complete briefing markdown for team Slack or notes"
              >
                {copiedBriefing ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                {copiedBriefing ? 'Copied!' : 'Copy Briefing'}
              </button>
            </div>
          </div>
        )}

        {showBriefingMarkdown && briefing.data && (
          <div className="mt-2 mb-3 p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 text-slate-300 text-xs font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
            {briefing.data.markdown}
          </div>
        )}

        {sum.loading && !d ? <div className="mt-3"><Skeletons rows={2} /></div> : d && d.focus.length > 0 && (
          <ol className="mt-3 grid gap-2 md:grid-cols-3">
            {d.focus.map((f, i) => (
              <li key={f.title}>
                <button onClick={() => go(f.target)} className="w-full h-full text-left rounded-xl border border-slate-800 hover:border-indigo-500/60 p-3 transition-colors group">
                  <div className="flex items-start gap-2">
                    <span className="h-5 w-5 rounded-full bg-indigo-500/15 text-indigo-300 text-[11px] font-semibold flex items-center justify-center shrink-0 tabular">{i + 1}</span>
                    <div className="min-w-0"><div className="text-sm font-medium text-slate-100">{f.title}</div><div className="text-xs text-slate-400 mt-0.5">{f.detail}</div></div>
                    <ArrowRight className="h-4 w-4 text-slate-600 group-hover:text-indigo-400 shrink-0 ml-auto" />
                  </div>
                </button>
              </li>))}
          </ol>)}
      </Card>

      {d && (
        <>
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <Kpi label="New prospects" p={d.kpis.new_leads} />
            <Kpi label="Sites audited" p={d.kpis.audits} />
            <Kpi label="Emails sent" p={d.kpis.emails_sent} />
            <Kpi label="Replies" p={d.kpis.replies} />
          </div>
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <div className="bento-tile rounded-2xl p-4"><div className="text-xs text-slate-400">Hot prospects</div><div className="text-2xl font-semibold text-white tabular mt-1">{d.kpis.hot_leads}</div><div className="text-[11px] text-slate-500 mt-1">priority score 70 or more</div></div>
            <div className="bento-tile rounded-2xl p-4"><div className="text-xs text-slate-400">Pipeline value</div><div className="text-2xl font-semibold text-white tabular mt-1">{!d.kpis.pipeline_value ? 'n/a' : `$${Math.round(d.kpis.pipeline_value).toLocaleString()}`}</div><div className="text-[11px] text-slate-500 mt-1">{d.kpis.unvalued_deals ? `${d.kpis.unvalued_deals} deal(s) have no value set` : 'from the values you entered'}</div></div>
            <div className="bento-tile rounded-2xl p-4"><div className="text-xs text-slate-400">Win rate</div><div className="text-2xl font-semibold text-white tabular mt-1">{d.kpis.win_rate_percent === null ? 'n/a' : `${d.kpis.win_rate_percent}%`}</div><div className="text-[11px] text-slate-500 mt-1">{d.kpis.win_rate_percent === null ? 'needs closed deals' : 'of closed deals'}</div></div>
            <div className="bento-tile rounded-2xl p-4"><div className="text-xs text-slate-400">Tasks for you</div><div className="text-2xl font-semibold text-white tabular mt-1">{d.kpis.open_tasks}</div><div className="text-[11px] text-slate-500 mt-1">{d.kpis.pending_approvals} draft(s) to approve</div></div>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <div className="flex items-center justify-between mb-2"><h2 className="text-sm font-semibold text-white">Channels</h2><button onClick={() => onGo('channels')} className="text-xs text-indigo-400 hover:underline">Open Channels</button></div>
              {attention.length === 0 ? <p className="text-xs text-slate-400">No follow-ups due and no messages waiting.</p> : (
                <ul className="divide-y divide-slate-800">{attention.map((c) => (
                  <li key={c.platform}><button onClick={() => onGo('channels')} className="w-full flex items-center gap-2 py-2 text-left">
                    <span className="text-sm text-slate-200 flex-1">{c.label}</span>
                    {c.unanswered > 0 && <Badge tone="warn">{c.unanswered} waiting</Badge>}{c.followups_due > 0 && <Badge tone="warn">{c.followups_due} follow-up</Badge>}
                  </button></li>))}</ul>)}
              <div className="flex flex-wrap gap-2 mt-3">{d.channels.filter((c) => c.open > 0).map((c) => <Badge key={c.platform} tone="accent">{c.label}: {c.open} open</Badge>)}</div>
            </Card>
            <Card>
              <h2 className="text-sm font-semibold text-white mb-2">Recent activity</h2>
              {d.activity.length === 0 ? <p className="text-xs text-slate-400">Activity appears here as work happens.</p> : (
                <ul className="space-y-2">{d.activity.slice(0, 6).map((a, i) => (
                  <li key={`${a.at}-${i}`} className="flex gap-2 text-xs">
                    <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-indigo-500 shrink-0" aria-hidden="true" />
                    <span className="flex-1 min-w-0 text-slate-300 truncate">{a.what}{a.company ? ` · ${a.company}` : ''}</span>
                    <time className="text-slate-500 shrink-0" dateTime={a.at}>{new Date(a.at.replace(' ', 'T') + (a.at.includes('Z') || a.at.includes('+') ? '' : 'Z')).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</time>
                  </li>))}</ul>)}
            </Card>
          </div>
        </>)}
    </div>
  );
};
