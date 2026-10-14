import type { FC, ReactNode } from 'react';
import {
  Activity, Globe, Database, Send,
  Sparkles, BarChart3, Video, Layers,
  Lock, Users, Terminal, X,
  Stethoscope, Radar, MapPinned, ShieldCheck, BookOpen, Mail
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

const NAV_GROUPS: Array<{ title: string; items: NavItemDef[] }> = [
  {
    title: 'CORE INTELLIGENCE',
    items: [
      { id: 'overview', label: 'Mission Control', icon: <Activity className="h-4 w-4" /> },
      { id: 'doctor', label: 'Website Doctor & Brief', icon: <Stethoscope className="h-4 w-4" />, badge: 'Evidence', badgeColor: 'bg-emerald-500/20 text-emerald-300' },
      { id: 'hunt', label: 'Local Client Hunt', icon: <MapPinned className="h-4 w-4" />, badge: 'Maps', badgeColor: 'bg-emerald-500/20 text-emerald-300' },
      { id: 'radar', label: 'Opportunity Radar', icon: <Radar className="h-4 w-4" />, badge: 'All Work', badgeColor: 'bg-cyan-500/20 text-cyan-300' },
      { id: 'portfolio', label: 'Portfolio & Proof', icon: <BookOpen className="h-4 w-4" />, badge: 'Required', badgeColor: 'bg-amber-500/20 text-amber-300' },
      { id: 'sequences', label: 'Sequences', icon: <Mail className="h-4 w-4" />, badge: 'Outbound', badgeColor: 'bg-indigo-500/20 text-indigo-300' },
      { id: 'governance', label: 'Autonomy Policy & Learning', icon: <ShieldCheck className="h-4 w-4" />, badge: 'L0-L3', badgeColor: 'bg-amber-500/20 text-amber-300' },
      { id: 'sourcing', label: 'Open Sourcing', icon: <Globe className="h-4 w-4" />, badge: 'Maps + LI', badgeColor: 'bg-indigo-500/20 text-indigo-300' },
      { id: 'waterfall', label: 'Waterfall Enrichment', icon: <Database className="h-4 w-4" />, badge: 'Clay-Free', badgeColor: 'bg-emerald-500/20 text-emerald-300' },
    ]
  },
  {
    title: 'OUTREACH & CONTENT',
    items: [
      { id: 'deliverability', label: 'Fleet Deliverability', icon: <Send className="h-4 w-4" />, badge: 'Spintax', badgeColor: 'bg-cyan-500/20 text-cyan-300' },
      { id: 'copycoach', label: 'Lavender Copy Coach', icon: <Sparkles className="h-4 w-4" /> },
      { id: 'callintel', label: 'Gong Call Intel & SOW', icon: <BarChart3 className="h-4 w-4" /> },
      { id: 'multimodal', label: 'Multimodal Video Studio', icon: <Video className="h-4 w-4" /> },
    ]
  },
  {
    title: 'INFRASTRUCTURE & GOVERNANCE',
    items: [
      { id: 'dns', label: 'DNS Fleet Studio', icon: <Layers className="h-4 w-4" /> },
      { id: 'suppression', label: 'CAN-SPAM Vault', icon: <Lock className="h-4 w-4" /> },
      { id: 'rbac', label: 'Enterprise RBAC', icon: <Users className="h-4 w-4" /> },
      { id: 'apidocs', label: 'Developer API Console', icon: <Terminal className="h-4 w-4" />, badge: 'REST /docs', badgeColor: 'bg-purple-500/20 text-purple-300' },
    ]
  }
];


export const Sidebar: FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  mobileMenuOpen,
  setMobileMenuOpen
}) => {
  const handleItemClick = (id: TabType) => {
    setActiveTab(id);
    setMobileMenuOpen(false);
  };

  const navContent = (
    <div className="flex flex-col h-full py-4 px-3 space-y-6">
      {NAV_GROUPS.map((group, gIdx) => (
        <div key={gIdx} className="space-y-1">
          <div className="px-3 text-[10px] font-mono font-semibold tracking-wider text-slate-400 uppercase">
            {group.title}
          </div>
          <div className="space-y-0.5 pt-1">
            {group.items.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleItemClick(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-medium transition-all group relative ${
                    isActive
                      ? 'bg-indigo-600/15 text-indigo-400 font-semibold border border-indigo-500/30 shadow-sm shadow-indigo-500/10'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
                >
                  {isActive && (
                    <div className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-indigo-500 shadow-sm shadow-indigo-500/50" />
                  )}
                  <div className="flex items-center space-x-2.5 pl-1 group-hover:translate-x-0.5 transition-transform">
                    <span className={isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-400'}>
                      {item.icon}
                    </span>
                    <span className="truncate">{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className={`px-1.5 py-0.5 rounded-md text-[10px] font-mono font-medium shrink-0 ${item.badgeColor || 'bg-slate-800 text-slate-300'}`}>
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Left Rail */}
      <aside className="hidden lg:block w-64 shrink-0 border-r border-slate-800/80 bg-slate-950/60 backdrop-blur-md overflow-y-auto min-h-[calc(100vh-4rem)]">
        {navContent}
      </aside>

      {/* Mobile Drawer Overlay */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          {/* Backdrop blur */}
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />
          {/* Drawer Content */}
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
