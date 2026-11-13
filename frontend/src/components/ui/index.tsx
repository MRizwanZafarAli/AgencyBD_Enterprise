import { useEffect, useId, useRef, useState } from 'react';
import type { FC, ReactNode, ButtonHTMLAttributes } from 'react';
import { Search, X } from 'lucide-react';
import { apiFetch } from '../../lib/api';

/* Small design-system layer. Semantic slate classes flip automatically between the dark and light themes (see index.css). */

export const field =
  'w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500';

type Tone = 'neutral' | 'good' | 'warn' | 'bad' | 'info' | 'accent';
const TONES: Record<Tone, string> = {
  neutral: 'bg-slate-800/70 text-slate-300 border-slate-700',
  good: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  warn: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  bad: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  info: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  accent: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
};

export const Badge: FC<{ tone?: Tone; children: ReactNode; title?: string }> = ({ tone = 'neutral', children, title }) => (
  <span title={title} className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${TONES[tone]}`}>{children}</span>
);

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-indigo-600 hover:bg-indigo-500 text-white',
  secondary: 'glass-btn text-slate-200',
  ghost: 'text-slate-300 hover:text-white hover:bg-slate-800/60',
  danger: 'bg-rose-600 hover:bg-rose-500 text-white',
};

export const Button: FC<ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; small?: boolean }> = ({
  variant = 'secondary', small, className = '', children, ...rest
}) => (
  <button
    {...rest}
    className={`inline-flex items-center justify-center gap-1.5 rounded-full font-medium transition-all duration-150 cursor-pointer hover:shadow-sm active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed ${
      small ? 'text-xs px-3 py-1.5' : 'text-sm px-4 py-2'
    } ${VARIANTS[variant]} ${className}`}
  >
    {children}
  </button>
);

export const Card: FC<{ children: ReactNode; className?: string }> = ({ children, className = '' }) => (
  <section className={`bento-tile rounded-3xl p-4 sm:p-6 ${className}`}>{children}</section>
);

export const PageHeader: FC<{ title: string; subtitle?: string; actions?: ReactNode }> = ({ title, subtitle, actions }) => (
  <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
    <div>
      <span className="eyebrow mb-3" aria-hidden="true">AgencyBD</span>
      <h1 className="text-3xl sm:text-4xl font-semibold text-white tracking-tight leading-[1.1]">{title}</h1>
      {subtitle && <p className="text-sm sm:text-base text-slate-400 mt-2 max-w-2xl">{subtitle}</p>}
    </div>
    {actions && <div className="flex gap-2">{actions}</div>}
  </div>
);

/** Counts up to a whole number once, then stays put. Shows the final value at once for people who asked for less motion. */
export const CountUp: FC<{ to: number }> = ({ to }) => {
  const reduce = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const [n, setN] = useState(0);
  useEffect(() => {
    if (reduce) return;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 900);
      setN(Math.round(to * (1 - Math.pow(1 - t, 3))));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, reduce]);
  return <>{(reduce ? to : n).toLocaleString()}</>;
};

export const Stat: FC<{ label: string; value: ReactNode; hint?: string }> = ({ label, value, hint }) => (
  <div className="bento-tile rounded-3xl p-5">
    <div className="text-xs font-medium text-slate-400">{label}</div>
    <div className="text-3xl font-semibold text-white tabular mt-1.5 tracking-tight">{typeof value === 'number' && Number.isInteger(value) ? <CountUp to={value} /> : value}</div>
    {hint && <div className="text-[11px] text-slate-500 mt-1">{hint}</div>}
  </div>
);

export const EmptyState: FC<{ title: string; hint?: string; action?: ReactNode }> = ({ title, hint, action }) => (
  <div className="text-center py-10 px-4">
    <div className="text-sm font-medium text-slate-200">{title}</div>
    {hint && <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">{hint}</p>}
    {action && <div className="mt-3">{action}</div>}
  </div>
);

export const Skeletons: FC<{ rows?: number }> = ({ rows = 4 }) => (
  <div className="space-y-3" aria-busy="true" aria-label="Loading">
    {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton h-16" />)}
  </div>
);

export const Tabs: FC<{ tabs: Array<{ id: string; label: string; count?: number }>; active: string; onChange: (id: string) => void }> = ({ tabs, active, onChange }) => (
  <div role="tablist" className="inline-flex flex-wrap gap-1 p-1 mb-6 rounded-full border border-slate-800 bg-slate-950">
    {tabs.map((t) => (
      <button
        key={t.id}
        role="tab"
        aria-selected={active === t.id}
        onClick={() => onChange(t.id)}
        className={`px-4 py-1.5 text-sm rounded-full cursor-pointer transition-all duration-200 ${active === t.id ? 'bg-indigo-600 text-white font-medium shadow-sm' : 'text-slate-400 hover:text-white hover:bg-slate-800/70 hover:shadow-inner'}`}
      >
        {t.label}{t.count !== undefined && <span className="ml-1.5 text-[11px] opacity-80 tabular">{t.count}</span>}
      </button>
    ))}
  </div>
);

export const Pager: FC<{ page: number; pageSize: number; total: number; onPage: (p: number) => void }> = ({ page, pageSize, total, onPage }) => {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <div className="flex items-center justify-between text-xs text-slate-400 pt-3">
      <span className="tabular">{page * pageSize + 1}-{Math.min(total, (page + 1) * pageSize)} of {total}</span>
      <div className="flex gap-2">
        <Button small disabled={page === 0} onClick={() => onPage(page - 1)}>Previous</Button>
        <Button small disabled={page >= pages - 1} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </div>
  );
};

/** Right-hand detail drawer. Closes on Escape or backdrop click, restores focus, and is announced as a dialog. */
export const Drawer: FC<{ open: boolean; title: string; onClose: () => void; children: ReactNode; wide?: boolean }> = ({ open, title, onClose, children, wide }) => {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      previous?.focus?.();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 scrim" onClick={onClose} />
      <div ref={panel} tabIndex={-1} className={`relative h-full w-full ${wide ? 'max-w-3xl' : 'max-w-xl'} glass-sheet border-l border-slate-800 overflow-y-auto animate-fade-up focus:outline-none`}>
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-3 border-b border-slate-800 glass-sheet-head">
          <h2 className="text-sm font-semibold text-white truncate">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
};

export const ScoreBar: FC<{ value: number }> = ({ value }) => (
  <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden" role="img" aria-label={`score ${Math.round(value)} of 100`}>
    <div className={`h-full rounded-full bar-grow ${value >= 60 ? 'bg-emerald-500' : value >= 35 ? 'bg-indigo-500' : 'bg-slate-600'}`} style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
  </div>
);

/** Search box: magnifier, clear button, Escape clears. Always give it a label for screen readers. */
export const SearchInput: FC<{ value: string; onChange: (v: string) => void; label: string; placeholder?: string; className?: string }> = ({ value, onChange, label, placeholder, className = '' }) => (
  <div className={`relative ${className}`}>
    <Search className="h-4 w-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" aria-hidden="true" />
    <input type="search" className={`${field} pl-9 pr-8`} aria-label={label} placeholder={placeholder ?? label} value={value} autoComplete="off" spellCheck={false}
      onChange={(e) => onChange(e.target.value)} onKeyDown={(e) => { if (e.key === 'Escape' && value) { e.preventDefault(); onChange(''); } }} />
    {value && <button type="button" aria-label={`Clear ${label.toLowerCase()}`} onClick={() => onChange('')} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-500 hover:text-slate-200"><X className="h-3.5 w-3.5" /></button>}
  </div>
);

export type SuggestKind = 'business' | 'skill' | 'city';
const titleCase = (s: string) => s.replace(/\b\w/g, (c) => c.toUpperCase());

/** Text field with suggestions. `kinds` asks the typo-tolerant search vocabulary (business types, skills, cities); `options` filters a list you pass in.
 *  Arrow keys move, Enter or Tab accepts, Escape closes. You can always type something that is not suggested. */
export const SuggestInput: FC<{
  value: string; onChange: (v: string) => void; label?: string; placeholder?: string; kinds?: SuggestKind[]; options?: string[]; required?: boolean; minLength?: number; className?: string;
}> = ({ value, onChange, label, placeholder, kinds, options, required, minLength, className = '' }) => {
  const id = useId();
  const [items, setItems] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const focused = useRef(false);
  const [tick, setTick] = useState(0);
  const kindKey = kinds?.join(',') ?? '';

  useEffect(() => {
    if (!focused.current) return;
    if (options || !kindKey) return;
    let live = true;
    const t = window.setTimeout(async () => {
      const res = await apiFetch(`/api/search/suggest?q=${encodeURIComponent(value)}&kinds=${kindKey}`).catch(() => null);
      if (!live || !res || !res.ok) return;
      const body = await res.json();
      setItems((body.suggestions as Array<{ label: string; type: string }>).map((s) => (s.type === 'city' ? titleCase(s.label) : s.label)).filter((l) => l.toLowerCase() !== value.trim().toLowerCase()));
    }, 120);
    return () => { live = false; window.clearTimeout(t); };
  }, [value, kindKey, options, tick]);

  const pick = (v: string) => { onChange(v); setOpen(false); setActive(-1); };
  const q = value.trim().toLowerCase();
  const list = options ? options.filter((o) => o.toLowerCase().includes(q) && o.toLowerCase() !== q).slice(0, 8) : items;
  const shown = open ? list : [];
  return (
    <div className={`relative ${className}`}>
      <input className={field} value={value} required={required} minLength={minLength} placeholder={placeholder} aria-label={label} autoComplete="off" spellCheck={false}
        role="combobox" aria-expanded={shown.length > 0} aria-controls={`${id}-list`} aria-autocomplete="list" aria-activedescendant={active >= 0 ? `${id}-${active}` : undefined}
        onChange={(e) => { onChange(e.target.value); setOpen(true); setActive(-1); }}
        onFocus={() => { focused.current = true; setOpen(true); setTick((t) => t + 1); }}
        onBlur={() => { focused.current = false; window.setTimeout(() => setOpen(false), 120); }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, list.length - 1)); }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          else if ((e.key === 'Enter' || e.key === 'Tab') && shown.length > 0 && active >= 0) { if (e.key === 'Enter') e.preventDefault(); pick(list[active]); }
          else if (e.key === 'Escape' && shown.length > 0) { e.preventDefault(); e.stopPropagation(); setOpen(false); }
        }} />
      {shown.length > 0 && (
        <ul id={`${id}-list`} role="listbox" className="absolute z-30 left-0 right-0 mt-1 max-h-60 overflow-auto rounded-xl border border-slate-700 bg-slate-900 shadow-xl py-1">
          {shown.map((s, i) => (
            <li key={s} id={`${id}-${i}`} role="option" aria-selected={i === active} onMouseDown={(e) => { e.preventDefault(); pick(s); }} onMouseEnter={() => setActive(i)}
              className={`px-3 py-1.5 text-sm cursor-pointer ${i === active ? 'bg-indigo-600/20 text-white' : 'text-slate-200'}`}>{s}</li>))}
        </ul>)}
    </div>
  );
};
