import { useEffect, useRef, useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Play, ChevronDown, ChevronRight } from 'lucide-react';
import { Button, Card, Badge, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send } from '../../lib/hooks';
import { apiFetch, apiErrorMessage } from '../../lib/api';

interface Skipped { name: string; reason: string }
interface RunLead { lead_id: number; company_name: string; domain: string; outcome: string; band?: string; priority?: number; reason?: string }
interface RunProgress { log: Array<{ step: string; message: string }>; processed: number }
interface RunStatus { run_id: string; status: 'running' | 'done' | 'failed'; error: string | null; progress: RunProgress | null; result?: RunResult }
interface RunResult { channel: string; sourced: number; skipped: Skipped[]; errors: string[]; drafts_pending_approval: number; work_items_opened: number; leads: RunLead[] }

const CHANNELS = [
  { id: 'hiring', label: 'Companies hiring engineers', query: 'Role keyword (e.g. React)', needsLocation: false },
  { id: 'local', label: 'Local businesses', query: 'Business type (e.g. dentist)', needsLocation: true },
  { id: 'sec_edgar', label: 'Newly funded companies (SEC filings)', query: '', needsLocation: false },
];
const OUTCOMES: Record<string, { text: string; tone: 'good' | 'warn' | 'neutral' | 'bad' }> = {
  draft_pending_approval: { text: 'Draft waiting for your approval', tone: 'good' },
  needs_contact: { text: 'Needs a decision maker', tone: 'warn' },
  nothing_to_say: { text: 'Nothing specific to say yet', tone: 'neutral' },
  blocked_by_policy: { text: 'Blocked by policy', tone: 'bad' },
  audit_failed: { text: 'Audit failed', tone: 'bad' },
};

export const DiscoveryPanel: FC<{ onDone: () => void; onOpenClient: (leadId: number) => void }> = ({ onDone, onOpenClient }) => {
  const [channel, setChannel] = useState('hiring');
  const [query, setQuery] = useState('');
  const [location, setLocation] = useState('');
  const [limit, setLimit] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<RunResult | null>(null);
  const [showSkipped, setShowSkipped] = useState(false);
  const [progress, setProgress] = useState<RunProgress | null>(null);
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);
  const def = CHANNELS.find((c) => c.id === channel)!;

  const poll = (runId: string) => {
    timer.current = window.setTimeout(async () => {
      try {
        const res = await apiFetch(`/api/autopilot/runs/${runId}`);
        const body: RunStatus = await res.json().catch(() => ({}) as RunStatus);
        if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
        setProgress(body.progress);
        if (body.status === 'running') return poll(runId);
        setBusy(false);
        if (body.status === 'failed') setError(body.error ?? 'The run failed.');
        else if (body.result) { setResult(body.result); onDone(); }
      } catch (err) {
        setBusy(false);
        setError(err instanceof Error ? err.message : 'Lost contact with the server.');
      }
    }, 1500);
  };

  const run = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    setResult(null);
    setProgress(null);
    try {
      const started = await send<{ run_id: string }>('/api/autopilot/run', 'POST', { channel, query, location, limit });
      poll(started.run_id);
    } catch (err) {
      setBusy(false);
      setError(err instanceof Error ? err.message : 'The run failed.');
    }
  };

  return (
    <Card>
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <h2 className="text-sm font-semibold text-white">Find and prepare new prospects</h2>
        <span className="text-[11px] text-slate-500">Checks the website, audits it, scores it, drafts for your approval. Sends nothing.</span>
      </div>
      <form onSubmit={run} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 items-end">
        <label className="text-xs text-slate-400 space-y-1 lg:col-span-2">Where to look
          <select className={field} value={channel} onChange={(e) => setChannel(e.target.value)}>
            {CHANNELS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </label>
        {def.query && (
          <label className="text-xs text-slate-400 space-y-1">{def.id === 'local' ? 'Business type' : 'Keyword'}
            <input className={field} required={channel === 'local'} placeholder={def.query} value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
        )}
        {def.needsLocation && (
          <label className="text-xs text-slate-400 space-y-1">City
            <input className={field} required placeholder="Leeds, UK" value={location} onChange={(e) => setLocation(e.target.value)} />
          </label>
        )}
        <label className="text-xs text-slate-400 space-y-1">How many
          <select className={field} value={limit} onChange={(e) => setLimit(Number(e.target.value))}>{[3, 5, 10, 20].map((n) => <option key={n}>{n}</option>)}</select>
        </label>
        <Button variant="primary" disabled={busy}><Play className="h-3.5 w-3.5" />{busy ? 'Running…' : 'Run'}</Button>
      </form>
      <div className="mt-3"><ErrorBanner message={error} /></div>
      {busy && (
        <div className="mt-3 space-y-1.5" role="status" aria-live="polite">
          <div className="skeleton h-2 w-1/2" />
          {(progress?.log ?? []).slice(-4).map((l, i) => <div key={i} className="text-xs text-slate-400">{l.message}</div>)}
          {!progress && <div className="text-xs text-slate-400">Starting… checking websites can take a minute.</div>}
        </div>
      )}

      {result && (
        <div className="mt-4 space-y-3 animate-fade-up">
          <div className="flex flex-wrap gap-2 text-xs">
            <Badge tone="accent">{result.sourced} with a verified website</Badge>
            <Badge tone="good">{result.drafts_pending_approval} drafts waiting</Badge>
            <Badge tone="warn">{result.work_items_opened} tasks for you</Badge>
            <Badge>{result.skipped.length} skipped</Badge>
          </div>
          {result.errors.map((m) => <ErrorBanner key={m} message={`Source problem: ${m}`} />)}
          <ul className="divide-y divide-slate-800">
            {result.leads.map((l) => {
              const o = OUTCOMES[l.outcome] ?? { text: l.outcome.replace(/_/g, ' '), tone: 'neutral' as const };
              return (
                <li key={l.lead_id} className="py-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                  <button className="text-left text-slate-100 hover:text-white" onClick={() => onOpenClient(l.lead_id)}>
                    <span className="font-medium">{l.company_name}</span> <span className="text-slate-500 font-mono text-xs">{l.domain}</span>
                  </button>
                  <span className="flex items-center gap-2">
                    {l.priority !== undefined && <Badge tone={l.band === 'hot' ? 'good' : l.band === 'warm' ? 'accent' : 'neutral'}>{l.band} · {l.priority}</Badge>}
                    <Badge tone={o.tone}>{o.text}</Badge>
                  </span>
                </li>
              );
            })}
          </ul>
          {result.skipped.length > 0 && (
            <div>
              <button onClick={() => setShowSkipped((v) => !v)} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200">
                {showSkipped ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}Why {result.skipped.length} were skipped
              </button>
              {showSkipped && (
                <ul className="mt-2 space-y-1 text-xs text-slate-400">
                  {result.skipped.map((s, i) => <li key={i}><span className="text-slate-300">{s.name}</span>: {s.reason}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
};
