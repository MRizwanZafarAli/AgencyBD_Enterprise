import type { FC } from 'react';
import { CheckCircle2, Circle, AlertTriangle, Copy } from 'lucide-react';
import { Badge, Button, Card, Skeletons } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useApi } from '../../lib/hooks';

interface Check { key: string; label: string; status: 'ok' | 'missing' | 'optional_missing'; required: boolean; detail: string | null; fix: string | null }
interface Status { environment: string; ready_to_send_email: boolean; required_missing: number; checks: Check[]; warnings: string[] }
interface Identity { fields: Array<{ env: string; label: string; value: string; set: boolean; warning?: string }>; core_services: string[] }

export const SetupWizard: FC<{ onGo: (section: string) => void }> = ({ onGo }) => {
  const status = useApi<Status>('/api/system/status');
  const identity = useApi<Identity>('/api/identity');
  const s = status.data;
  const envLines = (identity.data?.fields ?? []).map((f) => `${f.env}=${f.value ?? ''}`).join('\n');

  return (
    <div className="space-y-5">
      <ErrorBanner message={status.error || identity.error} />
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-white">Setup checklist</h2>
          {s && <Badge tone={s.required_missing ? 'warn' : 'good'}>{s.required_missing ? `${s.required_missing} required item(s) missing` : 'All required items done'}</Badge>}
        </div>
        {status.loading && !s ? <Skeletons rows={4} /> : (
          <ul className="divide-y divide-slate-800">
            {s?.checks.map((c) => (
              <li key={c.key} className="py-2.5 flex gap-3 text-sm">
                {c.status === 'ok' ? <CheckCircle2 className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" /> : c.required ? <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" /> : <Circle className="h-4 w-4 text-slate-600 mt-0.5 shrink-0" />}
                <div className="min-w-0"><div className="text-slate-100">{c.label}{c.detail ? <span className="text-slate-500"> · {c.detail}</span> : null}{!c.required && c.status !== 'ok' && <span className="text-slate-500"> (optional)</span>}</div>
                  {c.status !== 'ok' && c.fix && <div className="text-xs text-slate-400 mt-0.5">{c.fix}</div>}</div>
              </li>))}
          </ul>
        )}
        {s?.warnings.map((w) => <p key={w} className="text-xs text-slate-500 mt-2">{w}</p>)}
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-1">Your agency identity</h2>
        <p className="text-xs text-slate-400 mb-3">Used in emails, reports and proposals. It comes from your .env file, so nothing here can be edited by a stranger through the app. Edit .env and restart.</p>
        <dl className="space-y-2 text-sm">
          {identity.data?.fields.map((f) => (
            <div key={f.env} className="grid sm:grid-cols-3 gap-1">
              <dt className="text-xs text-slate-400">{f.label}<div className="font-mono text-[10px] text-slate-500">{f.env}</div></dt>
              <dd className="sm:col-span-2 text-slate-100 break-words">{f.set ? f.value : <span className="text-amber-300">not set</span>}{f.warning && f.set && <div className="text-xs text-amber-300 mt-0.5">{f.warning}</div>}</dd>
            </div>))}
        </dl>
        {identity.data && <Button small className="mt-3" onClick={() => navigator.clipboard?.writeText(envLines)}><Copy className="h-3.5 w-3.5" />Copy as .env lines</Button>}
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-2">First-run steps</h2>
        <ol className="space-y-2 text-sm text-slate-300 list-decimal pl-5">
          <li>Check the identity above is yours and that every sentence is true.</li>
          <li><button className="text-indigo-300 hover:text-indigo-200 underline" onClick={() => onGo('services')}>Add your services</button> and at least one real case study. Proposals can only cite these.</li>
          <li><button className="text-indigo-300 hover:text-indigo-200 underline" onClick={() => onGo('keys')}>Add your API keys</button>: a language model, and for the best local search a Google Places key.</li>
          <li><button className="text-indigo-300 hover:text-indigo-200 underline" onClick={() => onGo('sending')}>Connect a sending mailbox</button> and set up DNS, only when you are ready to send.</li>
          <li>Go to Today and run your first search. Nothing is sent without your approval.</li>
        </ol>
      </Card>
    </div>
  );
};
