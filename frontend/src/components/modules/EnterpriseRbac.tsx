import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { ShieldCheck, Webhook } from 'lucide-react';
import { PasswordsPanel } from '../settings/PasswordsPanel';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

interface Props { selectedTenant: string }

export const EnterpriseRbac: FC<Props> = () => {
  const [roles, setRoles] = useState<Record<string, string[]>>({});
  const [you, setYou] = useState<any>(null);
  const [secret, setSecret] = useState<{ label: string; value: string } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiFetch('/api/security/roles').then(async (r) => {
      if (!active || !r.ok) return;
      const d = await r.json();
      setRoles(d.roles);
      setYou(d.you);
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

  const rotateWebhook = () => guard(async () => {
    const d = await post('/api/security/webhook_secret');
    setSecret({ label: `Webhook signing secret for ${d.org_id} (send X-AgencyBD-Org: ${d.org_id})`, value: d.webhook_secret });
  });

  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
          <ShieldCheck className="h-6 w-6 text-indigo-400" />
          <span>Access and passwords</span>
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
          <div className="text-amber-300 font-medium">Copy this now. It cannot be recovered or displayed again.</div>
          <button onClick={() => setSecret(null)} className="px-3 py-1.5 rounded-lg bg-amber-600/20 text-amber-300 hover:bg-amber-600/30 border border-amber-500/30 text-xs font-semibold">I have safely stored it</button>
        </div>
      )}

      <div className="bento-tile specular-border rounded-2xl p-6">
        <h2 className="text-sm font-semibold text-white mb-3">Enterprise Role Permissions</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {Object.entries(roles).map(([role, perms]) => (
            <div key={role} className="rounded-xl border border-slate-750 bg-slate-900/60 p-3.5 text-xs">
              <div className="font-mono font-bold text-indigo-400 text-sm">{role}</div>
              <div className="text-slate-400 mt-1.5 leading-relaxed break-words">{perms.includes('*') ? 'Full administrative authority (including every tier password)' : perms.join(' · ')}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="bento-tile specular-border rounded-2xl p-6 space-y-3">
        <h2 className="text-sm font-semibold text-white flex items-center space-x-2"><Webhook className="h-4 w-4 text-cyan-400" /><span>Inbound Reply Webhook Signature</span></h2>
        <p className="text-xs text-slate-400 leading-relaxed">Your mail infrastructure posts prospect replies to <code>/api/webhooks/inbound</code>, cryptographically signed with your workspace secret. Rotating immediately invalidates past signatures.</p>
        <button onClick={rotateWebhook} className="rounded-xl bg-slate-800 hover:bg-slate-750 px-4 py-2 text-xs font-semibold text-slate-200 border border-slate-700 shadow-sm transition-all">Generate / Rotate Inbound Webhook Secret</button>
      </div>

      {you && <PasswordsPanel myRole={you.role} />}
    </div>
  );
};
