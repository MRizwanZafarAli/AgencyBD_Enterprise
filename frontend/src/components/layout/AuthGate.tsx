import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { ArrowRight, Cpu, KeyRound } from 'lucide-react';
import { setApiKey, verifyKey } from '../../lib/api';
import type { Me } from '../../lib/api';

const RIBBON = ['Lead Finder', 'Alert Desk', 'Site Clinic', 'Fixed-price offers', 'Chase today', 'Partner tracker', 'Weekly scorecard', 'Reply drafts', 'Pipeline'];

interface AuthGateProps {
  onAuthenticated: (me: Me) => void;
  notice?: string;
}

export const AuthGate: FC<AuthGateProps> = ({ onAuthenticated, notice }) => {
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const me = await verifyKey(key.trim());
      if (!me) {
        setError('That API key was rejected. Check it or ask an admin for a new one.');
        return;
      }
      setApiKey(key.trim());
      setKey('');
      onAuthenticated(me);
    } catch {
      setError('Could not reach the API. Is the backend running on :8001?');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen text-slate-100 grid lg:grid-cols-[1.15fr_1fr] gap-4 p-4">
      <aside className="hero-card hidden lg:flex flex-col justify-between p-10 !backdrop-blur-none" aria-hidden="true">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-2xl bg-indigo-600 flex items-center justify-center"><Cpu className="h-5 w-5" /></div>
          <span className="font-semibold tracking-tight text-lg">AgencyBD</span>
        </div>
        <div className="relative z-10">
          <span className="eyebrow mb-5">Built for small agencies</span>
          <h2 className="text-5xl font-semibold tracking-tight leading-[1.05] max-w-xl">Find clients. <span className="hero-accent">Answer fast.</span> Win more.</h2>
          <p className="hero-muted mt-5 max-w-md text-base">One calm place for every lead, message and follow-up. Everything is measured or typed by you, and nothing is ever made up.</p>
        </div>
        <div className="marquee relative z-10" aria-hidden="true">
          <div className="marquee-track text-sm font-medium hero-muted">
            {[...RIBBON, ...RIBBON].map((r, i) => <span key={i} className="inline-flex items-center gap-2 whitespace-nowrap"><span className="h-1.5 w-1.5 rounded-full bg-teal-400" />{r}</span>)}
          </div>
        </div>
      </aside>
      <div className="flex items-center justify-center">
        <form onSubmit={submit} className="bento-tile w-full max-w-md p-8 sm:p-10 space-y-5">
          <div className="flex items-center space-x-3 lg:hidden">
            <div className="h-10 w-10 rounded-2xl bg-indigo-600 flex items-center justify-center"><Cpu className="h-5 w-5" /></div>
            <div className="font-bold tracking-tight">AgencyBD</div>
          </div>
          <div>
            <h1 className="text-3xl font-semibold text-white tracking-tight">Welcome back</h1>
            <p className="text-sm text-slate-400 mt-1.5">Sign in with your API key</p>
          </div>
          {notice && <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-2xl p-3">{notice}</div>}
          <label className="block space-y-2">
            <span className="text-xs font-medium text-slate-400 flex items-center space-x-1"><KeyRound className="h-3 w-3" /><span>X-API-Key</span></span>
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="agy_live_…"
              className="w-full rounded-2xl bg-slate-900 border border-slate-800 px-4 py-3 font-mono text-sm focus:outline-none focus:border-indigo-500"
            />
          </label>
          {error && <div className="text-xs text-rose-300" role="alert">{error}</div>}
          <button
            type="submit"
            disabled={busy || key.trim().length < 12}
            className="w-full rounded-full bg-indigo-600 disabled:opacity-40 py-3 text-sm font-semibold inline-flex items-center justify-center gap-2"
          >
            {busy ? 'Verifying…' : <>Connect<ArrowRight className="h-4 w-4" /></>}
          </button>

          <p className="text-[11px] text-slate-500">
            Keys are issued with <code className="font-mono">python scripts/create_admin_key.py</code>. The key is kept for this browser tab only.
          </p>
        </form>
      </div>
    </div>
  );
};
