import { useState } from 'react';
import type { FC } from 'react';
import { ChevronDown, ChevronRight, Compass } from 'lucide-react';

export const TabGuide: FC<{
  id: string;
  title: string;
  steps: [string, string, string];
  note?: string;
}> = ({ id, title, steps, note }) => {
  const key = `agencybd.find.guide.${id}`;
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(key) === '1'; } catch { return false; }
  });

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem(key, next ? '1' : '0'); } catch { /* ignore */ }
  };

  return (
    <div className="rounded-2xl border border-indigo-500/25 bg-indigo-950/20 px-4 py-2.5 text-xs">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={toggle}
          className="flex items-center gap-2 font-semibold text-indigo-200 hover:text-white transition text-left"
        >
          <Compass className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
          <span>How {title} works</span>
          {collapsed ? <ChevronRight className="h-3.5 w-3.5 text-slate-400" /> : <ChevronDown className="h-3.5 w-3.5 text-slate-400" />}
        </button>
        {note && <span className="hidden sm:inline text-[11px] text-slate-400">{note}</span>}
      </div>
      {!collapsed && (
        <div className="mt-2 grid gap-2 sm:grid-cols-3 text-[11px] text-slate-300">
          {steps.map((s, idx) => (
            <div key={idx} className="flex items-start gap-2 rounded-xl bg-slate-950/50 border border-slate-800/80 px-3 py-2">
              <span className="h-4 w-4 rounded-full bg-indigo-500/20 text-indigo-300 font-mono text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                {idx + 1}
              </span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
