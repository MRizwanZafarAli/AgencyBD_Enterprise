import { useState } from 'react';
import type { FC } from 'react';
import {
  Database, Play, RefreshCw, CheckCircle2,
  Sparkles, ArrowRight, ShieldCheck, Mail,
  AlertTriangle, Copy, Check, DollarSign, Cpu,
  BookmarkCheck, Layers, Terminal, UserCheck
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

const PRESET_PROSPECTS = [
  { first: 'Alex', last: 'Bouaziz', company: 'Deel', domain: 'deel.com', title: 'CEO & Co-Founder' },
  { first: 'Patrick', last: 'Collison', company: 'Stripe', domain: 'stripe.com', title: 'CEO & Co-Founder' },
  { first: 'Guillermo', last: 'Rauch', company: 'Vercel', domain: 'vercel.com', title: 'CEO' },
  { first: 'Matt', last: 'Mullenweg', company: 'Automattic', domain: 'automattic.com', title: 'Founder & CEO' }
];

export const WaterfallEnrich: FC<WaterfallEnrichProps> = ({
  initialFirst = '',
  initialLast = '',
  initialCompany = '',
  initialDomain = '',
  onBridgeToCopyCoach,
  setActiveTab
}) => {
  const [error, setError] = useState('');
  const [first, setFirst] = useState(initialFirst);
  const [last, setLast] = useState(initialLast);
  const [company, setCompany] = useState(initialCompany);
  const [domain, setDomain] = useState(initialDomain);
  const [title, setTitle] = useState('Chief Executive Officer');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WaterfallResult | null>(null);
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [crmSaved, setCrmSaved] = useState(false);
  const [savingCrm, setSavingCrm] = useState(false);

  const [prevProps, setPrevProps] = useState({ initialFirst, initialLast, initialCompany, initialDomain });
  if (
    prevProps.initialFirst !== initialFirst ||
    prevProps.initialLast !== initialLast ||
    prevProps.initialCompany !== initialCompany ||
    prevProps.initialDomain !== initialDomain
  ) {
    setPrevProps({ initialFirst, initialLast, initialCompany, initialDomain });
    if (initialFirst) setFirst(initialFirst);
    if (initialLast) setLast(initialLast);
    if (initialCompany) setCompany(initialCompany);
    if (initialDomain) setDomain(initialDomain);
  }

  const handleRunWaterfall = async () => {
    if (!domain.trim()) {
      setError('Corporate domain is required for the native waterfall sequence.');
      return;
    }
    setLoading(true);
    setError('');
    setCrmSaved(false);
    try {
      const res = await apiFetch('/api/native/waterfall_enrich', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: first.trim() || 'Executive',
          last_name: last.trim() || 'Leader',
          company_name: company.trim() || domain.split('.')[0],
          domain: domain.trim(),
          title: title.trim() || 'Decision Maker'
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the waterfall engine.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyEmail = (emailStr: string) => {
    navigator.clipboard.writeText(emailStr);
    setCopiedEmail(true);
    setTimeout(() => setCopiedEmail(false), 2000);
  };

  const handleSaveToCrm = async () => {
    if (!result) return;
    setSavingCrm(true);
    try {
      const res = await apiFetch('/api/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: company || result.company || domain,
          domain: domain || result.domain,
          source_channel: result.catch_all_decoded ? 'waterfall_decoded_catchall' : 'native_waterfall',
          notes: `ENRICHED LEAD: ${result.prospect_name} (${title}) | Email: ${result.resolved_email} | Confidence: ${result.confidence_score}% | Stack: ${result.autonomous_research_dossier?.detected_stack?.slice(0, 3).join(', ')}`
        })
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(apiErrorMessage(res.status, d));
      }
      setCrmSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save lead to CRM.');
    } finally {
      setSavingCrm(false);
    }
  };

  const applyPreset = (p: typeof PRESET_PROSPECTS[0]) => {
    setFirst(p.first);
    setLast(p.last);
    setCompany(p.company);
    setDomain(p.domain);
    setTitle(p.title);
  };

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      <ErrorBanner message={error} />

      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2.5">
            <span className="bg-gradient-to-r from-indigo-400 via-cyan-400 to-emerald-400 bg-clip-text text-transparent">
              Native Waterfall Enrichment & Catch-All Decoder
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold tracking-wider">
              100% FREE / ZERO CLAY CREDITS
            </span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-3xl leading-relaxed">
            Multi-tier autonomous intelligence combining DNS MX auditing, statistical corporate permutation matrices,
            socket-level SMTP verification, and the breakthrough <span className="text-indigo-300 font-semibold">Sovereign Catch-All Decoder</span> using Gravatar & OpenPGP identity footprints.
          </p>
        </div>

        {/* Live Savings Counter */}
        <div className="glass-panel px-4 py-2.5 rounded-xl border border-emerald-500/30 bg-emerald-950/20 flex items-center space-x-3 shrink-0">
          <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400">
            <DollarSign className="h-5 w-5" />
          </div>
          <div>
            <div className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider font-semibold">
              Commercial SaaS Saved
            </div>
            <div className="text-base font-bold text-white font-mono">
              ${result?.estimated_commercial_dollars_saved?.toFixed(2) || '4.50'} / lead
            </div>
          </div>
        </div>
      </div>

      {/* Quick Presets Bar */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs text-slate-400">
        <span className="font-semibold text-slate-300 shrink-0 flex items-center space-x-1">
          <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
          <span>Quick 1-Click Presets:</span>
        </span>
        {PRESET_PROSPECTS.map((p, idx) => (
          <button
            key={idx}
            onClick={() => applyPreset(p)}
            className="px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 hover:text-white border border-slate-700/60 transition-all shrink-0 font-mono text-[11px]"
          >
            {p.company} ({p.first})
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Input Parameters Panel */}
        <div className="lg:col-span-5 glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Database className="h-4 w-4 text-indigo-400" />
              <h3 className="text-sm font-semibold text-white">Target Lead Parameters</h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">Step 1 of 2</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 font-medium">First Name</label>
              <input
                value={first}
                placeholder="Alex"
                onChange={(e) => setFirst(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none transition-colors"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 font-medium">Last Name</label>
              <input
                value={last}
                placeholder="Bouaziz"
                onChange={(e) => setLast(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none transition-colors"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 font-medium">Company Name</label>
              <input
                value={company}
                placeholder="Deel"
                onChange={(e) => setCompany(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none transition-colors"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 font-medium">Target Domain</label>
              <input
                value={domain}
                placeholder="deel.com"
                onChange={(e) => setDomain(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none transition-colors font-mono"
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-400 font-medium">Executive Title</label>
            <input
              value={title}
              placeholder="Chief Executive Officer"
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none transition-colors"
            />
          </div>

          {/* Sourcing Info Box */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5 text-xs text-slate-400">
            <div className="text-[11px] font-semibold text-slate-300 flex items-center space-x-1.5">
              <Layers className="h-3.5 w-3.5 text-cyan-400" />
              <span>Autonomous 5-Tier Verification Stack</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              1. DNS MX Lookup → 2. Permutation Generator → 3. Deep Socket Handshake → 4. Catch-All Decoder (Gravatar/OpenPGP) → 5. Claygent Tech Stack Fingerprint.
            </p>
          </div>

          <button
            onClick={handleRunWaterfall}
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/20 active:scale-[0.99]"
          >
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            <span>{loading ? 'Executing Multi-Tier Handshake...' : 'Execute Sovereign Waterfall Handshake'}</span>
          </button>
        </div>

        {/* Results Panel */}
        <div className="lg:col-span-7 glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <h3 className="text-sm font-semibold text-white">Verification & Enrichment Telemetry</h3>
            </div>
            {result && (
              <span className={`text-[11px] font-mono px-2.5 py-0.5 rounded-full border flex items-center space-x-1.5 font-bold ${
                result.confidence_score >= 80
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : result.confidence_score >= 60
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                  : 'bg-red-500/20 text-red-300 border-red-500/40'
              }`}>
                <span>{result.confidence_score}% CONFIDENCE</span>
              </span>
            )}
          </div>

          {result ? (
            <div className="space-y-4 text-xs">
              {/* Catch-All Decoder Alert Banner */}
              {result.catch_all_decoded && (
                <div className="p-3.5 rounded-xl bg-gradient-to-r from-purple-900/40 via-indigo-900/30 to-cyan-900/40 border border-purple-500/40 space-y-1 animate-pulse">
                  <div className="flex items-center space-x-2 text-purple-300 font-bold text-xs">
                    <Sparkles className="h-4 w-4 text-purple-400" />
                    <span>⚡ SOVEREIGN CATCH-ALL DECODER SUCCESS</span>
                  </div>
                  <p className="text-[11px] text-purple-200/90 leading-relaxed font-mono">
                    {result.decoder_evidence || 'Catch-all email server bypassed using social identity footprint confirmation.'}
                  </p>
                </div>
              )}

              {result.catch_all && !result.catch_all_decoded && (
                <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-500/30 flex items-start space-x-2 text-amber-300">
                  <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                  <div className="text-[11px]">
                    <span className="font-bold">Catch-All Domain Notice:</span> This mail server accepts all simulated RCPT test addresses. No social footprint match was found.
                  </div>
                </div>
              )}

              {/* Verified Result Card */}
              <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-700/80 space-y-3 shadow-inner">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div>
                    <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-semibold">Executive Contact</span>
                    <div className="font-bold text-white text-base flex items-center space-x-2">
                      <span>{result.prospect_name}</span>
                      <span className="text-xs text-indigo-300 font-normal">({title})</span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleCopyEmail(result.resolved_email)}
                      className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center space-x-1.5 text-xs font-mono transition-all"
                    >
                      {copiedEmail ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5 text-slate-400" />}
                      <span>{copiedEmail ? 'Copied' : 'Copy Email'}</span>
                    </button>
                    <button
                      onClick={handleSaveToCrm}
                      disabled={crmSaved || savingCrm}
                      className="px-2.5 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1.5 text-xs font-medium transition-all"
                    >
                      {crmSaved ? <BookmarkCheck className="h-3.5 w-3.5 text-emerald-400" /> : <UserCheck className="h-3.5 w-3.5" />}
                      <span>{crmSaved ? 'Saved in CRM' : 'Save to CRM'}</span>
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <div>
                    <span className="text-slate-400 text-[11px]">Verified Mailbox:</span>
                    <div className="font-mono text-emerald-400 font-bold text-sm flex items-center space-x-1.5 mt-0.5">
                      <Mail className="h-4 w-4 shrink-0 text-emerald-400" />
                      <span className="truncate">{result.resolved_email}</span>
                    </div>
                  </div>

                  <div>
                    <span className="text-slate-400 text-[11px]">ESP Infrastructure:</span>
                    <div className="font-mono text-indigo-300 font-semibold text-xs mt-1 flex items-center space-x-1.5">
                      <Cpu className="h-3.5 w-3.5 text-indigo-400" />
                      <span>{result.esp_provider}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Candidate Permutation Matrix */}
              {result.candidate_matrix && result.candidate_matrix.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
                      <Terminal className="h-3.5 w-3.5 text-indigo-400" />
                      <span>Evaluated Permutation Matrix</span>
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">Statistical Distribution</span>
                  </div>

                  <div className="border border-slate-800 rounded-xl overflow-hidden divide-y divide-slate-800/80 bg-slate-900/50">
                    {result.candidate_matrix.map((c, i) => (
                      <div key={i} className="px-3 py-2 flex items-center justify-between text-[11px] font-mono">
                        <div className="flex items-center space-x-2 truncate">
                          {c.is_primary ? (
                            <span className="px-1.5 py-0.5 rounded text-[9px] bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                              SELECTED
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 rounded text-[9px] bg-slate-800 text-slate-400">
                              ALT {i + 1}
                            </span>
                          )}
                          <span className={c.is_primary ? 'text-white font-semibold' : 'text-slate-400'}>
                            {c.email}
                          </span>
                        </div>

                        <div className="flex items-center space-x-2 shrink-0">
                          {c.gravatar_active ? (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1">
                              <Check className="h-3 w-3" />
                              <span>Gravatar Active</span>
                            </span>
                          ) : (
                            <span className="text-slate-500 text-[10px]">No avatar anchor</span>
                          )}
                          <button
                            onClick={() => handleCopyEmail(c.email)}
                            className="p-1 text-slate-400 hover:text-white"
                          >
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Claygent Autonomous Research Dossier */}
              {result.autonomous_research_dossier && (
                <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-indigo-300 flex items-center space-x-1.5">
                      <Cpu className="h-3.5 w-3.5 text-cyan-400" />
                      <span>Claygent Autonomous Intelligence Dossier</span>
                    </span>
                    <span className="text-[10px] font-mono text-emerald-400 font-semibold">
                      Tech Debt: {result.autonomous_research_dossier.tech_debt_score}/100
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {result.autonomous_research_dossier.detected_stack.map((tech, idx) => (
                      <span key={idx} className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 text-[10px] font-mono border border-slate-700/60">
                        {tech}
                      </span>
                    ))}
                  </div>

                  <div className="pt-2 text-[11px] text-slate-300 border-t border-slate-800/80">
                    <span className="text-slate-400 font-medium">Calculated Pitch Angle: </span>
                    <span className="text-indigo-200">{result.autonomous_research_dossier.custom_pitch_angle}</span>
                  </div>
                </div>
              )}

              {/* Verification Steps Trace */}
              <div className="space-y-1.5 pt-1">
                <div className="font-semibold text-slate-300 text-xs">Autonomous Execution Trace:</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                  {(result.steps_completed || result.waterfall_steps_executed || []).map((st, i) => (
                    <div key={i} className="flex items-center space-x-2 text-slate-400 text-[11px] bg-slate-900/40 p-1.5 rounded-lg border border-slate-800/50">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                      <span className="truncate">{st}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 1-Click Action Bridge to Copy Coach */}
              <div className="pt-3 border-t border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <button
                  onClick={() => setActiveTab('overview')}
                  className="text-xs text-slate-400 hover:text-white flex items-center space-x-1"
                >
                  <span>← Return to CRM Kanban</span>
                </button>

                <button
                  onClick={() => {
                    onBridgeToCopyCoach(first, company, domain);
                    setActiveTab('copycoach');
                  }}
                  className="px-4 py-2 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white rounded-xl text-xs font-semibold flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/25 active:scale-[0.98]"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>⚡ Draft High-Converting Pitch in Copy Coach</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-xs space-y-3 border border-dashed border-slate-800 rounded-2xl bg-slate-950/40 p-6 text-center">
              <div className="p-3 rounded-2xl bg-slate-900 border border-slate-800 text-slate-400">
                <Database className="h-8 w-8 text-indigo-400/80" />
              </div>
              <div className="space-y-1">
                <div className="font-semibold text-slate-300 text-sm">Ready for Zero-Cost Waterfall Verification</div>
                <p className="max-w-md text-slate-400 text-[11px] leading-relaxed">
                  Enter prospect parameters on the left or select a 1-click preset to run the DNS audit, permutation matrix, socket probe, and catch-all decoder.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
