import { useState } from 'react';
import type { FC } from 'react';
import { Sparkles } from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send } from '../../lib/hooks';
import type { Catalog } from './types';
import { STATUS_LABEL } from './types';

interface Parsed {
  text: string; platform: string | null; needs: string[]; notes: string[]; understood: string[];
  record: { title: string | null; status: string; value: number | null; next_followup: string | null; counterparty: string | null };
}

/** Type one sentence, check the draft, confirm. Nothing is saved until you press Save, and a missing platform or title is asked for, never guessed. */
export const QuickLog: FC<{ catalog: Catalog; seed?: { text: string; n: number } | null; onSaved: (platform: string) => void }> = ({ catalog, seed, onSaved }) => {
  const [text, setText] = useState('');
  const [draft, setDraft] = useState<Parsed | null>(null);
  const [platform, setPlatform] = useState('');
  const [rec, setRec] = useState<Parsed['record'] | null>(null);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [lastSeed, setLastSeed] = useState(0);

  const parse = async (value: string) => {
    if (!value.trim()) return;
    setError(''); setSaved('');
    try {
      const p = await send<Parsed>('/api/channels/parse', 'POST', { text: value });
      setDraft(p); setPlatform(p.platform ?? ''); setRec(p.record);
    } catch (e) { setError((e as Error).message); }
  };
  if (seed && seed.n !== lastSeed) { setLastSeed(seed.n); setText(seed.text); setTimeout(() => parse(seed.text), 0); }      // handed over from the command palette

  const save = async () => {
    if (!rec || !platform) return;
    try {
      await send(`/api/channels/${platform}/records`, 'POST', { type: 'pipeline', data: { ...rec, value: rec.value ?? null } });
      setSaved(`Saved to ${catalog.platforms.find((p) => p.id === platform)?.label}.`); setDraft(null); setText('');
      onSaved(platform);
    } catch (e) { setError((e as Error).message); }
  };

  return (
    <Card>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); parse(text); }}>
        <div className="relative flex-1">
          <Sparkles className="h-4 w-4 text-indigo-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input className={`${field} pl-9`} aria-label="Log in plain words" autoComplete="off" value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Log in plain words: applied to react dashboard on upwork $1200 follow up friday" />
        </div>
        <Button type="submit" variant="primary" disabled={!text.trim()}>Read it</Button>
      </form>
      <ErrorBanner message={error} />
      {saved && <p role="status" className="text-xs text-emerald-300 mt-2">{saved}</p>}
      {draft && rec && (
        <div className="mt-3 rounded-xl border border-slate-800 p-3 space-y-3" role="group" aria-label="Draft to confirm">
          <div className="flex flex-wrap gap-1.5">{draft.understood.map((u) => <Badge key={u} tone="accent">{u}</Badge>)}{draft.notes.map((n) => <Badge key={n} tone="warn">{n}</Badge>)}</div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
            <label className="text-xs text-slate-400 space-y-1">Platform
              <select className={field} value={platform} onChange={(e) => setPlatform(e.target.value)}><option value="">Choose…</option>{catalog.platforms.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
            <label className="text-xs text-slate-400 space-y-1 lg:col-span-2">Title<input className={field} value={rec.title ?? ''} onChange={(e) => setRec({ ...rec, title: e.target.value || null })} /></label>
            <label className="text-xs text-slate-400 space-y-1">Status
              <select className={field} value={rec.status} onChange={(e) => setRec({ ...rec, status: e.target.value })}>{catalog.statuses.map((s) => <option key={s} value={s}>{STATUS_LABEL[s] ?? s}</option>)}</select></label>
            <label className="text-xs text-slate-400 space-y-1">Value $<input className={field} inputMode="decimal" value={rec.value ?? ''} onChange={(e) => setRec({ ...rec, value: e.target.value === '' ? null : Number(e.target.value) })} /></label>
            <label className="text-xs text-slate-400 space-y-1">Follow up<input className={field} type="date" value={rec.next_followup ?? ''} onChange={(e) => setRec({ ...rec, next_followup: e.target.value || null })} /></label>
          </div>
          {(!platform || !rec.title) && <p className="text-xs text-amber-300">Still needed: {[!platform && 'the platform', !rec.title && 'a title'].filter(Boolean).join(' and ')}. Nothing is guessed.</p>}
          <div className="flex gap-2"><Button variant="primary" onClick={save} disabled={!platform || !rec.title}>Save to pipeline</Button><Button variant="ghost" onClick={() => setDraft(null)}>Discard</Button></div>
        </div>)}
    </Card>
  );
};
