import { useEffect, useRef, useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Sparkles, ArrowRight } from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { apiFetch } from '../../lib/api';
import { send, useApi } from '../../lib/hooks';

export interface SearchRun { kind: 'local' | 'jobs' | 'tenders' | null; category?: string; city?: string; only_gaps?: boolean; q?: string; min_budget?: number | null; max_budget?: number | null; remote?: boolean }
interface Parsed {
  intent: 'local' | 'jobs' | 'tenders' | null; explanation: string; corrections: Array<{ from: string; to: string }>; needs_clarification: boolean; clarification: string | null;
  run: SearchRun; alternatives: Array<{ kind: 'local' | 'jobs' | 'tenders'; label: string }>; raw: string; business: string[]; skills: string[]; location: string | null;
}
interface Suggestion { type: string; label: string; insert: string }
interface Catalog { business: string[]; skills: string[]; cities: string[] }

const RECENT_KEY = 'agencybd.search.recent';
const loadRecent = (): string[] => { try { const v = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]'); return Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(0, 6) : []; } catch { return []; } };
const saveRecent = (list: string[]) => { try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch { /* recent searches just will not persist */ } };

const EXAMPLES = ['dentists in Leeds without a website', 'react developer remote over $5k', 'plumbers in Manchester', 'government tenders software', 'python freelance jobs', 'restaurants in Dubai with a slow website'];

export const SmartSearch: FC<{ onRun: (run: SearchRun) => void; seed?: { text: string; n: number } | null }> = ({ onRun, seed }) => {
  const [text, setText] = useState('');
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [recent, setRecent] = useState<string[]>(loadRecent);
  const [active, setActive] = useState(-1);
  const [lastSeed, setLastSeed] = useState(0);
  const [browse, setBrowse] = useState<'business' | 'skills' | null>(null);
  const catalog = useApi<Catalog>(browse ? '/api/search/catalog' : null);
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);

  const onChange = (value: string) => {
    setText(value);
    setParsed(null);
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      if (!value.trim()) { setSuggestions([]); return; }
      const res = await apiFetch(`/api/search/suggest?q=${encodeURIComponent(value)}`);
      if (res.ok) setSuggestions((await res.json()).suggestions);
    }, 150);
  };

  const submit = async (e?: FormEvent, value = text) => {
    e?.preventDefault();
    if (!value.trim()) return;
    setBusy(true); setError(''); setSuggestions([]);
    try {
      const p = await send<Parsed>('/api/search/parse', 'POST', { q: value });
      setParsed(p);
      if (p.intent) { const next = [value.trim(), ...recent.filter((r) => r.toLowerCase() !== value.trim().toLowerCase())].slice(0, 6); setRecent(next); saveRecent(next); }
      if (p.intent && !p.needs_clarification) onRun(p.run);          // clear enough: run it straight away
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not understand that'); }
    finally { setBusy(false); }
  };

  const pick = (s: Suggestion) => { setText(s.insert + ' '); setSuggestions([]); setActive(-1); };
  if (seed && seed.n !== lastSeed) { setLastSeed(seed.n); setText(seed.text); setTimeout(() => submit(undefined, seed.text), 0); }
  const insertWord = (w: string) => { setText((t) => `${t.trim()} ${w}`.trim() + ' '); setParsed(null); };

  return (
    <Card className="space-y-3">
      <form onSubmit={submit} className="relative">
        <label htmlFor="smart-search" className="sr-only">Search for clients, businesses, jobs or tenders</label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Sparkles className="h-4 w-4 text-indigo-400 absolute left-3 top-3" />
            <input id="smart-search" className={`${field} pl-9`} autoComplete="off" spellCheck={false} placeholder="Describe who or what you want: dentists in Leeds with no website, react developer remote over $5k…"
              value={text} onChange={(e) => { onChange(e.target.value); setActive(-1); }} role="combobox" aria-expanded={suggestions.length > 0} aria-controls="smart-suggestions" aria-activedescendant={active >= 0 ? `smart-opt-${active}` : undefined}
              onKeyDown={(e) => {
                if (!suggestions.length) return;
                if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, suggestions.length - 1)); }
                else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
                else if ((e.key === 'Enter' || e.key === 'Tab') && active >= 0) { e.preventDefault(); pick(suggestions[active]); }
                else if (e.key === 'Escape') { e.stopPropagation(); setSuggestions([]); setActive(-1); }
              }} />
            {suggestions.length > 0 && (
              <ul id="smart-suggestions" role="listbox" className="absolute z-20 left-0 right-0 mt-1 rounded-xl border border-slate-700 bg-slate-900 shadow-xl overflow-hidden">
                {suggestions.map((s, i) => (
                  <li key={`${s.type}-${s.label}`} id={`smart-opt-${i}`} role="option" aria-selected={i === active} className={i === active ? 'bg-indigo-500/10' : ''}>
                    <button type="button" onClick={() => pick(s)} className="w-full flex items-center justify-between px-3 py-2 text-sm text-slate-200 hover:bg-indigo-500/10 text-left">
                      <span>{s.label}</span><Badge tone={s.type === 'business' ? 'good' : s.type === 'skill' ? 'accent' : 'info'}>{s.type === 'business' ? 'business' : s.type === 'skill' ? 'skill' : 'place'}</Badge>
                    </button>
                  </li>))}
              </ul>)}
          </div>
          <Button variant="primary" disabled={busy || !text.trim()}>{busy ? 'Understanding…' : 'Go'}<ArrowRight className="h-4 w-4" /></Button>
        </div>
      </form>
      <ErrorBanner message={error} />

      {parsed && (
        <div className="rounded-xl border border-slate-800 p-3 space-y-2 text-sm animate-fade-up" role="status" aria-live="polite">
          <p className="text-slate-200">{parsed.explanation}</p>
          {parsed.corrections.length > 0 && <div className="flex flex-wrap gap-1.5">{parsed.corrections.map((c) => <Badge key={c.from} tone="warn">Did you mean {c.to}? (typed {c.from})</Badge>)}</div>}
          {parsed.clarification && <p className="text-xs text-amber-300">{parsed.clarification}</p>}
          <div className="flex flex-wrap gap-2">
            {parsed.intent && parsed.needs_clarification && parsed.run && <Button small variant="primary" onClick={() => onRun(parsed.run)}>Search anyway</Button>}
            {parsed.alternatives.map((a) => <Button key={a.kind} small onClick={() => onRun({ ...parsed.run, kind: a.kind, q: parsed.run.q ?? [...parsed.skills, ...parsed.business].join(' ') })}>{a.label}</Button>)}
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="text-slate-500">Try:</span>
        {EXAMPLES.map((ex) => <button key={ex} type="button" onClick={() => { setText(ex); submit(undefined, ex); }} className="px-2 py-1 rounded-md border border-slate-800 text-slate-400 hover:text-white hover:border-slate-600">{ex}</button>)}
        <span className="mx-1 text-slate-700">|</span>
        <button type="button" onClick={() => setBrowse(browse === 'business' ? null : 'business')} className="text-indigo-300 hover:text-indigo-200 underline">Browse business types</button>
        <button type="button" onClick={() => setBrowse(browse === 'skills' ? null : 'skills')} className="text-indigo-300 hover:text-indigo-200 underline">Browse skills</button>
      </div>
      {recent.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs" aria-label="Recent searches">
          <span className="text-slate-500">Recent:</span>
          {recent.map((r) => <button key={r} type="button" onClick={() => { setText(r); submit(undefined, r); }} className="px-2 py-1 rounded-md border border-slate-800 text-slate-300 hover:text-white hover:border-slate-600">{r}</button>)}
          <button type="button" onClick={() => { setRecent([]); saveRecent([]); }} className="text-slate-500 hover:text-slate-300 underline">Clear</button>
        </div>)}
      {browse && catalog.data && (
        <div className="flex flex-wrap gap-1.5 max-h-40 overflow-auto rounded-lg bg-slate-900/60 p-2">
          {(browse === 'business' ? catalog.data.business : catalog.data.skills).map((w) => <button key={w} type="button" onClick={() => insertWord(w)} className="px-2 py-1 rounded-md border border-slate-800 text-xs text-slate-300 hover:border-indigo-500">{w}</button>)}
        </div>)}
    </Card>
  );
};
