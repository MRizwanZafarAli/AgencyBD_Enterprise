import { useState } from 'react';
import type { FC } from 'react';
import {
  BarChart3, RefreshCw, FileText, CheckCircle2, ShieldAlert,
  Zap, Copy, Check, MessageSquare, ChevronRight, HelpCircle
} from 'lucide-react';
import type { CallIntelResult } from '../../types';
import { GongDialChart } from '../charts/GongDialChart';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

interface ObjectionResult {
  matched: boolean;
  category: string;
  label: string;
  reframe: string;
  verbal_counter_script: string;
  grounded_portfolio_cite: string;
  bridge_question: string;
  all_categories?: { id: string; label: string }[];
}

const PRESET_OBJECTIONS = [
  { id: 'pricing', label: 'Price is too high / no budget', prompt: 'Your pricing is way too high and we do not have budget for this right now.' },
  { id: 'in_house_team', label: 'We have an in-house team', prompt: 'We already have 8 internal developers and we build everything in-house.' },
  { id: 'timing_not_now', label: 'Not a priority right now', prompt: 'We are too busy this quarter, check back with us next year.' },
  { id: 'send_info', label: 'Just email me some info', prompt: 'Can you just email me your brochure or slide deck?' },
  { id: 'competitor_comparison', label: 'Comparing to Toptal/offshore', prompt: 'Why should we work with you when we can hire developers on Toptal or Upwork for half the price?' },
];

export const CallIntel: FC = () => {
  const [activeTab, setActiveTab] = useState<'gong' | 'objections'>('gong');
  const [error, setError] = useState('');
  const [transcript, setTranscript] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CallIntelResult | null>(null);

  // Objection Simulator state
  const [customObjection, setCustomObjection] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [objectionResult, setObjectionResult] = useState<ObjectionResult | null>(null);
  const [copiedScript, setCopiedScript] = useState(false);

  const handleSimulateObjection = async (text: string) => {
    setSimulating(true);
    try {
      const res = await apiFetch('/api/native/simulate_objection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objection_text: text }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setError('');
      setObjectionResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the API.');
    } finally {
      setSimulating(false);
    }
  };

  const handleAnalyzeCall = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/native/analyze_sales_call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript, founder_speaker_label: 'Me' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setError('');
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the API.');
    } finally {
      setLoading(false);
    }
  };

  const copyScript = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedScript(true);
    setTimeout(() => setCopiedScript(false), 2000);
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />

      {/* Header and Mode Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Sales Intelligence & Deal Desk Hub</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              GONG & CHORUS REPLACEMENT
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Real-time discovery call telemetry, automated SOW scoping, and live psychological objection counter-scripts.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1 bg-slate-900/90 p-1 border border-slate-800 rounded-xl backdrop-blur-md self-start">
          <button
            onClick={() => setActiveTab('gong')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              activeTab === 'gong'
                ? 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-md shadow-indigo-600/25'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            <span>Call Telemetry & SOW</span>
          </button>
          <button
            onClick={() => {
              setActiveTab('objections');
              if (!objectionResult) {
                handleSimulateObjection(PRESET_OBJECTIONS[0].prompt);
              }
            }}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              activeTab === 'objections'
                ? 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-md shadow-indigo-600/25'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <Zap className="h-3.5 w-3.5" />
            <span>Objection Battlecards</span>
          </button>
        </div>
      </div>

      {/* TAB 1: Gong Call Analysis */}
      {activeTab === 'gong' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Transcript Input */}
          <div className="bento-tile p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <BarChart3 className="h-5 w-5 text-indigo-400" />
                <h3 className="text-sm font-semibold text-white">Call Transcript Input</h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                {transcript ? `${transcript.split(/\s+/).filter(Boolean).length} words` : '0 words'}
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs text-slate-400 font-medium">Sales Discovery Transcript</label>
                <button
                  type="button"
                  onClick={() => setTranscript(`Me: Thanks for taking the time today. I reviewed your web vitals before our call and noticed mobile LCP is around 3.8 seconds on 4G. How is that impacting inbound conversions?
Prospect: It's our primary bottleneck. We're running Next.js with an unoptimized bundle. Our marketing team is spending heavily on paid acquisition, and our bounce rate on product pages is nearly 65%. We estimate losing significant pipeline every month.
Me: That makes complete sense. Hydration bottlenecks often delay the main thread when SSR bundles grow. If we were to execute a 3-week edge architecture overhaul to guarantee sub-1.5s LCP, what would the approval process look like on your end?
Prospect: If you can guarantee sub-1.5s LCP with verified before-and-after Lighthouse audits, our engineering leadership has an allocated technical budget and we can approve an SOW this month.`)}
                  className="text-[11px] font-mono text-indigo-400 hover:text-indigo-300 flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-950/50 border border-indigo-700/50 hover:bg-indigo-900/50 transition cursor-pointer"
                >
                  <Zap className="h-3 w-3" />
                  <span>Insert Discovery Template</span>
                </button>
              </div>
              <textarea
                rows={10}
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="Paste discovery call transcript here, e.g.:&#10;Founder: What is currently holding back your mobile signups?&#10;Lead: The site is extremely sluggish on 4G and marketing spend is bouncing..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs text-slate-200 font-mono leading-relaxed focus:border-indigo-500 focus:outline-none placeholder:text-slate-600 transition"
              />
            </div>

            <button
              onClick={handleAnalyzeCall}
              disabled={loading || !transcript.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold py-3 rounded-xl text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/25 active:scale-[0.99] cursor-pointer"
            >
              {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
              <span>Analyze Call Telemetry & Generate Proposal SOW</span>
            </button>
          </div>

          {/* Intelligence Output */}
          <div className="bento-tile p-5 sm:p-6 space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center justify-between">
              <span>Deal Telemetry & Proposal Scope</span>
              {result && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  Analysis Complete
                </span>
              )}
            </h3>

            {result ? (
              <div className="space-y-4 text-xs">
                {/* Talk Ratio Gauge */}
                <GongDialChart
                  repPct={result.talk_ratio.rep_pct}
                  prospectPct={result.talk_ratio.prospect_pct}
                  questionsCount={result.questions_asked}
                />

                {/* Competitors & Pain Points */}
                <div className="space-y-3 pt-2 border-t border-slate-800/80">
                  {result.competitors_mentioned.length > 0 && (
                    <div className="flex items-center space-x-2">
                      <span className="text-slate-400">Competitors Flagged:</span>
                      {result.competitors_mentioned.map((comp, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 font-semibold font-mono text-[10px] border border-rose-500/30">
                          ⚠️ {comp}
                        </span>
                      ))}
                    </div>
                  )}
                  <div>
                    <div className="font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
                      <span>Identified Prospect Pain Points:</span>
                    </div>
                    <div className="space-y-1.5">
                      {result.pain_points.map((pt, i) => (
                        <div key={i} className="flex items-start space-x-2 text-slate-300 p-2 rounded-lg bg-slate-950/60 border border-slate-800/60">
                          <CheckCircle2 className="h-3.5 w-3.5 text-amber-400 mt-0.5 shrink-0" />
                          <span>{pt}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Synthesized SOW Box */}
                <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/30 space-y-2.5">
                  <div className="flex items-center space-x-1.5 text-indigo-300 font-bold">
                    <FileText className="h-4 w-4" />
                    <span>Synthesized Proposal Scope of Work (SOW)</span>
                  </div>
                  <div className="text-slate-200 font-medium leading-relaxed">{result.sow_draft.scope_of_work}</div>
                  <div className="flex justify-between items-center text-slate-400 pt-2 border-t border-indigo-500/20 text-[11px] font-mono">
                    <span>Estimated Timeline: {result.sow_draft.timeline_weeks} Weeks</span>
                    <span className="text-emerald-400 font-bold text-xs">{result.sow_draft.estimated_investment}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-72 flex flex-col items-center justify-center text-slate-500 text-xs space-y-2.5 border border-dashed border-slate-800 rounded-xl bg-slate-950/30">
                <BarChart3 className="h-8 w-8 text-slate-600 animate-pulse" />
                <span className="font-medium text-slate-400">Ready for discovery call analysis</span>
                <span className="text-[11px] text-slate-500 text-center max-w-xs">
                  Paste transcript on the left or click "Insert Discovery Template" to see live talk-to-listen ratios and SOW.
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Live Objection Simulator & Deal Desk */}
      {activeTab === 'objections' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Objection Selector & Input */}
          <div className="lg:col-span-5 bento-tile p-5 sm:p-6 space-y-5">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-amber-400" />
                <span>Simulate Prospect Objection</span>
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Select a common sales objection or type custom prospect resistance to retrieve the psychological reframe and verbatim script.
              </p>
            </div>

            {/* Quick Preset Buttons */}
            <div className="space-y-2">
              <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider font-semibold">Common Enterprise Objections:</span>
              <div className="space-y-1.5">
                {PRESET_OBJECTIONS.map((obj) => (
                  <button
                    key={obj.id}
                    onClick={() => {
                      setCustomObjection(obj.prompt);
                      handleSimulateObjection(obj.prompt);
                    }}
                    className={`w-full text-left px-3.5 py-2.5 rounded-xl text-xs transition flex items-center justify-between border cursor-pointer ${customObjection === obj.prompt ? 'border-indigo-500 bg-indigo-500/15 text-indigo-200 shadow-sm' : 'border-slate-800 bg-slate-950/60 text-slate-300 hover:border-slate-700 hover:bg-slate-900/60'}`}
                  >
                    <span className="font-medium">{obj.label}</span>
                    <ChevronRight className="h-3.5 w-3.5 text-slate-500" />
                  </button>
                ))}
              </div>
            </div>

            {/* Custom Input */}
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <label className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                <MessageSquare className="h-3.5 w-3.5 text-indigo-400" />
                <span>Custom Prospect Objection:</span>
              </label>
              <textarea
                rows={3}
                value={customObjection}
                onChange={(e) => setCustomObjection(e.target.value)}
                placeholder="e.g., 'We decided to hire a junior dev to do this internally next year...'"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 transition"
              />
              <button
                onClick={() => handleSimulateObjection(customObjection)}
                disabled={simulating || !customObjection.trim()}
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition shadow-md shadow-indigo-600/25 active:scale-[0.99] cursor-pointer"
              >
                {simulating ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
                <span>Generate Live Counter-Strategy</span>
              </button>
            </div>
          </div>

          {/* Strategy Output */}
          <div className="lg:col-span-7 bento-tile p-5 sm:p-6 space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Zap className="h-4 w-4 text-emerald-400" />
              <span>Challenger Counter-Script & Psychological Reframe</span>
            </h3>

            {objectionResult ? (
              <div className="space-y-4 text-xs">
                {/* Reframe Banner */}
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-1">
                  <div className="text-[10px] uppercase tracking-wider font-mono text-amber-400 font-bold">
                    Tactical Empathy Reframe: {objectionResult.label}
                  </div>
                  <div className="text-slate-200 font-medium leading-relaxed">
                    {objectionResult.reframe}
                  </div>
                </div>

                {/* Word-for-Word Script */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white flex items-center gap-1.5">
                      <MessageSquare className="h-3.5 w-3.5 text-indigo-400" />
                      <span>Verbatim Counter-Script (Say This):</span>
                    </span>
                    <button
                      onClick={() => copyScript(objectionResult.verbal_counter_script)}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-950/60 border border-indigo-700/50 text-[11px] font-mono text-indigo-300 hover:text-white transition cursor-pointer"
                    >
                      {copiedScript ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                      <span>{copiedScript ? 'Copied to Clipboard' : 'Copy Script'}</span>
                    </button>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 leading-relaxed font-sans text-xs">
                    "{objectionResult.verbal_counter_script}"
                  </div>
                </div>

                {/* Grounded Portfolio Proof */}
                <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
                  <div className="text-[10px] uppercase tracking-wider font-mono text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" /> Grounded Proof Point to Cite
                  </div>
                  <div className="text-slate-300">
                    {objectionResult.grounded_portfolio_cite}
                  </div>
                </div>

                {/* Bridge Question */}
                <div className="p-3.5 rounded-xl bg-indigo-950/25 border border-indigo-500/30 space-y-1">
                  <div className="text-[10px] uppercase tracking-wider font-mono text-indigo-400 font-semibold flex items-center gap-1">
                    <HelpCircle className="h-3 w-3" /> Conversational Bridge Question
                  </div>
                  <div className="text-white font-medium italic">
                    "{objectionResult.bridge_question}"
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-72 flex flex-col items-center justify-center text-slate-500 text-xs space-y-2 border border-dashed border-slate-800 rounded-xl bg-slate-950/30">
                <Zap className="h-8 w-8 text-slate-600 animate-pulse" />
                <span className="font-medium text-slate-400">Select an objection preset or type resistance</span>
                <span className="text-[11px] text-slate-500 text-center max-w-xs">
                  Generates instant psychological reframes, verbatim counter-phrases, and verified case study proof points.
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
