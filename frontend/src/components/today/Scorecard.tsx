import { useState } from 'react';
import type { FC } from 'react';
import { Card, Select } from '../ui';
import { useApi } from '../../lib/hooks';

interface Row { key: string; label: string; hint: string; this_week: number; last_week: number }
interface Sheet { rows: Row[]; reply_rate_percent: number | null; last_reply_rate_percent: number | null; winners_by_source: Array<{ source: string; n: number }>; note: string }

const arrow = (a: number, b: number) => (a === b ? 'No change' : a > b ? `Up from ${b}` : `Down from ${b}`);

export const Scorecard: FC = () => {
  const [period, setPeriod] = useState<'7' | '30' | '90'>('7');
  const s = useApi<Sheet>('/api/today/scorecard');
  if (!s.data) return null;
  const d = s.data;
  const active = d.rows.filter((r) => r.this_week > 0 || r.last_week > 0);
  return (
    <Card>
      <div className="flex items-center justify-between gap-2 mb-2">
        <h2 className="text-sm font-semibold text-white">Performance Pulse</h2>
        <div className="w-24">
          <Select
            small
            value={period}
            onChange={(v) => setPeriod(v as '7' | '30' | '90')}
            aria-label="Scorecard period"
            options={[
              { value: '7', label: '7d' },
              { value: '30', label: '30d' },
              { value: '90', label: '90d' },
            ]}
          />
        </div>
      </div>
      {active.length === 0 ? (
        <p className="text-xs text-slate-400">Activity metrics populate as you save leads, send emails, and close deals.</p>
      ) : (
        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3 mt-2">
          {active.map((r) => (
            <div key={r.key} title={r.hint}>
              <dt className="text-xs text-slate-400">{r.label}</dt>
              <dd className="text-xl font-semibold text-white leading-tight">{r.this_week}</dd>
              <dd className="text-[11px] text-slate-500">{arrow(r.this_week, r.last_week)}</dd>
            </div>
          ))}
          {d.reply_rate_percent !== null && (
            <div>
              <dt className="text-xs text-slate-400">Reply rate</dt>
              <dd className="text-xl font-semibold text-white leading-tight">{d.reply_rate_percent}%</dd>
              <dd className="text-[11px] text-slate-500">
                {d.last_reply_rate_percent !== null ? `Previous: ${d.last_reply_rate_percent}%` : 'Baseline period'}
              </dd>
            </div>
          )}
        </dl>
      )}
      {d.winners_by_source.length > 0 && (
        <p className="text-xs text-slate-300 mt-3">
          Won deal sources: {d.winners_by_source.map((w) => `${w.source} (${w.n})`).join(', ')}
        </p>
      )}
    </Card>
  );
};
