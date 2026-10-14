import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Globe, Copy } from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

interface RowProps { label: string; type: string; host: string; value: string | null; note?: string; copied: string; onCopy: (text: string, key: string) => void }

const Row: FC<RowProps> = ({ label, type, host, value, note, copied, onCopy }) => (
  <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs space-y-1">
    <div className="flex justify-between"><span className="font-semibold text-white">{label}</span><span className="font-mono text-slate-400">{type} · {host}</span></div>
    {value ? (
      <div className="flex justify-between gap-2 font-mono text-slate-200 break-all"><span>{value}</span>
        <button onClick={() => onCopy(value, label)} aria-label={`Copy ${label}`} className="text-slate-400 hover:text-white shrink-0"><Copy className="h-3.5 w-3.5" /></button></div>
    ) : <div className="text-amber-300">The value comes from your mail provider.</div>}
    {copied === label && <div className="text-emerald-400">Copied</div>}
    {note && <div className="text-slate-400">{note}</div>}
  </div>
);

export const DnsStudio: FC = () => {
  const [domain, setDomain] = useState('');
  const [esp, setEsp] = useState('google_workspace');
  const [policy, setPolicy] = useState('none');
  const [records, setRecords] = useState<any>(null);
  const [audit, setAudit] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState('');

  const post = async (path: string, body: unknown) => {
    const res = await apiFetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
    return data;
  };
  const run = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      setRecords(await post('/api/outbound/dns/records', { domain, esp_provider: esp, dmarc_policy: policy }));
      setAudit(await post('/api/outbound/dns/audit', { domain }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed.');
    } finally {
      setBusy(false);
    }
  };
  const copy = async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied(''), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };
  const state = (v: boolean | null) => (v === null ? <span className="text-slate-400">could not check</span> : v ? <span className="text-emerald-400">found</span> : <span className="text-amber-300">missing</span>);

  const input = 'rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500';
  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2"><Globe className="h-6 w-6 text-cyan-400" /><span>Sending domain setup</span></h1>
        <p className="text-sm text-slate-400 mt-1">The DNS records a sending domain needs, and a live check of what is published today. Use a secondary domain for outreach, never your main one.</p>
      </div>
      <form onSubmit={run} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 flex flex-wrap gap-2">
        <input className={`${input} flex-1 min-w-[220px]`} placeholder="send.youragency.com" value={domain} onChange={(e) => setDomain(e.target.value)} required />
        <select className={input} value={esp} onChange={(e) => setEsp(e.target.value)}>
          <option value="google_workspace">Google Workspace</option><option value="microsoft_365">Microsoft 365</option>
        </select>
        <select className={input} value={policy} onChange={(e) => setPolicy(e.target.value)} title="Start with none and tighten after reading reports">
          <option value="none">DMARC: monitor (p=none)</option><option value="quarantine">DMARC: quarantine</option><option value="reject">DMARC: reject</option>
        </select>
        <button disabled={busy} className="rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-4 text-sm font-semibold">{busy ? 'Checking…' : 'Generate & check'}</button>
      </form>

      {audit && (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 text-xs space-y-1">
          <div className="font-semibold text-white mb-1">Live DNS right now ({audit.checked_at})</div>
          <div>Mail routing (MX): {state(audit.mx_active)}</div>
          <div>SPF: {state(audit.spf_active)}</div>
          <div>DKIM: {state(audit.dkim_active)}{audit.dkim_selector ? ` (selector ${audit.dkim_selector})` : ''}</div>
          <div>DMARC: {state(audit.dmarc_active)}{audit.dmarc_policy ? ` (p=${audit.dmarc_policy})` : ''}</div>
          <div className={audit.ready_for_outreach ? 'text-emerald-300 pt-1' : 'text-amber-300 pt-1'}>
            {audit.ready_for_outreach ? 'All four are in place.' : 'Not ready: publish the missing records below, wait for DNS to propagate, then check again.'}
          </div>
        </div>
      )}

      {records && (
        <div className="space-y-2">
          <Row label="SPF" type={records.spf.type} host={records.domain} value={records.spf.value} copied={copied} onCopy={copy} />
          <Row label="DKIM" type={records.dkim.type} host={records.dkim.host} value={records.dkim.value} note={records.dkim.how_to_get_value} copied={copied} onCopy={copy} />
          <Row label="DMARC" type={records.dmarc.type} host={records.dmarc.host} value={records.dmarc.value} copied={copied} onCopy={copy} />
          {records.mx.map((m: any, i: number) => <Row key={i} label={`MX ${m.priority}`} type="MX" host="@" value={m.value} copied={copied} onCopy={copy} />)}
          <ul className="text-[11px] text-slate-400 list-disc list-inside space-y-0.5 pt-2">{records.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul>
        </div>
      )}
    </div>
  );
};
