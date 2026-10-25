import { useState } from 'react';
import type { FC } from 'react';
import { Check, Plus, Trash2 } from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { send, useApi } from '../../lib/hooks';
import { localDay } from '../channels/types';

interface Note { id: number; kind: 'note' | 'task'; body: string; due_date: string | null; done_at: string | null; created_by: string | null; created_at: string }
interface Data { items: Note[]; timeline: Array<{ at: string; what: string; actor: string }> }

const when = (s: string) => new Date(s.replace(' ', 'T') + (/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? '' : 'Z')).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

/** Your team's notes and follow-up tasks on a client, plus what the system did. Tasks due today or earlier show on Today. */
export const ClientNotes: FC<{ leadId: number; onChanged?: () => void }> = ({ leadId, onChanged }) => {
  const data = useApi<Data>(`/api/clients/${leadId}/notes`);
  const [kind, setKind] = useState<'note' | 'task'>('note');
  const [body, setBody] = useState('');
  const [due, setDue] = useState('');
  const [error, setError] = useState('');
  const today = localDay();
  const run = async (fn: () => Promise<unknown>) => { try { setError(''); await fn(); data.reload(); onChanged?.(); } catch (e) { setError((e as Error).message); } };
  const patch = (id: number, d: Record<string, unknown>) => run(async () => {
    const res = await apiFetch(`/api/clients/${leadId}/notes/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) });
    if (!res.ok) throw new Error(apiErrorMessage(res.status, await res.json().catch(() => ({}))));
  });
  const items = data.data?.items ?? [];

  return (
    <Card>
      <h3 className="text-sm font-semibold text-white mb-2">Notes and follow-ups</h3>
      <ErrorBanner message={error || data.error} />
      <form className="space-y-2 mb-3" onSubmit={(e) => { e.preventDefault(); run(() => send(`/api/clients/${leadId}/notes`, 'POST', { kind, body, due_date: kind === 'task' && due ? due : null })).then(() => { setBody(''); setDue(''); }); }}>
        <div className="flex gap-1.5" role="group" aria-label="What to add">
          {(['note', 'task'] as const).map((k) => <button type="button" key={k} aria-pressed={kind === k} onClick={() => setKind(k)}
            className={`px-2.5 py-1 rounded-md text-xs border ${kind === k ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-300' : 'border-slate-700 text-slate-400'}`}>{k === 'note' ? 'Note' : 'Follow-up task'}</button>)}
        </div>
        <textarea className={field} rows={2} aria-label={kind === 'note' ? 'Note' : 'Task'} placeholder={kind === 'note' ? 'What happened? A call, a quote, what they said…' : 'What needs doing?'} value={body} onChange={(e) => setBody(e.target.value)} required />
        <div className="flex flex-wrap items-center gap-2">
          {kind === 'task' && <label className="text-xs text-slate-400">Due <input className={`${field} !w-auto`} type="date" value={due} onChange={(e) => setDue(e.target.value)} /></label>}
          <Button small type="submit" variant="primary" className="ml-auto"><Plus className="h-3.5 w-3.5" />{kind === 'note' ? 'Add note' : 'Add task'}</Button>
        </div>
      </form>
      {items.length === 0 ? <p className="text-xs text-slate-500">Nothing yet.</p> : (
        <ul className="divide-y divide-slate-800">{items.map((n) => (
          <li key={n.id} className="py-2 flex items-start gap-2 group">
            {n.kind === 'task' ? (
              <button role="checkbox" aria-checked={!!n.done_at} aria-label={`${n.body}: ${n.done_at ? 'done' : 'not done'}`} onClick={() => patch(n.id, { done: !n.done_at })}
                className={`mt-0.5 h-5 w-5 rounded border flex items-center justify-center shrink-0 ${n.done_at ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-slate-600'}`}>{n.done_at && <Check className="h-3.5 w-3.5" />}</button>
            ) : <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-slate-500 shrink-0 ml-1.5 mr-1" aria-hidden="true" />}
            <div className="flex-1 min-w-0">
              <div className={`text-sm whitespace-pre-wrap ${n.done_at ? 'text-slate-500 line-through' : 'text-slate-200'}`}>{n.body}</div>
              <div className="text-[11px] text-slate-500">{n.created_by ?? 'someone'} · {when(n.created_at)}
                {n.kind === 'task' && n.due_date && !n.done_at && <> · <Badge tone={n.due_date <= today ? 'warn' : 'neutral'}>{n.due_date <= today ? 'Due' : 'Due'} {n.due_date}</Badge></>}</div>
            </div>
            <button aria-label={`Delete ${n.kind}`} onClick={() => run(() => send(`/api/clients/${leadId}/notes/${n.id}`, 'DELETE'))} className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 text-slate-500 hover:text-rose-400"><Trash2 className="h-3.5 w-3.5" /></button>
          </li>))}</ul>)}
      {(data.data?.timeline.length ?? 0) > 0 && (
        <details className="mt-3">
          <summary className="text-xs text-slate-400 cursor-pointer">System timeline ({data.data!.timeline.length})</summary>
          <ul className="mt-2 space-y-1">{data.data!.timeline.map((t, i) => <li key={i} className="text-[11px] text-slate-400">{when(t.at)} · {t.what} <span className="text-slate-600">({t.actor})</span></li>)}</ul>
        </details>)}
    </Card>
  );
};
