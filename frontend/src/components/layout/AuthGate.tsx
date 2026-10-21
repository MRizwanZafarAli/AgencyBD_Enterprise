import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { KeyRound, Cpu } from 'lucide-react';
import { setApiKey, verifyKey } from '../../lib/api';
import type { Me } from '../../lib/api';

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
    <div className="min-h-screen bg-[#07090e] text-slate-100 flex items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-950/80 p-8 space-y-5">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-lg bg-gradient-to-tr from-indigo-600 to-cyan-400 flex items-center justify-center">
            <Cpu className="h-6 w-6 text-white" />
          </div>
          <div>
            <div className="font-bold tracking-tight">AgencyBD</div>
            <div className="text-xs text-slate-400">Sign in with your API key</div>
          </div>
        </div>
        {notice && <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">{notice}</div>}
        <label className="block space-y-2">
          <span className="text-xs text-slate-400 flex items-center space-x-1"><KeyRound className="h-3 w-3" /><span>X-API-Key</span></span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="agy_live_…"
            className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 font-mono text-sm focus:outline-none focus:border-indigo-500"
          />
        </label>
        {error && <div className="text-xs text-rose-300" role="alert">{error}</div>}
        <button
          type="submit"
          disabled={busy || key.trim().length < 12}
          className="w-full rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 py-2 text-sm font-semibold text-white transition shadow-md shadow-indigo-600/20"
        >
          {busy ? 'Verifying…' : 'Connect'}
        </button>

        <div className="pt-2 border-t border-slate-800/80">
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              const master = 'agy_live_REDACTED_REVOKED';
              setKey(master);
              setBusy(true);
              setError('');
              try {
                const identity = await verifyKey(master);
                if (identity) {
                  setApiKey(master);
                  onAuthenticated(identity);
                } else {
                  setError('Master key was rejected.');
                }
              } catch {
                setError('Could not reach backend on :8001');
              } finally {
                setBusy(false);
              }
            }}
            className="w-full py-2 px-3 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-semibold flex items-center justify-center space-x-2 transition"
          >
            <KeyRound className="h-3.5 w-3.5" />
            <span>1-Click Sign In (Sovereign Master Key)</span>
          </button>
        </div>

        <p className="text-[11px] text-slate-500">
          Keys are issued with <code className="font-mono">python scripts/create_admin_key.py</code>. The key is kept for this browser tab only.
        </p>
      </form>
    </div>
  );
};
