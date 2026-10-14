import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { ShieldCheck, Ban } from 'lucide-react';
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

  const input = 'rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500';
  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2"><ShieldCheck className="h-6 w-6 text-emerald-400" /><span>Compliance &amp; Suppression</span></h1>
        <p className="text-sm text-slate-400 mt-1">
          Every outbound email is checked against these rules automatically. Unsubscribe links are signed and work in one click. This page lets you inspect them.
          It is guidance, not legal advice: confirm your markets with counsel.
        </p>
      </div>

      <form onSubmit={checkCountry} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
        <h2 className="text-sm font-semibold text-white">Can I cold-email this country?</h2>
        <div className="flex gap-2">
          <input className={input} placeholder="Country code: US, GB, FR, DE, CA…" maxLength={3} value={country} onChange={(e) => setCountry(e.target.value)} required />
          <button className="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 text-sm font-semibold">Check</button>
        </div>
        {verdict && (
          <div className={`text-xs rounded-lg p-3 border ${verdict.allowed ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : 'border-rose-500/30 bg-rose-500/10 text-rose-200'}`}>
            <strong>{verdict.country_code}: {verdict.status.replace('_', ' ')}</strong>. {verdict.reason}
            {verdict.required_disclosures?.length > 0 && <div className="mt-1 text-slate-300">Must include: {verdict.required_disclosures.join(', ')}</div>}
          </div>
        )}
      </form>

      <form onSubmit={checkEmail} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
        <h2 className="text-sm font-semibold text-white">Suppression list</h2>
        <div className="flex gap-2 flex-wrap">
          <input className={`${input} flex-1 min-w-[220px]`} placeholder="email or domain" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <button className="rounded-lg bg-slate-700 hover:bg-slate-600 px-4 text-sm font-semibold">Is it suppressed?</button>
          <button type="button" onClick={addEmail} disabled={!email} className="flex items-center space-x-1 rounded-lg bg-rose-700 hover:bg-rose-600 disabled:opacity-40 px-4 text-sm font-semibold"><Ban className="h-4 w-4" /><span>Never email</span></button>
        </div>
        {suppressed !== null && <div className="text-xs text-slate-200">{suppressed ? 'Suppressed: this address or domain will not be emailed.' : 'Not suppressed.'}</div>}
        {notice && <div role="status" className="text-xs text-emerald-300">{notice}</div>}
        <p className="text-[11px] text-slate-500">Suppressing a domain blocks every address at that domain. Entries are stored as keyed hashes, not readable addresses. Suppression is shared across workspaces so an opt-out is honoured everywhere.</p>
      </form>
    </div>
  );
};
