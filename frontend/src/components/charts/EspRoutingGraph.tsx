import type { FC } from 'react';
import { Network, Server, ShieldCheck, Zap } from 'lucide-react';

interface EspRoutingGraphProps {
  targetMx?: string;
  selectedSender?: string;
  selectedEsp?: string;
  deliverabilityBoost?: string;
}

export const EspRoutingGraph: FC<EspRoutingGraphProps> = ({
  targetMx = 'aspmx.l.google.com (Google Workspace)',
  selectedSender = '',
  selectedEsp = 'Google Workspace',
  deliverabilityBoost = '+28% Primary Tab Placement'
}) => {
  const isGoogle = targetMx.toLowerCase().includes('google');

  return (
    <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <Network className="h-4 w-4 text-indigo-400" />
          <span className="text-xs font-semibold text-white">Smartlead Dynamic ESP Routing Matrix</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            ESP-MATCHED
          </span>
        </div>
        <div className="text-[11px] font-mono text-emerald-400 font-bold bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-lg self-start sm:self-auto">
          {deliverabilityBoost}
        </div>
      </div>

      <div className="relative p-4 rounded-xl bg-slate-950/70 border border-slate-850 overflow-hidden">
        {/* Visual Architecture Flow */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
          {/* Node 1: Sender Fleet */}
          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-400 font-mono">1. Sender Inbox</span>
              <Server className="h-3.5 w-3.5 text-indigo-400" />
            </div>
            <div className="text-xs font-mono font-bold text-white truncate">{selectedSender}</div>
            <div className="flex items-center space-x-1.5 text-[10px] font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span className="text-emerald-400">{selectedEsp}</span>
            </div>
            <div className="text-[10px] text-slate-500 font-mono">
              Daily Limit: 14/35 emails (Paced)
            </div>
          </div>

          {/* Node 2: Smart Router Engine (Center) */}
          <div className="p-3 rounded-lg bg-indigo-950/30 border border-indigo-500/30 text-center space-y-1.5 shadow-lg shadow-indigo-950/20">
            <div className="flex items-center justify-center space-x-1 text-indigo-300 text-[11px] font-bold">
              <Zap className="h-3.5 w-3.5 text-indigo-400 animate-pulse" />
              <span>Smartlead ESP Matching</span>
            </div>
            <p className="text-[10px] text-slate-400">
              Analyzes MX DNS record in real time to match sender provider protocol
            </p>
            <div className="text-[10px] font-mono text-cyan-300 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-800/40 inline-block">
              {isGoogle ? 'Google ➜ Google Pipeline' : 'M365 ➜ M365 Pipeline'}
            </div>
          </div>

          {/* Node 3: Target MX Host */}
          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-400 font-mono">2. Recipient MX</span>
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            </div>
            <div className="text-xs font-mono font-bold text-white truncate">{targetMx}</div>
            <div className="flex items-center space-x-1.5 text-[10px] font-mono">
              <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
              <span className="text-cyan-400">Target Provider Detected</span>
            </div>
            <div className="text-[10px] text-slate-500 font-mono">
              Check SPF / DKIM / DMARC in Domain DNS
            </div>
          </div>
        </div>

        {/* Pacing Banner */}
        <div className="mt-3 pt-2.5 border-t border-slate-850 flex flex-wrap items-center justify-between text-[11px] text-slate-400 font-mono">
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-500">Anti-Clustering Pacing:</span>
            <span className="text-slate-300">12 min ± 3 min human jitter</span>
          </div>
          <div className="flex items-center space-x-1 text-emerald-400">
            <span>Primary Tab Placement Guaranteed</span>
          </div>
        </div>
      </div>
    </div>
  );
};
