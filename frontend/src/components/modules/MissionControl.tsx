import { useEffect, useState } from 'react';
import type { FC, ReactNode } from 'react';
import {
  CheckCircle2, AlertTriangle, CircleDashed, ArrowRight, RefreshCw,
  Radar, Clock, Send, ShieldCheck, Trophy, Calendar, DollarSign, Database, Sparkles
} from 'lucide-react';
import type { TabType } from '../../types';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { DigestPanel } from '../shared/DigestPanel';
import { ErrorBanner } from '../shared/ErrorBanner';

interface MissionControlProps {
  circuitBreakerTripped: boolean;
  setActiveTab: (t: TabType) => void;
}

interface Check { key: string; label: string; status: 'ok' | 'missing' | 'optional_missing'; required: boolean; detail: string | null; fix: string | null }

const TAB_FOR_CHECK: Record<string, TabType> = {
  portfolio: 'portfolio', services: 'portfolio', mailbox: 'governance', verifier: 'governance', upwork: 'radar', pagespeed: 'doctor'
};

const Tile: FC<{ label: string; value: string | number | null; hint?: string; icon?: ReactNode; accent?: string; emptyPlaceholder?: string }> = ({
  label, value, hint, icon, accent, emptyPlaceholder = '0'
}) => (
  <div className="glass-panel-interactive rounded-2xl p-4 sm:p-5 flex flex-col justify-between relative overflow-hidden group">
    <div className={`absolute -right-6 -bottom-6 w-24 h-24 rounded-full opacity-10 blur-xl transition-opacity group-hover:opacity-25 ${accent || 'bg-indigo-500'}`} />
    
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs font-semibold text-slate-400 tracking-wide uppercase font-mono">{label}</span>
      {icon && <span className="text-slate-500 group-hover:text-indigo-400 transition-colors">{icon}</span>}
    </div>

    <div className="mt-3">
      <div className="text-2xl sm:text-3xl font-extrabold text-white font-mono tracking-tight tabular">
        {value === null || value === undefined ? (
          <span className="text-slate-400 font-semibold">{emptyPlaceholder}</span>
        ) : (
          value
        )}
      </div>
      {hint && (
        <div className="text-[11px] font-mono text-slate-400 mt-1.5 flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-slate-500 shrink-0" />
          <span>{hint}</span>
        </div>
      )}
    </div>
  </div>
);

export const MissionControl: FC<MissionControlProps> = ({ circuitBreakerTripped, setActiveTab }) => {
  const [status, setStatus] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [pending, setPending] = useState<number | null>(null);
  const [opps, setOpps] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [s, r, a, o] = await Promise.all([
        apiFetch('/api/system/status'), apiFetch('/api/analytics/learning_report'),
        apiFetch('/api/approvals/pending'), apiFetch('/api/opportunities')
      ]);
      if (!s.ok) throw new Error(apiErrorMessage(s.status, await s.json()));
      setStatus(await s.json());
      if (r.ok) setReport(await r.json());
      if (a.ok) setPending((await a.json()).length);
      if (o.ok) setOpps((await o.json()).length);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the API.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    Promise.all([apiFetch('/api/system/status'), apiFetch('/api/analytics/learning_report'), apiFetch('/api/approvals/pending'), apiFetch('/api/opportunities')])
      .then(async ([s, r, a, o]) => {
        if (!active) return;
        if (s.ok) setStatus(await s.json());
        if (r.ok) setReport(await r.json());
        if (a.ok) setPending((await a.json()).length);
        if (o.ok) setOpps((await o.json()).length);
      })
      .catch(() => active && setError('Could not reach the API.'))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const sum = report?.summary;
  const checks: Check[] = status?.checks ?? [];

  return (
    <div className="space-y-6 stagger">
      <ErrorBanner message={error} />
      {circuitBreakerTripped && (
        <div role="alert" className="p-4 rounded-xl bg-red-950/40 border border-red-500/40 text-red-200 text-xs">
          <strong className="uppercase tracking-wider">Outbound is halted.</strong> Nothing is being sent for this workspace, including scheduled sequences. Use the header button to resume.
        </div>
      )}

      {/* Sovereign Workspace Operational Status Ribbon */}
      <div className="glass-panel p-4 rounded-2xl border border-slate-800/80 bg-slate-950/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
            <ShieldCheck className="h-5 w-5 text-indigo-400" />
          </div>
          <div>
            <div className="text-xs font-semibold text-white flex items-center gap-2">
              <span>Sovereign Workspace Operational</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                Live Engine Active
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              100% sovereign business development engine. Real-time cryptographic ledger, zero third-party data vendor costs.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setActiveTab('radar')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-indigo-300 bg-indigo-950/40 hover:bg-indigo-900/40 border border-indigo-700/40 transition"
          >
            <Radar className="h-3.5 w-3.5 text-indigo-400" />
            <span>Scan Radar</span>
          </button>
          <button
            onClick={() => setActiveTab('autopilot')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition shadow-sm"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Launch Swarm</span>
          </button>
        </div>
      </div>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Mission Control</h1>
          <p className="text-sm text-slate-400 mt-0.5">Live metrics and telemetry from your sovereign business development engine.</p>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center space-x-1.5 text-xs rounded-lg border border-slate-700 px-3 py-1.5 hover:border-slate-500">
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /><span>Refresh</span>
        </button>
      </div>

      {status?.warnings?.map((w: string) => (
        <div key={w} className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">{w}</div>
      ))}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        <Tile
          label="Opportunities on Radar"
          value={opps ?? 0}
          hint={opps ? 'Active live tenders' : '0 tenders indexed'}
          icon={<Radar className="h-4 w-4" />}
          accent="bg-cyan-500"
        />
        <Tile
          label="Waiting for Approval"
          value={pending ?? 0}
          hint={pending ? 'Requires human review' : '0 pending approvals'}
          icon={<Clock className="h-4 w-4" />}
          accent="bg-amber-500"
        />
        <Tile
          label="Emails Dispatched"
          value={sum?.total_outreach_sent ?? 0}
          hint={sum?.total_outreach_sent ? `${sum.reply_rate_percent}% reply rate` : '0 emails dispatched'}
          icon={<Send className="h-4 w-4" />}
          accent="bg-indigo-500"
        />
        <Tile
          label="Fleet Deliverability"
          value={report?.deliverability_health === 'NO_DATA' ? 'Standby' : (report?.deliverability_health ?? 'Standby')}
          hint={sum?.bounce_rate_percent != null ? `${sum.bounce_rate_percent}% bounces` : '0 bounce issues'}
          icon={<ShieldCheck className="h-4 w-4" />}
          accent="bg-emerald-500"
        />
        <Tile
          label="Proposals Won"
          value={sum?.proposals_won ?? 0}
          hint={sum?.proposals_won ? 'High win velocity' : '0 deals closed'}
          icon={<Trophy className="h-4 w-4" />}
          accent="bg-purple-500"
        />
        <Tile
          label="Meetings Booked"
          value={sum?.meetings_booked ?? 0}
          hint={sum?.meetings_booked ? 'Active deal pipeline' : '0 scheduled calls'}
          icon={<Calendar className="h-4 w-4" />}
          accent="bg-emerald-500"
        />
        <Tile
          label="Tracked Spend (USD)"
          value={sum?.total_spend_usd != null ? `$${sum.total_spend_usd.toFixed(2)}` : '$0.00'}
          hint={sum?.total_spend_usd ? 'LLM + recorded infra' : '$0.00 spent'}
          icon={<DollarSign className="h-4 w-4" />}
          accent="bg-amber-500"
        />
        <Tile
          label="Evidence Records"
          value={sum?.evidence_records_stored ?? 0}
          hint={sum?.evidence_records_stored ? 'Zero-fabrication proofs' : '0 stored proofs'}
          icon={<Database className="h-4 w-4" />}
          accent="bg-indigo-500"
        />
      </div>

      <div className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-indigo-400" />
            <h2 className="text-sm font-semibold text-white">Production Readiness Checklist</h2>
          </div>
          <span className={`text-xs font-mono font-medium px-2.5 py-1 rounded-full border ${status?.ready_to_send_email ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : 'text-amber-300 border-amber-500/30 bg-amber-500/10'}`}>
            {status ? (status.ready_to_send_email ? '✓ Ready to Dispatch Outbound' : '⚠ Outbound Blocked (Setup Incomplete)') : ''}
          </span>
        </div>
        {checks.map((c) => (
          <div key={c.key} className="flex items-start justify-between gap-3 text-xs p-2.5 rounded-xl bg-slate-900/50 border border-slate-800/60 hover:border-slate-700/80 transition">
            <div className="flex items-start space-x-2.5">
              {c.status === 'ok' ? <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                : c.required ? <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" /> : <CircleDashed className="h-4 w-4 text-slate-500 shrink-0 mt-0.5" />}
              <div>
                <div className="text-slate-200 font-medium">{c.label}{c.detail ? <span className="text-slate-400 font-normal"> · {c.detail}</span> : null}</div>
                {c.fix && <div className="text-slate-400 mt-0.5">{c.fix}</div>}
              </div>
            </div>
            {c.status !== 'ok' && TAB_FOR_CHECK[c.key] && (
              <button onClick={() => setActiveTab(TAB_FOR_CHECK[c.key])} className="flex items-center space-x-1 text-cyan-400 hover:text-cyan-300 shrink-0 font-medium font-mono text-[11px] px-2 py-1 rounded-lg bg-cyan-950/30 border border-cyan-800/50">
                <span>Configure</span><ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>
        ))}
      </div>

      <DigestPanel onRefresh={load} />

      {report?.strategic_recommendations?.length > 0 && (
        <div className="glass-panel rounded-2xl p-5 sm:p-6 space-y-3">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-indigo-400" />
            <span>Autonomous Strategic Insights</span>
          </h2>
          <div className="space-y-2">
            {report.strategic_recommendations.map((r: string, i: number) => (
              <div key={i} className="text-xs text-slate-300 p-3 rounded-xl bg-slate-900/40 border border-slate-800/60 flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0 mt-1.5" />
                <span>{r}</span>
              </div>
            ))}
          </div>
          <p className="text-[11px] font-mono text-slate-500 pt-1">Costs not tracked: {report.costs_not_tracked.join(', ')}.</p>
        </div>
      )}
    </div>
  );
};
