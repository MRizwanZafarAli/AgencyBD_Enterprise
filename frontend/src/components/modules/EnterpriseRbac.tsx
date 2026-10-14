import { useEffect, useState } from 'react';
import type { FC, FormEvent } from 'react';
import { KeyRound, Webhook } from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

interface Props { selectedTenant: string }

export const EnterpriseRbac: FC<Props> = () => {
  const [roles, setRoles] = useState<Record<string, string[]>>({});
  const [you, setYou] = useState<any>(null);
  const [keys, setKeys] = useState<any[] | null>(null);
  const [form, setForm] = useState({ name: '', user_id: '', role: 'growth_lead' });
  const [secret, setSecret] = useState<{ label: string; value: string } | null>(null);
  const [error, setError] = useState('');

  const loadKeys = async () => {
    const res = await apiFetch('/api/security/list_keys');
    setKeys(res.ok ? (await res.json()).keys : null);   // 403 for non-admins: the panel is simply hidden
  };

  useEffect(() => {
    let active = true;
    Promise.all([apiFetch('/api/security/roles'), apiFetch('/api/security/list_keys')]).then(async ([r, k]) => {
      if (!active) return;
      if (r.ok) {
        const d = await r.json();
        setRoles(d.roles);
        setYou(d.you);
      }
      setKeys(k.ok ? (await k.json()).keys : null);
    });
    return () => {
      active = false;
    };
  }, []);

  const post = async (path: string, body?: unknown) => {
    const res = await apiFetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json();
    if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
    return data;
  };
  const guard = async (fn: () => Promise<void>) => {
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed.');
    }
  };

  const createKey = (e: FormEvent) => {
    e.preventDefault();
    guard(async () => {
      const d = await post('/api/security/create_key', form);
      setSecret({ label: `API key for ${d.name} (${d.role})`, value: d.api_key });
      setForm({ name: '', user_id: '', role: 'growth_lead' });
      await loadKeys();
    });
  };
  const revoke = (id: number) => guard(async () => {
    await post('/api/security/revoke_key', { key_id: id });
    await loadKeys();
  });
  const rotateWebhook = () => guard(async () => {
    const d = await post('/api/security/webhook_secret');
    setSecret({ label: `Webhook signing secret for ${d.org_id} (send X-AgencyBD-Org: ${d.org_id})`, value: d.webhook_secret });
  });

  const input = 'rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500';
  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2"><KeyRound className="h-6 w-6 text-amber-400" /><span>Access &amp; keys</span></h1>
        {you && <p className="text-sm text-slate-400 mt-1">Signed in as <span className="font-mono text-slate-200">{you.user_id}</span> · role <span className="font-mono text-slate-200">{you.role}</span> · workspace <span className="font-mono text-slate-200">{you.org_id}</span></p>}
      </div>

      {secret && (
        <div role="status" className="rounded-xl border border-amber-500/40 bg-amber-950/30 p-4 text-xs space-y-1">
          <div className="font-semibold text-amber-200">{secret.label}</div>
          <div className="font-mono text-white break-all select-all">{secret.value}</div>
          <div className="text-amber-300">Copy it now. It cannot be shown again.</div>
          <button onClick={() => setSecret(null)} className="text-slate-400 underline">I have stored it</button>
        </div>
      )}

      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
        <h2 className="text-sm font-semibold text-white mb-2">Roles</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {Object.entries(roles).map(([role, perms]) => (
            <div key={role} className="rounded-lg border border-slate-800 p-3 text-xs">
              <div className="font-mono font-semibold text-indigo-300">{role}</div>
              <div className="text-slate-400 mt-1 break-words">{perms.includes('*') ? 'everything, including API keys' : perms.join(', ')}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-2">
        <h2 className="text-sm font-semibold text-white flex items-center space-x-2"><Webhook className="h-4 w-4" /><span>Inbound reply webhook</span></h2>
        <p className="text-xs text-slate-400">Your mail provider posts replies to /api/webhooks/inbound, signed with your workspace secret. Rotating invalidates the old one.</p>
        <button onClick={rotateWebhook} className="rounded-lg bg-slate-700 hover:bg-slate-600 px-4 py-1.5 text-xs font-semibold">Create / rotate webhook secret</button>
      </div>

      {keys !== null && (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white">API keys (admins only)</h2>
          <form onSubmit={createKey} className="flex flex-wrap gap-2">
            <input className={input} placeholder="Key name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <input className={input} placeholder="User id" value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })} required />
            <select className={input} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {Object.keys(roles).map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <button className="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 text-sm font-semibold">Create key</button>
          </form>
          {keys.map((k) => (
            <div key={k.id} className="flex justify-between items-center text-xs border-t border-slate-800 pt-2">
              <div className="font-mono"><span className="text-white">{k.name}</span> <span className="text-slate-500">{k.prefix} · {k.role} · {k.user_id}</span></div>
              {k.revoked ? <span className="text-slate-500">revoked</span> : <button onClick={() => revoke(k.id)} className="text-rose-400 hover:text-rose-300">Revoke</button>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
