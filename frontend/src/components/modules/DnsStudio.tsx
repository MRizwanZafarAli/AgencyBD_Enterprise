import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Globe, Copy } from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

interface RowProps { label: string; type: string; host: string; value: string | null; note?: string; copied: string; onCopy: (text: string, key: string) => void }

const Row: FC<RowProps> = ({ label, type, host, value, note, copied, onCopy }) => (
  <div className="rounded-xl border border-slate-750 bg-slate-900/80 p-4 text-xs space-y-1.5 shadow-sm">
    <div className="flex justify-between items-center"><span className="font-semibold text-white text-sm">{label}</span><span className="font-mono text-slate-400 bg-slate-800/60 px-2 py-0.5 rounded text-[11px]">{type} · {host}</span></div>
    {value ? (
      <div className="flex justify-between items-center gap-2 font-mono text-slate-200 break-all bg-slate-950/70 p-2.5 rounded-lg border border-slate-800/80">
        <span className="select-all">{value}</span>
        <button onClick={() => onCopy(value, label)} aria-label={`Copy ${label}`} className="text-slate-400 hover:text-white shrink-0 p-1 hover:bg-slate-800 rounded transition"><Copy className="h-4 w-4" /></button>
      </div>
    ) : <div className="text-amber-300 font-medium">The value comes from your mail provider.</div>}
    {copied === label && <div className="text-emerald-400 font-medium flex items-center space-x-1">✓ Copied to clipboard</div>}
    {note && <div className="text-slate-400 text-[11px] leading-relaxed">{note}</div>}
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
  const state = (v: boolean | null) => (v === null ? <span className="text-slate-400 font-mono">could not check</span> : v ? <span className="text-emerald-400 font-mono font-bold">✅ FOUND</span> : <span className="text-amber-300 font-mono font-bold">⚠️ MISSING</span>);

  const input = 'rounded-xl bg-slate-900 border border-slate-750 px-3.5 py-2.5 text-sm focus:outline-none focus:border-cyan-500 transition-all';
  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
          <Globe className="h-6 w-6 text-cyan-400" />
          <span>Sending Domain DNS Studio</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            SPF · DKIM · DMARC · MX
          </span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">Live DNS verification and instant record generator for isolated cold outbound domains.</p>
      </div>
      <form onSubmit={run} className="glass-panel rounded-2xl p-6 flex flex-wrap gap-3 items-center">
        <input className={`${input} flex-1 min-w-[240px]`} placeholder="send.youragency.com" value={domain} onChange={(e) => setDomain(e.target.value)} required />
        <select className={input} value={esp} onChange={(e) => setEsp(e.target.value)}>
          <option value="google_workspace">Google Workspace</option>
          <option value="microsoft_365">Microsoft 365</option>
        </select>
        <select className={input} value={policy} onChange={(e) => setPolicy(e.target.value)} title="Start with none and tighten after reading reports">
          <option value="none">DMARC: monitor (p=none)</option>
          <option value="quarantine">DMARC: quarantine</option>
          <option value="reject">DMARC: reject</option>
        </select>
        <button disabled={busy} className="rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-cyan-600/20 transition-all">
          {busy ? 'Checking Live DNS…' : 'Generate & Audit'}
        </button>
      </form>

      {audit && (
        <div className="glass-panel rounded-2xl p-6 text-xs space-y-3">
          <div className="font-semibold text-white text-sm mb-1 flex items-center justify-between">
            <span>Live DNS Status ({audit.checked_at})</span>
            <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono ${audit.ready_for_outreach ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'}`}>
              {audit.ready_for_outreach ? '100% PRODUCTION READY' : 'RECORDS PENDING PROPAGATION'}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <span className="text-slate-400 block mb-1">Mail Routing (MX)</span>
              {state(audit.mx_active)}
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <span className="text-slate-400 block mb-1">SPF Record</span>
              {state(audit.spf_active)}
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <span className="text-slate-400 block mb-1">DKIM Signature</span>
              <div>{state(audit.dkim_active)}{audit.dkim_selector ? ` (${audit.dkim_selector})` : ''}</div>
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <span className="text-slate-400 block mb-1">DMARC Policy</span>
              <div>{state(audit.dmarc_active)}{audit.dmarc_policy ? ` (p=${audit.dmarc_policy})` : ''}</div>
            </div>
          </div>
          <div className={audit.ready_for_outreach ? 'text-emerald-300 pt-1 text-xs' : 'text-amber-300 pt-1 text-xs'}>
            {audit.ready_for_outreach ? 'All 4 critical authentication records are verified active.' : 'Publish the missing records below into your DNS host (Cloudflare, Namecheap, Route53), wait a few minutes, then check again.'}
          </div>
        </div>
      )}

      {records && (
        <div className="space-y-3">
          <Row label="SPF" type={records.spf.type} host={records.domain} value={records.spf.value} copied={copied} onCopy={copy} />
          <Row label="DKIM" type={records.dkim.type} host={records.dkim.host} value={records.dkim.value} note={records.dkim.how_to_get_value} copied={copied} onCopy={copy} />
          <Row label="DMARC" type={records.dmarc.type} host={records.dmarc.host} value={records.dmarc.value} copied={copied} onCopy={copy} />
          {records.mx.map((m: any, i: number) => <Row key={i} label={`MX ${m.priority}`} type="MX" host="@" value={m.value} copied={copied} onCopy={copy} />)}
          <ul className="text-[11px] text-slate-400 list-disc list-inside space-y-1 pt-2">{records.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul>
        </div>
      )}
    </div>
  );
};
