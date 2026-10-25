import type { FC } from 'react';
import { Badge, Card } from '../ui';
import { useApi } from '../../lib/hooks';

interface Item { id: number; lead_id: number; company: string; body: string; due_date: string | null }

/** Open follow-up tasks from every client page: what is due now, then what is coming. */
export const FollowupsPanel: FC<{ onOpenClient: (leadId: number) => void; refreshKey?: number }> = ({ onOpenClient }) => {
  const f = useApi<{ due: Item[]; upcoming: Item[] }>('/api/followups');
  const due = f.data?.due ?? [];
  const upcoming = (f.data?.upcoming ?? []).slice(0, 5);
  if (!f.data || (due.length === 0 && upcoming.length === 0)) return null;
  const row = (i: Item, tone: 'warn' | 'neutral') => (
    <li key={i.id}><button onClick={() => onOpenClient(i.lead_id)} className="w-full flex items-center gap-2 py-2 text-left">
      <span className="flex-1 min-w-0"><span className="block text-sm text-slate-100 truncate">{i.body}</span><span className="block text-[11px] text-slate-500">{i.company}</span></span>
      {i.due_date ? <Badge tone={tone}>{i.due_date}</Badge> : <Badge>no date</Badge>}
    </button></li>);
  return (
    <Card>
      <h2 className="text-sm font-semibold text-white mb-1">Client follow-ups</h2>
      <ul className="divide-y divide-slate-800">{due.map((i) => row(i, 'warn'))}{upcoming.map((i) => row(i, 'neutral'))}</ul>
    </Card>
  );
};
