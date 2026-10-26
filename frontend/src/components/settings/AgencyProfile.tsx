import { useState } from 'react';
import type { FC } from 'react';
import { Lock, ShieldAlert } from 'lucide-react';
import { Badge, Button, Card, Skeletons, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';

interface F { key: string; label: string; group: string; help: string; value: string; set: boolean; source: 'settings' | 'env' | 'default'; env: string | null; needed_to_send: boolean; required: boolean; multiline: boolean; placeholder: string; warning: string | null }
interface Profile { fields: F[]; can_edit: boolean; ready_to_send: boolean; note: string }

const SOURCE: Record<F['source'], { tone: 'good' | 'info' | 'neutral'; text: string }> = { settings: { tone: 'good', text: 'Saved in Settings' }, env: { tone: 'info', text: 'From .env' }, default: { tone: 'neutral', text: 'Not set' } };

const Row: FC<{ f: F; canEdit: boolean; onChanged: () => void }> = ({ f, canEdit, onChanged }) => {
  const [value, setValue] = useState(f.value);
  const [serverValue, setServerValue] = useState(f.value);
  if (f.value !== serverValue) { setServerValue(f.value); setValue(f.value); }                  // the saved value changed on the server: show it, keep the confirmation message
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const dirty = value !== f.value;
  const run = async (label: string, fn: () => Promise<unknown>, done: string) => {
    setBusy(label); setError(''); setNote('');
    try { await fn(); setNote(done); onChanged(); } catch (e) { setError((e as Error).message); } finally { setBusy(''); }
  };
  const Input = f.multiline ? 'textarea' : 'input';
  return (
    <li className="py-4 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={`pf-${f.key}`} className="text-sm font-medium text-white">{f.label}</label>
        <Badge tone={SOURCE[f.source].tone}>{SOURCE[f.source].text}</Badge>
        {f.needed_to_send && !f.set && <Badge tone="warn">Needed before sending</Badge>}
      </div>
      <p className="text-xs text-slate-400">{f.help}</p>
      {f.warning && <p role="alert" className="flex gap-1.5 text-xs text-amber-300"><ShieldAlert className="h-4 w-4 shrink-0" aria-hidden="true" />{f.warning}</p>}
      <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); run('save', () => send(`/api/workspace/profile/${f.key}`, 'PUT', { value }), 'Saved and active now.'); }}>
        <Input id={`pf-${f.key}`} className={`${field} flex-1 min-w-56`} {...(f.multiline ? { rows: 2 } : {})} value={value} disabled={!canEdit} placeholder={f.placeholder} autoComplete="off" spellCheck={false}
          onChange={(e: { target: { value: string } }) => setValue(e.target.value)} />
        {canEdit && <Button small variant="primary" type="submit" disabled={!dirty || busy !== ''}>{busy === 'save' ? 'Saving…' : 'Save'}</Button>}
        {canEdit && f.source === 'settings' && <Button small type="button" disabled={busy !== ''} onClick={() => run('reset', () => send(`/api/workspace/profile/${f.key}`, 'DELETE').then(() => undefined), 'Back to the .env value.')}>Reset to .env</Button>}
        {canEdit && f.source === 'env' && f.set && !f.required && <Button small type="button" variant="ghost" disabled={busy !== ''} onClick={() => run('clear', () => send(`/api/workspace/profile/${f.key}`, 'PUT', { value: '' }), 'Cleared.')}>Clear</Button>}
      </form>
      <ErrorBanner message={error} />
      {note && <p role="status" className="text-xs text-slate-300">{note}</p>}
    </li>
  );
};

/** Who you are as an agency. Editable here (super-admin), applied immediately, and nothing quoted to a prospect without proof. */
export const AgencyProfile: FC = () => {
  const data = useApi<Profile>('/api/workspace/profile');
  const d = data.data;
  const by = (k: string) => d?.fields.find((f) => f.key === k)?.value ?? '';
  const groups = Array.from(new Set(d?.fields.map((f) => f.group) ?? []));
  return (
    <div className="space-y-5">
      <ErrorBanner message={data.error} />
      {d && !d.can_edit && <Card><p className="flex gap-2 text-sm text-slate-300"><Lock className="h-4 w-4 shrink-0 mt-0.5 text-slate-500" aria-hidden="true" />These details are shared by everyone on this installation, so only an administrator can change them. You can see what is set.</p></Card>}
      {data.loading && !d ? <Skeletons rows={4} /> : d && (
        <>
          <div className="grid gap-5 xl:grid-cols-[1fr_340px] items-start">
            <div className="space-y-5 min-w-0">
              {groups.map((g) => (
                <Card key={g}>
                  <h2 className="text-sm font-semibold text-white">{g}</h2>
                  <ul className="divide-y divide-slate-800">{d.fields.filter((f) => f.group === g).map((f) => <Row key={f.key} f={f} canEdit={d.can_edit} onChanged={data.reload} />)}</ul>
                </Card>))}
            </div>
            <div className="space-y-5 xl:sticky xl:top-24">
              <Card>
                <h2 className="text-sm font-semibold text-white mb-2">How your emails will read</h2>
                <div className="rounded-xl border border-slate-800 p-3 text-xs text-slate-200 space-y-2" aria-label="Email preview">
                  <p className="text-slate-400">Hi Sam, I took a look at your website and noticed…</p>
                  <p>Best,<br />{by('sender_name') || <span className="text-amber-300">sender name not set</span>}{by('sender_title') ? `, ${by('sender_title')}` : ''}<br />{by('name') || <span className="text-amber-300">agency name not set</span>}</p>
                  {by('booking_link') && <p className="text-slate-400">Book a call: {by('booking_link')}</p>}
                  {by('case_study_metric') && <p className="text-slate-300">{by('case_study_metric')}</p>}
                  <hr className="border-slate-800" />
                  <p className="text-[11px] text-slate-400">{by('name') || 'Your agency'}<br />{by('sender_address') || <span className="text-amber-300">postal address not set</span>}<br />
                    Unsubscribe: {by('public_base_url') ? `${by('public_base_url')}/unsubscribe/…` : <span className="text-amber-300">public address not set</span>}</p>
                </div>
              </Card>
              <Card>
                <div className="flex items-center justify-between mb-1"><h2 className="text-sm font-semibold text-white">Ready to send email?</h2><Badge tone={d.ready_to_send ? 'good' : 'warn'}>{d.ready_to_send ? 'Legal footer complete' : 'Footer incomplete'}</Badge></div>
                <p className="text-xs text-slate-400">Every commercial email must carry a real postal address and a working unsubscribe link. {d.ready_to_send ? 'Both are set.' : 'Fill both under Legal footer. Nothing can be sent until you do.'}</p>
              </Card>
              <p className="text-[11px] text-slate-500">{d.note}</p>
            </div>
          </div>
        </>)}
    </div>
  );
};
