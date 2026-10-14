import { useState } from 'react';
import type { FC } from 'react';
import {
  Stethoscope, RefreshCw,
  Zap, FileText, CheckCircle2, AlertTriangle,
  Play
} from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';

export const WebsiteDoctor: FC = () => {
  const [domainInput, setDomainInput] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [city, setCity] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeSubTab, setActiveSubTab] = useState<'audit' | 'brief' | 'rescue'>('audit');
  const [auditResult, setAuditResult] = useState<any>(null);
  const [resolveResult, setResolveResult] = useState<any>(null);
  const [briefResult, setBriefResult] = useState<any>(null);
  const [rescueResult, setRescueResult] = useState<any>(null);

  const post = async (path: string, body: unknown) => {
    const res = await apiFetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
    return data;
  };

  const handleRunFullAnalysis = async () => {
    setLoading(true);
    setError('');
    setAuditResult(null);
    setBriefResult(null);
    setRescueResult(null);
    setResolveResult(null);
    try {
      // 1. Verify who the company is (a domain you type is checked, a name is searched and verified)
      const resolved = await post('/api/companies/resolve', { company_name: companyName || domainInput, hint_domain: domainInput || null });
      setResolveResult(resolved);

      // 2. Audit the verified site, then build the evidence-linked brief
      if (resolved.domain) {
        setAuditResult(await post('/api/audits/run', { domain: resolved.domain, company_id: resolved.company_id }));
        setBriefResult(await post(`/api/companies/${resolved.company_id}/brief`, {}));
      }

      // 3. Presence check: reports what it could and could not establish
      setRescueResult(await post('/api/companies/presence', { business_name: companyName || domainInput, city, domain: resolved.domain || domainInput || null }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <Stethoscope className="h-6 w-6 text-emerald-400" />
            <span>Website Doctor & Evidence Briefing</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              ZERO-FABRICATION EVIDENCE
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Full-spectrum audit across Performance, SEO, Security, AI-Readiness (GEO), and Accessibility. Every claim links to stored proof.
          </p>
        </div>
      </div>

      {/* Target Input Card */}
      <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-xs text-slate-400 font-medium">Target Company Name</label>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Company name"
              className="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono mt-1 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 font-medium">City (for local businesses)</label>
            <input
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. Austin, TX"
              className="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono mt-1 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 font-medium">Domain (optional, verified if given)</label>
            <input
              type="text"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              placeholder="e.g. example.com"
              className="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white font-mono mt-1 focus:border-emerald-500 focus:outline-none"
            />
          </div>
        </div>

        {error && <div role="alert" className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 text-xs text-amber-200">{error}</div>}
        {resolveResult && resolveResult.status !== 'resolved' && (
          <div role="status" className="p-3 rounded-xl bg-slate-900 border border-slate-700 text-xs text-slate-300">
            <strong>{resolveResult.status.replace('_', ' ')}.</strong> {resolveResult.note}
            {resolveResult.candidates?.length > 0 && (
              <div className="mt-1 font-mono text-[11px] text-slate-400">
                Closest: {resolveResult.candidates.map((c: any) => `${c.domain} (${Math.round(c.score * 100)}%)`).join(', ')}
              </div>
            )}
          </div>
        )}

        <button
          onClick={handleRunFullAnalysis}
          disabled={loading || (!companyName && !domainInput)}
          className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 rounded-xl text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-emerald-600/25"
        >
          {loading ? (
            <>
              <RefreshCw className="h-4 w-4 animate-spin" />
              <span>Verifying the company, auditing the site and collecting evidence...</span>
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              <span>Run Website Doctor Audit & Generate Company Brief</span>
            </>
          )}
        </button>
      </div>

      {/* Sub-Tabs Navigation */}
      <div className="flex border-b border-slate-800 space-x-2">
        <button
          onClick={() => setActiveSubTab('audit')}
          className={`pb-3 px-4 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
            activeSubTab === 'audit'
              ? 'border-emerald-400 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Stethoscope className="h-4 w-4" />
          <span>Website Doctor Diagnostic ({auditResult?.findings?.length || 0} Findings)</span>
        </button>
        <button
          onClick={() => setActiveSubTab('brief')}
          className={`pb-3 px-4 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
            activeSubTab === 'brief'
              ? 'border-indigo-400 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="h-4 w-4" />
          <span>Executive Brief & Pitch Kit</span>
        </button>
        <button
          onClick={() => setActiveSubTab('rescue')}
          className={`pb-3 px-4 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
            activeSubTab === 'rescue'
              ? 'border-cyan-400 text-cyan-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Zap className="h-4 w-4" />
          <span>Presence Rescue (No-Website Leads)</span>
        </button>
      </div>

      {/* Sub-Tab 1: Website Doctor Findings */}
      {activeSubTab === 'audit' && (
        <div className="space-y-4">
          {auditResult ? (
            <>
              {/* Score Ribbon */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="glass-panel rounded-2xl p-4 border border-slate-800 flex items-center justify-between">
                  <div>
                    <span className="text-xs text-slate-400">Overall Health Score</span>
                    <div className="text-3xl font-extrabold text-emerald-400 font-mono mt-0.5">
                      {auditResult.overall_score === null ? 'n/a' : `${auditResult.overall_score} / 100`}
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold font-mono">
                    {auditResult.overall_score === null ? '?' : auditResult.overall_score >= 80 ? 'A' : auditResult.overall_score >= 60 ? 'B' : 'C'}
                  </div>
                </div>

                <div className="glass-panel rounded-2xl p-4 border border-slate-800 flex items-center justify-between">
                  <div>
                    <span className="text-xs text-slate-400">Response time</span>
                    <div className="text-2xl font-extrabold text-white font-mono mt-0.5">
                      {auditResult.status === 'unreachable' ? 'n/a' : `${auditResult.response_time_ms} ms`}
                    </div>
                  </div>
                  <span className="text-xs font-mono text-cyan-400">{auditResult.status === 'unreachable' ? 'Unreachable' : 'Measured'}</span>
                </div>

                <div className="glass-panel rounded-2xl p-4 border border-slate-800 flex items-center justify-between">
                  <div>
                    <span className="text-xs text-slate-400">Diagnosed Issues</span>
                    <div className="text-2xl font-extrabold text-amber-400 font-mono mt-0.5">
                      {auditResult.findings_count} Items
                    </div>
                  </div>
                  <AlertTriangle className="h-5 w-5 text-amber-400" />
                </div>
              </div>

              {/* Findings List */}
              <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-3">
                <h3 className="text-sm font-semibold text-white">Categorized Diagnostic Findings & Remediation</h3>
                <div className="space-y-2.5">
                  {auditResult.findings.map((f: any, idx: number) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold ${
                              f.severity === 'critical'
                                ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                                : f.severity === 'high'
                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                            }`}
                          >
                            {f.severity}
                          </span>
                          <span className="font-semibold text-xs text-white">{f.finding}</span>
                        </div>
                        <span className="text-[10px] font-mono text-slate-500 uppercase">{f.category}</span>
                      </div>

                      <div className="text-xs text-slate-300 pl-1">
                        <span className="text-slate-500 font-medium">Fix: </span>
                        {f.fix}
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-850 font-mono">
                        <span>Impact: <strong className="text-slate-300">{f.estimated_impact}</strong></span>
                        <span className="text-emerald-400">Service: {f.service_id}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="glass-panel rounded-2xl p-8 border border-slate-800 text-center text-slate-400 text-xs">
              Click &quot;Run Website Doctor Audit&quot; above to inspect live performance, security, SEO, and AI-readiness.
            </div>
          )}
        </div>
      )}

      {/* Sub-Tab 2: Company Brief & Pitch Kit */}
      {activeSubTab === 'brief' && (
        <div className="space-y-4">
          {briefResult ? (
            <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-5">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-lg font-bold text-white">{briefResult.company_name}</h3>
                  <p className="text-xs text-slate-400 font-mono">{briefResult.domain || 'no verified website'} · status: {briefResult.status}</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  {briefResult.evidence_count} evidence items
                </span>
              </div>

              {briefResult.what_they_do && (
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-xs font-semibold text-emerald-300">What they say they do</span>
                  <p className="text-xs text-slate-200">{briefResult.what_they_do.text}</p>
                </div>
              )}

              {briefResult.pitch_kit ? (
                <>
                  <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                    <span className="text-xs font-semibold text-indigo-300">Recommended angle</span>
                    <p className="text-xs text-slate-200">{briefResult.pitch_kit.angle?.text || 'The audit found nothing serious enough to lead with. Look for another angle.'}</p>
                    <p className="text-[11px] font-mono text-slate-400">
                      Price band: {briefResult.pitch_kit.price_band || briefResult.pitch_kit.price_band_note}
                    </p>
                  </div>
                  <div className="space-y-2">
                    <span className="text-xs font-semibold text-slate-300">Talking points (each backed by a measurement)</span>
                    <ul className="space-y-1.5 text-xs text-slate-300 list-disc list-inside">
                      {briefResult.pitch_kit.talking_points.map((tp: any, i: number) => (
                        <li key={i}>{tp.text}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="space-y-2">
                    <span className="text-xs font-semibold text-amber-400">Objections to prepare for (generic checklist, not facts about this company)</span>
                    <ul className="space-y-1 text-xs text-slate-400 list-disc list-inside">
                      {briefResult.pitch_kit.objections_to_prepare_for.items.map((obj: string, i: number) => (
                        <li key={i}>{obj}</li>
                      ))}
                    </ul>
                  </div>
                </>
              ) : (
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300">
                  No pitch kit: {briefResult.status === 'unreachable' ? 'the site could not be reached, so nothing was measured.' : 'there is not enough verified information yet.'}
                  {briefResult.next_steps?.map((n: string, i: number) => <div key={i} className="mt-1 text-slate-400">• {n}</div>)}
                </div>
              )}

              {briefResult.signals?.length > 0 && (
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-cyan-300">Signals seen on the Radar</span>
                  {briefResult.signals.map((sg: any, i: number) => <div key={i} className="text-xs text-slate-300">• {sg.text}</div>)}
                </div>
              )}

              {briefResult.unknown?.length > 0 && (
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-400">
                  <strong className="text-slate-300">Not established:</strong> {briefResult.unknown.join(', ')}. These are left blank rather than estimated.
                </div>
              )}

              {briefResult.evidence?.length > 0 && (
                <details className="text-[11px] text-slate-400">
                  <summary className="cursor-pointer text-slate-300">Evidence behind this brief</summary>
                  <ul className="mt-2 space-y-1 font-mono">
                    {briefResult.evidence.map((e: any) => (
                      <li key={e.id}>#{e.id} {e.claim} <span className="text-slate-500">({e.source_url}, {e.observed_at})</span></li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          ) : (
            <div className="glass-panel rounded-2xl p-8 border border-slate-800 text-center text-slate-400 text-xs">
              Run the analysis above to generate the evidence-linked executive brief.
            </div>
          )}
        </div>
      )}

      {/* Sub-Tab 3: Presence Rescue */}
      {activeSubTab === 'rescue' && (
        <div className="space-y-4">
          {rescueResult ? (
            <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-5">
              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-sm font-semibold text-white">Web presence check</h3>
                  <p className="text-xs text-slate-400">{rescueResult.verified ? 'Verified result.' : 'Not verified. Treat as a lead to confirm, not a fact.'} Confidence {Math.round(rescueResult.confidence * 100)}%.</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-mono uppercase bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold">
                  {rescueResult.classification.replace(/_/g, ' ')}
                </span>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-300">Checks performed</span>
                {rescueResult.checks_performed.map((c: any, i: number) => (
                  <div key={i} className="text-[11px] font-mono text-slate-400">• {c.check}: {c.outcome}</div>
                ))}
              </div>
              {rescueResult.limitations?.map((l: string, i: number) => (
                <div key={i} className="text-[11px] text-amber-300">⚠ {l}</div>
              ))}

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                <div className="text-xs font-bold text-emerald-400 uppercase tracking-wider">{rescueResult.offer?.service}</div>
                <div className="text-xs text-slate-300 font-mono">
                  Price band: <strong className="text-white">{rescueResult.offer?.price_band || rescueResult.offer?.price_note}</strong>
                </div>
                {rescueResult.offer?.components?.map((c: string, idx: number) => (
                  <div key={idx} className="flex items-center space-x-2 text-xs text-slate-400">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    <span>{c}</span>
                  </div>
                ))}
              </div>

              <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/30 space-y-1.5">
                <span className="text-[11px] font-mono text-indigo-300 uppercase font-bold">Phone / email opener (states only what we checked):</span>
                <p className="text-xs text-slate-200 italic">&quot;{rescueResult.offer?.cold_call_hook}&quot;</p>
              </div>
            </div>
          ) : (
            <div className="glass-panel rounded-2xl p-8 border border-slate-800 text-center text-slate-400 text-xs">
              Run the analysis above to check web presence.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
