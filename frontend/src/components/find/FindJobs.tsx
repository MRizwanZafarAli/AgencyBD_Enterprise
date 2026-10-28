import { matchesQuery } from '../../lib/textMatch';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { FC } from 'react';
import { RefreshCw, ExternalLink, Sparkles } from 'lucide-react';
import { Badge, Button, Card, Drawer, EmptyState, Pager, ScoreBar, Skeletons, SuggestInput, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { normalizeUrl } from '../../lib/urls';

interface Opp {
  id: number; type: string; source: string; title: string; description: string | null; company_name: string | null; budget_min: number | null; budget_max: number | null;
  currency: string | null; url: string | null; posted_at: string | null; fit_score: number | null; fit_reasons: string[]; risk_flags: string[];
}
interface Source { source: string; status: string; detail?: string; requires_api_key: boolean; last_run: { status: string; fetched: number; stored: number; detail?: string } | null }
interface Variant { body: string; focus?: string; verification?: { ok: boolean; violations?: string[] } }
interface Draft { status: string; variant_a: Variant; variant_b: Variant; no_relevant_proof: boolean }
interface Fit { verdict: string; summary: string; reasons: Array<{ point: string; quote: string }>; risks: Array<{ point: string; quote: string }>; questions_to_ask: string[]; unsupported_points_dropped: number }

const PAGE = 15;
const TYPE_LABEL: Record<string, string> = { marketplace: 'Project', tender: 'Tender', hiring_signal: 'Hiring', inbound: 'Request', outbound: 'Outbound' };

export interface JobsPreset { q: string; min_budget?: number | null; max_budget?: number | null; remote?: boolean; nonce: number }

export const FindJobs: FC<{ types?: string[]; preset?: JobsPreset | null }> = ({ types, preset }) => {
  const opps = useApi<Opp[]>('/api/opportunities?limit=200');
  const sources = useApi<Source[]>('/api/connectors');
  const [q, setQ] = useState('');
  const [source, setSource] = useState('');
  const [minFit, setMinFit] = useState(0);
  const [minBudget, setMinBudget] = useState('');
  const [maxBudget, setMaxBudget] = useState('');
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [scanNote, setScanNote] = useState('');
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);
  const [error, setError] = useState('');
  const [open, setOpen] = useState<Opp | null>(null);
  const [fit, setFit] = useState<Fit | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState('');
  const [panelError, setPanelError] = useState('');


  const seen = useRef(0);
  useEffect(() => {
    if (!preset || preset.nonce === seen.current) return;
    seen.current = preset.nonce;
    const t = window.setTimeout(() => { setQ(preset.q); setMinBudget(preset.min_budget ? String(preset.min_budget) : ''); setMaxBudget(preset.max_budget ? String(preset.max_budget) : ''); setRemoteOnly(!!preset.remote); setSource(''); setMinFit(0); setPage(0); }, 0);
    return () => window.clearTimeout(t);
  }, [preset]);

  const rows = useMemo(() => (opps.data ?? []).filter((o) =>
    (!types || types.includes(o.type)) && (!source || o.source === source) && (o.fit_score ?? 0) * 100 >= minFit &&
    (!minBudget || (o.budget_max ?? -1) >= Number(minBudget)) && (!maxBudget || (o.budget_max != null && o.budget_max <= Number(maxBudget))) &&
    (!remoteOnly || /remote|anywhere|worldwide/i.test(`${o.title} ${o.description ?? ''}`)) &&
    matchesQuery(`${o.title} ${o.company_name ?? ''} ${o.description ?? ''}`, q)), [opps.data, types, source, minFit, q, minBudget, maxBudget, remoteOnly]);
  const sourceNames = useMemo(() => Array.from(new Set((opps.data ?? []).filter((o) => !types || types.includes(o.type)).map((o) => o.source))).sort(), [opps.data, types]);

  const poll = (runId: string) => {
    timer.current = window.setTimeout(async () => {
      try {
        const res = await apiFetch(`/api/autopilot/runs/${runId}`);
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
        const p = body.progress;
        if (p) setScanNote(`${p.processed ?? 0} of ${p.total ?? '?'} sources read. ${p.log?.[p.log.length - 1]?.message ?? ''}`);
        if (body.status === 'running') return poll(runId);
        setScanning(false); setScanNote('');
        if (body.status === 'failed') setError(body.error ?? 'The scan failed.'); else { opps.reload(); sources.reload(); }
      } catch (e) { setScanning(false); setScanNote(''); setError(e instanceof Error ? e.message : 'Lost contact with the server.'); }
    }, 1500);
  };

  const scan = async () => {
    setScanning(true); setError(''); setScanNote('Starting…');
    try { poll((await send<{ run_id: string }>('/api/radar/scan/start', 'POST')).run_id); }
    catch (e) { setScanning(false); setScanNote(''); setError(e instanceof Error ? e.message : 'Scan failed'); }
  };

  const connectUpwork = async () => {
    setError('');
    const res = await apiFetch('/api/connectors/upwork/authorize');
    const body = await res.json().catch(() => ({}));
    if (res.ok) window.open(body.authorize_url, '_blank', 'noopener');
    else setError(apiErrorMessage(res.status, body));
  };

  const openRow = (o: Opp) => { setOpen(o); setFit(null); setDraft(null); setPanelError(''); };
  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setPanelError('');
    try { await fn(); } catch (e) { setPanelError(e instanceof Error ? e.message : 'Failed'); } finally { setBusy(''); }
  };

  const slice = rows.slice(page * PAGE, (page + 1) * PAGE);
  const money = (o: Opp) => (o.budget_max ? `${o.currency ?? 'USD'} ${Math.round(o.budget_max).toLocaleString()}${o.type === 'hiring_signal' ? ' salary' : ''}` : '–');

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-400 space-y-1 flex-1 min-w-48">Search<SuggestInput kinds={['skill', 'business']} placeholder="react, tender, fintech…" value={q} onChange={(v) => { setQ(v); setPage(0); }} /></label>
          <label className="text-xs text-slate-400 space-y-1">Source
            <select className={field} value={source} onChange={(e) => { setSource(e.target.value); setPage(0); }}><option value="">All</option>{sourceNames.map((s) => <option key={s}>{s}</option>)}</select></label>
          <label className="text-xs text-slate-400 space-y-1">Minimum fit
            <select className={field} value={minFit} onChange={(e) => { setMinFit(Number(e.target.value)); setPage(0); }}>{[0, 30, 50, 70].map((n) => <option key={n} value={n}>{n ? `${n}%+` : 'Any'}</option>)}</select></label>
          <label className="text-xs text-slate-400 space-y-1">Budget from<input className={`${field} w-24`} inputMode="numeric" placeholder="any" value={minBudget} onChange={(e) => { setMinBudget(e.target.value.replace(/[^0-9]/g, '')); setPage(0); }} /></label>
          <label className="text-xs text-slate-400 space-y-1">to<input className={`${field} w-24`} inputMode="numeric" placeholder="any" value={maxBudget} onChange={(e) => { setMaxBudget(e.target.value.replace(/[^0-9]/g, '')); setPage(0); }} /></label>
          <label className="flex items-center gap-2 text-xs text-slate-300 pb-2"><input type="checkbox" checked={remoteOnly} onChange={(e) => { setRemoteOnly(e.target.checked); setPage(0); }} />Remote only</label>
          <Button variant="primary" onClick={scan} disabled={scanning}><RefreshCw className={`h-4 w-4 ${scanning ? 'animate-spin' : ''}`} />{scanning ? 'Scanning…' : 'Scan sources'}</Button>
        </div>
        {scanning && <p role="status" aria-live="polite" className="mt-3 text-xs text-slate-400">{scanNote} Sources are read in parallel; the slowest one (usually the tender feeds) sets the time, about a minute.</p>}
        {(minBudget || maxBudget) && <p className="text-[11px] text-slate-500 mt-2">Budget filters show only posts that state a budget.</p>}
        {sources.data && (
          <div className="flex flex-wrap items-center gap-1.5 mt-3">
            {sources.data.some((x) => x.source === 'upwork' && x.status === 'not_connected') && <Button small onClick={connectUpwork}>Connect Upwork</Button>}
            {sources.data.map((s) => (
              <Badge key={s.source} tone={s.status === 'not_configured' ? 'neutral' : s.last_run?.status === 'ok' ? 'good' : s.last_run ? 'warn' : 'neutral'} title={s.detail ?? s.last_run?.detail ?? ''}>
                {s.source}{s.last_run ? ` · ${s.last_run.stored} kept` : s.status === 'not_configured' ? ' · needs key' : ' · not scanned'}
              </Badge>))}
          </div>
        )}
      </Card>
      <ErrorBanner message={error || opps.error} />

      <Card>
        {opps.loading && !opps.data ? <Skeletons rows={5} /> : rows.length === 0 ? (
          <EmptyState title="Nothing here yet" hint="Press Scan sources to read the free job, project and tender feeds. Add your services and a case study in Settings so fit can be scored." />
        ) : (
          <>
            <div className="text-xs text-slate-400 mb-3 tabular">{rows.length} results</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-slate-500 border-b border-slate-800"><th className="py-2 pr-3 w-24">Fit</th><th className="py-2 pr-3">Opportunity</th><th className="py-2 pr-3 hidden md:table-cell">Source</th><th className="py-2 pr-3 hidden md:table-cell">Budget</th></tr></thead>
                <tbody>
                  {slice.map((o) => (
                    <tr key={o.id} className="border-b border-slate-800/70 hover:bg-slate-900/60 cursor-pointer" onClick={() => openRow(o)}>
                      <td className="py-2.5 pr-3">{o.fit_score == null ? <span className="text-xs text-slate-500">not scored</span> : <><div className="font-mono tabular text-white">{Math.round(o.fit_score * 100)}%</div><ScoreBar value={o.fit_score * 100} /></>}</td>
                      <td className="py-2.5 pr-3"><button className="text-left text-slate-100 hover:text-white font-medium line-clamp-1">{o.title}</button>
                        <div className="text-xs text-slate-500 flex gap-2 items-center"><Badge>{TYPE_LABEL[o.type] ?? o.type}</Badge>{o.company_name && <span>{o.company_name}</span>}</div></td>
                      <td className="py-2.5 pr-3 hidden md:table-cell text-xs text-slate-400">{o.source}</td>
                      <td className="py-2.5 pr-3 hidden md:table-cell text-xs text-slate-300 tabular">{money(o)}</td>
                    </tr>))}
                </tbody>
              </table>
            </div>
            <Pager page={page} pageSize={PAGE} total={rows.length} onPage={setPage} />
          </>
        )}
      </Card>

      <Drawer open={open !== null} title={open?.title ?? ''} onClose={() => setOpen(null)} wide>
        {open && (
          <div className="space-y-5 text-sm">
            <div className="flex flex-wrap gap-2"><Badge tone="accent">{open.source}</Badge><Badge>{TYPE_LABEL[open.type] ?? open.type}</Badge>{open.fit_score != null && <Badge tone="good">Fit {Math.round(open.fit_score * 100)}%</Badge>}{open.risk_flags.map((f) => <Badge key={f} tone="warn">{f.replace(/_/g, ' ')}</Badge>)}</div>
            {open.url && <a className="inline-flex gap-1.5 text-xs text-indigo-300 hover:text-indigo-200" href={normalizeUrl(open.url)} target="_blank" rel="noreferrer noopener"><ExternalLink className="h-3.5 w-3.5" />Open the original post</a>}
            {open.fit_reasons.length > 0 && <ul className="text-xs text-slate-300 list-disc pl-4 space-y-0.5">{open.fit_reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
            <p className="text-xs text-slate-300 whitespace-pre-wrap max-h-60 overflow-auto bg-slate-900 border border-slate-800 rounded-lg p-3 leading-relaxed">{open.description || 'No description.'}</p>
            <ErrorBanner message={panelError} />
            <div className="flex flex-wrap gap-2">
              <Button disabled={busy !== ''} onClick={() => run('fit', async () => setFit(await send<Fit>(`/api/opportunities/${open.id}/analyze`)))}>{busy === 'fit' ? 'Analyzing…' : 'Should we chase this?'}</Button>
              <Button variant="primary" disabled={busy !== ''} onClick={() => run('draft', async () => setDraft(await send<Draft>('/api/proposals/draft', 'POST', { opportunity_id: open.id, client_name: open.company_name })))}><Sparkles className="h-4 w-4" />{busy === 'draft' ? 'Drafting…' : 'Draft proposal'}</Button>
            </div>
            {fit && (
              <div className="rounded-xl border border-slate-800 p-4 space-y-2 text-xs animate-fade-up">
                <div className="flex items-center gap-2"><Badge tone={fit.verdict === 'pursue' ? 'good' : fit.verdict === 'skip' ? 'bad' : 'warn'}>{fit.verdict}</Badge><span className="text-slate-300">{fit.summary}</span></div>
                {fit.reasons.map((r) => <div key={r.point} className="text-slate-300"><span className="text-emerald-400">+</span> {r.point} <span className="text-slate-500">&ldquo;{r.quote}&rdquo;</span></div>)}
                {fit.risks.map((r) => <div key={r.point} className="text-slate-300"><span className="text-rose-400">!</span> {r.point} <span className="text-slate-500">&ldquo;{r.quote}&rdquo;</span></div>)}
                {fit.questions_to_ask.length > 0 && <div className="text-slate-400">Ask the client: {fit.questions_to_ask.join(' · ')}</div>}
                <div className="text-slate-500">Each point is backed by a quote from the post; {fit.unsupported_points_dropped} unsupported point(s) were removed.</div>
              </div>
            )}
            {draft && (
              <div className="space-y-3 animate-fade-up">
                {[draft.variant_a, draft.variant_b].map((v, i) => (
                  <div key={i} className="rounded-xl border border-slate-800 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs"><span className="font-semibold text-slate-200">Variant {i ? 'B' : 'A'}{v.focus ? `: ${v.focus}` : ''}</span>{v.verification?.ok ? <Badge tone="good">Claims verified</Badge> : <Badge tone="bad">Rejected by verifier</Badge>}</div>
                    <pre className="text-xs text-slate-200 whitespace-pre-wrap font-sans leading-relaxed">{v.body}</pre>
                    {!v.verification?.ok && <ul className="text-xs text-amber-300 list-disc pl-4">{(v.verification?.violations ?? []).map((x) => <li key={x}>{x}</li>)}</ul>}
                  </div>))}
                <p className="text-xs text-slate-400">{draft.status === 'pending_human_approval' ? 'Verified variants are waiting for you on Today. Nothing is submitted without your approval.' : 'No variant passed verification. Add a relevant case study in Settings, then try again.'}</p>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
};
