import { useState } from 'react';
import type { FC, ReactNode } from 'react';
import {
  Activity, Globe, Database, Send,
  Sparkles, BarChart3, Video, Layers,
  Lock, Users, Terminal, X, BookOpen,
  Stethoscope, Radar, MapPinned, ShieldCheck, Mail, Kanban, Bot
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
    title: 'COMMAND & PIPELINE',
    items: [
      { id: 'overview', label: 'Mission Control', icon: <Activity className="h-4 w-4" /> },
      { id: 'autopilot', label: 'Swarm Auto-Pilot', icon: <Bot className="h-4 w-4" />, badge: '100% Auto', badgeColor: 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' },
      { id: 'portfolio', label: 'Deal Pipeline & CRM', icon: <Kanban className="h-4 w-4" />, badge: 'CRM', badgeColor: 'bg-emerald-500/20 text-emerald-300' },
    ]
  },
  {
    title: 'PROSPECTING & RADAR',
    items: [
      { id: 'radar', label: 'Opportunity Radar', icon: <Radar className="h-4 w-4" />, badge: 'Feeds', badgeColor: 'bg-cyan-500/20 text-cyan-300' },
      { id: 'hunt', label: 'Local Client Hunt', icon: <MapPinned className="h-4 w-4" />, badge: 'Maps', badgeColor: 'bg-emerald-500/20 text-emerald-300' },
      { id: 'sourcing', label: 'Open Sourcing', icon: <Globe className="h-4 w-4" />, badge: 'Multi-Src', badgeColor: 'bg-indigo-500/20 text-indigo-300' },
      { id: 'waterfall', label: 'Waterfall Enrichment', icon: <Database className="h-4 w-4" />, badge: '$0 Clay', badgeColor: 'bg-emerald-500/20 text-emerald-300' },
    ]
  },
  {
    title: 'SALES ENGINEERING',
    items: [
      { id: 'doctor', label: 'Website Doctor & Brief', icon: <Stethoscope className="h-4 w-4" />, badge: 'Evidence', badgeColor: 'bg-emerald-500/20 text-emerald-300' },
      { id: 'callintel', label: 'Gong Call Intel & SOW', icon: <BarChart3 className="h-4 w-4" />, badge: 'Deal Desk', badgeColor: 'bg-cyan-500/20 text-cyan-300' },
      { id: 'copycoach', label: 'Lavender Copy Coach', icon: <Sparkles className="h-4 w-4" /> },
      { id: 'multimodal', label: 'Video Pitch Studio', icon: <Video className="h-4 w-4" /> },
      { id: 'sequences', label: 'Multi-Step Sequences', icon: <Mail className="h-4 w-4" />, badge: 'Cadence', badgeColor: 'bg-indigo-500/20 text-indigo-300' },
    ]
  },
  {
    title: 'INFRASTRUCTURE & GOVERNANCE',
    items: [
      { id: 'deliverability', label: 'Fleet Deliverability', icon: <Send className="h-4 w-4" />, badge: 'Spintax', badgeColor: 'bg-cyan-500/20 text-cyan-300' },
      { id: 'dns', label: 'DNS Fleet Studio', icon: <Layers className="h-4 w-4" /> },
      { id: 'suppression', label: 'CAN-SPAM Vault', icon: <Lock className="h-4 w-4" /> },
      { id: 'governance', label: 'Autonomy Policy & Learning', icon: <ShieldCheck className="h-4 w-4" />, badge: 'L0-L3', badgeColor: 'bg-amber-500/20 text-amber-300' },
      { id: 'rbac', label: 'Enterprise RBAC', icon: <Users className="h-4 w-4" /> },
      { id: 'apidocs', label: 'Developer API Console', icon: <Terminal className="h-4 w-4" />, badge: 'Docs', badgeColor: 'bg-purple-500/20 text-purple-300' },
    ]
  }
];

const PLATFORM_PAGE_GUIDE = [
  {
    name: 'Mission Control',
    purpose: 'Executive cockpit tracking real workspace pipeline ($ won, meetings booked, dispatch telemetry) and production readiness.',
    howToUse: 'Check the 8 real-time KPI tiles tracking active pipelines, deal values, and outreach dispatch volume directly from the database.'
  },
  {
    name: 'Swarm Auto-Pilot',
    purpose: 'Fully autonomous multi-agent pipeline orchestrator (Sourcing Scout, Forensics Engineer, Deal Strategist, Deliverability Sentinel).',
    howToUse: 'Select target channel (SEC EDGAR, Local Maps, Venture DB), set target count, and click "Launch Swarm Auto-Pilot". The agents autonomously find, audit, and enroll qualified leads.'
  },
  {
    name: 'Deal Pipeline & CRM',
    purpose: 'Unified deal tracker displaying active pipeline, won contracts, portfolio assets, and priced services.',
    howToUse: 'Review incoming bids and signed deals. Mark won proposals to feed the machine learning calibration engine.'
  },
  {
    name: 'Opportunity Radar',
    purpose: 'Aggregates inbound tenders and high-value RFP feeds from Upwork, GitHub, and procurement databases.',
    howToUse: 'Filter by budget and skill keyword. Click any opportunity to instantly generate a zero-hallucination proposal citing verified case studies.'
  },
  {
    name: 'Local Client Hunt',
    purpose: 'High-intent local business sourcing using free OpenStreetMap coordinates (zero Google Places API cost).',
    howToUse: 'Enter a business category (e.g. "Dental", "HVAC") and city (e.g. "Austin, TX"). Click Search to inspect ratings and identify slow websites.'
  },
  {
    name: 'Open Sourcing',
    purpose: 'Multi-channel B2B directory scraper discovering companies with verified domain names.',
    howToUse: 'Choose a data source (Venture DB, Crunchbase-style feeds), execute query, and push verified companies straight into Waterfall Enrichment.'
  },
  {
    name: 'Waterfall Enrichment',
    purpose: '100% free contact finder replacing Clay. Generates 8 RFC-compliant email permutations and performs zero-cost SMTP MX handshakes.',
    howToUse: 'Enter any Prospect Name and Company Domain. Click "Run Waterfall". Identifies the exact deliverable mailbox without third-party API credits.'
  },
  {
    name: 'Website Doctor & Brief',
    purpose: 'Enterprise technical audit engine measuring Core Web Vitals (LCP, TTFB), SSL, headers, and SEO. Generates 1-click Teardown Decks.',
    howToUse: 'Enter any target company domain (e.g. your prospect website). Click "Run Comprehensive Audit" to inspect performance and export an executive pitch deck.'
  },
  {
    name: 'Gong Call Intel & SOW',
    purpose: 'Replaces Gong/Chorus: analyzes sales call transcripts for talk-to-listen ratios, objections, and generates 3-tier Statements of Work.',
    howToUse: 'Paste a sales call transcript or click "Insert Discovery Template", then click "Analyze Call & Generate Proposal SOW". Instantly view talk-time dial, objection counters, and SOW.'
  },
  {
    name: 'Lavender Copy Coach',
    purpose: 'Cold email scoring engine grading readability, spam trigger words, subject line length, and sentiment.',
    howToUse: 'Draft your email subject and body. The coach provides a live 0-100 score with tactical suggestions to maximize positive reply rates.'
  },
  {
    name: 'Video Pitch Studio',
    purpose: 'Automated video & audio storyboard generator producing personalized 60-second video teardown scripts for founders.',
    howToUse: 'Input company details and audit metrics. Generates scene-by-scene script, visual directions, and founder voiceover hooks.'
  },
  {
    name: 'Multi-Step Sequences',
    purpose: 'Multi-touch outbound cadence engine orchestrating follow-ups across day 1, 3, 7, and 14 with auto-stop on reply.',
    howToUse: 'Create or enroll leads into 4-step sequences. When a prospect replies, the sequence halts automatically to protect sender reputation.'
  },
  {
    name: 'Fleet Deliverability',
    purpose: 'ESP routing and Spintax generator. Balances email dispatch across Gmail, Outlook, and private SMTP based on recipient MX records.',
    howToUse: 'Test Spintax variations with {Hi|Hello|Hey} syntax and match recipient MX hosts to the optimal inbox to avoid the spam folder.'
  },
  {
    name: 'DNS Fleet Studio',
    purpose: 'Verifies SPF, DKIM, DMARC, and MX records across your sending domains to ensure 99%+ inbox placement.',
    howToUse: 'Enter your domain to run a DNS audit. Flags missing DMARC policies or SPF alignment errors before sending emails.'
  },
  {
    name: 'CAN-SPAM Vault',
    purpose: 'Cryptographic HMAC suppression registry ensuring opt-outs and unsubscribes are honored across all campaigns forever.',
    howToUse: 'Search suppressed emails or add unsubscribes. The system mathematically prevents sending to suppressed addresses.'
  },
  {
    name: 'Autonomy Policy & Learning',
    purpose: 'Configures human-in-the-loop safety levels (L0 Manual to L3 Full Autonomy) and monitors the proposal learning loop.',
    howToUse: 'Set approval thresholds for deal sizes. When proposals win or lose, the Bayesian calibration adjusts win predictions.'
  },
  {
    name: 'Enterprise RBAC',
    purpose: 'Role-Based Access Control and scoped API key management (Admin, SDR, Auditor, Growth Lead).',
    howToUse: 'Issue role-scoped keys for team members or integrations with cryptographic HMAC hashing.'
  },
  {
    name: 'Developer API Console',
    purpose: 'Interactive OpenAPI / Swagger documentation and raw endpoint tester for headless integration.',
    howToUse: 'Inspect all 40+ REST endpoints, review JSON schemas, and test curl requests directly.'
  }
];

export const Sidebar: FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  mobileMenuOpen,
  setMobileMenuOpen
}) => {
  const [guideOpen, setGuideOpen] = useState(false);

  const handleItemClick = (id: TabType) => {
    setActiveTab(id);
    setMobileMenuOpen(false);
  };

  const navContent = (
    <div className="flex flex-col h-full py-4 px-3 space-y-6">
      {NAV_GROUPS.map((group, gIdx) => (
        <div key={gIdx} className="space-y-1">
          <div className="px-3 text-[11px] font-mono font-bold tracking-wider text-slate-400 uppercase">
            {group.title}
          </div>
          <div className="space-y-1 pt-1">
            {group.items.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleItemClick(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-[13px] font-medium transition-all group relative ${
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
      ))}

      {/* Platform Guide Launcher Button */}
      <div className="pt-2 px-1">
        <button
          onClick={() => setGuideOpen(true)}
          className="w-full flex items-center justify-center gap-2 p-2.5 rounded-xl text-xs font-semibold text-indigo-300 bg-indigo-950/40 hover:bg-indigo-900/50 border border-indigo-700/40 transition shadow-sm"
        >
          <BookOpen className="h-4 w-4 text-indigo-400" />
          <span>📖 Platform Guide & Usage</span>
        </button>
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

      {/* Platform Guide Modal */}
      {guideOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="relative w-full max-w-4xl max-h-[85vh] bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
            {/* Header */}
            <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/50">
              <div className="flex items-center gap-2.5">
                <BookOpen className="h-5 w-5 text-indigo-400" />
                <div>
                  <h3 className="text-base font-bold text-white">AgencyBD Enterprise Platform Guide</h3>
                  <p className="text-xs text-slate-400">Complete roadmap, purpose, and 1-2-3 usage for every module in your sovereign BD stack</p>
                </div>
              </div>
              <button
                onClick={() => setGuideOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Content List */}
            <div className="p-6 overflow-y-auto space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {PLATFORM_PAGE_GUIDE.map((page, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2 hover:border-slate-700 transition">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-bold text-indigo-300">{page.name}</h4>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">
                        Module #{idx + 1}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">{page.purpose}</p>
                    <div className="p-2.5 rounded-lg bg-indigo-950/20 border border-indigo-500/20 text-[11px] text-slate-300 space-y-1">
                      <span className="font-semibold text-indigo-400 font-mono">HOW TO USE:</span>
                      <div>{page.howToUse}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-800 bg-slate-950/50 flex justify-between items-center text-xs text-slate-400">
              <span>All modules run 100% sovereignly with zero recurring API costs.</span>
              <button
                onClick={() => setGuideOpen(false)}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition"
              >
                Close Guide
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
