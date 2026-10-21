import { useState } from 'react';
import type { FC } from 'react';
import { Video, RefreshCw, Sparkles, Monitor, Mic } from 'lucide-react';
import type { VideoPitchStoryboard } from '../../types';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

export const MultimodalStudio: FC = () => {
  const [error, setError] = useState('');
  const [prospectName, setProspectName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [domain, setDomain] = useState('deel.com');
  const [lcpScore, setLcpScore] = useState<number | ''>('');
  const [proofPoint, setProofPoint] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VideoPitchStoryboard | null>(null);

  const handleGeneratePitch = async () => {
    if (!prospectName.trim() || !companyName.trim() || !domain.trim()) {
      setError('Please provide a Prospect Name, Company Name, and Target Domain.');
      return;
    }
    setLoading(true);
    try {
      const res = await apiFetch('/api/native/generate_video_storyboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prospect_name: prospectName.trim(),
          company_name: companyName.trim(),
          domain: domain.trim(),
          lcp_score: lcpScore === '' ? null : lcpScore,
          proof_point: proofPoint.trim() || null
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

  const loadSample = () => {
    setProspectName('Sarah Connor');
    setCompanyName('Cyberdyne Systems');
    setDomain('cyberdyne.io');
    setLcpScore(4.2);
    setProofPoint('Engineered a 68% LCP speedup for an enterprise SaaS platform, dropping TTFB to 140ms.');
    setError('');
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Multimodal Video Storyboard Studio</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-purple-500/10 text-purple-400 border border-purple-500/20">
              TAVUS / LOOM REPLACEMENT
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Generates personalized, high-converting video pitch scripts and visual action storyboards mapped to prospect websites.
          </p>
        </div>
        <button
          type="button"
          onClick={loadSample}
          className="self-start sm:self-auto px-3 py-1.5 rounded-xl border border-indigo-500/30 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 text-xs font-semibold flex items-center gap-1.5 transition"
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>Load Sample Target</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Parameters */}
        <div className="bento-tile specular-border rounded-2xl p-5 sm:p-6 space-y-4">
          <div className="flex items-center space-x-2">
            <Video className="h-5 w-5 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Prospect Teardown Targets</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 font-medium">Prospect Name *</label>
              <input
                value={prospectName}
                onChange={(e) => setProspectName(e.target.value)}
                placeholder="e.g. Sarah Connor"
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 font-medium">Company Name *</label>
              <input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Acme Corp"
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 font-medium">Target Website Domain *</label>
              <input
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="e.g. acme.com"
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 font-medium">Measured LCP in seconds (optional)</label>
              <input
                type="number"
                step="0.1"
                value={lcpScore}
                onChange={(e) => setLcpScore(e.target.value === '' ? '' : parseFloat(e.target.value))}
                placeholder="e.g. 3.8"
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-400 font-medium">Proof point from your portfolio (optional)</label>
            <input
              type="text"
              value={proofPoint}
              onChange={(e) => setProofPoint(e.target.value)}
              placeholder="e.g. We cut page load from 4.1s to 1.2s for a logistics client"
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <button
            onClick={handleGeneratePitch}
            disabled={loading || !prospectName.trim() || !companyName.trim() || !domain.trim()}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white font-semibold py-2.5 rounded-lg text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/20"
          >
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            <span>Synthesize 4-Scene Loom Storyboard</span>
          </button>
        </div>

        {/* Storyboard Output */}
        <div className="bento-tile specular-border rounded-2xl p-5 sm:p-6 space-y-4">
          <h3 className="text-sm font-semibold text-white">Storyboard Execution Blueprint</h3>

          {result ? (
            <div className="space-y-3 max-h-[460px] overflow-y-auto pr-1">
              {result.scenes.map((sc) => (
                <div key={sc.scene_number} className="p-3.5 bg-slate-900/90 rounded-xl border border-slate-800 space-y-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-indigo-300">Scene {sc.scene_number}: {sc.title}</span>
                    <span className="text-[10px] font-mono text-slate-500">~15 SEC</span>
                  </div>
                  <div className="flex items-start space-x-2 text-slate-400 text-[11px]">
                    <Monitor className="h-3.5 w-3.5 text-cyan-400 shrink-0 mt-0.5" />
                    <span><strong className="text-slate-300">Visual:</strong> {sc.visual_action}</span>
                  </div>
                  <div className="flex items-start space-x-2 text-slate-300 text-[11px] bg-slate-950/60 p-2 rounded-lg border border-slate-800/80 italic">
                    <Mic className="h-3.5 w-3.5 text-purple-400 shrink-0 mt-0.5" />
                    <span>{sc.script_audio}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-48 flex flex-col items-center justify-center text-slate-500 text-xs space-y-2 border border-dashed border-slate-800 rounded-xl">
              <Video className="h-8 w-8 text-slate-600" />
              <span>Enter target teardown metrics to synthesize storyboard</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
