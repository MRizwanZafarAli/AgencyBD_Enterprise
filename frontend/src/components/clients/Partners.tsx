import { useState } from 'react';
import type { FC } from 'react';
import { Check, Plus, Trash2 } from 'lucide-react';
import { Badge, Button, Card, EmptyState, Stat, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';

interface Partner {
  id: number; name: string; kind: string; stage: string; contact_name: string | null; contact_where: string | null; website: string | null; offer: string | null;
  next_step_date: string | null; last_contact_at: string | null; notes: string | null; referrals_in: number; referrals_out: number; attention: string | null;
}
interface Data { partners: Partner[]; summary: { total: number; active: number; needs_attention: number; referrals_in: number; referrals_out: number }; kinds: Record<string, string>; stages: Record<string, string> }

const BLANK = { name: '', kind: 'agency', contact_name: '', contact_where: '', website: '', offer: '', notes: '' };
const IDEAS = 'Good first partners: design and marketing studios, accountants and company-formation agents (they meet new businesses first), lawyers, freelance designers and photographers, coworking spaces.';

/** People who could send you work. You type everything; this only remembers, counts referrals and reminds you. */
export const Partners: FC = () => {
  const data = useApi<Data>('/api/partners');
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState(BLANK);
  const run = async (fn: () => Promise<unknown>) => { setError(''); try { await fn(); data.reload(); } catch (e) { setError((e as Error).message); } };
  const d = data.data;
  const log = (p: Partner, kind: string, body?: string) => run(() => send(`/api/partners/${p.id}/events`, 'POST', { kind, body }));

  return (
    <div className="space-y-5">
      <ErrorBanner message={error || data.error} />
      {d && d.summary.total > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="Partners" value={d.summary.total} /><Stat label="Active" value={d.summary.active} />
          <Stat label="Clients they sent" value={d.summary.referrals_in} /><Stat label="Clients you sent them" value={d.summary.referrals_out} />
        </div>)}
      <Card>
        <div className="flex items-center gap-2 mb-2"><h2 className="text-sm font-semibold text-white mr-auto">Referral partners</h2>
          <Button small onClick={() => setAdding((v) => !v)}><Plus className="h-3.5 w-3.5" />Add partner</Button></div>
        <p className="text-xs text-slate-400 mb-3">{IDEAS}</p>
        {adding && (
          <form className="grid gap-2 sm:grid-cols-2 mb-4 p-3 rounded-xl border border-slate-800" onSubmit={(e) => { e.preventDefault(); run(async () => { await send('/api/partners', 'POST', f); setF(BLANK); setAdding(false); }); }}>
            <label className="text-xs text-slate-400">Name<input className={`${field} mt-1`} required maxLength={100} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
            <label className="text-xs text-slate-400">Kind<select className={`${field} mt-1`} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{Object.entries(d?.kinds ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            <label className="text-xs text-slate-400">Contact person<input className={`${field} mt-1`} value={f.contact_name} onChange={(e) => setF({ ...f, contact_name: e.target.value })} /></label>
            <label className="text-xs text-slate-400">How to reach them<input className={`${field} mt-1`} value={f.contact_where} onChange={(e) => setF({ ...f, contact_where: e.target.value })} placeholder="Email, phone or profile link" /></label>
            <label className="text-xs text-slate-400">Website<input className={`${field} mt-1`} value={f.website} onChange={(e) => setF({ ...f, website: e.target.value })} placeholder="example.com" /></label>
            <label className="text-xs text-slate-400">What you will offer them<input className={`${field} mt-1`} value={f.offer} onChange={(e) => setF({ ...f, offer: e.target.value })} placeholder="White-label builds, 10% on the first project" /></label>
            <div className="sm:col-span-2 flex justify-end"><Button variant="primary" type="submit">Save partner</Button></div>
          </form>)}
        {d && d.partners.length === 0 ? <EmptyState title="No partners yet" hint="One good partner can send ten clients. Start with three people you could message this week." /> : (
          <ul className="divide-y divide-slate-800">{(d?.partners ?? []).map((p) => (
            <li key={p.id} className="py-3 space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-white">{p.name}</span><Badge>{d!.kinds[p.kind]}</Badge>
                <select className={`${field} max-w-[11rem] py-1`} aria-label={`Stage of ${p.name}`} value={p.stage} onChange={(e) => run(() => send(`/api/partners/${p.id}`, 'PUT', { stage: e.target.value }))}>
                  {Object.entries(d!.stages).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
                {p.attention && <Badge tone="warn">{p.attention}</Badge>}
                <span className="ml-auto flex gap-1.5">
                  <Button small onClick={() => log(p, 'contacted')} aria-label={`I contacted ${p.name}`}><Check className="h-3.5 w-3.5" />Contacted today</Button>
                  <Button small variant="ghost" onClick={() => log(p, 'referral_in')} aria-label={`${p.name} sent me a client`}>They sent one</Button>
                  <Button small variant="ghost" onClick={() => log(p, 'referral_out')} aria-label={`I sent ${p.name} a client`}>I sent one</Button>
                  <Button small variant="ghost" onClick={() => run(() => send(`/api/partners/${p.id}`, 'DELETE'))} aria-label={`Delete ${p.name}`}><Trash2 className="h-3.5 w-3.5" /></Button>
                </span>
              </div>
              <p className="text-xs text-slate-400">{[p.contact_name, p.contact_where, p.website].filter(Boolean).join(' · ') || 'No contact details yet'}{p.offer ? ` · Offer: ${p.offer}` : ''}</p>
              <p className="text-xs text-slate-500">Sent to you: {p.referrals_in} · You sent: {p.referrals_out}{p.last_contact_at ? ` · Last contact ${p.last_contact_at.slice(0, 10)}` : ''}
                <label className="ml-3">Next step <input type="date" className={`${field} inline-block w-auto py-0.5`} aria-label={`Next step date for ${p.name}`} value={p.next_step_date ?? ''} onChange={(e) => run(() => send(`/api/partners/${p.id}`, 'PUT', { next_step_date: e.target.value }))} /></label></p>
            </li>))}</ul>)}
      </Card>
    </div>
  );
};
