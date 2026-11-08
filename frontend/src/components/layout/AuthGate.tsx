import { useEffect, useState } from 'react';
import type { FC, FormEvent } from 'react';
import { ArrowRight, Cpu, Eye, EyeOff, LockKeyhole } from 'lucide-react';
import { loadTiers, login } from '../../lib/api';
import type { Me, Tier } from '../../lib/api';

const RIBBON = ['Lead Finder', 'Alert Desk', 'Site Clinic', 'Fixed-price offers', 'Chase today', 'Partner tracker', 'Weekly scorecard', 'Reply drafts', 'Pipeline'];

interface AuthGateProps {
  onAuthenticated: (me: Me) => void;
  notice?: string;
}

const FALLBACK: Tier[] = [
  { role: 'super_admin', label: 'Super admin', available: true }, { role: 'growth_lead', label: 'Growth lead', available: true },
  { role: 'sdr_rep', label: 'Sales rep', available: true }, { role: 'auditor', label: 'Auditor', available: true },
];

export const AuthGate: FC<AuthGateProps> = ({ onAuthenticated, notice }) => {
  const [tiers, setTiers] = useState<Tier[]>(FALLBACK);
  const [anySet, setAnySet] = useState(true);
  const [role, setRole] = useState('growth_lead');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    loadTiers().then((t) => { if (!t) return; setTiers(t.tiers); setAnySet(t.any_set); const first = t.tiers.find((x) => x.available); if (first) setRole((r) => (t.tiers.find((x) => x.role === r && x.available) ? r : first.role)); });
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const me = await login(role, password);
      setPassword('');
      onAuthenticated(me);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.');
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
            <p className="text-sm text-slate-400 mt-1.5">Choose your tier and type its password</p>
          </div>
          {notice && <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-2xl p-3">{notice}</div>}
          {!anySet && <div role="alert" className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-2xl p-3">No passwords are set yet. On the server, run <code className="font-mono">python scripts/set_passwords.py</code>, then reload this page.</div>}
          <label className="block space-y-2">
            <span className="text-xs font-medium text-slate-400">Tier</span>
            <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Tier" className="w-full rounded-2xl bg-slate-900 border border-slate-800 px-4 py-3 text-sm focus:outline-none focus:border-indigo-500">
              {tiers.map((t) => <option key={t.role} value={t.role}>{t.label}</option>)}
            </select>
          </label>
          <label className="block space-y-2">
            <span className="text-xs font-medium text-slate-400 flex items-center space-x-1"><LockKeyhole className="h-3 w-3" /><span>Password</span></span>
            <div className="relative">
              <input
                type={show ? 'text' : 'password'}
                autoComplete="current-password"
                spellCheck={false}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Your tier's password"
                className="w-full rounded-2xl bg-slate-900 border border-slate-800 pl-4 pr-12 py-3 text-sm focus:outline-none focus:border-indigo-500"
              />
              <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-full text-slate-400 hover:text-white">
                {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </label>
          {error && <div className="text-xs text-rose-300" role="alert">{error}</div>}
          <button
            type="submit"
            disabled={busy || !anySet || password.length < 1}
            className="w-full rounded-full bg-indigo-600 disabled:opacity-40 py-3 text-sm font-semibold inline-flex items-center justify-center gap-2"
          >
            {busy ? 'Checking…' : <>Sign in<ArrowRight className="h-4 w-4" /></>}
          </button>

          <p className="text-[11px] text-slate-500">
            Each tier has its own secret password, set on the server with <code className="font-mono">python scripts/set_passwords.py</code>. Five wrong tries lock you out for 15 minutes. Your session lasts 12 hours and ends with this browser tab.
          </p>
        </form>
      </div>
    </div>
  );
};
