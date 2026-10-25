import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { ExternalLink, KeyRound } from 'lucide-react';
import { Badge, Button, Card, Skeletons, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';

interface Row { name: string; label: string; group: string; purpose: string; get_url: string; cost: string; secret: boolean; set: boolean; source: 'settings' | 'env' | null; display: string | null; updated_at: string | null; testable: boolean }
interface Listing { integrations: Row[]; note: string }

const KeyRow: FC<{ row: Row; onChanged: () => void }> = ({ row, onChanged }) => {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setError(''); setNote('');
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : 'Failed'); } finally { setBusy(''); }
  };
  const save = (e: FormEvent) => { e.preventDefault(); run('save', async () => { await send(`/api/integrations/${row.name}`, 'PUT', { value }); setValue(''); setNote('Saved and active now.'); onChanged(); }); };
  const test = () => run('test', async () => { const r = await send<{ ok: boolean | null; message: string }>(`/api/integrations/${row.name}/test`, 'POST'); setNote(`${r.ok === true ? 'Works. ' : r.ok === false ? 'Failed. ' : ''}${r.message}`); });
  const remove = () => run('remove', async () => { await send(`/api/integrations/${row.name}`, 'DELETE'); onChanged(); });

  return (
    <li className="py-4 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-white">{row.label}</span>
        {row.set ? <Badge tone="good">{row.source === 'settings' ? 'Saved in Settings' : 'Set in .env'}</Badge> : <Badge tone="neutral">Not set</Badge>}
        {row.display && <span className="font-mono text-xs text-slate-400">{row.display}</span>}
      </div>
      <p className="text-xs text-slate-400">{row.purpose} <span className="text-slate-500">Cost: {row.cost}.</span>{' '}
        <a className="inline-flex items-center gap-0.5 text-indigo-300 hover:text-indigo-200" href={row.get_url} target="_blank" rel="noreferrer noopener">Get a key<ExternalLink className="h-3 w-3" /></a></p>
      <form onSubmit={save} className="flex flex-wrap gap-2">
        <input className={`${field} flex-1 min-w-56`} type={row.secret ? 'password' : 'text'} autoComplete="off" spellCheck={false} aria-label={`${row.label} value`}
          placeholder={row.set ? 'Paste a new value to replace it' : row.secret ? 'Paste the key' : 'Paste the value'} value={value} onChange={(e) => setValue(e.target.value)} />
        <Button variant="primary" small disabled={!value || busy !== ''}>{busy === 'save' ? 'Saving…' : 'Save'}</Button>
        {row.set && row.testable && <Button small type="button" disabled={busy !== ''} onClick={test}>{busy === 'test' ? 'Testing…' : 'Test'}</Button>}
        {row.source === 'settings' && <Button small type="button" variant="ghost" disabled={busy !== ''} onClick={remove}>Remove</Button>}
      </form>
      <ErrorBanner message={error} />
      {note && <div role="status" className="text-xs text-slate-300">{note}</div>}
    </li>
  );
};

export const IntegrationsPanel: FC = () => {
  const data = useApi<Listing>('/api/integrations');
  const groups = Array.from(new Set((data.data?.integrations ?? []).map((i) => i.group)));
  return (
    <div className="space-y-5">
      <div className="flex gap-2 items-start text-xs text-slate-400 max-w-3xl"><KeyRound className="h-4 w-4 text-slate-500 shrink-0 mt-0.5" />
        <p>Add the API keys of the products you use. They are encrypted, shared by this whole installation, never shown again after saving, and take effect immediately. A key saved here overrides the same one in .env; removing it restores the .env value.</p></div>
      <ErrorBanner message={data.error.includes('permission') ? 'Only an administrator can manage keys.' : data.error} />
      {data.loading && !data.data ? <Skeletons rows={4} /> : groups.map((g) => (
        <Card key={g}>
          <h2 className="text-sm font-semibold text-white mb-1">{g}</h2>
          <ul className="divide-y divide-slate-800">{data.data!.integrations.filter((i) => i.group === g).map((r) => <KeyRow key={r.name} row={r} onChanged={data.reload} />)}</ul>
        </Card>))}
    </div>
  );
};
