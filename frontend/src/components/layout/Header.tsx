import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { Shield, Activity, Menu, X, Cpu, Command } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import type { Me } from '../../lib/api';

interface HeaderProps {
  circuitBreakerTripped: boolean;
  onToggleHalt: () => void;
  mobileMenuOpen: boolean;
  setMobileMenuOpen: (o: boolean) => void;
  identity?: Me;
  onSignOut?: () => void;
}

export const Header: FC<HeaderProps> = ({
  circuitBreakerTripped,
  onToggleHalt,
  mobileMenuOpen,
  setMobileMenuOpen,
  identity,
  onSignOut
}) => {
  const [api, setApi] = useState<{ ok: boolean; ms: number | null }>({ ok: false, ms: null });
  useEffect(() => {
    let active = true;
    const ping = async () => {
      const t0 = performance.now();
      try {
        const r = await apiFetch('/healthz/live', { cache: 'no-store' });
        if (active) setApi({ ok: r.ok, ms: Math.round(performance.now() - t0) });
      } catch {
        if (active) setApi({ ok: false, ms: null });
      }
    };
    ping();
    const id = window.setInterval(ping, 15000);
    return () => { active = false; window.clearInterval(id); };
  }, []);

  return (
    <header className="sticky top-0 z-40 h-16 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl px-4 sm:px-6 flex items-center justify-between transition-all">
      {/* Left: Mobile hamburger + Brand */}
      <div className="flex items-center space-x-3 sm:space-x-4">
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="lg:hidden p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white focus:outline-none"
          aria-label="Toggle navigation menu"
        >
          {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>

        <div className="flex items-center space-x-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shadow-lg shadow-indigo-500/25 flex items-center justify-center">
            <Cpu className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-white tracking-tight text-sm sm:text-base">AgencyBD</span>
              <span className="hidden sm:inline-flex px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                ENTERPRISE
              </span>
            </div>
            <div className="text-[10px] text-slate-400 hidden sm:block -mt-0.5 font-mono">Client and project hunting</div>
          </div>
        </div>
      </div>

      {/* Center: live API status (measured from /healthz/live) */}
      <div className="hidden md:flex items-center space-x-4 px-3 py-1.5 rounded-full bg-slate-900/60 border border-slate-800/70 text-xs font-mono">
        <div className={`flex items-center space-x-1.5 ${api.ok ? 'text-emerald-400' : 'text-rose-400'}`}>
          <span className="relative flex h-2 w-2">
            {api.ok && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${api.ok ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
          </span>
          <span>{api.ok ? 'API online' : 'API unreachable'}</span>
        </div>
        {api.ms !== null && (
          <>
            <span className="text-slate-700">|</span>
            <div className="text-slate-400 flex items-center space-x-1 tabular">
              <Activity className="h-3.5 w-3.5 text-cyan-400" />
              <span>{api.ms} ms</span>
            </div>
          </>
        )}
        <span className="text-slate-700">|</span>
        <div className="text-slate-500 flex items-center space-x-1">
          <Command className="h-3 w-3" /><span>K to jump</span>
        </div>
      </div>

      {/* Right: Tenant Switcher + Circuit Breaker */}
      <div className="flex items-center space-x-2 sm:space-x-3">
        {/* Global Kill Switch */}
        <button
          onClick={onToggleHalt}
          className={`flex items-center space-x-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
            circuitBreakerTripped
              ? 'bg-red-500/20 border-red-500/50 text-red-300 shadow-lg shadow-red-500/20 animate-pulse'
              : 'bg-slate-900 border-slate-700 hover:border-slate-600 text-slate-300'
          }`}
          title={circuitBreakerTripped ? "Outbound is halted. Click to resume sending." : "Emergency stop: halts every outbound send for this workspace"}
        >
          <Shield className={`h-3.5 w-3.5 ${circuitBreakerTripped ? 'text-red-400' : 'text-slate-400'}`} />
          <span className="hidden sm:inline">{circuitBreakerTripped ? 'HALTED' : 'KILL SWITCH'}</span>
        </button>

        {identity && (
          <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
            <span className="hidden lg:inline" title={`${identity.user_id} · ${identity.auth_method}`}>
              {identity.org_id} · {identity.role}
            </span>
            {onSignOut && (
              <button
                onClick={onSignOut}
                className="px-2.5 py-1.5 rounded-lg border border-slate-700 hover:border-slate-500 text-slate-300"
              >
                Sign out
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
};
