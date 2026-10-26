import type { FC } from 'react';
import { LogOut, ShieldCheck, ShieldOff } from 'lucide-react';
import { Badge, Button, Card } from '../ui';
import { useApi } from '../../lib/hooks';
import type { Me } from '../../lib/api';

const HYGIENE = [
  'Your key is kept for this browser tab only and disappears when you close it.',
  'Give each person their own key under Team and keys, with the lowest role that does the job.',
  'Revoke a key the day someone leaves. A revoked key stops working immediately.',
  'Never paste a key into a chat, an email or a shared document. Anyone with it acts as you.',
  'Integration keys and mailbox passwords are encrypted here and are never shown again after saving.',
];

export const SecurityPanel: FC<{ me: Me; onSignOut: () => void }> = ({ me, onSignOut }) => {
  const halt = useApi<{ halted: boolean; reason?: string }>('/api/controls/outbound');
  const all = me.permissions.includes('*');
  const groups = all ? [] : Object.entries(me.permissions.reduce<Record<string, string[]>>((m, p) => { const [g, a] = p.split(':'); (m[g] ??= []).push(a ?? ''); return m; }, {}));
  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <span className="h-11 w-11 rounded-full bg-slate-800 text-slate-100 text-sm font-semibold flex items-center justify-center" aria-hidden="true">{me.user_id.slice(0, 2).toUpperCase()}</span>
          <div className="mr-auto min-w-0"><div className="text-sm font-semibold text-white truncate">{me.user_id}</div><div className="text-xs text-slate-400">{me.role.replace('_', ' ')} · workspace {me.org_id} · signed in with {me.auth_method === 'jwt' ? 'a token' : 'an API key'}</div></div>
          <Button onClick={onSignOut}><LogOut className="h-4 w-4" />Sign out</Button>
        </div>
      </Card>
      <Card>
        <h2 className="text-sm font-semibold text-white mb-1">What you can do</h2>
        {all ? <p className="text-sm text-slate-300">Everything. This is an administrator key, so keep it private and give teammates their own keys with narrower roles.</p> : (
          <dl className="grid gap-2 sm:grid-cols-2 text-xs">{groups.map(([g, acts]) => <div key={g} className="rounded-lg border border-slate-800 p-2.5"><dt className="font-medium text-slate-100 capitalize">{g}</dt><dd className="text-slate-400 mt-0.5">{acts.join(', ')}</dd></div>)}</dl>)}
      </Card>
      <Card>
        <div className="flex items-center gap-2 mb-1">{halt.data?.halted ? <ShieldOff className="h-4 w-4 text-rose-400" aria-hidden="true" /> : <ShieldCheck className="h-4 w-4 text-emerald-400" aria-hidden="true" />}<h2 className="text-sm font-semibold text-white">Outbound email switch</h2>
          {halt.data && <Badge tone={halt.data.halted ? 'bad' : 'good'}>{halt.data.halted ? 'Sending is stopped' : 'Sending is allowed'}</Badge>}</div>
        <p className="text-xs text-slate-400">The Stop sending button in the header halts every send for this workspace, including scheduled emails, until someone resumes it.{halt.data?.reason ? ` Reason given: ${halt.data.reason}.` : ''}</p>
      </Card>
      <Card><h2 className="text-sm font-semibold text-white mb-2">Key hygiene</h2><ul className="list-disc pl-5 space-y-1 text-sm text-slate-300">{HYGIENE.map((h) => <li key={h}>{h}</li>)}</ul></Card>
    </div>
  );
};
