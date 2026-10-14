import { useEffect, useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Mail, Plus, Square } from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';

interface Step { subject: string; body: string; delay_days: number }
interface Sequence { id: number; name: string; steps: Step[] }
interface Enrollment { id: number; sequence_id: number; recipient_email: string; country_code: string; current_step: number; next_run_at: string; status: string; stop_reason: string | null }

const blankStep = (n: number): Step => ({ subject: '', body: '', delay_days: n === 0 ? 0 : 3 });

export const SequencesManager: FC = () => {
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [name, setName] = useState('');
  const [steps, setSteps] = useState<Step[]>([blankStep(0)]);
  const [enroll, setEnroll] = useState({ sequence_id: 0, recipient_email: '', recipient_name: '', company_name: '', country_code: '' });
  const [msg, setMsg] = useState('');

  const load = async () => {
    const [s, e] = await Promise.all([apiFetch('/api/sequences'), apiFetch('/api/sequences/enrollments')]);
    if (s.ok) setSequences(await s.json());
    if (e.ok) setEnrollments(await e.json());
  };

  useEffect(() => {
    let active = true;
    Promise.all([apiFetch('/api/sequences'), apiFetch('/api/sequences/enrollments')]).then(async ([s, e]) => {
      if (!active) return;
      if (s.ok) setSequences(await s.json());
      if (e.ok) setEnrollments(await e.json());
    });
    return () => {
      active = false;
    };
  }, []);

  const post = async (path: string, body: unknown) => {
    const res = await apiFetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
    return data;
  };

  const createSequence = async (e: FormEvent) => {
    e.preventDefault();
    setMsg('');
    try {
      await post('/api/sequences', { name, steps });
      setName('');
      setSteps([blankStep(0)]);
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Failed');
    }
  };

  const enrollRecipient = async (e: FormEvent) => {
    e.preventDefault();
    setMsg('');
    try {
      await post(`/api/sequences/${enroll.sequence_id}/enroll`, { ...enroll });
      setEnroll({ ...enroll, recipient_email: '', recipient_name: '', company_name: '' });
      await load();
      setMsg('Enrolled. The first email goes to the Approval Inbox before anything is sent (default policy).');
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Failed');
    }
  };

  const stop = async (id: number) => {
    await apiFetch(`/api/sequences/enrollments/${id}/stop`, { method: 'POST' });
    await load();
  };

  const input = 'w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500';
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2"><Mail className="h-6 w-6 text-indigo-400" /><span>Sequences</span></h1>
        <p className="text-sm text-slate-400 mt-1">
          Multi-day email cadences. Each send re-checks jurisdiction, suppression, replies, email verification and your autonomy policy. Use {'{first_name}'} and {'{company}'} in templates.
          Sends only happen on weekdays inside the send window.
        </p>
      </div>
      {msg && <div role="status" className="text-xs text-amber-200 bg-amber-950/40 border border-amber-500/30 rounded-lg p-3">{msg}</div>}

      <form onSubmit={createSequence} className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4">
        <input className={input} placeholder="Sequence name" value={name} onChange={(e) => setName(e.target.value)} required />
        {steps.map((s, i) => (
          <div key={i} className="grid sm:grid-cols-[1fr_100px] gap-2.5 p-3 rounded-xl bg-slate-900/40 border border-slate-800/60">
            <input className={input} placeholder={`Step ${i + 1} subject`} value={s.subject} onChange={(e) => setSteps(steps.map((x, j) => j === i ? { ...x, subject: e.target.value } : x))} required />
            <input className={input} type="number" min={0} max={60} title="Days after the previous step" value={s.delay_days} onChange={(e) => setSteps(steps.map((x, j) => j === i ? { ...x, delay_days: Number(e.target.value) } : x))} />
            <textarea className={`${input} sm:col-span-2`} rows={3} placeholder="Body (state only facts you can prove)" value={s.body} onChange={(e) => setSteps(steps.map((x, j) => j === i ? { ...x, body: e.target.value } : x))} required />
          </div>
        ))}
        <div className="flex items-center gap-2 pt-1">
          <button type="button" onClick={() => setSteps([...steps, blankStep(steps.length)])} className="rounded-xl border border-slate-700/80 hover:border-slate-600 px-3 py-2 text-xs font-medium text-slate-300 transition">Add Step</button>
          <button className="flex items-center space-x-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-indigo-600/25 transition"><Plus className="h-4 w-4" /><span>Create Sequence</span></button>
        </div>
      </form>

      {sequences.length > 0 && (
        <form onSubmit={enrollRecipient} className="glass-panel rounded-2xl p-5 sm:p-6 grid sm:grid-cols-3 gap-3">
          <select className={input} value={enroll.sequence_id} onChange={(e) => setEnroll({ ...enroll, sequence_id: Number(e.target.value) })} required>
            <option value={0} disabled>Choose a sequence</option>
            {sequences.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.steps.length} steps)</option>)}
          </select>
          <input className={input} type="email" placeholder="Recipient email" value={enroll.recipient_email} onChange={(e) => setEnroll({ ...enroll, recipient_email: e.target.value })} required />
          <input className={input} placeholder="Country code (US, GB, FR...) required" maxLength={3} value={enroll.country_code} onChange={(e) => setEnroll({ ...enroll, country_code: e.target.value })} required />
          <input className={input} placeholder="Recipient name" value={enroll.recipient_name} onChange={(e) => setEnroll({ ...enroll, recipient_name: e.target.value })} />
          <input className={input} placeholder="Company" value={enroll.company_name} onChange={(e) => setEnroll({ ...enroll, company_name: e.target.value })} />
          <button disabled={!enroll.sequence_id} className="rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-emerald-600/25 transition">Enroll Recipient</button>
        </form>
      )}

      <div className="space-y-2">
        {enrollments.map((e) => (
          <div key={e.id} className="glass-panel-interactive rounded-xl p-3.5 text-xs flex justify-between gap-3 items-center">
            <div className="font-mono space-y-0.5">
              <div className="text-white font-semibold">{e.recipient_email} <span className="text-slate-500 font-normal">({e.country_code})</span></div>
              <div className="text-slate-400">Step {e.current_step} · {e.status.replace('_', ' ')} · Next {e.next_run_at} UTC{e.stop_reason ? ` · ${e.stop_reason}` : ''}</div>
            </div>
            {(e.status === 'active' || e.status === 'awaiting_approval') && (
              <button onClick={() => stop(e.id)} className="flex items-center space-x-1 text-slate-400 hover:text-rose-400 text-xs px-2.5 py-1 rounded-lg border border-slate-800 hover:border-rose-500/30 transition"><Square className="h-3.5 w-3.5" /><span>Stop</span></button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
