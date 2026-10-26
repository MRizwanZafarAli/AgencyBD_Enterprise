import { useEffect, useMemo, useRef, useState } from 'react';
import type { FC } from 'react';
import { Search } from 'lucide-react';
import { COMMANDS } from './commands';
import type { Command } from './commands';

/** ⌘K / Ctrl+K quick navigation. `openSignal` lets the header button open it. */
export const CommandPalette: FC<{ onNavigate: (c: Command) => void; onText: (kind: 'find' | 'quicklog', text: string) => void; openSignal: number }> = ({ onNavigate, onText, openSignal }) => {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [cursor, setCursor] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const [lastSignal, setLastSignal] = useState(openSignal);
  if (openSignal !== lastSignal) { setLastSignal(openSignal); setOpen(true); setQ(''); setCursor(0); }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setOpen((o) => !o); setQ(''); setCursor(0); }
      else if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  useEffect(() => { if (open) input.current?.focus(); }, [open]);

  const matches = useMemo(() => COMMANDS.filter((c) => `${c.label} ${c.hint}`.toLowerCase().includes(q.toLowerCase())), [q]);
  const go = (c: Command) => { onNavigate(c); setOpen(false); };
  const text = q.trim();
  const looksLikeLog = /\b(upwork|fiverr|linkedin|freelancer|peopleperhour|pph|contra|toptal|guru|applied|proposal|bid)\b/i.test(text);
  type Item = { key: string; label: string; hint: string; act: () => void };
  const items: Item[] = [
    ...matches.map((c): Item => ({ key: c.id, label: c.label, hint: c.hint, act: () => go(c) })),
    ...(text.length >= 3 ? [{ key: 'ask-find', label: `Search for “${text}”`, hint: 'understands typos, skills, cities, budgets', act: () => { onText('find', text); setOpen(false); } }] : []),
    ...(text.length >= 3 && looksLikeLog ? [{ key: 'ask-log', label: `Log “${text}” as an application`, hint: 'opens Channels with a draft to confirm', act: () => { onText('quicklog', text); setOpen(false); } }] : []),
  ];
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[15vh] px-4" role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="absolute inset-0 scrim" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden animate-pop">
        <div className="flex items-center gap-2 px-4 border-b border-slate-800">
          <Search className="h-4 w-4 text-slate-500" />
          <input ref={input} value={q} onChange={(e) => { setQ(e.target.value); setCursor(0); }} placeholder="Go to…" aria-label="Go to"
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setCursor((c) => Math.min(c + 1, items.length - 1)); }
              if (e.key === 'ArrowUp') { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
              if (e.key === 'Enter' && items[cursor]) items[cursor].act();
            }} className="flex-1 bg-transparent py-3.5 text-sm text-white placeholder:text-slate-500 focus:outline-none" />
          <kbd className="text-[10px] font-mono text-slate-500 border border-slate-700 rounded px-1.5 py-0.5">esc</kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto p-1.5">
          {items.length === 0 && <li className="px-3 py-6 text-center text-xs text-slate-500">Nothing matches.</li>}
          {items.map((c, i) => (
            <li key={c.key}><button onClick={c.act} onMouseEnter={() => setCursor(i)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm ${i === cursor ? 'bg-indigo-600/20 text-white' : 'text-slate-300'}`}>
              <span className="truncate">{c.label}</span><span className="text-xs text-slate-500 ml-3 shrink-0">{c.hint}</span></button></li>))}
        </ul>
      </div>
    </div>
  );
};
