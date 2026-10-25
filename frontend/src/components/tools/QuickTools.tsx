import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Badge, Button, Card, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { openProtected } from '../../lib/api';
import { send } from '../../lib/hooks';

interface Issue { check_id: string; severity: string; finding: string; measured: string }
interface Compared {
  comparable: boolean; note: string | null; hook: string | null;
  target: { domain: string; overall_score: number | null; status: string }; competitor: { domain: string; overall_score: number | null; status: string };
  target_only_issues: Issue[]; competitor_only_issues: Issue[];
}

export const CompareSites: FC<{ initialA?: string }> = ({ initialA = '' }) => {
  const [a, setA] = useState(initialA); const [b, setB] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [out, setOut] = useState<Compared | null>(null);
  const run = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(''); setOut(null);
    try { setOut(await send<Compared>('/api/compare', 'POST', { target_domain: a, competitor_domain: b })); }
    catch (err) { setError(err instanceof Error ? err.message : 'Comparison failed'); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400 max-w-2xl">Runs the same real checks on both sites and lists only the measured differences. No revenue estimates.</p>
      <form onSubmit={run} className="grid gap-3 sm:grid-cols-3 items-end">
        <label className="text-xs text-slate-400 space-y-1">Prospect website<input className={field} required placeholder="prospect.com" value={a} onChange={(e) => setA(e.target.value)} /></label>
        <label className="text-xs text-slate-400 space-y-1">Competitor website<input className={field} required placeholder="competitor.com" value={b} onChange={(e) => setB(e.target.value)} /></label>
        <div className="flex gap-2"><Button type="button" variant="ghost" aria-label="Swap the two sites" onClick={() => { setA(b); setB(a); }}>Swap</Button><Button variant="primary" disabled={busy} className="flex-1">{busy ? 'Checking both sites…' : 'Compare'}</Button></div>
      </form>
      <ErrorBanner message={error} />
      {out && (!out.comparable ? <p className="text-sm text-amber-300">{out.note}</p> : (
        <div className="space-y-3 animate-fade-up">
          <div className="flex gap-2"><Badge tone="accent">{out.target.domain}: {out.target.overall_score}/100</Badge><Badge>{out.competitor.domain}: {out.competitor.overall_score}/100</Badge></div>
          {out.hook && <div className="flex flex-wrap items-start gap-2"><p className="text-sm text-slate-200 flex-1 min-w-48">{out.hook}</p><Button small onClick={() => navigator.clipboard?.writeText(out.hook ?? '').catch(() => undefined)}>Copy hook</Button></div>}
          <div className="grid gap-4 md:grid-cols-2">
            {[{ title: `Issues only ${out.target.domain} has`, list: out.target_only_issues }, { title: `Issues only ${out.competitor.domain} has`, list: out.competitor_only_issues }].map((col) => (
              <Card key={col.title}><h3 className="text-sm font-semibold text-white mb-2">{col.title}</h3>
                {col.list.length === 0 ? <p className="text-xs text-slate-400">None found.</p> : <ul className="space-y-2 text-xs text-slate-300">{col.list.slice(0, 8).map((i) => <li key={i.check_id}><Badge tone={i.severity === 'high' || i.severity === 'critical' ? 'bad' : 'warn'}>{i.severity}</Badge> {i.finding} <span className="text-slate-500">({i.measured})</span></li>)}</ul>}</Card>))}
          </div>
        </div>))}
    </div>
  );
};

export const ClientReportTool: FC<{ initialDomain?: string }> = ({ initialDomain = '' }) => {
  const [domain, setDomain] = useState(initialDomain); const [comp, setComp] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [note, setNote] = useState('');
  const run = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(''); setNote('');
    try {
      const r = await send<{ html_filename: string; pdf_filename: string | null; overall_score: number | null }>('/api/reports/client', 'POST', { domain, competitor_domain: comp || null, output_format: 'both' });
      setNote(`Report ready (health score ${r.overall_score ?? 'n/a'}). Opening it in a new tab.`);
      await openProtected(`/api/reports/view/${r.pdf_filename ?? r.html_filename}`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not make the report'); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400 max-w-2xl">A printable report for any website: health score, what was found with the measured value, the fix, the service that addresses it, and what was not checked. Add a competitor to include a comparison.</p>
      <form onSubmit={run} className="grid gap-3 sm:grid-cols-3 items-end">
        <label className="text-xs text-slate-400 space-y-1">Website<input className={field} required placeholder="prospect.com" value={domain} onChange={(e) => setDomain(e.target.value)} /></label>
        <label className="text-xs text-slate-400 space-y-1">Competitor (optional)<input className={field} placeholder="competitor.com" value={comp} onChange={(e) => setComp(e.target.value)} /></label>
        <Button variant="primary" disabled={busy}>{busy ? 'Building report…' : 'Create report'}</Button>
      </form>
      <ErrorBanner message={error} />
      {note && <div role="status" className="text-sm text-slate-200">{note}</div>}
    </div>
  );
};
