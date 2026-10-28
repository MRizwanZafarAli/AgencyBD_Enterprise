import { useState } from 'react';
import type { FC } from 'react';
import { Check, Copy, Download, FileText, GitCompare, Loader2, Presentation, RefreshCw, Stethoscope, UserPlus } from 'lucide-react';
import { Badge, Button, Card, Drawer, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { openProtected } from '../../lib/api';
import { send } from '../../lib/hooks';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { BlockedNotice, Diagnosis, PitchAndPresence, Surgery, Vitals } from './ClinicChart';
import { parseTarget } from './types';
import type { Audit, Brief, Chart, History, Presence, Rec, Resolve, Target } from './types';

const STEPS = ['Triage: who is the patient', 'Examination: read the public site', 'Chart: findings, plan, history'];

async function get<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
  return body as T;
}

export const SiteClinic: FC<{ initial?: string; autoRun?: boolean; onOpenClient: (leadId: number) => void; onHandoff: (tool: 'compare' | 'report' | 'email', domain: string) => void }> = ({ initial = '', autoRun = false, onOpenClient, onHandoff }) => {
  const [text, setText] = useState(initial);
  const [step, setStep] = useState(-1);
  const [error, setError] = useState('');
  const [chart, setChart] = useState<Chart | null>(null);
  const [options, setOptions] = useState<Resolve | null>(null);
  const [teardown, setTeardown] = useState<{ markdown: string; filename: string } | null>(null);
  const [note, setNote] = useState('');
  const [copied, setCopied] = useState(false);
  const busy = step >= 0 && step < STEPS.length;

  const examine = async (target: Target, hintDomain?: string) => {
    setError(''); setNote(''); setOptions(null); setChart(null); setStep(0);
    try {
      const name = target.kind === 'site' ? target.domain : target.name;
      const hint = hintDomain ?? (target.kind === 'site' ? target.domain : null);
      const resolve = await send<Resolve>('/api/companies/resolve', 'POST', { company_name: name, hint_domain: hint });
      if (resolve.status !== 'resolved' || !resolve.domain) { setOptions(resolve); setStep(-1); return; }
      setStep(1);
      const audit = await send<Audit>('/api/audits/run', 'POST', { domain: resolve.domain, company_id: resolve.company_id });
      setStep(2);
      const [brief, advice, history, presence] = await Promise.all([
        get<Brief>(`/api/companies/${resolve.company_id}/brief`).catch(() => null),
        get<{ recommendations: Rec[] }>(`/api/companies/${resolve.company_id}/advice`).then((a) => a.recommendations).catch(() => [] as Rec[]),
        get<History>(`/api/companies/${resolve.company_id}/audit_history`).catch(() => null),
        target.kind === 'business' ? send<Presence>('/api/companies/presence', 'POST', { business_name: target.name, city: target.city, domain: resolve.domain }).catch(() => null) : Promise.resolve(null),
      ]);
      setChart({ resolve, audit, brief, advice, history, presence, target });
      setStep(STEPS.length);
    } catch (e) { setError((e as Error).message); setStep(-1); }
  };

  const [started, setStarted] = useState(false);
  const submit = () => {
    const t = parseTarget(text);
    if (!t) { setError('Paste a website (acme.com) or type a business and its place (Acme Plumbing, Austin).'); return; }
    examine(t);
  };

  if (autoRun && !started) { setStarted(true); setTimeout(submit, 0); }

  const act = async (fn: () => Promise<void>) => { setNote(''); setError(''); try { await fn(); } catch (e) { setError((e as Error).message); } };
  const domain = chart?.resolve.domain ?? '';
  const saveClient = () => act(async () => { const lead = await send<{ id: number }>('/api/pipeline/deals/create', 'POST', { company_name: chart!.resolve.name, domain }); onOpenClient(lead.id); });
  const report = () => act(async () => { const r = await send<{ html_filename: string; pdf_filename: string | null }>('/api/reports/client', 'POST', { domain, output_format: 'both' }); await openProtected(`/api/reports/view/${r.pdf_filename ?? r.html_filename}`); });
  const openDeck = () => act(async () => { const r = await send<{ html_filename: string; pdf_filename: string | null; view_url: string }>('/api/reports/deck', 'POST', { domain, output_format: 'both' }); await openProtected(r.view_url); });
  const openTeardown = () => act(async () => setTeardown(await get<{ markdown: string; filename: string }>(`/api/companies/${chart!.resolve.company_id}/teardown`)));
  const copy = async () => { if (!teardown) return; try { await navigator.clipboard.writeText(teardown.markdown); setCopied(true); window.setTimeout(() => setCopied(false), 1600); } catch { setNote('Copy was blocked by the browser; use Download.'); } };
  const download = () => { if (!teardown) return; const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([teardown.markdown], { type: 'text/markdown' })); a.download = teardown.filename; a.click(); URL.revokeObjectURL(a.href); };

  return (
    <div className="space-y-5">
      <Card>
        <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="flex flex-wrap gap-2">
          <div className="relative flex-1 min-w-64">
            <Stethoscope className="h-4 w-4 text-indigo-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
            <input className={`${field} pl-9`} aria-label="Site or business to examine" autoComplete="off" spellCheck={false} value={text} onChange={(e) => setText(e.target.value)}
              placeholder="Paste a website, or a business and place: acme.com  ·  Acme Plumbing, Austin" />
          </div>
          <Button type="submit" variant="primary" disabled={busy || !text.trim()}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Stethoscope className="h-4 w-4" />}{busy ? 'Examining…' : 'Examine'}</Button>
        </form>
        <p className="text-[11px] text-slate-500 mt-2">Reads only what the public can see: headers, TLS, SEO, accessibility, email DNS and visible software versions. Nothing is attacked, filled in or logged into.</p>
        {step >= 0 && (
          <ol className="mt-3 grid gap-2 sm:grid-cols-3" aria-label="Progress" aria-live="polite">{STEPS.map((s, i) => (
            <li key={s} className={`flex items-center gap-2 text-xs rounded-lg border px-3 py-2 ${i < step ? 'border-emerald-500/40 text-emerald-300' : i === step ? 'border-indigo-500/50 text-white' : 'border-slate-800 text-slate-500'}`}>
              {i < step ? <Check className="h-3.5 w-3.5" /> : i === step ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <span className="h-3.5 w-3.5" />}{s}</li>))}</ol>)}
      </Card>
      <ErrorBanner message={error} />
      {note && <p role="status" className="text-xs text-slate-300">{note}</p>}

      {options && (
        <Card>
          <h2 className="text-sm font-semibold text-white">Could not pin down the site</h2>
          <p className="text-sm text-slate-300 mt-1">{options.note ?? 'No verified website for that name.'} Nothing was guessed.</p>
          {options.candidates && options.candidates.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">{options.candidates.map((c) => <Button key={c.domain} small onClick={() => examine({ kind: 'site', domain: c.domain }, c.domain)}>{c.domain} <span className="text-slate-500">{Math.round(c.score * 100)}%</span></Button>)}</div>)}
        </Card>)}

      {chart && (
        <>
          <Card>
            <div className="flex flex-wrap items-center gap-2">
              <div className="min-w-0 mr-auto"><div className="text-sm font-semibold text-white truncate">{chart.resolve.name}</div>
                <a href={`https://${domain}`} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-300 hover:underline">{domain}</a>
                {chart.audit?.status && chart.audit.status !== 'completed' && <Badge tone="warn">{chart.audit.status}</Badge>}</div>
              <Button small onClick={() => examine(chart.target, domain)} disabled={busy}><RefreshCw className="h-3.5 w-3.5" />Re-examine</Button>
              <Button small onClick={openTeardown} disabled={chart.audit?.status !== 'completed'}><FileText className="h-3.5 w-3.5" />Teardown</Button>
              <Button small onClick={report} disabled={chart.audit?.status !== 'completed'}><Download className="h-3.5 w-3.5" />PDF report</Button>
              <Button small onClick={openDeck} disabled={chart.audit?.status !== 'completed'}><Presentation className="h-3.5 w-3.5 text-amber-400" />Executive deck</Button>
              <Button small onClick={() => onHandoff('compare', domain)}><GitCompare className="h-3.5 w-3.5" />Compare</Button>
              <Button small variant="primary" onClick={saveClient}><UserPlus className="h-3.5 w-3.5" />Save as client</Button>
            </div>
          </Card>
          {chart.audit && chart.audit.status === 'unreachable' && <Card><p className="text-sm text-amber-300">The site could not be reached from our servers. One failed check is not proof it is down, so nothing was scored.</p></Card>}
          <BlockedNotice chart={chart} />
          <Vitals chart={chart} />
          <div className="grid gap-5 xl:grid-cols-2"><Diagnosis chart={chart} /><Surgery chart={chart} /></div>
          <PitchAndPresence chart={chart} />
        </>)}

      <Drawer open={teardown !== null} title="Website teardown" onClose={() => setTeardown(null)} wide>
        <div className="flex flex-wrap gap-2 mb-3">
          <Button small onClick={copy}>{copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}{copied ? 'Copied' : 'Copy'}</Button>
          <Button small onClick={download}><Download className="h-3.5 w-3.5" />Download .md</Button>
          <Button small onClick={openDeck} variant="primary"><Presentation className="h-3.5 w-3.5" />Open presentation deck</Button>
        </div>
        <pre className="text-xs text-slate-200 whitespace-pre-wrap font-mono leading-relaxed">{teardown?.markdown}</pre>
      </Drawer>
    </div>
  );
};
