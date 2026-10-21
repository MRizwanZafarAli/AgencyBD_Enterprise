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

  const input = 'rounded-xl bg-slate-900 border border-slate-750 px-3.5 py-2.5 text-sm focus:outline-none focus:border-indigo-500 transition-all';
  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
          <KeyRound className="h-6 w-6 text-amber-400" />
          <span>Enterprise Access, RBAC &amp; API Keys</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
            RBAC &amp; TENANT ISOLATION
          </span>
        </h1>
        {you && <p className="text-sm text-slate-400 mt-1">Signed in as <span className="font-mono text-slate-200">{you.user_id}</span> · role <span className="font-mono text-indigo-400 font-semibold">{you.role}</span> · workspace <span className="font-mono text-slate-200">{you.org_id}</span></p>}
      </div>

      {secret && (
        <div role="status" className="rounded-2xl border border-amber-500/40 bg-amber-950/30 p-5 text-xs space-y-2 shadow-lg">
          <div className="font-semibold text-amber-200 text-sm">{secret.label}</div>
          <div className="font-mono text-white break-all select-all bg-slate-950/80 p-3 rounded-xl border border-amber-500/30 text-sm font-semibold">{secret.value}</div>
          <div className="text-amber-300 font-medium">⚠️ Copy this key now. For zero-trust security, it cannot be recovered or displayed again.</div>
          <button onClick={() => setSecret(null)} className="px-3 py-1.5 rounded-lg bg-amber-600/20 text-amber-300 hover:bg-amber-600/30 border border-amber-500/30 text-xs font-semibold">I have safely stored it</button>
        </div>
      )}

      <div className="bento-tile specular-border rounded-2xl p-6">
        <h2 className="text-sm font-semibold text-white mb-3">Enterprise Role Permissions</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {Object.entries(roles).map(([role, perms]) => (
            <div key={role} className="rounded-xl border border-slate-750 bg-slate-900/60 p-3.5 text-xs">
              <div className="font-mono font-bold text-indigo-400 text-sm">{role}</div>
              <div className="text-slate-400 mt-1.5 leading-relaxed break-words">{perms.includes('*') ? 'Full administrative authority (including cryptographic key management)' : perms.join(' · ')}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="bento-tile specular-border rounded-2xl p-6 space-y-3">
        <h2 className="text-sm font-semibold text-white flex items-center space-x-2"><Webhook className="h-4 w-4 text-cyan-400" /><span>Inbound Reply Webhook Signature</span></h2>
        <p className="text-xs text-slate-400 leading-relaxed">Your mail infrastructure posts prospect replies to <code>/api/webhooks/inbound</code>, cryptographically signed with your workspace secret. Rotating immediately invalidates past signatures.</p>
        <button onClick={rotateWebhook} className="rounded-xl bg-slate-800 hover:bg-slate-750 px-4 py-2 text-xs font-semibold text-slate-200 border border-slate-700 shadow-sm transition-all">Generate / Rotate Inbound Webhook Secret</button>
      </div>

      {keys !== null && (
        <div className="bento-tile specular-border rounded-2xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-white">Cryptographic API Keys (Tenant Administrator Gate)</h2>
          <form onSubmit={createKey} className="flex flex-wrap gap-2.5 items-center">
            <input className={input} placeholder="Key name (e.g. CI/CD Dispatcher)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <input className={input} placeholder="User identifier" value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })} required />
            <select className={input} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {Object.keys(roles).map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <button className="rounded-xl bg-indigo-600 hover:bg-indigo-500 px-5 py-2.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 transition-all">Issue API Key</button>
          </form>
          <div className="space-y-2 pt-2">
            {keys.map((k) => (
              <div key={k.id} className="flex justify-between items-center text-xs p-3 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="font-mono"><span className="text-white font-semibold">{k.name}</span> <span className="text-slate-400">({k.prefix}… · {k.role} · {k.user_id})</span></div>
                {k.revoked ? <span className="text-slate-500 font-mono text-[11px] bg-slate-800/80 px-2 py-0.5 rounded">REVOKED</span> : <button onClick={() => revoke(k.id)} className="text-rose-400 hover:text-rose-300 font-semibold text-xs px-2.5 py-1 rounded-lg hover:bg-rose-950/40 border border-rose-500/20 transition-all">Revoke</button>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
