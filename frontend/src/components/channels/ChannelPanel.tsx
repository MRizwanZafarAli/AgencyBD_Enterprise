import { useState } from 'react';
import type { FC } from 'react';
import { ExternalLink, ShieldCheck } from 'lucide-react';
import { Card, Skeletons, Stat } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { apiFetch } from '../../lib/api';
import { send, useApi } from '../../lib/hooks';
import { Activity, Availability, Experiments, Features, Funnel, Pacing, Messages, OpenInBrowser, Performance, Pipeline, ProfileHealth, QuickPages, Routine, Templates } from './ChannelSections';
import { fmtMinutes, localDay } from './types';
import type { Catalog, Platform, Rec, Summary } from './types';
import type { Run } from './shared';

const money = (n: number) => `$${Math.round(n).toLocaleString()}`;

/** Runs one action, shows its error, then refreshes what is on screen. */
function useAction(reload: () => void): { error: string; run: Run } {
  const [error, setError] = useState('');
  const run: Run = async (fn: () => Promise<unknown>) => { try { setError(''); await fn(); reload(); } catch (e) { setError((e as Error).message); } };
  return { error, run };
}

export const ChannelPanel: FC<{ platform: Platform; catalog: Catalog }> = ({ platform, catalog }) => {
  const id = platform.id;
  const summary = useApi<Summary>(`/api/channels/${id}/summary`);
  const records = useApi<{ records: Rec[] }>(`/api/channels/${id}/records`);
  const routines = useApi<{ records: Rec[] }>(`/api/channels/${id}/records?type=routine`);   // first read seeds the default routine
  const reload = () => { summary.reload(); records.reload(); routines.reload(); };
  const { error, run } = useAction(reload);
  const all = records.data?.records ?? [];
  const of = (t: string) => all.filter((r) => r.type === t);
  const s = summary.data;
  const today = localDay();
  const doneToday = new Map(of('done').filter((d) => d.day === today).map((d) => [d.routine_id, d.id]));
  const post = (type: string, data: Record<string, unknown>) => send(`/api/channels/${id}/records`, 'POST', { type, data });
  const update = (rid: number, data: Record<string, unknown>) => run(async () => {
    const res = await apiFetch(`/api/channels/${id}/records/${rid}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ data }) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Could not save');
  });
  const remove = (rid: number) => run(() => send(`/api/channels/${id}/records/${rid}`, 'DELETE'));
  const loading = (records.loading && !records.data) || (summary.loading && !summary.data);

  return (
    <div className="space-y-5">
      <ErrorBanner message={error || summary.error || records.error} />
      <Card className="!border-emerald-500/30">
        <div className="flex gap-3">
          <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-white">How {platform.label} works here</h2>
            <ul className="mt-1.5 space-y-1 text-xs text-slate-300 list-disc pl-4">{platform.rules.map((r) => <li key={r}>{r}</li>)}</ul>
            {platform.terms && <a href={platform.terms} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:underline mt-2">Read their terms <ExternalLink className="h-3 w-3" /></a>}
          </div>
        </div>
      </Card>

      {loading ? <Skeletons rows={3} /> : s && (
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-5">
          <Stat label="Open applications" value={s.pipeline.open} hint={s.pipeline.value_open ? `${money(s.pipeline.value_open)} in play` : 'none valued'} />
          <Stat label="Follow-ups due" value={s.pipeline.followups_due} hint={s.pipeline.due_titles[0] ?? 'nothing overdue'} />
          <Stat label="Win rate" value={s.pipeline.win_rate_percent === null ? 'n/a' : `${s.pipeline.win_rate_percent}%`} hint={s.pipeline.win_rate_percent === null ? 'needs a won or lost' : `${money(s.pipeline.value_won)} won`} />
          <Stat label="Avg reply time" value={fmtMinutes(s.response.average_minutes)} hint={`${s.response.unanswered} waiting`} />
          <Stat label="Routine streak" value={`${s.routine.streak_days} d`} hint={`${s.routine.done_today}/${s.routine.total} done today`} />
        </div>
      )}

      <QuickPages platform={platform} />
      <Pacing s={s} />
      <Funnel s={s} />

      <div className="grid gap-5 lg:grid-cols-2">
        <Routine id={id} routines={routines.data?.records ?? []} doneToday={doneToday} today={today} run={run} post={post} remove={remove} />
        <OpenInBrowser platform={platform} links={of('link')} run={run} post={post} remove={remove} />
      </div>

      <Pipeline statuses={catalog.statuses} items={of('pipeline')} run={run} post={post} update={update} remove={remove} />

      <div className="grid gap-5 lg:grid-cols-2">
        <Templates platform={platform} items={of('template')} run={run} post={post} remove={remove} />
        <Messages items={of('message')} s={s} run={run} post={post} update={update} remove={remove} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Activity kinds={catalog.activity_kinds} s={s} today={today} run={run} post={post} />
        <Availability platform={platform} setting={s?.setting ?? null} s={s} run={run} post={post} />
      </div>
      <Performance platform={platform} s={s} />
      <Experiments items={of('experiment')} s={s} run={run} post={post} update={update} remove={remove} />
      <Features platform={platform} />
      <ProfileHealth platform={platform} />
    </div>
  );
};

