import { useEffect, useState } from 'react';
import type { FC } from 'react';
import {
  Shield, Activity, Menu, X, Cpu, Command, Sun, Moon,
  Sparkles, Download, RefreshCw, CheckCircle2, GitBranch, AlertCircle, ChevronRight
} from 'lucide-react';
import { apiFetch } from '../../lib/api';
import type { Me } from '../../lib/api';
import type { TabType } from '../../types';
import { useTheme } from '../../lib/useTheme';

interface HeaderProps {
  activeTab?: TabType;
  circuitBreakerTripped: boolean;
  onToggleHalt: () => void;
  mobileMenuOpen: boolean;
  setMobileMenuOpen: (o: boolean) => void;
  identity?: Me;
  onSignOut?: () => void;
}

const TAB_TITLES: Record<string, string> = {
  overview: 'Mission Control',
  autopilot: 'Swarm Auto-Pilot',
  portfolio: 'Deal Pipeline & CRM',
  guide: 'Visual User Guide',
  radar: 'Opportunity Radar',
  hunt: 'Local Client Hunt',
  sourcing: 'Open Sourcing',
  waterfall: 'Waterfall Enrichment',
  doctor: 'Website Doctor & Brief',
  callintel: 'Gong Call Intel & SOW',
  copycoach: 'Lavender Copy Coach',
  multimodal: 'Video Pitch Studio',
  sequences: 'Multi-Step Sequences',
  deliverability: 'Fleet Deliverability',
  dns: 'DNS Fleet Studio',
  suppression: 'CAN-SPAM Vault',
  governance: 'Autonomy Policy & Learning',
  rbac: 'Enterprise RBAC',
  apidocs: 'Developer API Console',
};

interface UpdaterStatus {
  status: string;
  update_available: boolean;
  current_commit: string;
  current_commit_short: string;
  latest_commit: string;
  latest_commit_short: string;
  behind_count: number;
  ahead_count: number;
  current_message: string;
  latest_message: string;
  changelog: string[];
  branch: string;
  remote: string;
  checked_at: string;
}

export const Header: FC<HeaderProps> = ({
  activeTab = 'overview',
  circuitBreakerTripped,
  onToggleHalt,
  mobileMenuOpen,
  setMobileMenuOpen,
  identity,
  onSignOut
}) => {
  const { theme, toggleTheme } = useTheme();
  const [api, setApi] = useState<{ ok: boolean; ms: number | null }>({ ok: false, ms: null });

  // System Updater State
  const [updater, setUpdater] = useState<UpdaterStatus | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [checking, setChecking] = useState(false);
  const [updateSuccess, setUpdateSuccess] = useState<any>(null);
  const [updateError, setUpdateError] = useState('');

  // 1. Live API Ping
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

  // 2. Automated Update Detection Poll (every 45s)
  useEffect(() => {
    let active = true;
    const fetchStatus = async () => {
      try {
        const res = await apiFetch('/api/system/updater/status');
        if (res.ok && active) {
          const data = await res.json();
          setUpdater(data);
        }
      } catch {
        // silent
      }
    };
    fetchStatus();
    const interval = window.setInterval(fetchStatus, 45000);
    return () => { active = false; window.clearInterval(interval); };
  }, []);

  const checkUpdates = async () => {
    setChecking(true);
    try {
      const res = await apiFetch('/api/system/updater/status');
      if (res.ok) {
        const data = await res.json();
        setUpdater(data);
      }
    } catch {
      // offline or silent fallback
    } finally {
      setChecking(false);
    }
  };

  // 3. Trigger Download, Replace & Hot-Restart
  const handleApplyUpdate = async () => {
    setUpdating(true);
    setUpdateError('');
    setUpdateSuccess(null);
    try {
      const res = await apiFetch('/api/system/updater/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_push: true })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || data.detail || 'Failed to apply update');
      setUpdateSuccess(data);
      // Wait 2.5s and reload interface to reflect hot-restarted server state
      setTimeout(() => {
        window.location.reload();
      }, 2500);
    } catch (e) {
      setUpdateError(e instanceof Error ? e.message : 'Update installation failed');
    } finally {
      setUpdating(false);
    }
  };

  return (
    <>
      <header className="sticky top-0 z-40 h-16 border-b border-[var(--app-border)] bg-[var(--app-header-bg)] backdrop-blur-xl px-4 sm:px-6 flex items-center justify-between transition-all">
        {/* Left: Mobile hamburger + Brand & Breadcrumb */}
        <div className="flex items-center space-x-3 sm:space-x-4">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="lg:hidden p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white focus:outline-none"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>

          <div className="flex items-center space-x-3">
            <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shadow-md shadow-indigo-500/20 flex items-center justify-center">
              <Cpu className="h-4.5 w-4.5 text-white" />
            </div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-white tracking-tight text-sm sm:text-base">AgencyBD</span>
              <span className="hidden sm:inline-flex px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                ENTERPRISE
              </span>
              <ChevronRight className="h-3.5 w-3.5 text-slate-600 hidden md:inline" />
              <span className="text-xs font-semibold text-slate-300 hidden md:inline tracking-tight font-sans">
                {TAB_TITLES[activeTab] || 'Mission Control'}
              </span>
            </div>
          </div>
        </div>

        {/* Center: Interactive Search / Jump Command + Telemetry */}
        <div className="hidden md:flex items-center space-x-3">
          {/* Animated Update Notification Pill */}
          {updater?.update_available && (
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white font-mono text-xs font-bold shadow-lg shadow-indigo-600/30 animate-pulse hover:brightness-110 transition-all cursor-pointer border border-pink-400/40"
              title="Click to review and apply new enterprise update"
            >
              <Sparkles className="h-3.5 w-3.5 text-yellow-300 animate-spin" style={{ animationDuration: '3s' }} />
              <span>Update Ready ({updater.behind_count} new)</span>
            </button>
          )}

          {/* Interactive Raycast-grade Command Bar */}
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('open-command-palette'))}
            className="flex items-center space-x-2.5 px-3.5 py-1.5 rounded-full bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-slate-700/80 text-xs font-mono text-slate-400 hover:text-slate-200 transition shadow-sm group cursor-pointer"
            title="Search modules and commands (⌘K)"
          >
            <Command className="h-3.5 w-3.5 text-slate-400 group-hover:text-indigo-400 transition-colors" />
            <span className="text-slate-400 group-hover:text-slate-200 font-sans text-xs">Jump to module…</span>
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800/90 text-[10px] text-slate-400 border border-slate-700/60 font-mono">⌘K</kbd>
          </button>

          {/* Live API Health & Latency */}
          <div className="flex items-center space-x-3 px-3 py-1.5 rounded-full bg-slate-900/60 border border-slate-800/70 text-xs font-mono">
            <div className={`flex items-center space-x-1.5 ${api.ok ? 'text-emerald-400' : 'text-rose-400'}`}>
              <span className="relative flex h-2 w-2">
                {api.ok && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
                <span className={`relative inline-flex rounded-full h-2 w-2 ${api.ok ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
              </span>
              <span>{api.ok ? 'API live' : 'API offline'}</span>
            </div>
            {api.ms !== null && (
              <>
                <span className="text-slate-700">|</span>
                <div className="text-slate-400 flex items-center space-x-1 tabular">
                  <Activity className="h-3 w-3 text-cyan-400" />
                  <span>{api.ms}ms</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right: Version / Sync Button + Theme Switcher + Kill Switch */}
        <div className="flex items-center space-x-2 sm:space-x-3">
          {/* Git Branch / Version Sync Button */}
          <button
            onClick={() => { checkUpdates(); setShowModal(true); }}
            className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-xl border border-slate-700/80 hover:border-indigo-500/50 bg-slate-900/60 hover:bg-slate-800/80 text-xs font-mono transition-all text-slate-300"
            title="System Version & GitHub Auto-Sync"
          >
            <GitBranch className="h-3.5 w-3.5 text-indigo-400" />
            <span className="hidden sm:inline font-semibold">{updater?.current_commit_short || 'main'}</span>
            {checking && <RefreshCw className="h-3 w-3 animate-spin text-slate-400" />}
          </button>

          {/* Dual-Theme Switcher (Dark / Light) */}
          <button
            onClick={toggleTheme}
            className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-xl border border-slate-700/80 hover:border-indigo-500/50 bg-slate-900/60 hover:bg-slate-800/80 text-xs font-mono transition-all group shadow-sm"
            title={`Switch to ${theme === 'dark' ? 'Light (Arctic Alabaster)' : 'Dark (Obsidian Velocity)'} theme`}
            aria-label="Toggle visual theme"
          >
            {theme === 'dark' ? (
              <>
                <Sun className="h-3.5 w-3.5 text-amber-400 group-hover:rotate-45 transition-transform duration-300" />
                <span className="hidden sm:inline text-slate-300 text-[11px] font-semibold">Light</span>
              </>
            ) : (
              <>
                <Moon className="h-3.5 w-3.5 text-indigo-500 group-hover:-rotate-12 transition-transform duration-300" />
                <span className="hidden sm:inline text-slate-700 text-[11px] font-semibold">Dark</span>
              </>
            )}
          </button>

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

      {/* =========================================================================
          UPDATE NOTIFICATION & RESTART MODAL
         ========================================================================= */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fadeIn">
          <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-5 overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-2xl pointer-events-none" />

            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <div className="p-2 bg-indigo-500/20 text-indigo-400 rounded-lg">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">System Synchronizer & Updater</h3>
                  <p className="text-xs text-slate-400 font-mono">Repository: MRizwanZafarAli/AgencyBD_Enterprise</p>
                </div>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Status Feedback */}
            {updateError && (
              <div className="p-3 bg-rose-950/50 border border-rose-500/40 rounded-xl text-xs text-rose-300 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                <span>{updateError}</span>
              </div>
            )}

            {updateSuccess && (
              <div className="p-4 bg-emerald-950/60 border border-emerald-500/40 rounded-xl text-xs text-emerald-300 space-y-2">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                  <span>Update Deployed & Replaced Successfully!</span>
                </div>
                <div className="font-mono text-[11px] text-slate-300">
                  Updated from <code>{updateSuccess.old_commit_short}</code> &rarr; <code>{updateSuccess.new_commit_short}</code><br />
                  Modified files: {updateSuccess.changed_files_count} | Git synced & pushed: Yes.<br />
                  <strong className="text-emerald-400">Restarting services and refreshing page in 2s...</strong>
                </div>
              </div>
            )}

            {/* Commit Comparison Box */}
            <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
                <span className="text-slate-400">Current Local Commit</span>
                <span className="text-slate-200 font-bold bg-slate-900 px-2 py-0.5 rounded border border-slate-700">
                  {updater?.current_commit_short || '7359ad9'}
                </span>
              </div>

              <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
                <span className="text-slate-400">Remote Target Commit</span>
                <span className="text-indigo-300 font-bold bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-700/50">
                  {updater?.latest_commit_short || 'origin/main'}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-400">Status</span>
                <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                  updater?.update_available ? 'bg-amber-950 text-amber-400 border border-amber-700/50 animate-pulse' : 'bg-emerald-950 text-emerald-400 border border-emerald-700/50'
                }`}>
                  {updater?.update_available ? `${updater.behind_count} update(s) available` : '100% Up to date'}
                </span>
              </div>
            </div>

            {/* Incoming Changelog (if updates available) */}
            {updater?.update_available && updater?.changelog && updater.changelog.length > 0 && (
              <div className="space-y-1.5">
                <label className="text-xs font-mono text-slate-400 uppercase tracking-wider block">Incoming Changelog</label>
                <div className="max-h-28 overflow-y-auto bg-slate-950/80 border border-slate-800 rounded-lg p-2.5 font-mono text-[11px] text-slate-300 space-y-1">
                  {updater.changelog.map((log, i) => (
                    <div key={i} className="truncate text-slate-300">&bull; {log}</div>
                  ))}
                </div>
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-800">
              <button
                onClick={checkUpdates}
                disabled={checking || updating}
                className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${checking ? 'animate-spin' : ''}`} />
                <span>Check Remote</span>
              </button>

              <button
                onClick={handleApplyUpdate}
                disabled={updating}
                className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50 cursor-pointer"
              >
                {updating ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Downloading, Replacing & Syncing...</span>
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    <span>Download, Replace & Restart</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
