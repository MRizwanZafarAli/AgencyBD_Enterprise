import { useState } from 'react';
import type { FC } from 'react';
import { Badge, Button, Card } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';

interface Item { lead_id: number; company: string; stage_label: string; days_quiet: number; reason: string }

const inDays = (n: number) => { const d = new Date(Date.now() + n * 86400000); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const WHEN = [{ label: 'Tomorrow', days: 1 }, { label: 'In 3 days', days: 3 }, { label: 'Next week', days: 7 }];

/** Clients that went quiet in a live stage with no follow-up planned. One tap sets a follow-up date, which takes them off this list. */
export const ChasePanel: FC<{ onOpenClient: (leadId: number) => void }> = ({ onOpenClient }) => {
  const chase = useApi<{ items: Item[] }>('/api/chase');
  const [error, setError] = useState('');
  const items = chase.data?.items ?? [];
  const plan = async (i: Item, days: number) => {
    setError('');
    try { await send(`/api/clients/${i.lead_id}/notes`, 'POST', { kind: 'task', body: `Follow up with ${i.company}`, due_date: inDays(days) }); chase.reload(); }
    catch (e) { setError((e as Error).message); }
  };
  if (!chase.data || items.length === 0) return null;
  return (
    <Card>
      <h2 className="text-sm font-semibold text-white mb-1">Chase today</h2>
      <p className="text-xs text-slate-400 mb-2">These went quiet and nothing is planned. Follow up now, or pick a day and they leave this list.</p>
      <ErrorBanner message={error} />
      <ul className="divide-y divide-slate-800">{items.map((i) => (
        <li key={i.lead_id} className="py-2.5 flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => onOpenClient(i.lead_id)} className="text-sm font-medium text-white hover:underline text-left">{i.company}</button>
          <Badge tone="warn">{i.stage_label}</Badge>
          <span className="text-xs text-slate-400">{i.days_quiet} day{i.days_quiet === 1 ? '' : 's'} quiet</span>
          <span className="ml-auto flex flex-wrap gap-1.5">{WHEN.map((w) => <Button key={w.days} small variant="ghost" onClick={() => plan(i, w.days)} aria-label={`${w.label}: follow up with ${i.company}`}>{w.label}</Button>)}</span>
        </li>))}</ul>
    </Card>
  );
};
