import { useState } from 'react';
import type { FC } from 'react';
import { Moon, Palette, Sun } from 'lucide-react';
import { Card } from '../ui';
import { SHORTCUTS } from '../../lib/useShortcuts';
import { useTheme } from '../../lib/useTheme';
import { applyWorkspaceAccent, type AccentPreset } from '../../lib/ThemeProvider';

const media = (q: string) => typeof window !== 'undefined' && !!window.matchMedia?.(q).matches;

const ACCENT_PRESETS: Array<{ id: Exclude<AccentPreset, 'custom'>; label: string; hint: string; swatch: string }> = [
  { id: 'emerald', label: 'Emerald Executive', hint: 'Deep Emerald Teal primary (Default)', swatch: '#0f766e' },
  { id: 'indigo', label: 'Midnight Indigo', hint: 'Crisp executive indigo', swatch: '#4338ca' },
  { id: 'cobalt', label: 'Slate Cobalt', hint: 'Classic B2B cobalt blue', swatch: '#1d4ed8' },
];

export const Preferences: FC = () => {
  const { theme, setTheme } = useTheme();
  const [preset, setPreset] = useState<AccentPreset>(() => (localStorage.getItem('agencybd_accent_preset') as AccentPreset) || 'emerald');
  const [brandHex, setBrandHex] = useState(() => localStorage.getItem('agencybd_brand_hex') || '#0f766e');
  const [density, setDensity] = useState<'comfortable' | 'compact'>(() =>
    typeof document !== 'undefined' && document.documentElement.classList.contains('density-compact') ? 'compact' : 'comfortable'
  );

  const selectAccent = (next: AccentPreset, hex = brandHex) => {
    setPreset(next);
    localStorage.setItem('agencybd_accent_preset', next);
    localStorage.setItem('agencybd_brand_hex', hex);
    applyWorkspaceAccent(next, hex, theme);
  };

  const toggleDensity = (next: 'comfortable' | 'compact') => {
    setDensity(next);
    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('density-compact', next === 'compact');
    }
    try { localStorage.setItem('agencybd.density', next); } catch { /* ignore */ }
  };

  const reducedMotion = media('(prefers-reduced-motion: reduce)');
  const reducedTransparency = media('(prefers-reduced-transparency: reduce)');
  const options = [
    { id: 'light' as const, label: 'Light Mode', hint: 'Soft off-white canvas, pure white cards & charcoal ink', icon: Sun },
    { id: 'dark' as const, label: 'Obsidian Dark Mode', hint: 'Linear/Raycast dark slate where Emerald Teal pops', icon: Moon },
  ];

  return (
    <div className="space-y-5">
      <Card>
        <h2 className="text-sm font-semibold text-white mb-3">Workspace Mode</h2>
        <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-2 max-w-2xl">
          {options.map((o) => (
            <button key={o.id} role="radio" aria-checked={theme === o.id} onClick={() => setTheme(o.id)}
              className={`text-left rounded-xl border p-3 flex items-center gap-3 transition-colors ${theme === o.id ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-700 hover:border-slate-500'}`}>
              <o.icon className="h-5 w-5 text-indigo-400 shrink-0" aria-hidden="true" />
              <span>
                <span className="block text-sm font-medium text-white">{o.label}</span>
                <span className="block text-xs text-slate-400">{o.hint}</span>
              </span>
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-3">
          Frosted-glass surfaces become solid when your system asks for reduced transparency ({reducedTransparency ? 'on' : 'off'}), and animations stop when it asks for reduced motion ({reducedMotion ? 'on' : 'off'}).
        </p>
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-1 flex items-center gap-2">
          <Palette className="h-4 w-4 text-indigo-400" />
          Curated Enterprise Themes &amp; White-Label Accent
        </h2>
        <p className="text-xs text-slate-400 mb-3">Choose a curated preset or enter your agency&apos;s brand hex color.</p>
        <div className="grid gap-3 sm:grid-cols-3 max-w-3xl mb-3">
          {ACCENT_PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => selectAccent(p.id)}
              className={`text-left rounded-xl border p-3 flex items-center gap-3 transition ${preset === p.id ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-700 hover:border-slate-500'}`}
            >
              <span className="h-6 w-6 rounded-full shrink-0 border border-white/20" style={{ backgroundColor: p.swatch }} />
              <span>
                <span className="block text-xs font-semibold text-white">{p.label}</span>
                <span className="block text-[11px] text-slate-400">{p.hint}</span>
              </span>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2.5 pt-2 border-t border-slate-800/80">
          <label className="text-xs text-slate-300 font-medium flex items-center gap-2">
            White-Label Brand Hex:
            <input
              type="color"
              value={/^#[0-9a-fA-F]{6}$/.test(brandHex) ? brandHex : '#0f766e'}
              onChange={(e) => { setBrandHex(e.target.value); selectAccent('custom', e.target.value); }}
              className="h-7 w-9 rounded cursor-pointer border border-slate-700 bg-transparent"
            />
          </label>
          <input
            type="text"
            value={brandHex}
            onChange={(e) => {
              const v = e.target.value;
              setBrandHex(v);
              if (/^#[0-9a-fA-F]{6}$/.test(v)) selectAccent('custom', v);
            }}
            placeholder="#0f766e"
            className="w-28 bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-xs font-mono text-white"
          />
          {preset === 'custom' && <span className="text-[11px] text-emerald-300 font-medium">Custom brand color active</span>}
        </div>
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-3">Workspace Density</h2>
        <div role="radiogroup" aria-label="Workspace Density" className="grid gap-3 sm:grid-cols-2 max-w-xl">
          {([
            { id: 'comfortable', label: 'Comfortable', hint: 'Generous breathing room and calm spacing' },
            { id: 'compact', label: 'Compact (Power User)', hint: 'Higher data density for rapid triage' },
          ] as const).map((d) => (
            <button key={d.id} role="radio" aria-checked={density === d.id} onClick={() => toggleDensity(d.id)}
              className={`text-left rounded-xl border p-3 transition-colors ${density === d.id ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-700 hover:border-slate-500'}`}>
              <span className="block text-sm font-medium text-white">{d.label}</span>
              <span className="block text-xs text-slate-400">{d.hint}</span>
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-3">Keyboard shortcuts</h2>
        <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2 text-sm">
          {SHORTCUTS.map((s) => (
            <div key={s.keys} className="flex items-center justify-between gap-3 border-b border-slate-800/70 py-1.5">
              <dt className="text-slate-300">{s.label}</dt>
              <dd><kbd className="font-mono text-xs text-slate-200 border border-slate-700 rounded px-1.5 py-0.5">{s.keys}</kbd></dd>
            </div>
          ))}
        </dl>
      </Card>
    </div>
  );
};
