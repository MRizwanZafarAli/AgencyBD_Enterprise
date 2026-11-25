import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { CalendarClock, Play, Plus, Power } from 'lucide-react';
import { Badge, Button, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';

interface Schedule {
  id: number;
  name: string;
  channel: string;
  query: string;
  cadence_hours: number;
  assign_mode: string;
  auto_send_tier_a: number;
  enabled: number;
  last_run_at?: string | null;
}

export const ScheduledAutopilot: FC = () => {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [open, setOpen] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState('Daily React & AI Hunt');
  const [channel, setChannel] = useState<'hiring' | 'local' | 'sec_edgar' | 'social'>('hiring');
  const [query, setQuery] = useState('react');
  const [cadence, setCadence] = useState('24');
  const [tierA, setTierA] = useState(false);
  const [note, setNote] = useState('');

  const load = async () => {
    const r = await apiFetch('/api/v1/swarm/schedules');
    if (r.ok) {
      const b = await r.json();
      setSchedules(b.schedules || []);
    }
  };

  useEffect(() => {
    if (open) load();
  }, [open]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setNote('');
    const r = await apiFetch('/api/v1/swarm/schedules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(),
        channel,
        query: query.trim(),
        cadence_hours: Number(cadence) || 24,
        assign_mode: 'round_robin',
        auto_send_tier_a: tierA,
      }),
    });
    const b = await r.json().catch(() => ({}));
    if (!r.ok) {
      setNote(apiErrorMessage(r.status, b));
      return;
    }
    setShowAdd(false);
    setNote('Schedule saved with round-robin rep assignment.');
    await load();
  };

  const toggle = async (id: number, enabled: boolean) => {
    await apiFetch(`/api/v1/swarm/schedules/${id}/toggle?enabled=${enabled}`, { method: 'POST' });
    await load();
  };

  const runDue = async () => {
    const r = await apiFetch('/api/v1/swarm/schedules/run-due', { method: 'POST' });
    if (r.ok) {
      const b = await r.json();
      setNote(`Triggered ${(b.triggered || []).length} due schedule(s).`);
      await load();
    }
  };

  return (
    <div className="mt-4 pt-4 border-t border-slate-800/80">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="text-xs font-medium text-indigo-300 hover:text-indigo-200 flex items-center gap-1.5"
        >
          <CalendarClock className="h-4 w-4" />
          {open ? 'Hide Recurring Autopilot Schedules' : 'Configure Recurring Autopilot Schedules (10-Rep Scale)'}
        </button>
        {open && (
          <div className="flex items-center gap-2">
            <Button small onClick={() => setShowAdd((v) => !v)}><Plus className="h-3.5 w-3.5" />New Schedule</Button>
            <Button small variant="primary" onClick={runDue}><Play className="h-3.5 w-3.5" />Run Due Now</Button>
          </div>
        )}
      </div>

      {open && (
        <div className="mt-3 space-y-3">
          {showAdd && (
            <form onSubmit={add} className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 grid gap-2 sm:grid-cols-4 items-end">
              <label className="text-xs text-slate-400 space-y-1">Name
                <input className={field} required value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="text-xs text-slate-400 space-y-1">Channel
                <select className={field} value={channel} onChange={(e) => setChannel(e.target.value as typeof channel)}>
                  <option value="hiring">Hiring</option>
                  <option value="social">Social Intent</option>
                  <option value="sec_edgar">SEC Filings</option>
                  <option value="local">Local</option>
                </select>
              </label>
              <label className="text-xs text-slate-400 space-y-1">Query / Every (hrs)
                <div className="flex gap-1.5">
                  <input className={field} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="react" />
                  <input className={`${field} w-20`} type="number" min={1} max={168} value={cadence} onChange={(e) => setCadence(e.target.value)} />
                </div>
              </label>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1.5 text-[11px] text-slate-300">
                  <input type="checkbox" checked={tierA} onChange={(e) => setTierA(e.target.checked)} /> Tier-A Auto
                </label>
                <Button type="submit" small variant="primary">Save</Button>
              </div>
            </form>
          )}
          {note && <p className="text-xs text-emerald-400">{note}</p>}
          {schedules.length === 0 ? (
            <p className="text-xs text-slate-500">No recurring schedules configured yet.</p>
          ) : (
            <ul className="divide-y divide-slate-800 text-xs">
              {schedules.map((s) => (
                <li key={s.id} className="py-2 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-medium text-white">{s.name}</span>{' '}
                    <Badge tone="accent">{s.channel}</Badge>{' '}
                    <Badge>{s.assign_mode}</Badge>{' '}
                    {s.auto_send_tier_a ? <Badge tone="good">Tier-A Auto</Badge> : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400">Every {s.cadence_hours}h</span>
                    <Button small onClick={() => toggle(s.id, !s.enabled)}>
                      <Power className={`h-3.5 w-3.5 ${s.enabled ? 'text-emerald-400' : 'text-slate-500'}`} />
                      {s.enabled ? 'Enabled' : 'Paused'}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};
