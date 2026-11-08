import type { FC } from 'react';
import { Moon, Sun } from 'lucide-react';
import { Card } from '../ui';
import { SHORTCUTS } from '../../lib/useShortcuts';
import { useTheme } from '../../lib/useTheme';

const media = (q: string) => typeof window !== 'undefined' && !!window.matchMedia?.(q).matches;

export const Preferences: FC = () => {
  const { theme, setTheme } = useTheme();
  const reducedMotion = media('(prefers-reduced-motion: reduce)');
  const reducedTransparency = media('(prefers-reduced-transparency: reduce)');
  const options = [{ id: 'light' as const, label: 'Light', hint: 'Warm paper, ink and teal', icon: Sun }, { id: 'dark' as const, label: 'Dark', hint: 'Zinc ink and bright teal', icon: Moon }];
  return (
    <div className="space-y-5">
      <Card>
        <h2 className="text-sm font-semibold text-white mb-3">Theme</h2>
        <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-2 max-w-xl">
          {options.map((o) => (
            <button key={o.id} role="radio" aria-checked={theme === o.id} onClick={() => setTheme(o.id)}
              className={`text-left rounded-xl border p-3 flex items-center gap-3 transition-colors ${theme === o.id ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-700 hover:border-slate-500'}`}>
              <o.icon className="h-5 w-5 text-indigo-400" aria-hidden="true" /><span><span className="block text-sm font-medium text-white">{o.label}</span><span className="block text-xs text-slate-400">{o.hint}</span></span>
            </button>))}
        </div>
        <p className="text-xs text-slate-400 mt-3">Your choice is remembered in this browser. Frosted-glass surfaces become solid when your system asks for reduced transparency ({reducedTransparency ? 'currently on' : 'currently off'}), and animations stop when it asks for reduced motion ({reducedMotion ? 'currently on' : 'currently off'}).</p>
      </Card>
      <Card>
        <h2 className="text-sm font-semibold text-white mb-3">Keyboard shortcuts</h2>
        <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2 text-sm">{SHORTCUTS.map((s) => <div key={s.keys} className="flex items-center justify-between gap-3 border-b border-slate-800/70 py-1.5"><dt className="text-slate-300">{s.label}</dt><dd><kbd className="font-mono text-xs text-slate-200 border border-slate-700 rounded px-1.5 py-0.5">{s.keys}</kbd></dd></div>)}</dl>
      </Card>
    </div>
  );
};
