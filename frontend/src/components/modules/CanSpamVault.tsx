import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { ShieldCheck, Ban, Globe } from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

export const CanSpamVault: FC = () => {
  const [country, setCountry] = useState('');
  const [verdict, setVerdict] = useState<any>(null);
  const [email, setEmail] = useState('');
  const [suppressed, setSuppressed] = useState<boolean | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const call = async (path: string, init?: RequestInit) => {
    const res = await apiFetch(path, init);
    const data = await res.json();
    if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
    return data;
  };
  const guard = async (fn: () => Promise<void>) => {
    setError('');
    setNotice('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed.');
    }
  };

  const checkCountry = (e: FormEvent) => {
    e.preventDefault();
    guard(async () => setVerdict(await call(`/api/compliance/country/${encodeURIComponent(country.trim())}`)));
  };
  const checkEmail = (e: FormEvent) => {
    e.preventDefault();
    guard(async () => setSuppressed((await call(`/api/compliance/suppression/check?email=${encodeURIComponent(email.trim())}`)).is_suppressed));
  };
  const addEmail = () =>
    guard(async () => {
      await call('/api/compliance/suppression/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ entity: email.trim(), entity_type: email.includes('@') ? 'email' : 'domain', reason: 'manual' }) });
      setSuppressed(true);
      setNotice(`${email.trim()} will never be emailed again.`);
    });

  const input = 'rounded-xl bg-slate-900 border border-slate-750 px-3.5 py-2.5 text-sm focus:outline-none focus:border-indigo-500 transition-all';
  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
          <ShieldCheck className="h-6 w-6 text-emerald-400" />
          <span>Compliance &amp; Suppression Vault</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            CAN-SPAM &amp; GDPR SAFEGUARD
          </span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Every outbound email is checked against these rules automatically. Unsubscribe links are cryptographic and work in one click.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form onSubmit={checkCountry} className="glass-panel rounded-2xl p-6 space-y-4">
          <div className="flex items-center space-x-2">
            <Globe className="h-5 w-5 text-indigo-400" />
            <h2 className="text-sm font-semibold text-white">Can I cold-email this country?</h2>
          </div>
          <div className="flex gap-2">
            <input className={`${input} flex-1`} placeholder="Country code: US, GB, FR, DE, CA…" maxLength={3} value={country} onChange={(e) => setCountry(e.target.value)} required />
            <button className="rounded-xl bg-indigo-600 hover:bg-indigo-500 px-4 py-2.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 transition-all">Check Jurisdiction</button>
          </div>
          {verdict && (
            <div className={`text-xs rounded-xl p-3.5 border transition-all ${verdict.allowed ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : 'border-rose-500/30 bg-rose-500/10 text-rose-200'}`}>
              <strong>{verdict.country_code}: {verdict.status.replace('_', ' ')}</strong>. {verdict.reason}
              {verdict.required_disclosures?.length > 0 && <div className="mt-1 text-slate-300">Must include: {verdict.required_disclosures.join(', ')}</div>}
            </div>
          )}
        </form>

        <form onSubmit={checkEmail} className="glass-panel rounded-2xl p-6 space-y-4">
          <div className="flex items-center space-x-2">
            <Ban className="h-5 w-5 text-rose-400" />
            <h2 className="text-sm font-semibold text-white">Universal Suppression List</h2>
          </div>
          <div className="flex gap-2 flex-wrap">
            <input className={`${input} flex-1 min-w-[200px]`} placeholder="email or corporate domain" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <button className="rounded-xl bg-slate-800 hover:bg-slate-750 px-3.5 py-2.5 text-xs font-semibold text-slate-200 transition-all border border-slate-700">Check</button>
            <button type="button" onClick={addEmail} disabled={!email} className="flex items-center space-x-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-40 px-3.5 py-2.5 text-xs font-semibold text-white shadow-md shadow-rose-600/20 transition-all">
              <Ban className="h-3.5 w-3.5" />
              <span>Suppress</span>
            </button>
          </div>
          {suppressed !== null && <div className="text-xs text-slate-200 p-2.5 rounded-lg bg-slate-900 border border-slate-800">{suppressed ? '⛔ Suppressed: this address or domain will never be emailed.' : '✅ Not suppressed: address is active and eligible.'}</div>}
          {notice && <div role="status" className="text-xs text-emerald-300 p-2 rounded-lg bg-emerald-950/40 border border-emerald-500/30">{notice}</div>}
          <p className="text-[11px] text-slate-400 leading-relaxed">Suppressing a domain blocks every address at that domain. Entries are stored as cryptographic hashes to protect data privacy. Shared across all workspaces.</p>
        </form>
      </div>
    </div>
  );
};
