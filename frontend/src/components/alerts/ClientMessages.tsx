import { useState } from 'react';
import type { FC } from 'react';
import { BellRing, Check, Copy, ExternalLink, PenLine, Plus, X } from 'lucide-react';
import { Badge, Button, Card, EmptyState, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { CHANNEL_LABEL } from './types';
import type { ClientMessage, DeskStatus } from './types';

const PLATFORMS = ['fiverr', 'upwork', 'linkedin', 'freelancer', 'peopleperhour', 'contra', 'toptal', 'guru', 'other'];
const ago = (at: string) => { const m = Math.max(0, Math.round((Date.now() - new Date(at.replace(' ', 'T') + 'Z').getTime()) / 60000)); return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`; };
interface Replies { drafts: Array<{ label: string; text: string }>; needs: string[]; note: string }
const TONE = { sent: 'good', failed: 'bad', skipped: 'neutral' } as const;

/** Client messages the Alert Desk found (or you added), newest first, with what has been tried and a way to say "I'm on it". */
export const ClientMessages: FC<{ onOpenAlerts?: () => void }> = ({ onOpenAlerts }) => {
  const data = useApi<{ messages: ClientMessage[]; status: DeskStatus }>('/api/alerts/messages');
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ platform: 'upwork', sender: '', text: '' });
  const [replies, setReplies] = useState<Record<number, Replies>>({});
  const [copied, setCopied] = useState('');
  const draft = async (id: number) => {
    setError('');
    try {
      const res = await apiFetch(`/api/alerts/messages/${id}/replies`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      setReplies({ ...replies, [id]: body as Replies });
    } catch (e) { setError((e as Error).message); }
  };
  const copy = async (key: string, text: string) => { try { await navigator.clipboard.writeText(text); setCopied(key); window.setTimeout(() => setCopied(''), 1600); } catch { setError('Copy was blocked by the browser. Select the text and copy it by hand.'); } };
  const msgs = data.data?.messages ?? [];
  const waiting = msgs.filter((m) => m.status === 'new');
  const done = msgs.filter((m) => m.status !== 'new').slice(0, 4);
  const st = data.data?.status;
  const act = async (id: number, what: 'ack' | 'dismiss') => { setError(''); try { await send(`/api/alerts/messages/${id}/${what}`); data.reload(); } catch (e) { setError((e as Error).message); } };
  const add = async () => { setError(''); try { await send('/api/alerts/messages', 'POST', f); setF({ ...f, sender: '', text: '' }); setAdding(false); data.reload(); } catch (e) { setError((e as Error).message); } };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <BellRing className="h-4 w-4 text-indigo-400" aria-hidden="true" /><h2 className="text-sm font-semibold text-white mr-auto">Client messages</h2>
        {st && <Badge tone={st.enabled ? 'good' : 'neutral'}>{st.enabled ? (st.paused ? 'Alerts paused' : 'Alert Desk on') : 'Alert Desk off'}</Badge>}
        {onOpenAlerts && <button type="button" onClick={onOpenAlerts} className="text-xs text-indigo-400 hover:underline">Alert settings</button>}
        <Button small onClick={() => setAdding((v) => !v)}><Plus className="h-3.5 w-3.5" />Add by hand</Button>
      </div>
      <ErrorBanner message={error || data.error} />
      {adding && (
        <form className="grid gap-2 sm:grid-cols-[9rem_10rem_1fr_auto] mb-3" onSubmit={(e) => { e.preventDefault(); add(); }}>
          <select className={field} aria-label="Platform" value={f.platform} onChange={(e) => setF({ ...f, platform: e.target.value })}>{PLATFORMS.map((p) => <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>)}</select>
          <input className={field} aria-label="Who wrote" placeholder="Who wrote" required value={f.sender} onChange={(e) => setF({ ...f, sender: e.target.value })} />
          <input className={field} aria-label="What they wrote" placeholder="What they wrote" required value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} />
          <Button variant="primary" type="submit">Add</Button>
        </form>)}
      {waiting.length === 0 ? <EmptyState title="Nothing waiting for a reply" hint={st?.enabled ? 'When a client writes, it appears here and reaches you on your phone.' : 'Switch the Alert Desk on in Settings and you will be told on your phone the moment a client writes.'} /> : (
        <ul className="divide-y divide-slate-800">{waiting.map((m) => (
          <li key={m.id} className="py-3 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2"><Badge tone="warn">{m.platform}</Badge><span className="text-sm font-medium text-white">{m.sender}</span><span className="text-xs text-slate-500">{ago(m.received_at)}</span>
              {m.url && <a href={m.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:underline">Open <ExternalLink className="h-3 w-3" /></a>}
              <span className="ml-auto flex gap-2"><Button small onClick={() => draft(m.id)} aria-label={`Draft a reply to ${m.sender}`}><PenLine className="h-3.5 w-3.5" />Draft a reply</Button><Button small variant="primary" onClick={() => act(m.id, 'ack')} aria-label={`I'm on it: ${m.sender}`}><Check className="h-3.5 w-3.5" />I&apos;m on it</Button>
                <Button small variant="ghost" onClick={() => act(m.id, 'dismiss')} aria-label={`Dismiss ${m.sender}`}><X className="h-3.5 w-3.5" /></Button></span></div>
            <p className="text-sm text-slate-300">{m.preview || m.subject}</p>
            {replies[m.id] && (
              <div className="space-y-2 rounded-xl border border-slate-800 p-3">
                {replies[m.id].needs.length > 0 && <p className="text-xs text-amber-300">To improve these drafts: {replies[m.id].needs.join(' ')}</p>}
                {replies[m.id].drafts.map((d) => (
                  <div key={d.label}>
                    <div className="flex items-center gap-2 mb-1"><span className="text-xs font-medium text-slate-300">{d.label}</span>
                      <Button small variant="ghost" onClick={() => copy(`${m.id}:${d.label}`, d.text)} aria-label={`Copy draft: ${d.label}`}>{copied === `${m.id}:${d.label}` ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}</Button></div>
                    <textarea readOnly rows={5} className={`${field} font-sans text-xs`} aria-label={`Draft reply: ${d.label}`} value={d.text} />
                  </div>))}
                <p className="text-xs text-slate-500">{replies[m.id].note}</p>
              </div>)}
            {m.attempts.length > 0 && <div className="flex flex-wrap gap-1.5">{m.attempts.map((a) => <Badge key={a.step_index} tone={TONE[a.status]} title={a.detail}>{CHANNEL_LABEL[a.channel]} {a.status}</Badge>)}</div>}
          </li>))}</ul>)}
      {done.length > 0 && <details className="mt-3"><summary className="text-xs text-slate-400 cursor-pointer">Recently handled ({done.length})</summary>
        <ul className="mt-2 space-y-1">{done.map((m) => <li key={m.id} className="text-xs text-slate-400">{m.sender} on {m.platform}, {ago(m.received_at)} · {m.status}{m.acknowledged_via ? ` via ${m.acknowledged_via}` : ''}</li>)}</ul></details>}
    </Card>
  );
};
