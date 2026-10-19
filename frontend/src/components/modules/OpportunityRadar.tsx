import { useState, useEffect } from 'react';
import type { FC } from 'react';
import {
  Radar, RefreshCw, CheckCircle2,
  DollarSign, Sparkles, XCircle, FileText
} from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ExternalLink } from '../shared/ClickableContact';

export const OpportunityRadar: FC = () => {
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedOpp, setSelectedOpp] = useState<any | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [proposalDraft, setProposalDraft] = useState<any | null>(null);
  const [draftError, setDraftError] = useState('');
  const [sources, setSources] = useState<any[]>([]);
  const [scanError, setScanError] = useState('');
  const [fit, setFit] = useState<Record<number, any>>({});
  const [fitBusy, setFitBusy] = useState<number | null>(null);
  const [fitError, setFitError] = useState('');

  const analyzeFit = async (opp: any) => {
    setFitBusy(opp.id);
    setFitError('');
    try {
      const res = await apiFetch(`/api/opportunities/${opp.id}/analyze`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) setFitError(apiErrorMessage(res.status, data));
      else setFit((f) => ({ ...f, [opp.id]: data }));
    } catch {
      setFitError('Could not reach the API.');
    } finally {
      setFitBusy(null);
    }
  };

  const fetchFeed = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/opportunities');
      const data = await res.json();
      setOpportunities(data);

      const apprRes = await apiFetch('/api/approvals/pending');
      const apprData = await apprRes.json();
      setPendingApprovals(apprData);
      await loadSources();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const loadSources = async () => {
    const res = await apiFetch('/api/connectors');
    if (res.ok) setSources(await res.json());
  };

  const connectUpwork = async () => {
    const res = await apiFetch('/api/connectors/upwork/authorize');
    const data = await res.json();
    if (!res.ok) {
      setScanError(apiErrorMessage(res.status, data));
      return;
    }
    window.open(data.authorize_url, '_blank', 'noopener');
  };

  useEffect(() => {
    // deferred so state updates happen after the first render, not synchronously inside the effect
    const t = setTimeout(fetchFeed, 0);
    return () => clearTimeout(t);
  }, []);

  const handleScanNow = async () => {
    setLoading(true);
    try {
      setScanError('');
      const res = await apiFetch('/api/radar/scan', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        setScanError(apiErrorMessage(res.status, data));
        return;
      }
      setOpportunities(data);
      await loadSources();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDraftProposal = async (opp: any) => {
    setSelectedOpp(opp);
    setDrafting(true);
    setDraftError('');
    setProposalDraft(null);
    try {
      const res = await apiFetch('/api/proposals/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ opportunity_id: opp.id, client_name: opp.company_name })
      });
      const data = await res.json();
      if (!res.ok) {
        setDraftError(apiErrorMessage(res.status, data));
        return;
      }
      setProposalDraft(data);

      // Refresh approvals list
      const apprRes = await apiFetch('/api/approvals/pending');
      const apprData = await apprRes.json();
      setPendingApprovals(apprData);
    } catch (e) {
      console.error(e);
      setDraftError('Could not reach the API.');
    } finally {
      setDrafting(false);
    }
  };

  const [inboxNotice, setInboxNotice] = useState('');

  const handleDecideApproval = async (approvalId: number, decision: string, appr?: any) => {
    try {
      setInboxNotice('');
      await apiFetch(`/api/approvals/${approvalId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, reason: `Decided via Human Approval Inbox (${decision})` })
      });
      // An approved outbound email is sent now, and every guard is re-checked at that moment.
      if (decision === 'approved' && appr?.subject_type === 'outbound_draft') {
        const sendRes = await apiFetch(`/api/outbound/drafts/${appr.subject_id}/send`, { method: 'POST' });
        const sendData = await sendRes.json();
        setInboxNotice(
          sendData.status === 'sent'
            ? `Sent to ${sendData.recipient_email}.`
            : `Not sent (${sendData.status}): ${sendData.reason || apiErrorMessage(sendRes.status, sendData)}`
        );
      }
      // Refresh pending list
      const apprRes = await apiFetch('/api/approvals/pending');
      const apprData = await apprRes.json();
      setPendingApprovals(apprData);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <Radar className="h-6 w-6 text-cyan-400" />
            <span>Opportunity Radar & Proposal Studio</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              ALL WORK SOURCES
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Ingests freelance contracts, public tenders (SAM.gov), and hiring signals. AI drafts proposal; human approves before send.
          </p>
        </div>
        <button
          onClick={handleScanNow}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold flex items-center space-x-2 shadow-lg shadow-cyan-600/25 transition-all self-start sm:self-auto"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Scan All Connectors Now</span>
        </button>
      </div>

      {/* Human-in-the-Loop Approval Inbox Banner */}
      {pendingApprovals.length > 0 && (
        <div className="p-5 rounded-2xl bg-indigo-950/40 border border-indigo-500/40 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-indigo-300 font-bold text-xs uppercase tracking-wider">
              <Sparkles className="h-4 w-4 text-indigo-400" />
              <span>Human Approval Inbox ({pendingApprovals.length} Pending Review)</span>
            </div>
            <span className="text-[11px] font-mono text-indigo-400">Policy: L1 Human Approval Required</span>
          </div>

          {inboxNotice && <div role="status" className="p-2.5 rounded-lg bg-slate-900 border border-slate-700 text-[11px] text-slate-200">{inboxNotice}</div>}
          <div className="space-y-2">
            {pendingApprovals.map((appr) => (
              <div
                key={appr.id}
                className="p-3.5 rounded-xl bg-slate-900 border border-slate-700/80 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <span className="text-[11px] font-mono text-slate-400 uppercase">
                    {appr.subject_type === 'outbound_draft'
                      ? `Email to ${appr.draft_recipient} (step ${appr.draft_step})`
                      : `Proposal #${appr.subject_id}`}
                  </span>
                  {appr.subject_type === 'outbound_draft' && (
                    <div className="text-slate-100 font-semibold text-[11px]">{appr.draft_subject}</div>
                  )}
                  <p className="text-slate-200 line-clamp-3 italic font-mono text-[11px] whitespace-pre-wrap">
                    &quot;{appr.proposal_body ?? appr.draft_body}&quot;
                  </p>
                </div>

                <div className="flex items-center space-x-2 shrink-0">
                  <button
                    onClick={() => handleDecideApproval(appr.id, 'approved', appr)}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center space-x-1 shadow-md shadow-emerald-600/20"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>Approve & Send</span>
                  </button>
                  <button
                    onClick={() => handleDecideApproval(appr.id, 'rejected', appr)}
                    className="px-3 py-1.5 rounded-lg bg-red-950/60 hover:bg-red-900/60 text-red-300 border border-red-500/30 flex items-center space-x-1"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    <span>Reject</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {fitError && <div role="alert" className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 text-xs text-amber-200">{fitError}</div>}
      {scanError && <div role="alert" className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 text-xs text-amber-200">{scanError}</div>}

      {/* Source status: what each source did on the last scan, never hidden */}
      <div className="glass-panel rounded-2xl p-4 border border-slate-800">
        <div className="text-xs font-semibold text-white mb-2">Sources</div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
          {sources.map((s) => {
            const state = s.last_run?.status ?? s.status ?? 'ready';
            const ok = state === 'ok' || state === 'ready' || state === 'connected';
            return (
              <div key={s.source} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] space-y-0.5">
                <div className="flex justify-between font-mono">
                  <span className="text-slate-200">{s.source}</span>
                  <span className={ok ? 'text-emerald-400' : state === 'error' ? 'text-red-400' : 'text-amber-300'}>{state.replace('_', ' ')}</span>
                </div>
                <div className="text-slate-500">
                  {s.last_run ? `${s.last_run.fetched} read, ${s.last_run.stored} kept` : 'not scanned yet'}
                  {s.automation_level === 'L1' ? ' · you submit' : ''}
                </div>
                {(s.last_run?.detail || s.detail) && <div className="text-amber-300/80 line-clamp-2">{s.last_run?.detail || s.detail}</div>}
                {s.source === 'upwork' && s.status === 'not_connected' && (
                  <button onClick={connectUpwork} className="text-cyan-400 hover:text-cyan-300 font-semibold">Connect Upwork</button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Grid: Feed + Proposal Studio */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Opportunities Feed */}
        <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Live Discovered Opportunities</h3>
            <span className="text-xs font-mono text-slate-400">{opportunities.length} Total</span>
          </div>

          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
            {opportunities.map((opp) => (
              <div
                key={opp.id}
                onClick={() => setSelectedOpp(opp)}
                className={`p-4 rounded-xl border transition-all cursor-pointer space-y-2 ${
                  selectedOpp?.id === opp.id
                    ? 'bg-slate-800/80 border-cyan-500/80 shadow-md'
                    : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-bold">
                    {opp.source} • {opp.type}
                  </span>
                  <div className="flex items-center space-x-1 text-emerald-400 font-mono text-xs font-bold">
                    <DollarSign className="h-3.5 w-3.5" />
                    <span>
                      {opp.budget_max
                        ? `${opp.type === 'hiring_signal' ? 'salary ' : 'budget '}${opp.currency || 'USD'} ${Math.round(opp.budget_max).toLocaleString()}`
                        : 'no amount stated'}
                    </span>
                  </div>
                </div>

                <h4 className="text-xs font-bold text-white leading-snug">{opp.title}</h4>
                <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">{opp.description}</p>
                {opp.risk_flags?.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {opp.risk_flags.map((f: string) => (
                      <span key={f} className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-300 border border-amber-500/20">{f.replace(/_/g, ' ')}</span>
                    ))}
                  </div>
                )}
                {opp.fit_reasons?.length > 0 && <div className="text-[10px] text-slate-500">{opp.fit_reasons[0]}</div>}

                <div className="flex items-center justify-between pt-1 border-t border-slate-850 text-[11px]">
                  <span className="text-indigo-300 font-mono" title={(opp.fit_reasons || []).join('\n')}>
                    Fit: {opp.fit_score === null || opp.fit_score === undefined ? 'n/a' : `${Math.round(opp.fit_score * 100)}%`}
                  </span>
                  {opp.url && (
                    <ExternalLink href={opp.url} className="text-slate-400 hover:text-white underline">
                      Open original
                    </ExternalLink>
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      analyzeFit(opp);
                    }}
                    disabled={fitBusy === opp.id}
                    className="text-slate-300 hover:text-white font-medium disabled:opacity-50"
                  >
                    {fitBusy === opp.id ? 'Analyzing…' : 'Should we chase this?'}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDraftProposal(opp);
                    }}
                    className="text-cyan-400 hover:text-cyan-300 font-semibold flex items-center space-x-1"
                  >
                    <Sparkles className="h-3 w-3" />
                    <span>Draft Winning Proposal</span>
                  </button>
                </div>
                {fit[opp.id] && (
                  <div className="mt-2 rounded-lg border border-slate-800 bg-slate-950/70 p-3 space-y-2 text-[11px] animate-pop">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded font-semibold uppercase tracking-wide ${fit[opp.id].verdict === 'pursue' ? 'bg-emerald-500/20 text-emerald-300' : fit[opp.id].verdict === 'skip' ? 'bg-rose-500/20 text-rose-300' : 'bg-amber-500/20 text-amber-300'}`}>{fit[opp.id].verdict}</span>
                      <span className="text-slate-300">{fit[opp.id].summary}</span>
                    </div>
                    {fit[opp.id].reasons.map((r: any) => (
                      <div key={r.point} className="text-slate-300"><span className="text-emerald-400">+</span> {r.point} <span className="text-slate-500">&ldquo;{r.quote}&rdquo;</span></div>
                    ))}
                    {fit[opp.id].risks.map((r: any) => (
                      <div key={r.point} className="text-slate-300"><span className="text-rose-400">!</span> {r.point} <span className="text-slate-500">&ldquo;{r.quote}&rdquo;</span></div>
                    ))}
                    {fit[opp.id].questions_to_ask.length > 0 && (
                      <div className="text-slate-400">Ask the client: {fit[opp.id].questions_to_ask.join(' · ')}</div>
                    )}
                    <div className="text-slate-600">Every point is backed by a quote from the post; unsupported points were removed ({fit[opp.id].unsupported_points_dropped}).</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Proposal Studio Drafter */}
        <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <FileText className="h-5 w-5 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Proposal Studio (Grounded RAG)</h3>
          </div>

          {selectedOpp ? (
            <div className="space-y-4">
              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs space-y-1">
                <span className="text-slate-400 font-medium">Selected Opportunity:</span>
                <div className="font-bold text-white">{selectedOpp.title}</div>
                <div className="text-[11px] text-slate-400 font-mono">Source: {selectedOpp.source}</div>
              </div>

              {drafting ? (
                <div className="p-8 text-center text-xs text-slate-400 flex flex-col items-center justify-center space-y-2">
                  <RefreshCw className="h-6 w-6 animate-spin text-indigo-400" />
                  <span>Retrieving portfolio proof assets and drafting 2 proposal variants...</span>
                </div>
              ) : proposalDraft ? (
                <div className="space-y-4 text-xs">
                  {/* Variant A */}
                  <div className="p-4 rounded-xl bg-slate-900/90 border border-indigo-500/40 space-y-2">
                    <div className="flex justify-between items-center text-indigo-300 font-bold">
                      <span>Variant A: {proposalDraft.variant_a?.focus}</span>
                      <span className="font-mono text-[10px] bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-500/30">
                        {proposalDraft.variant_a?.model}
                      </span>
                    </div>
                    <p className="text-slate-200 whitespace-pre-wrap font-mono text-[11px] leading-relaxed bg-slate-950 p-3 rounded-lg border border-slate-850">
                      {proposalDraft.variant_a?.body}
                    </p>
                    {proposalDraft.variant_a?.verification?.ok ? (
                      <div className="text-[11px] text-emerald-300">Verified: every figure and past-work claim traces to the job post or your case studies.</div>
                    ) : (
                      <div className="text-[11px] text-amber-300 space-y-1">
                        <div className="font-semibold">Rejected by the claim verifier (not queued for approval):</div>
                        {(proposalDraft.variant_a?.verification?.violations || []).map((x: string, i: number) => <div key={i}>• {x}</div>)}
                      </div>
                    )}
                  </div>

                  {/* Variant B */}
                  <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-750 space-y-2">
                    <div className="flex justify-between items-center text-cyan-300 font-bold">
                      <span>Variant B: {proposalDraft.variant_b?.focus}</span>
                      <span className="font-mono text-[10px] bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30">
                        {proposalDraft.variant_b?.model}
                      </span>
                    </div>
                    <p className="text-slate-200 whitespace-pre-wrap font-mono text-[11px] leading-relaxed bg-slate-950 p-3 rounded-lg border border-slate-850">
                      {proposalDraft.variant_b?.body}
                    </p>
                    {proposalDraft.variant_b?.verification?.ok ? (
                      <div className="text-[11px] text-emerald-300">Verified: every figure and past-work claim traces to the job post or your case studies.</div>
                    ) : (
                      <div className="text-[11px] text-amber-300 space-y-1">
                        <div className="font-semibold">Rejected by the claim verifier (not queued for approval):</div>
                        {(proposalDraft.variant_b?.verification?.violations || []).map((x: string, i: number) => <div key={i}>• {x}</div>)}
                      </div>
                    )}
                  </div>

                  <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-[11px] text-emerald-300 flex items-center space-x-2">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                    <span>
                      {proposalDraft.status === 'pending_human_approval'
                        ? 'Verified variants are in the Human Approval Inbox above. Nothing is submitted without you.'
                        : 'No variant passed verification. Edit the drafts or add more relevant case studies to your portfolio.'}
                    </span>
                  </div>
                </div>
              ) : (
                <>
                {draftError && (
                  <div role="alert" className="mb-3 p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 text-[11px] text-amber-200">{draftError}</div>
                )}
                <button
                  onClick={() => handleDraftProposal(selectedOpp)}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 rounded-xl text-xs flex items-center justify-center space-x-2 shadow-lg shadow-indigo-600/20 transition-all"
                >
                  <Sparkles className="h-4 w-4" />
                  <span>Synthesize Grounded Proposals</span>
                </button>
                </>
              )}
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-slate-400">
              Select any discovered opportunity on the left to draft a tailored proposal.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
