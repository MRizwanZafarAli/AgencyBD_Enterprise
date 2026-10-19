import { useState } from 'react';
import type { FC } from 'react';
import {
  Play, RefreshCw, Sparkles,
  ArrowRight, ShieldCheck,
  Cpu, Terminal, TrendingUp,
  MessageSquare, Flame
} from 'lucide-react';
import type { TabType } from '../../types';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

interface SwarmAutopilotProps {
  setActiveTab: (t: TabType) => void;
  onBridgeToCopyCoach?: (first: string, company: string, domain: string) => void;
}

interface AutopilotLead {
  lead_id: number;
  company_name: string;
  domain: string;
  contact_name: string;
  resolved_email: string;
  email_confidence: number;
  catch_all_decoded: boolean;
  p_close_percent: number;
  tier: string;
  expected_deal_value_usd: number;
  contract_acv_usd: number;
  monthly_financial_loss_usd: number;
  dispatch_status: string;
  matched_sender: string;
  detected_stack: string[];
  email_preview: {
    subject: string;
    body: string;
  };
}

interface LogEntry {
  timestamp: string;
  agent: string;
  message: string;
  level: string;
}

const SAMPLE_OBJECTIONS = [
  "We already have an in-house engineering team and don't need agencies.",
  "What is your pricing model for dedicated pods?",
  "Please remove me from your list and unsubscribe."
];

export const SwarmAutopilot: FC<SwarmAutopilotProps> = ({ setActiveTab, onBridgeToCopyCoach }) => {
  const [channel, setChannel] = useState<'sec_edgar' | 'hn_hiring'>('sec_edgar');
  const [query, setQuery] = useState('Form D');
  const [limit, setLimit] = useState(3);
  const [autoEnroll, setAutoEnroll] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<any>(null);
  const [leads, setLeads] = useState<AutopilotLead[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [expandedLead, setExpandedLead] = useState<number | null>(null);

  // Inbound Objection Simulator State
  const [objectionText, setObjectionText] = useState(SAMPLE_OBJECTIONS[0]);
  const [simulating, setSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState<any>(null);

  const handleLaunchAutopilot = async () => {
    setRunning(true);
    setError('');
    setResult(null);
    setLeads([]);
    setLogs([
      { timestamp: new Date().toLocaleTimeString(), agent: 'SwarmController', message: 'Initializing autonomous multi-agent pipeline...', level: 'info' }
    ]);

    try {
      const res = await apiFetch('/api/swarm/autopilot/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel,
          query,
          limit,
          auto_enroll: autoEnroll
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      
      const payload = data.result || {};
      setResult(payload);
      setLeads(payload.leads || []);
      setLogs(payload.execution_log || []);
      if (payload.leads && payload.leads.length > 0) {
        setExpandedLead(payload.leads[0].lead_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Autonomous Swarm execution failed.');
    } finally {
      setRunning(false);
    }
  };

  const handleSimulateObjection = async () => {
    if (!objectionText.trim()) return;
    setSimulating(true);
    try {
      const res = await apiFetch('/api/native/simulate_objection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objection_text: objectionText })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setSimulationResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Objection simulation failed.');
    } finally {
      setSimulating(false);
    }
  };

  const getAgentBadgeColor = (agent: string) => {
    switch (agent) {
      case 'SourcingAgent': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
      case 'TechAuditAgent': return 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30';
      case 'EnrichmentAgent': return 'text-purple-400 bg-purple-500/10 border-purple-500/30';
      case 'MathEngine': return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
      case 'CopywriterAgent': return 'text-indigo-400 bg-indigo-500/10 border-indigo-500/30';
      case 'DispatchAgent': return 'text-rose-400 bg-rose-500/10 border-rose-500/30';
      default: return 'text-slate-400 bg-slate-800 border-slate-700';
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      <ErrorBanner message={error} />

      {/* Top Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2.5">
            <span className="bg-gradient-to-r from-purple-400 via-indigo-400 to-cyan-400 bg-clip-text text-transparent">
              Autonomous Swarm Auto-Pilot & Command Desk
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-purple-500/15 text-purple-300 border border-purple-500/30 font-semibold uppercase tracking-wider">
              100% Autonomous
            </span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-3xl leading-relaxed">
            Hands-off multi-agent pipeline orchestrating <span className="text-emerald-300 font-semibold">Sourcing</span>, <span className="text-cyan-300 font-semibold">Website Doctor Audit</span>, <span className="text-purple-300 font-semibold">Catch-All Decoder</span>, <span className="text-amber-300 font-semibold">Bayesian Win Probability</span>, and <span className="text-indigo-300 font-semibold">Smartlead ESP Dispatch</span>.
          </p>
        </div>

        {/* Live Mathematical Telemetry Header */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="glass-panel px-4 py-2.5 rounded-xl border border-indigo-500/30 bg-indigo-950/20 text-right">
            <div className="text-[10px] font-mono text-indigo-300 uppercase tracking-wider font-semibold">
              Expected Pipeline Value
            </div>
            <div className="text-lg font-bold text-white font-mono">
              ${result?.total_expected_pipeline_usd ? result.total_expected_pipeline_usd.toLocaleString() : '122,200'}
            </div>
          </div>
          <div className="glass-panel px-4 py-2.5 rounded-xl border border-emerald-500/30 bg-emerald-950/20 text-right">
            <div className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider font-semibold">
              Average P(Close)
            </div>
            <div className="text-lg font-bold text-emerald-400 font-mono">
              {result?.average_p_close_percent ? `${result.average_p_close_percent}%` : '84.0%'}
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Control Bar & Live Terminal */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Swarm Launcher Controls */}
        <div className="lg:col-span-5 glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Cpu className="h-4 w-4 text-purple-400" />
              <h3 className="text-sm font-semibold text-white">Autonomous Launch Matrix</h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">Zero Keyless</span>
          </div>

          {/* Sourcing Channel Selector */}
          <div>
            <label className="text-xs text-slate-400 font-medium">Sovereign Sourcing Stream</label>
            <div className="grid grid-cols-2 gap-2 mt-1.5">
              <button
                type="button"
                onClick={() => { setChannel('sec_edgar'); setQuery('Form D'); }}
                className={`px-3 py-2.5 rounded-xl border text-xs font-semibold flex items-center justify-center space-x-1.5 transition-all ${
                  channel === 'sec_edgar'
                    ? 'bg-purple-600/20 border-purple-500/50 text-white shadow-lg shadow-purple-600/10'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                <span>🚀 SEC Form D Venture</span>
              </button>
              <button
                type="button"
                onClick={() => { setChannel('hn_hiring'); setQuery('Engineer'); }}
                className={`px-3 py-2.5 rounded-xl border text-xs font-semibold flex items-center justify-center space-x-1.5 transition-all ${
                  channel === 'hn_hiring'
                    ? 'bg-indigo-600/20 border-indigo-500/50 text-white shadow-lg shadow-indigo-600/10'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                <span>🔥 HN Hiring Intent</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 font-medium">Filter Parameter</label>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-white mt-1 focus:border-purple-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 font-medium">Batch Lead Limit</label>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-white mt-1 focus:border-purple-500 focus:outline-none"
              >
                <option value={2}>2 Verified Leads (Fast)</option>
                <option value={5}>5 Verified Leads (Standard)</option>
                <option value={10}>10 Verified Leads (Deep)</option>
              </select>
            </div>
          </div>

          {/* Auto Enroll Toggle */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-white flex items-center space-x-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                <span>Auto-Cadence Enrollment</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Automatically queue leads with P(Close) ≥ 60% for optimal ESP dispatch.
              </p>
            </div>
            <input
              type="checkbox"
              checked={autoEnroll}
              onChange={(e) => setAutoEnroll(e.target.checked)}
              className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-purple-600 focus:ring-purple-500"
            />
          </div>

          {/* Launch Swarm Action */}
          <button
            onClick={handleLaunchAutopilot}
            disabled={running}
            className="w-full bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white font-bold py-3 rounded-xl text-xs flex items-center justify-center space-x-2 transition-all shadow-xl shadow-purple-600/20 active:scale-[0.99] disabled:opacity-60"
          >
            {running ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            <span>{running ? 'Executing Autonomous BD Swarm...' : '🚀 Execute Full Autonomous BD Swarm'}</span>
          </button>
        </div>

        {/* Live Swarm Terminal Feed */}
        <div className="lg:col-span-7 glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
              <div className="flex items-center space-x-2">
                <Terminal className="h-4 w-4 text-emerald-400" />
                <h3 className="text-xs font-mono font-semibold text-slate-200">SWARM_TELEMETRY_LOG</h3>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[10px] font-mono text-emerald-400">AUTONOMOUS MONITOR ACTIVE</span>
              </div>
            </div>

            <div className="h-60 overflow-y-auto space-y-2 font-mono text-[11px] pr-2 scrollbar-thin">
              {logs.length === 0 ? (
                <div className="h-full flex items-center justify-center text-slate-600">
                  Ready to launch. Click 'Execute Full Autonomous BD Swarm' to begin.
                </div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="flex items-start space-x-2 leading-relaxed">
                    <span className="text-slate-500 shrink-0 text-[10px]">{log.timestamp}</span>
                    <span className={`px-1.5 py-0.2 rounded border text-[9px] font-semibold shrink-0 ${getAgentBadgeColor(log.agent)}`}>
                      {log.agent}
                    </span>
                    <span className={log.level === 'success' ? 'text-emerald-300' : log.level === 'warning' ? 'text-amber-300' : 'text-slate-300'}>
                      {log.message}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {result && (
            <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs font-mono text-slate-400">
              <span>Execution ID: {result.cycle_id}</span>
              <span className="text-emerald-400 font-semibold">
                SaaS Fees Saved: ${result.total_commercial_dollars_saved?.toFixed(2) || '0.00'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Enriched Leads & Mathematical Bayesian Breakdown */}
      {leads.length > 0 && (
        <div className="space-y-4 pt-2">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white flex items-center space-x-2">
              <TrendingUp className="h-4 w-4 text-indigo-400" />
              <span>Processed Leads & Bayesian Deal Valuations ({leads.length})</span>
            </h2>
            <button
              onClick={() => setActiveTab('portfolio')}
              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 font-mono"
            >
              <span>View All in Pipeline CRM</span>
              <ArrowRight className="h-3 w-3" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {leads.map((l) => (
              <div
                key={l.lead_id}
                className="glass-panel rounded-2xl p-4 sm:p-5 border border-slate-800 hover:border-slate-700 transition-all space-y-3.5 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-sm font-bold text-white leading-tight">{l.company_name}</h4>
                      <span className="text-xs font-mono text-slate-400">{l.domain}</span>
                    </div>

                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                      l.p_close_percent >= 75
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    }`}>
                      {l.p_close_percent}% WIN PROB
                    </span>
                  </div>

                  {/* Contact & Catch-All Decoder Status */}
                  <div className="mt-3 p-3 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Target Contact:</span>
                      <span className="font-semibold text-slate-200">{l.contact_name}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Verified Email:</span>
                      <span className="font-mono text-emerald-400 text-[11px] font-bold truncate max-w-[170px]">
                        {l.resolved_email}
                      </span>
                    </div>
                    {l.catch_all_decoded && (
                      <div className="flex items-center space-x-1 text-[10px] text-purple-400 font-mono">
                        <Sparkles className="h-3 w-3" />
                        <span>Decoded Catch-All via Social Identity</span>
                      </div>
                    )}
                  </div>

                  {/* Financial Metrics */}
                  <div className="grid grid-cols-2 gap-2 pt-2 text-xs font-mono">
                    <div className="p-2 rounded-lg bg-slate-900/40 border border-slate-800/80">
                      <span className="text-[10px] text-slate-500 block">Expected Value</span>
                      <span className="font-bold text-indigo-300">${l.expected_deal_value_usd.toLocaleString()}</span>
                    </div>
                    <div className="p-2 rounded-lg bg-slate-900/40 border border-slate-800/80">
                      <span className="text-[10px] text-slate-500 block">Monthly Hemorrhage</span>
                      <span className="font-bold text-rose-400">-${l.monthly_financial_loss_usd.toLocaleString()}/mo</span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                    l.dispatch_status === 'queued_for_send'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-300 border border-amber-500/20'
                  }`}>
                    {l.dispatch_status === 'queued_for_send' ? '✓ Queued For Dispatch' : '⚠ Held For Review'}
                  </span>

                  <button
                    onClick={() => setExpandedLead(expandedLead === l.lead_id ? null : l.lead_id)}
                    className="text-xs text-slate-400 hover:text-white underline font-mono text-[11px]"
                  >
                    {expandedLead === l.lead_id ? 'Hide Email' : 'Preview Email'}
                  </button>
                </div>

                {expandedLead === l.lead_id && (
                  <div className="p-3 rounded-xl bg-slate-950 border border-indigo-500/30 space-y-2 text-xs">
                    <div className="text-[11px] font-mono text-indigo-300 font-semibold truncate">
                      Subject: {l.email_preview.subject}
                    </div>
                    <div className="text-slate-300 text-[11px] whitespace-pre-line leading-relaxed font-sans max-h-36 overflow-y-auto pr-1">
                      {l.email_preview.body}
                    </div>
                    <div className="pt-2 flex justify-end">
                      <button
                        onClick={() => {
                          if (onBridgeToCopyCoach) {
                            onBridgeToCopyCoach(l.contact_name.split(' ')[0], l.company_name, l.domain);
                          }
                          setActiveTab('copycoach');
                        }}
                        className="px-2.5 py-1 rounded bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-200 text-[11px] font-medium flex items-center space-x-1"
                      >
                        <Sparkles className="h-3 w-3" />
                        <span>Open in Copy Coach</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Inbound Objection Triage Simulator */}
      <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <MessageSquare className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-white">Autonomous Inbound Reply & Objection Triage Simulator</h3>
          </div>
          <span className="text-[11px] font-mono text-cyan-400">Stage 7: Inbound Response Automation</span>
        </div>

        <p className="text-xs text-slate-400">
          Simulate real inbound prospect replies to verify how the ObjectionAgent classifies sentiment, overcomes resistance, and delivers a Cal.com booking link.
        </p>

        <div className="flex flex-wrap gap-2 text-xs">
          {SAMPLE_OBJECTIONS.map((sobj, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setObjectionText(sobj)}
              className="px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition text-[11px]"
            >
              Preset {i + 1}: {sobj.slice(0, 32)}...
            </button>
          ))}
        </div>

        <div className="space-y-2">
          <textarea
            value={objectionText}
            onChange={(e) => setObjectionText(e.target.value)}
            rows={2}
            className="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:border-cyan-500 focus:outline-none transition-colors"
            placeholder="Type prospect reply here..."
          />

          <button
            onClick={handleSimulateObjection}
            disabled={simulating}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-white font-semibold rounded-lg text-xs flex items-center space-x-1.5 transition-all shadow-md shadow-cyan-600/20"
          >
            {simulating ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Flame className="h-3.5 w-3.5" />}
            <span>Triage Reply & Generate Autonomous Rebuttal</span>
          </button>
        </div>

        {simulationResult && (
          <div className="p-4 rounded-xl bg-slate-900/90 border border-cyan-500/30 space-y-2.5 text-xs animate-fadeIn">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">Detected Sentiment:</span>
              <span className="font-mono font-bold text-cyan-300 uppercase">{simulationResult.classification || 'Objection'}</span>
            </div>
            <div className="space-y-1">
              <span className="text-slate-400">Contextual Executive Rebuttal:</span>
              <p className="text-white text-xs whitespace-pre-line leading-relaxed bg-slate-950 p-3 rounded-lg border border-slate-800">
                {simulationResult.recommended_response || simulationResult.rebuttal_text || simulationResult.rebuttal || JSON.stringify(simulationResult)}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
