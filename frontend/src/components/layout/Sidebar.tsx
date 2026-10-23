import { useState } from 'react';
import type { FC, ReactNode } from 'react';
import {
  Activity, Globe, Database, Send,
  Sparkles, BarChart3, Video, Layers,
  Lock, Users, Terminal, X, BookOpen,
  Stethoscope, Radar, MapPinned, ShieldCheck, Mail, Kanban, Bot,
  ChevronDown, ChevronRight, SlidersHorizontal
} from 'lucide-react';
import type { TabType } from '../../types';

interface SidebarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  mobileMenuOpen: boolean;
  setMobileMenuOpen: (o: boolean) => void;
}

interface NavItemDef {
  id: TabType;
  label: string;
  icon: ReactNode;
  badge?: string;
  badgeColor?: string;
}

// 1. Core Autonomous Workflows (Always prominent & accessible)
const PRIMARY_NAV_ITEMS: NavItemDef[] = [
  {
    id: 'autopilot',
    label: 'Swarm Auto-Pilot',
    icon: <Bot className="h-4 w-4" />,
    badge: '1-Click',
    badgeColor: 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
  },
  {
    id: 'overview',
    label: 'Mission Control',
    icon: <Activity className="h-4 w-4" />
  },
  {
    id: 'radar',
    label: 'Opportunity Radar',
    icon: <Radar className="h-4 w-4" />
  },
  {
    id: 'doctor',
    label: 'Website Doctor',
    icon: <Stethoscope className="h-4 w-4" />
  },
  {
    id: 'portfolio',
    label: 'Deal Pipeline & CRM',
    icon: <Kanban className="h-4 w-4" />
  },
  {
    id: 'guide',
    label: 'Visual User Guide',
    icon: <BookOpen className="h-4 w-4" />,
    badge: 'Diagrams',
    badgeColor: 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
  }
];

// 2. Specialized Engineering Suite (Cleanly collapsed by default to eliminate clutter)
const SPECIALIZED_NAV_ITEMS: NavItemDef[] = [
  { id: 'hunt', label: 'Local Client Hunt', icon: <MapPinned className="h-4 w-4" /> },
  { id: 'waterfall', label: 'Waterfall Enrichment', icon: <Database className="h-4 w-4" /> },
  { id: 'sourcing', label: 'Open Sourcing', icon: <Globe className="h-4 w-4" /> },
  { id: 'callintel', label: 'Gong Call Intel & SOW', icon: <BarChart3 className="h-4 w-4" /> },
  { id: 'copycoach', label: 'Lavender Copy Coach', icon: <Sparkles className="h-4 w-4" /> },
  { id: 'multimodal', label: 'Video Pitch Studio', icon: <Video className="h-4 w-4" /> },
  { id: 'sequences', label: 'Multi-Step Sequences', icon: <Mail className="h-4 w-4" /> },
  { id: 'deliverability', label: 'Fleet Deliverability', icon: <Send className="h-4 w-4" /> },
  { id: 'dns', label: 'DNS Fleet Studio', icon: <Layers className="h-4 w-4" /> },
  { id: 'suppression', label: 'CAN-SPAM Vault', icon: <Lock className="h-4 w-4" /> },
  { id: 'governance', label: 'Autonomy Policy & Learning', icon: <ShieldCheck className="h-4 w-4" /> },
  { id: 'rbac', label: 'Enterprise RBAC', icon: <Users className="h-4 w-4" /> },
  { id: 'apidocs', label: 'Developer API Console', icon: <Terminal className="h-4 w-4" /> }
];

export const Sidebar: FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  mobileMenuOpen,
  setMobileMenuOpen
}) => {
  // Check if activeTab is inside specialized items to keep section open
  const isSpecializedActive = SPECIALIZED_NAV_ITEMS.some((item) => item.id === activeTab);

  const [manuallyToggled, setManuallyToggled] = useState<boolean | null>(null);

  const isExpanded = manuallyToggled !== null ? manuallyToggled : isSpecializedActive;

  const toggleSpecialized = () => {
    setManuallyToggled(!isExpanded);
  };

  const handleItemClick = (id: TabType) => {
    setActiveTab(id);
    setMobileMenuOpen(false);
  };

  const navContent = (
    <div className="flex flex-col h-full py-5 px-3 justify-between">
      <div className="space-y-6">
        {/* Core Autonomous Operations */}
        <div className="space-y-1">
          <div className="px-3 pb-1 text-[11px] font-mono font-bold tracking-wider text-slate-400 uppercase flex items-center justify-between">
            <span>Autonomous Core</span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-400 font-semibold border border-indigo-500/20">
              Active
            </span>
          </div>

          <div className="space-y-1 pt-1">
            {PRIMARY_NAV_ITEMS.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleItemClick(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-[13px] font-medium transition-all group relative cursor-pointer ${
                    isActive
                      ? 'bg-indigo-600/15 text-indigo-400 font-semibold border border-indigo-500/30 shadow-sm shadow-indigo-500/10'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
                >
                  {isActive && (
                    <div className="absolute left-0 top-2 bottom-2 w-1.5 rounded-r-full bg-indigo-500 shadow-sm shadow-indigo-500/60" />
                  )}
                  <div className="flex items-center space-x-3 pl-1 group-hover:translate-x-0.5 transition-transform">
                    <span className={isActive ? 'text-indigo-400 font-bold' : 'text-slate-400 group-hover:text-slate-200'}>
                      {item.icon}
                    </span>
                    <span className="truncate">{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold shrink-0 ${item.badgeColor || 'bg-slate-800 text-slate-300'}`}>
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Specialized Engineering Suite (Collapsible) */}
        <div className="space-y-1 pt-2 border-t border-[var(--app-border-subtle)]">
          <button
            onClick={toggleSpecialized}
            className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition cursor-pointer"
          >
            <div className="flex items-center space-x-2">
              <SlidersHorizontal className="h-3.5 w-3.5 text-indigo-400" />
              <span className="font-mono uppercase tracking-wider text-[11px] font-bold">Specialized Suite</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400">
                {SPECIALIZED_NAV_ITEMS.length}
              </span>
            </div>
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-slate-400" />
            )}
          </button>

          {isExpanded && (
            <div className="space-y-1 pt-1 pl-1 animate-fade-in">
              {SPECIALIZED_NAV_ITEMS.map((item) => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleItemClick(item.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-[12.5px] font-medium transition-all group relative cursor-pointer ${
                      isActive
                        ? 'bg-indigo-600/15 text-indigo-400 font-semibold border border-indigo-500/30 shadow-sm shadow-indigo-500/10'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`}
                  >
                    {isActive && (
                      <div className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full bg-indigo-500 shadow-sm shadow-indigo-500/60" />
                    )}
                    <div className="flex items-center space-x-2.5 pl-1 group-hover:translate-x-0.5 transition-transform">
                      <span className={isActive ? 'text-indigo-400 font-bold' : 'text-slate-500 group-hover:text-slate-300'}>
                        {item.icon}
                      </span>
                      <span className="truncate">{item.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Sleek Minimalist Footer Status (Zero Clutter, Zero Duplicates) */}
      <div className="pt-4 mt-4 border-t border-[var(--app-border-subtle)] px-2">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <div className="flex items-center space-x-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[11px] text-slate-300 font-medium">Sovereign BD Engine</span>
          </div>
          <span className="text-[10px] text-slate-500">v2.4</span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Left Rail */}
      <aside className="hidden lg:block w-64 shrink-0 border-r border-[var(--app-border)] bg-[var(--app-sidebar-bg)] backdrop-blur-md overflow-y-auto min-h-[calc(100vh-4rem)]">
        {navContent}
      </aside>

      {/* Mobile Drawer Overlay */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative w-72 max-w-[80vw] bg-slate-950 border-r border-slate-800 flex flex-col h-full z-10 shadow-2xl">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <span className="font-bold text-white text-sm">Navigation</span>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {navContent}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
