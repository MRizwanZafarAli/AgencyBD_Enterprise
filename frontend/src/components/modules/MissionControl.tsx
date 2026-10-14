import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { CheckCircle2, AlertTriangle, CircleDashed, ArrowRight, RefreshCw } from 'lucide-react';
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

const Tile: FC<{ label: string; value: string | number | null; hint?: string }> = ({ label, value, hint }) => (
  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
    <div className="text-xs text-slate-400">{label}</div>
    <div className="text-2xl font-extrabold text-white font-mono mt-1">{value === null || value === undefined ? 'n/a' : value}</div>
    {hint && <div className="text-[11px] text-slate-500 mt-1">{hint}</div>}
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

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Mission Control</h1>
          <p className="text-sm text-slate-400 mt-0.5">Live numbers from your workspace. Nothing here is a demo figure: an empty box means nothing has happened yet.</p>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center space-x-1.5 text-xs rounded-lg border border-slate-700 px-3 py-1.5 hover:border-slate-500">
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /><span>Refresh</span>
        </button>
      </div>

      {status?.warnings?.map((w: string) => (
        <div key={w} className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">{w}</div>
      ))}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Tile label="Opportunities on the Radar" value={opps} hint="from your connected sources" />
        <Tile label="Waiting for your approval" value={pending} hint="proposals and emails" />
        <Tile label="Emails sent" value={sum?.total_outreach_sent ?? null} hint={sum?.reply_rate_percent != null ? `${sum.reply_rate_percent}% reply rate` : 'no sends yet'} />
        <Tile label="Deliverability" value={report?.deliverability_health ?? null} hint={sum?.bounce_rate_percent != null ? `${sum.bounce_rate_percent}% bounces` : undefined} />
        <Tile label="Proposals won" value={sum?.proposals_won ?? null} />
        <Tile label="Meetings booked" value={sum?.meetings_booked ?? null} />
        <Tile label="Tracked spend (USD)" value={sum ? sum.total_spend_usd : null} hint="LLM + costs you record" />
        <Tile label="Evidence records" value={sum?.evidence_records_stored ?? null} hint="measured facts behind briefs" />
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Setup checklist</h2>
          <span className={`text-xs font-mono ${status?.ready_to_send_email ? 'text-emerald-400' : 'text-amber-300'}`}>
            {status ? (status.ready_to_send_email ? 'ready to send email' : 'email sending blocked until required items are done') : ''}
          </span>
        </div>
        {checks.map((c) => (
          <div key={c.key} className="flex items-start justify-between gap-3 text-xs">
            <div className="flex items-start space-x-2">
              {c.status === 'ok' ? <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                : c.required ? <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" /> : <CircleDashed className="h-4 w-4 text-slate-500 shrink-0" />}
              <div>
                <div className="text-slate-200">{c.label}{c.detail ? <span className="text-slate-500"> · {c.detail}</span> : null}</div>
                {c.fix && <div className="text-slate-400">{c.fix}</div>}
              </div>
            </div>
            {c.status !== 'ok' && TAB_FOR_CHECK[c.key] && (
              <button onClick={() => setActiveTab(TAB_FOR_CHECK[c.key])} className="flex items-center space-x-1 text-cyan-400 hover:text-cyan-300 shrink-0">
                <span>Open</span><ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>
        ))}
      </div>

      <DigestPanel />

      {report?.strategic_recommendations?.length > 0 && (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-2">
          <h2 className="text-sm font-semibold text-white">What the data says</h2>
          {report.strategic_recommendations.map((r: string, i: number) => <p key={i} className="text-xs text-slate-300">• {r}</p>)}
          <p className="text-[11px] text-slate-500">Costs not tracked: {report.costs_not_tracked.join(', ')}.</p>
        </div>
      )}
    </div>
  );
};
