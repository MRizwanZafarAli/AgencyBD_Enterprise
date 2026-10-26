import type { FC } from 'react';
import { ArrowRight, CheckCircle2, Circle, AlertTriangle } from 'lucide-react';
import { Badge, Button, Card, Skeletons } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import type { ApiState } from '../../lib/hooks';

export interface Check { key: string; label: string; status: 'ok' | 'missing' | 'optional_missing'; required: boolean; detail: string | null; fix: string | null }
export interface Status { environment: string; ready_to_send_email: boolean; required_missing: number; checks: Check[]; warnings: string[] }

/** Where each unfinished item is fixed. Items with no entry (the scheduler) are done outside the app, and say how. */
const FIX_IN: Record<string, { section: string; label: string }> = {
  llm: { section: 'keys', label: 'Add a key' }, verifier: { section: 'keys', label: 'Add a key' }, pagespeed: { section: 'keys', label: 'Add a key' }, places: { section: 'keys', label: 'Add a key' },
  search: { section: 'keys', label: 'Add a key' }, sam_gov: { section: 'keys', label: 'Add a key' }, upwork: { section: 'keys', label: 'Connect' },
  portfolio: { section: 'services', label: 'Add a case study' }, services: { section: 'services', label: 'Set prices' },
  mailbox: { section: 'sending', label: 'Connect a mailbox' }, webhook_secret: { section: 'sending', label: 'Open sending' },
  sender_identity: { section: 'profile', label: 'Fill the footer' },
};

const Item: FC<{ c: Check; onGo: (s: string) => void }> = ({ c, onGo }) => {
  const fix = FIX_IN[c.key];
  return (
    <li className="py-3 flex items-start gap-3 text-sm">
      {c.status === 'ok' ? <CheckCircle2 className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" aria-label="Done" /> : c.required ? <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" aria-label="Needs attention" /> : <Circle className="h-4 w-4 text-slate-500 mt-0.5 shrink-0" aria-label="Optional" />}
      <div className="min-w-0 flex-1">
        <div className="text-slate-100">{c.label}{c.detail ? <span className="text-slate-500"> · {c.detail}</span> : null}</div>
        {c.status !== 'ok' && c.fix && <div className="text-xs text-slate-400 mt-0.5">{c.fix}</div>}
      </div>
      {c.status !== 'ok' && fix && <Button small variant={c.required ? 'primary' : 'secondary'} onClick={() => onGo(fix.section)}>{fix.label}<ArrowRight className="h-3.5 w-3.5" /></Button>}
    </li>
  );
};

export const SetupWizard: FC<{ status: ApiState<Status>; onGo: (section: string) => void }> = ({ status, onGo }) => {
  const s = status.data;
  const required = s?.checks.filter((c) => c.required) ?? [];
  const optional = s?.checks.filter((c) => !c.required) ?? [];
  const done = (list: Check[]) => list.filter((c) => c.status === 'ok').length;
  const pct = s ? Math.round((100 * done(s.checks)) / s.checks.length) : 0;

  return (
    <div className="space-y-5">
      <ErrorBanner message={status.error} />
      <Card>
        <div className="flex flex-wrap items-center gap-6">
          <div role="img" aria-label={`${pct} percent of setup done`} className="relative h-20 w-20 shrink-0">
            <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90"><circle cx="18" cy="18" r="15.5" fill="none" strokeWidth="3.5" className="stroke-slate-800" />
              <circle cx="18" cy="18" r="15.5" fill="none" strokeWidth="3.5" strokeLinecap="round" strokeDasharray={`${(pct / 100) * 97.4} 97.4`} className="stroke-indigo-500 transition-all duration-700" /></svg>
            <div className="absolute inset-0 flex items-center justify-center text-lg font-semibold text-white tabular">{pct}%</div>
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-white">{s ? (s.required_missing ? `${s.required_missing} required step${s.required_missing === 1 ? '' : 's'} left` : 'All required steps are done') : 'Checking your setup…'}</h2>
            <p className="text-xs text-slate-400 mt-1 max-w-xl">{s?.ready_to_send_email ? 'You can send email: a verifier, a mailbox and your legal footer are in place. Every first email still waits for your approval.'
              : 'Searching, auditing and drafting work already. Sending email needs a verifier, a mailbox with credentials and your legal footer.'}</p>
            {s && <div className="flex flex-wrap gap-2 mt-2"><Badge tone={s.ready_to_send_email ? 'good' : 'warn'}>{s.ready_to_send_email ? 'Ready to send' : 'Not ready to send'}</Badge><Badge>{done(required)}/{required.length} required</Badge><Badge>{done(optional)}/{optional.length} optional</Badge></div>}
          </div>
        </div>
      </Card>

      {status.loading && !s ? <Skeletons rows={4} /> : s && (
        <>
          <Card><h2 className="text-sm font-semibold text-white">Required</h2><ul className="divide-y divide-slate-800">{required.map((c) => <Item key={c.key} c={c} onGo={onGo} />)}</ul></Card>
          <Card><h2 className="text-sm font-semibold text-white">Optional, when you want more</h2><ul className="divide-y divide-slate-800">{optional.map((c) => <Item key={c.key} c={c} onGo={onGo} />)}</ul>
            {s.warnings.map((w) => <p key={w} className="text-xs text-slate-500 mt-2">{w}</p>)}</Card>
        </>)}
    </div>
  );
};
