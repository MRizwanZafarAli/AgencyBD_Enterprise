import { useState } from 'react';
import type { FC } from 'react';
import {
  BarChart3, RefreshCw, FileText, CheckCircle2
} from 'lucide-react';
import type { CallIntelResult } from '../../types';
import { GongDialChart } from '../charts/GongDialChart';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

export const CallIntel: FC = () => {
  const [error, setError] = useState('');
  const [transcript, setTranscript] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CallIntelResult | null>(null);

  const handleAnalyzeCall = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/native/analyze_sales_call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript, founder_speaker_label: 'Me' })
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

  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
          <span>Gong Call Intelligence & Automated SOW</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            GONG.IO REPLACEMENT
          </span>
        </h1>
        <p className="text-sm text-slate-400 mt-0.5">
          Analyzes discovery call transcripts, tracks talk ratios, flags competitor battlecards, and synthesizes scoped SOWs without $1,400/rep/yr.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Transcript Input */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <BarChart3 className="h-5 w-5 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Call Transcript Input</h3>
          </div>

          <div>
            <label className="text-xs text-slate-400 font-medium">Sales Call Transcript</label>
            <textarea
              rows={9}
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg p-3 text-xs text-white font-mono leading-relaxed mt-1 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <button
            onClick={handleAnalyzeCall}
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/20"
          >
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
            <span>Analyze Call & Generate Proposal SOW</span>
          </button>
        </div>

        {/* Intelligence Output */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <h3 className="text-sm font-semibold text-white">Deal Telemetry & Proposal Scope</h3>

          {result ? (
            <div className="space-y-4 text-xs">
              {/* Talk Ratio Gauge */}
              <GongDialChart
                repPct={result.talk_ratio.rep_pct}
                prospectPct={result.talk_ratio.prospect_pct}
                questionsCount={result.questions_asked}
              />

              {/* Competitors & Pain Points */}
              <div className="space-y-2">
                {result.competitors_mentioned.length > 0 && (
                  <div className="flex items-center space-x-2">
                    <span className="text-slate-400">Competitors Flagged:</span>
                    {result.competitors_mentioned.map((comp, i) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 font-bold font-mono text-[10px]">
                        ⚠️ {comp}
                      </span>
                    ))}
                  </div>
                )}
                <div>
                  <div className="font-semibold text-slate-300 mb-1">Identified Pain Points:</div>
                  {result.pain_points.map((pt, i) => (
                    <div key={i} className="flex items-start space-x-2 text-slate-400">
                      <CheckCircle2 className="h-3.5 w-3.5 text-amber-400 mt-0.5 shrink-0" />
                      <span>{pt}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Synthesized SOW Box */}
              <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/30 space-y-2">
                <div className="flex items-center space-x-1.5 text-indigo-300 font-bold">
                  <FileText className="h-4 w-4" />
                  <span>Synthesized Proposal SOW</span>
                </div>
                <div className="text-slate-300 font-medium">{result.sow_draft.scope_of_work}</div>
                <div className="flex justify-between text-slate-400 pt-1 border-t border-indigo-500/20 text-[11px] font-mono">
                  <span>Timeline: {result.sow_draft.timeline_weeks} Weeks</span>
                  <span className="text-emerald-400 font-bold">{result.sow_draft.estimated_investment}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-48 flex flex-col items-center justify-center text-slate-500 text-xs space-y-2 border border-dashed border-slate-800 rounded-xl">
              <BarChart3 className="h-8 w-8 text-slate-600" />
              <span>Input conversation transcript and run intelligence</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
