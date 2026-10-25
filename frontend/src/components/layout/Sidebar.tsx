import { useEffect, useRef, useState } from 'react';
import type { FC, ReactNode } from 'react';
import { Inbox, PanelRight, Radio, Search, Users, Wrench, Settings, X, PanelLeftClose, PanelLeftOpen, LogOut, Keyboard, ChevronsUpDown } from 'lucide-react';
import type { Surface } from '../../types';
import type { Me } from '../../lib/api';

interface NavDef { id: Surface; label: string; hint: string; icon: ReactNode; key: string }
const WORKSPACE: NavDef[] = [
  { id: 'today', label: 'Today', hint: 'What needs you', icon: <Inbox className="h-[18px] w-[18px]" />, key: 'G T' },
  { id: 'find', label: 'Find', hint: 'New prospects and work', icon: <Search className="h-[18px] w-[18px]" />, key: 'G F' },
  { id: 'clients', label: 'Clients', hint: 'Pipeline and audits', icon: <Users className="h-[18px] w-[18px]" />, key: 'G C' },
  { id: 'channels', label: 'Channels', hint: 'LinkedIn and freelance sites', icon: <Radio className="h-[18px] w-[18px]" />, key: 'G H' },
];
const UTILITIES: NavDef[] = [{ id: 'tools', label: 'Tools', hint: 'Audit, compare, write', icon: <Wrench className="h-[18px] w-[18px]" />, key: 'G O' }];
const ADMIN: NavDef[] = [{ id: 'settings', label: 'Settings', hint: 'Set up once', icon: <Settings className="h-[18px] w-[18px]" />, key: 'G S' }];

export interface SidebarProps {
  active: Surface; onNavigate: (s: Surface) => void; badge?: number; collapsed: boolean; onToggleCollapsed: () => void;
  mobileMenuOpen: boolean; setMobileMenuOpen: (o: boolean) => void; identity: Me; onSignOut: () => void; onPalette: () => void; onHelp: () => void; onDock: () => void; halted: boolean;
}

const Tip: FC<{ text: string; shortcut?: string }> = ({ text, shortcut }) => (
  <span role="tooltip" className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-3 z-50 whitespace-nowrap rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-100 shadow-lg opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 group-focus-visible:opacity-100 transition">
    {text}{shortcut && <kbd className="ml-2 font-mono text-[10px] text-slate-400">{shortcut}</kbd>}
  </span>
);

const NavButton: FC<{ item: NavDef; active: boolean; collapsed: boolean; badge?: number; onClick: () => void }> = ({ item, active, collapsed, badge, onClick }) => (
  <button
    onClick={onClick}
    aria-current={active ? 'page' : undefined}
    aria-label={collapsed ? item.label : undefined}
    className={`group relative w-full flex items-center ${collapsed ? 'justify-center px-0' : 'gap-3 px-3'} h-10 rounded-lg text-left transition-colors ${
      active ? 'bg-indigo-500/10 text-white' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/70'}`}
  >
    {active && <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r bg-indigo-500" aria-hidden="true" />}
    <span className={active ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'}>{item.icon}</span>
    {!collapsed && <span className="flex-1 min-w-0 text-sm font-medium truncate">{item.label}</span>}
    {!collapsed && !!badge && <span className="px-1.5 min-w-5 text-center rounded-md bg-indigo-500 text-white text-[11px] font-semibold tabular">{badge > 99 ? '99+' : badge}</span>}
    {collapsed && !!badge && <span className="absolute top-1.5 right-3 h-2 w-2 rounded-full bg-indigo-500 ring-2 ring-slate-950" aria-label={`${badge} waiting`} />}
    {collapsed && <Tip text={item.label} shortcut={item.key} />}
  </button>
);

const Group: FC<{ title: string; collapsed: boolean; children: ReactNode }> = ({ title, collapsed, children }) => (
  <div className="space-y-1">
    {collapsed ? <div className="mx-3 my-2 h-px bg-slate-800" aria-hidden="true" /> : <div className="px-3 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{title}</div>}
    {children}
  </div>
);

const SidebarBody: FC<SidebarProps & { collapsed: boolean; inDrawer?: boolean }> = (p) => {
  const { collapsed } = p;
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setMenu(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);
  const go = (s: Surface) => { p.onNavigate(s); p.setMobileMenuOpen(false); };
  const initials = p.identity.user_id.slice(0, 2).toUpperCase();

  return (
    <div className="flex flex-col h-full">
      <div className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between px-4'} h-14 shrink-0 border-b border-slate-800/80`}>
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="h-8 w-8 rounded-lg bg-indigo-600 text-white text-xs font-bold flex items-center justify-center shrink-0">BD</div>
          {!collapsed && <div className="min-w-0"><div className="text-sm font-semibold text-white leading-tight">AgencyBD</div><div className="text-[11px] text-slate-500 truncate leading-tight">{p.identity.org_id}</div></div>}
        </div>
      </div>

      <div className={`px-3 pt-3 ${collapsed ? 'px-2' : ''}`}>
        <button onClick={() => { p.onPalette(); p.setMobileMenuOpen(false); }} aria-label="Search or jump to"
          className={`group relative w-full flex items-center ${collapsed ? 'justify-center' : 'gap-2 px-3'} h-9 rounded-lg border border-slate-800 bg-slate-900/50 text-slate-500 hover:border-slate-600 hover:text-slate-300`}>
          <Search className="h-4 w-4" />{!collapsed && <><span className="text-xs flex-1 text-left">Search…</span><kbd className="font-mono text-[10px] border border-slate-700 rounded px-1">⌘K</kbd></>}
          {collapsed && <Tip text="Search or jump to" shortcut="⌘K" />}
        </button>
      </div>

      <nav aria-label="Main" className="flex-1 overflow-y-auto px-3 pb-3 pt-1">
        <Group title="Workspace" collapsed={collapsed}>{WORKSPACE.map((i) => <NavButton key={i.id} item={i} active={p.active === i.id} collapsed={collapsed} badge={i.id === 'today' ? p.badge : undefined} onClick={() => go(i.id)} />)}</Group>
        <Group title="Utilities" collapsed={collapsed}>{UTILITIES.map((i) => <NavButton key={i.id} item={i} active={p.active === i.id} collapsed={collapsed} onClick={() => go(i.id)} />)}</Group>
        <Group title="Admin" collapsed={collapsed}>{ADMIN.map((i) => <NavButton key={i.id} item={i} active={p.active === i.id} collapsed={collapsed} onClick={() => go(i.id)} />)}</Group>
      </nav>

      <div className={`px-3 pb-2 ${collapsed ? 'px-2' : ''}`}>
        <button onClick={() => { p.onDock(); p.setMobileMenuOpen(false); }} aria-label="Browser dock"
          className={`group relative w-full flex items-center ${collapsed ? 'justify-center' : 'gap-3 px-3'} h-10 rounded-lg border border-slate-800 text-slate-300 hover:border-indigo-500/60 hover:text-white`}>
          <PanelRight className="h-[18px] w-[18px] text-indigo-400" />{!collapsed && <span className="text-sm font-medium flex-1 text-left">Browser dock</span>}
          {collapsed && <Tip text="Browser dock" />}
        </button>
      </div>

      {p.halted && !collapsed && <div className="mx-3 mb-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-[11px] text-rose-300">Sending is stopped</div>}

      <div className="border-t border-slate-800/80 p-3 space-y-1 relative" ref={ref}>
        {!p.inDrawer && (
          <button onClick={p.onToggleCollapsed} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed}
            className={`group relative w-full flex items-center ${collapsed ? 'justify-center' : 'gap-3 px-3'} h-9 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-900/70`}>
            {collapsed ? <PanelLeftOpen className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
            {!collapsed && <><span className="text-xs flex-1 text-left">Collapse</span><kbd className="font-mono text-[10px] border border-slate-700 rounded px-1">[</kbd></>}
            {collapsed && <Tip text="Expand sidebar" shortcut="[" />}
          </button>)}
        <button onClick={() => setMenu((v) => !v)} aria-haspopup="menu" aria-expanded={menu} aria-label="Account menu"
          className={`group relative w-full flex items-center ${collapsed ? 'justify-center' : 'gap-3 px-2'} h-12 rounded-lg hover:bg-slate-900/70`}>
          <span className="h-8 w-8 rounded-full bg-slate-800 text-slate-200 text-xs font-semibold flex items-center justify-center shrink-0">{initials}</span>
          {!collapsed && <><span className="flex-1 min-w-0 text-left"><span className="block text-sm text-slate-100 truncate">{p.identity.user_id}</span><span className="block text-[11px] text-slate-500 truncate">{p.identity.role.replace('_', ' ')}</span></span><ChevronsUpDown className="h-4 w-4 text-slate-500" /></>}
          {collapsed && <Tip text={`${p.identity.user_id} (${p.identity.role})`} />}
        </button>
        {menu && (
          <div role="menu" className={`absolute z-50 bottom-full mb-2 ${collapsed ? 'left-2 w-56' : 'left-3 right-3'} rounded-xl border border-slate-800 bg-slate-950 shadow-2xl p-1.5 text-xs animate-pop`}>
            <div className="px-2.5 py-2"><div className="text-slate-100 font-medium truncate">{p.identity.user_id}</div><div className="text-slate-500">{p.identity.role.replace('_', ' ')} · {p.identity.org_id}</div></div>
            <button role="menuitem" onClick={() => { setMenu(false); p.onHelp(); }} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-slate-300 hover:bg-slate-800/60"><Keyboard className="h-3.5 w-3.5" />Keyboard shortcuts<kbd className="ml-auto font-mono text-[10px] text-slate-500">?</kbd></button>
            <button role="menuitem" onClick={p.onSignOut} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-slate-300 hover:bg-slate-800/60"><LogOut className="h-3.5 w-3.5" />Sign out</button>
          </div>)}
      </div>
    </div>
  );
};

export const Sidebar: FC<SidebarProps> = (p) => (
  <>
    <aside className={`hidden lg:block shrink-0 sticky top-0 h-screen border-r border-slate-800/80 bg-slate-950/70 backdrop-blur-md transition-[width] duration-200 ${p.collapsed ? 'w-[68px]' : 'w-64'}`}>
      <SidebarBody {...p} />
    </aside>
    {p.mobileMenuOpen && (
      <div className="lg:hidden fixed inset-0 z-50 flex">
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm animate-pop" onClick={() => p.setMobileMenuOpen(false)} />
        <div className="relative w-[18rem] max-w-[85vw] bg-slate-950 border-r border-slate-800 h-full z-10 animate-fade-up" role="dialog" aria-modal="true" aria-label="Menu">
          <button onClick={() => p.setMobileMenuOpen(false)} aria-label="Close menu" className="absolute top-3 right-3 z-10 p-1.5 rounded-lg text-slate-400 hover:text-white"><X className="h-5 w-5" /></button>
          <SidebarBody {...p} collapsed={false} inDrawer />
        </div>
      </div>)}
  </>
);

/** Phone-only bottom tab bar (the sidebar becomes a drawer below 1024px). */
export const MobileTabBar: FC<{ active: Surface; onNavigate: (s: Surface) => void; badge?: number }> = ({ active, onNavigate, badge }) => (
  <nav aria-label="Mobile" className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t border-slate-800 bg-slate-950/95 backdrop-blur flex pb-[env(safe-area-inset-bottom)]">
    {[...WORKSPACE, ...UTILITIES, ...ADMIN].map((i) => (
      <button key={i.id} onClick={() => onNavigate(i.id)} aria-current={active === i.id ? 'page' : undefined} aria-label={i.label}
        className={`relative flex-1 flex flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium ${active === i.id ? 'text-indigo-300' : 'text-slate-500'}`}>
        {i.icon}<span>{i.label}</span>
        {i.id === 'today' && !!badge && <span className="absolute top-1 left-1/2 ml-2 min-w-4 px-1 text-center rounded-full bg-indigo-500 text-white text-[9px] tabular">{badge > 99 ? '99+' : badge}</span>}
      </button>))}
  </nav>
);
