import { useEffect, useRef } from 'react';
import type { FC } from 'react';
import { X } from 'lucide-react';
import { SHORTCUTS } from '../../lib/useShortcuts';

export const ShortcutsHelp: FC<{ open: boolean; onClose: () => void }> = ({ open, onClose }) => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[65] flex items-center justify-center px-4" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
      <div className="absolute inset-0 scrim" onClick={onClose} />
      <div ref={ref} tabIndex={-1} className="relative w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl p-5 animate-pop focus:outline-none">
        <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-semibold text-white">Keyboard shortcuts</h2><button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-white"><X className="h-4 w-4" /></button></div>
        <ul className="divide-y divide-slate-800">{SHORTCUTS.map((s) => <li key={s.keys} className="flex items-center justify-between py-2 text-sm text-slate-300"><span>{s.label}</span><kbd className="font-mono text-xs border border-slate-700 rounded px-1.5 py-0.5 text-slate-400">{s.keys}</kbd></li>)}</ul>
      </div>
    </div>
  );
};
