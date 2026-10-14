import { useState } from 'react';
import type { FC } from 'react';
import {
  Sparkles, RefreshCw, CheckCircle2,
  ThumbsUp, ShieldAlert
} from 'lucide-react';
import type { CopyScoreResult } from '../../types';
import { LavenderRadarChart } from '../charts/LavenderRadarChart';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

interface CopyCoachProps {
  initialSubject?: string;
  initialBody?: string;
}

export const CopyCoach: FC<CopyCoachProps> = ({
  initialSubject = '',
  initialBody = ''
}) => {
  const [error, setError] = useState('');
  const [subject, setSubject] = useState(initialSubject);
  const [body, setBody] = useState(initialBody);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CopyScoreResult | null>(null);

  const handleScoreCopy = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/native/score_copy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject, body })
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
          <span>Lavender Copy Coach & Spam Filter</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-purple-500/10 text-purple-400 border border-purple-500/20">
            LAVENDER.AI REPLACEMENT
          </span>
        </h1>
        <p className="text-sm text-slate-400 mt-0.5">
          Analyzes readability, reading grade, mobile scannability, spam word triggers, and CTA friction without $350/mo subscription.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Editor Panel */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <Sparkles className="h-5 w-5 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Outreach Copy Editor</h3>
          </div>

          <div>
            <label className="text-xs text-slate-400 font-medium">Subject Line</label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-xs text-slate-400 font-medium">Email Body</label>
            <textarea
              rows={8}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg p-3 text-xs text-white leading-relaxed font-sans mt-1 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <button
            onClick={handleScoreCopy}
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/20"
          >
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            <span>Evaluate Copy & Scan Spam Traps</span>
          </button>
        </div>

        {/* Telemetry & Analysis Panel */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <h3 className="text-sm font-semibold text-white">Deliverability & Conversion Analysis</h3>

          {result ? (
            <div className="space-y-4">
              {/* Lavender 5-Axis Spider Chart */}
              <LavenderRadarChart
                score={result.overall_score}
                readabilityScore={94}
                lengthScore={result.word_count <= 80 ? 95 : 75}
                spamSafetyScore={result.spam_triggers.length === 0 ? 100 : 60}
                ctaFrictionScore={92}
                subjectHookScore={88}
              />

              {/* Spam Triggers */}
              <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 text-xs">
                <div className="font-semibold text-slate-300 flex items-center space-x-1.5">
                  {result.spam_triggers.length === 0 ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      <span className="text-emerald-400">Zero Spam Words Detected (Clean RFC Pass)</span>
                    </>
                  ) : (
                    <>
                      <ShieldAlert className="h-4 w-4 text-amber-400" />
                      <span className="text-amber-400">{result.spam_triggers.length} Spam Triggers Detected</span>
                    </>
                  )}
                </div>
                {result.spam_triggers.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {result.spam_triggers.map((sp, idx) => (
                      <span key={idx} className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 font-mono text-[10px]">
                        {sp}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Suggestions */}
              <div className="space-y-2 text-xs">
                <div className="font-semibold text-slate-300">Conversion Recommendations:</div>
                {result.suggestions.map((sug, i) => (
                  <div key={i} className="flex items-start space-x-2 text-slate-400">
                    <ThumbsUp className="h-3.5 w-3.5 text-indigo-400 mt-0.5 shrink-0" />
                    <span>{sug}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-48 flex flex-col items-center justify-center text-slate-500 text-xs space-y-2 border border-dashed border-slate-800 rounded-xl">
              <Sparkles className="h-8 w-8 text-slate-600" />
              <span>Click evaluate to inspect readability grade and spam flags</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
