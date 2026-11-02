import type { FC } from 'react';
import { Card } from '../ui';
import { useApi } from '../../lib/hooks';

interface Row { key: string; label: string; hint: string; this_week: number; last_week: number }
interface Sheet { rows: Row[]; reply_rate_percent: number | null; last_reply_rate_percent: number | null; winners_by_source: Array<{ source: string; n: number }>; note: string }

const arrow = (a: number, b: number) => (a === b ? 'same as last week' : a > b ? `up from ${b}` : `down from ${b}`);

/** This week against last week, counted from your own records. A rate shows only when there is something to divide by. */
export const Scorecard: FC = () => {
  const s = useApi<Sheet>('/api/today/scorecard');
  if (!s.data) return null;
  const d = s.data;
  const active = d.rows.filter((r) => r.this_week > 0 || r.last_week > 0);
  return (
    <Card>
      <h2 className="text-sm font-semibold text-white mb-1">Your week</h2>
      {active.length === 0 ? <p className="text-xs text-slate-400">Nothing logged yet this week or last. Numbers appear here as you find leads, send emails, book calls and win clients.</p> : (
        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3 mt-2">
          {active.map((r) => (
            <div key={r.key} title={r.hint}><dt className="text-xs text-slate-400">{r.label}</dt><dd className="text-xl font-semibold text-white leading-tight">{r.this_week}</dd><dd className="text-[11px] text-slate-500">{arrow(r.this_week, r.last_week)}</dd></div>))}
          {d.reply_rate_percent !== null && <div><dt className="text-xs text-slate-400">Reply rate</dt><dd className="text-xl font-semibold text-white leading-tight">{d.reply_rate_percent}%</dd><dd className="text-[11px] text-slate-500">{d.last_reply_rate_percent !== null ? `last week ${d.last_reply_rate_percent}%` : 'no emails sent last week'}</dd></div>}
        </dl>)}
      {d.winners_by_source.length > 0 && <p className="text-xs text-slate-300 mt-3">Where your won clients came from: {d.winners_by_source.map((w) => `${w.source} (${w.n})`).join(', ')}</p>}
      <p className="text-[11px] text-slate-500 mt-2">{d.note}</p>
    </Card>
  );
};
