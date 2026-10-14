import { useState } from 'react';
import type { FC } from 'react';
import {
  Database, Play, RefreshCw, CheckCircle2,
  Sparkles, ArrowRight, ShieldCheck, Mail
} from 'lucide-react';
import type { WaterfallResult, TabType } from '../../types';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

interface WaterfallEnrichProps {
  initialFirst?: string;
  initialLast?: string;
  initialCompany?: string;
  initialDomain?: string;
  onBridgeToCopyCoach: (first: string, company: string, domain: string) => void;
  setActiveTab: (t: TabType) => void;
}

export const WaterfallEnrich: FC<WaterfallEnrichProps> = ({
  initialFirst = '',
  initialLast = '',
  initialCompany = '',
  initialDomain = '',
  onBridgeToCopyCoach
}) => {
  const [error, setError] = useState('');
  const [first, setFirst] = useState(initialFirst);
  const [last, setLast] = useState(initialLast);
  const [company, setCompany] = useState(initialCompany);
  const [domain, setDomain] = useState(initialDomain);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WaterfallResult | null>(null);

  const handleRunWaterfall = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/native/waterfall_enrich', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: first,
          last_name: last,
          company_name: company,
          domain: domain,
          title: 'Chief Executive Officer'
        })
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
          <span>Native Waterfall Enrichment Studio</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            CLAY REPLACEMENT
          </span>
        </h1>
        <p className="text-sm text-slate-400 mt-0.5">
          Chains DNS MX discovery, corporate permutation matrices, and Port 25 SMTP socket handshakes without Clay credits.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Parameters Panel */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <Database className="h-5 w-5 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Target Lead Parameters</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 font-medium">First Name</label>
              <input
                value={first}
                onChange={(e) => setFirst(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 font-medium">Last Name</label>
              <input
                value={last}
                onChange={(e) => setLast(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 font-medium">Company Name</label>
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 font-medium">Corporate Domain</label>
              <input
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <button
            onClick={handleRunWaterfall}
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/20"
          >
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            <span>Execute Native Waterfall Handshake</span>
          </button>
        </div>

        {/* Results Panel */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Verification Telemetry</h3>
            {result && (
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1">
                <ShieldCheck className="h-3 w-3" />
                <span>{result.confidence_score}% CONFIDENCE</span>
              </span>
            )}
          </div>

          {result ? (
            <div className="space-y-4 text-xs">
              {/* Highlight Box */}
              <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-700 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Prospect:</span>
                  <span className="font-bold text-white text-sm">{result.prospect_name}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Verified Corporate Email:</span>
                  <span className="font-mono text-emerald-400 font-bold text-sm flex items-center space-x-1">
                    <Mail className="h-3.5 w-3.5" />
                    <span>{result.resolved_email}</span>
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">ESP Infrastructure:</span>
                  <span className="font-mono text-indigo-300 font-semibold">{result.esp_provider}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Catch-All Status:</span>
                  <span className={`font-mono font-semibold ${result.catch_all ? 'text-amber-400' : 'text-emerald-400'}`}>
                    {result.catch_all ? '⚠️ Catch-All Detected' : '✅ Verified Non-Catch-All'}
                  </span>
                </div>
              </div>

              {/* Execution Steps */}
              <div className="space-y-1.5">
                <div className="font-semibold text-slate-300 text-xs">Verification Trace:</div>
                {result.steps_completed.map((st, i) => (
                  <div key={i} className="flex items-center space-x-2 text-slate-400">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <span>{st}</span>
                  </div>
                ))}
              </div>

              {/* Bridge to Copy Coach */}
              <div className="pt-2 border-t border-slate-800 flex justify-end">
                <button
                  onClick={() => onBridgeToCopyCoach(first, company, domain)}
                  className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-all"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>⚡ 1-Click: Draft Personalized Pitch in Copy Coach</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ) : (
            <div className="h-48 flex flex-col items-center justify-center text-slate-500 text-xs space-y-2 border border-dashed border-slate-800 rounded-xl">
              <Database className="h-8 w-8 text-slate-600" />
              <span>Enter prospect details and execute handshake</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
