import { useEffect, useMemo, useRef, useState } from 'react';
import type { FC } from 'react';
import { Search } from 'lucide-react';
import type { TabType } from '../../types';

const COMMANDS: Array<{ id: TabType; label: string; hint: string }> = [
  { id: 'hunt', label: 'Local Client Hunt', hint: 'find businesses by city' },
  { id: 'radar', label: 'Opportunity Radar', hint: 'jobs, tenders, bounties' },
  { id: 'overview', label: 'Mission Control', hint: 'setup, KPIs, digest' },
  { id: 'doctor', label: 'Website Doctor & Brief', hint: 'audit a company' },
  { id: 'portfolio', label: 'Portfolio & Proof', hint: 'case studies for proposals' },
  { id: 'sequences', label: 'Sequences', hint: 'outbound email' },
  { id: 'governance', label: 'Autonomy Policy & Learning', hint: 'approvals, mailboxes' },
  { id: 'suppression', label: 'CAN-SPAM Vault', hint: 'unsubscribe list' },
  { id: 'dns', label: 'DNS Fleet Studio', hint: 'SPF, DKIM, DMARC' },
  { id: 'rbac', label: 'Enterprise RBAC', hint: 'keys and roles' },
];

/** ⌘K / Ctrl+K quick navigation. */
export const CommandPalette: FC<{ onNavigate: (tab: TabType) => void }> = ({ onNavigate }) => {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [cursor, setCursor] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
        setQ('');
        setCursor(0);
      } else if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  const matches = useMemo(
    () => COMMANDS.filter((c) => `${c.label} ${c.hint}`.toLowerCase().includes(q.toLowerCase())),
    [q],
  );
  const go = (tab: TabType) => {
    onNavigate(tab);
    setOpen(false);
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[15vh] px-4" role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <div className="relative w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden animate-pop">
        <div className="flex items-center gap-2 px-4 border-b border-slate-800">
          <Search className="h-4 w-4 text-slate-500" />
          <input
            ref={input}
            value={q}
            onChange={(e) => { setQ(e.target.value); setCursor(0); }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setCursor((c) => Math.min(c + 1, matches.length - 1)); }
              if (e.key === 'ArrowUp') { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
              if (e.key === 'Enter' && matches[cursor]) go(matches[cursor].id);
            }}
            placeholder="Go to…"
            className="flex-1 bg-transparent py-3.5 text-sm text-white placeholder:text-slate-500 focus:outline-none"
          />
          <kbd className="text-[10px] font-mono text-slate-500 border border-slate-700 rounded px-1.5 py-0.5">esc</kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto p-1.5">
          {matches.length === 0 && <li className="px-3 py-6 text-center text-xs text-slate-500">Nothing matches.</li>}
          {matches.map((c, i) => (
            <li key={c.id}>
              <button
                onClick={() => go(c.id)}
                onMouseEnter={() => setCursor(i)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm ${i === cursor ? 'bg-indigo-600/20 text-white' : 'text-slate-300'}`}
              >
                <span>{c.label}</span>
                <span className="text-xs text-slate-500">{c.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
