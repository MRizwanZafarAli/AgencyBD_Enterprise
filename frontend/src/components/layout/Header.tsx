import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { Menu, OctagonX, Play, Sun, Moon, Search, ChevronRight } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { useTheme } from '../../lib/useTheme';

interface HeaderProps { halted: boolean; onToggleHalt: () => void; setMobileMenuOpen: (o: boolean) => void; onPalette: () => void; crumbs: string[] }

export const Header: FC<HeaderProps> = ({ halted, onToggleHalt, setMobileMenuOpen, onPalette, crumbs }) => {
  const { theme, toggleTheme } = useTheme();
  const [api, setApi] = useState<{ ok: boolean; ms: number | null }>({ ok: false, ms: null });

  useEffect(() => {
    let active = true;
    const ping = async () => {
      const t0 = performance.now();
      try {
        const r = await apiFetch('/healthz/live', { cache: 'no-store' });
        if (active) setApi({ ok: r.ok, ms: Math.round(performance.now() - t0) });
      } catch { if (active) setApi({ ok: false, ms: null }); }
    };
    ping();
    const id = window.setInterval(ping, 15000);
    return () => { active = false; window.clearInterval(id); };
  }, []);

  return (
    <header className="sticky top-0 z-30 h-14 border-b border-slate-800/80 px-3 sm:px-6 flex items-center justify-between gap-3" style={{ background: 'var(--app-header-bg)', backdropFilter: 'blur(14px)' }}>
      <div className="flex items-center gap-2 min-w-0">
        <button onClick={() => setMobileMenuOpen(true)} className="lg:hidden p-2 -ml-1 rounded-lg text-slate-300 hover:text-white" aria-label="Open menu"><Menu className="h-5 w-5" /></button>
        <div className="lg:hidden h-7 w-7 rounded-lg bg-indigo-600 text-white text-[11px] font-bold flex items-center justify-center shrink-0">BD</div>
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm min-w-0">
          {crumbs.map((c, i) => (
            <span key={c} className="flex items-center gap-1.5 min-w-0">
              {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-slate-600 shrink-0" />}
              <span className={`truncate ${i === crumbs.length - 1 ? 'text-slate-100 font-medium' : 'text-slate-500 hidden sm:inline'}`}>{c}</span>
            </span>))}
        </nav>
      </div>

      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        <button onClick={onPalette} className="hidden md:flex items-center gap-2 w-56 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/60 text-xs text-slate-500 hover:border-slate-600" aria-label="Search or jump to">
          <Search className="h-3.5 w-3.5" />Search or jump to…<kbd className="ml-auto font-mono border border-slate-700 rounded px-1">⌘K</kbd>
        </button>
        <button onClick={onPalette} className="md:hidden p-2 rounded-lg text-slate-400 hover:text-white" aria-label="Search or jump to"><Search className="h-4 w-4" /></button>
        <span className={`hidden sm:flex items-center gap-1.5 text-xs ${api.ok ? 'text-emerald-400' : 'text-rose-400'}`} role="status">
          <span className={`h-2 w-2 rounded-full ${api.ok ? 'bg-emerald-500' : 'bg-rose-500'}`} />{api.ok ? 'Online' : 'Offline'}{api.ms !== null && <span className="text-slate-500 tabular hidden xl:inline">{api.ms} ms</span>}
        </span>
        <button onClick={onToggleHalt} title={halted ? 'Sending is stopped. Click to resume.' : 'Stop all sending for this workspace, including scheduled emails'}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-semibold ${halted ? 'bg-rose-500/15 border-rose-500/50 text-rose-300' : 'border-slate-700 text-slate-300 hover:border-rose-500/50 hover:text-rose-300'}`}>
          {halted ? <Play className="h-3.5 w-3.5" /> : <OctagonX className="h-3.5 w-3.5" />}<span className="hidden sm:inline">{halted ? 'Resume sending' : 'Stop sending'}</span>
        </button>
        <button onClick={toggleTheme} className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60" aria-label="Toggle light and dark theme">{theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
      </div>
    </header>
  );
};
