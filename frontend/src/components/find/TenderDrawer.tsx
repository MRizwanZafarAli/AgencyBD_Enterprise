import { useEffect, useState } from 'react';
import type { FC } from 'react';
import {
  AlertTriangle,
  BellPlus,
  Building2,
  Calendar,
  CheckCircle2,
  ClipboardCheck,
  Copy,
  Download,
  ExternalLink,
  FileText,
  HelpCircle,
  Mail,
  Phone,
  ShieldCheck,
  Sparkles,
  Users,
  X,
  Zap,
} from 'lucide-react';
import { Badge, Button, Card } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';

export interface TenderOpportunity {
  id: number;
  type: string;
  source: string;
  title: string;
  description: string;
  company_name?: string | null;
  url?: string | null;
  budget_max?: number | null;
  currency?: string;
  deadline?: string | null;
  posted_at?: string | null;
  fit_score?: number | null;
  fit_reasons?: string[];
  skills_required?: string[];
  risk_flags?: string[];
  status?: string;
  metadata?: {
    language?: string;
    country?: string;
    locality?: string;
    buyer_email?: string;
    buyer_phone?: string;
    buyer_contact_name?: string;
    notice_stage?: 'pin' | 'rfp' | 'framework' | 'award';
    cpv_codes?: string[];
    lots_count?: number;
    incumbent?: string;
    award_date?: string;
  };
}

interface ScorecardCheck {
  name: string;
  status: 'pass' | 'warn' | 'fail';
  detail: string;
}

interface BidScorecard {
  verdict: 'GO' | 'CONDITIONAL' | 'NO-GO';
  score: number;
  days_left: number | null;
  checks: ScorecardCheck[];
  mega_tender_teaming: { is_mega: boolean; strategy: string };
  pin_early_access: { is_pin: boolean; tip: string };
  renewal_tracker: { is_award: boolean; incumbent: string; award_date: string; tip: string };
}

interface ComplianceItem {
  id: string;
  category: string;
  requirement: string;
  mandatory: boolean;
  weight: string;
}

export const TENDER_SOURCE_LABELS: Record<string, string> = {
  ted: 'TED (EU)',
  uk_fts: 'UK Find a Tender',
  uk_cf: 'UK Contracts Finder',
  sam_gov: 'SAM.gov (US)',
  ungm: 'UNGM (UN)',
};

export const TenderDrawer: FC<{
  tender: TenderOpportunity | null;
  onClose: () => void;
  onOpenClient?: (leadId: number) => void;
  onSendEmail?: (params: {
    recipient: string;
    recipientName?: string;
    companyName?: string;
    subject?: string;
    body?: string;
  }) => void;
}> = ({ tender, onClose, onOpenClient, onSendEmail }) => {
  const [scorecard, setScorecard] = useState<BidScorecard | null>(null);
  const [loadingScore, setLoadingScore] = useState(false);
  const [matrix, setMatrix] = useState<ComplianceItem[]>([]);
  const [loadingMatrix, setLoadingMatrix] = useState(false);
  const [artifact, setArtifact] = useState<{ title: string; content: string } | null>(null);
  const [loadingArtifact, setLoadingArtifact] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!tender) return;
    setScorecard(null);
    setMatrix([]);
    setArtifact(null);
    setNotice('');
    setError('');
    setLoadingScore(true);
    apiFetch(`/api/tenders/${tender.id}/scorecard`, { method: 'POST' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setScorecard(d); })
      .catch(() => {})
      .finally(() => setLoadingScore(false));
  }, [tender]);

  if (!tender) return null;

  const meta = tender.metadata || {};
  const buyerName = tender.company_name || 'Contracting Authority';
  const cpvs = meta.cpv_codes || tender.skills_required || [];

  const parseCompliance = async () => {
    setLoadingMatrix(true);
    setError('');
    try {
      const res = await apiFetch(`/api/tenders/${tender.id}/compliance-matrix`, { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      setMatrix(body.items || []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingMatrix(false);
    }
  };

  const generateBidDoc = async (action: 'executive_summary' | 'clarification_qa') => {
    setLoadingArtifact(true);
    setError('');
    try {
      const res = await apiFetch(`/api/tenders/${tender.id}/bid-actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      setArtifact(body);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingArtifact(false);
    }
  };

  const addToBidPipeline = async () => {
    const res = await apiFetch(`/api/opportunities/${tender.id}/convert_to_lead`, { method: 'POST' });
    const body = await res.json().catch(() => ({}));
    if (res.ok) {
      setNotice(`Added "${buyerName}" to Bid Pipeline / Clients (Deadline tracked: ${(tender.deadline || 'TBD').slice(0, 10)}).`);
      if (body.lead_id && onOpenClient) onOpenClient(body.lead_id);
    } else {
      setError(apiErrorMessage(res.status, body));
    }
  };

  const watchBuyerOrCpv = async (mode: 'buyer' | 'cpv') => {
    const q = mode === 'buyer' ? buyerName : (cpvs[0] || '72200000');
    const res = await apiFetch('/api/leadfinder/searches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: mode === 'buyer' ? `Watch Authority: ${buyerName.slice(0, 40)}` : `Watch CPV: ${q}`,
        source: 'hiring',
        params: { q },
        notify: true,
        every_hours: 24,
      }),
    });
    if (res.ok) {
      setNotice(`Watching "${q}" — new notices & deadline alerts will appear in your Watching tab.`);
    }
  };

  const exportMatrixCsv = () => {
    if (!matrix.length) return;
    const rows = ['Category,Requirement,Mandatory,Weight'].concat(
      matrix.map((m) => `${m.category},"${m.requirement.replace(/"/g, '""')}",${m.mandatory ? 'Yes' : 'No'},${m.weight}`),
    );
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `compliance-matrix-${tender.id}.csv`;
    a.click();
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-2xl bg-slate-950 border-l border-slate-800 h-full overflow-y-auto p-6 space-y-5 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge tone="accent">{TENDER_SOURCE_LABELS[tender.source] || tender.source}</Badge>
              {meta.country && <Badge>{meta.country}</Badge>}
              {meta.notice_stage === 'pin' && <Badge tone="good">Pre-Market PIN</Badge>}
              {meta.notice_stage === 'framework' && <Badge tone="neutral">Framework / DPS</Badge>}
              {meta.notice_stage === 'award' && <Badge tone="warn">Award Notice</Badge>}
            </div>
            <h2 className="text-lg font-semibold text-white leading-snug">{tender.title}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            aria-label="Close tender drawer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Structured Procurement Metadata Header */}
        <Card className="!bg-slate-900/70 space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-semibold text-white flex items-center gap-1.5">
              <Building2 className="h-4 w-4 text-indigo-400" />
              {buyerName}
            </span>
            <div className="flex flex-wrap gap-1.5">
              <Button small variant="secondary" onClick={() => watchBuyerOrCpv('buyer')}>
                <BellPlus className="h-3.5 w-3.5 text-emerald-400" />
                Watch Authority
              </Button>
              {cpvs[0] && (
                <Button small variant="secondary" onClick={() => watchBuyerOrCpv('cpv')}>
                  <BellPlus className="h-3.5 w-3.5 text-indigo-400" />
                  Watch {cpvs[0]}
                </Button>
              )}
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-2 text-xs text-slate-300">
            <div className="flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5 text-slate-400" />
              <span>Published: <strong>{(tender.posted_at || '—').slice(0, 10)}</strong></span>
            </div>
            <div className="flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5 text-amber-400" />
              <span>Submission Deadline: <strong className="text-white">{(tender.deadline || 'Rolling / Portal').slice(0, 10)}</strong></span>
            </div>
            <div>
              Contract Value: <strong className="text-white">
                {tender.budget_max ? `${tender.currency || 'GBP'} ${Number(tender.budget_max).toLocaleString()}` : 'Not stated'}
              </strong>
              {meta.lots_count && meta.lots_count > 1 ? ` · ${meta.lots_count} Lots` : ''}
            </div>
            <div>
              CPV / NAICS: <strong className="text-indigo-300">{cpvs.slice(0, 3).join(', ') || 'IT Services'}</strong>
            </div>
          </div>

          {/* Direct Contracting Authority Contact parsed from notice */}
          {(meta.buyer_email || meta.buyer_phone || tender.url) && (
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800 text-xs">
              {meta.buyer_email && (
                <button
                  type="button"
                  onClick={() => onSendEmail?.({
                    recipient: meta.buyer_email!,
                    recipientName: meta.buyer_contact_name || buyerName,
                    companyName: buyerName,
                    subject: `Clarification / Early Engagement: ${tender.title.slice(0, 70)}`,
                  })}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 border border-indigo-500/30"
                >
                  <Mail className="h-3.5 w-3.5" />
                  {meta.buyer_email}
                </button>
              )}
              {meta.buyer_phone && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300">
                  <Phone className="h-3.5 w-3.5" />
                  {meta.buyer_phone}
                </span>
              )}
              {tender.url && (
                <a
                  href={tender.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  Official Portal Notice
                </a>
              )}
            </div>
          )}
        </Card>

        {/* Enterprise Strategic Banners */}
        {scorecard?.mega_tender_teaming?.is_mega && (
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 flex items-start gap-2">
            <Users className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <strong>Mega-Tender Subcontractor / Teaming Angle:</strong> {scorecard.mega_tender_teaming.strategy}
            </div>
          </div>
        )}
        {scorecard?.pin_early_access?.is_pin && (
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 flex items-start gap-2">
            <Zap className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <strong>Early Access (PIN):</strong> {scorecard.pin_early_access.tip}
            </div>
          </div>
        )}
        {scorecard?.renewal_tracker?.is_award && (
          <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-xs text-indigo-300 flex items-start gap-2">
            <Sparkles className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
            <div>
              <strong>Incumbent &amp; Renewal Tracker:</strong>{' '}
              {scorecard.renewal_tracker.incumbent ? `Awarded to ${scorecard.renewal_tracker.incumbent}. ` : ''}
              {scorecard.renewal_tracker.tip}
            </div>
          </div>
        )}

        {/* AI Go / No-Go Bid Scorecard */}
        <Card className="!bg-slate-900/60 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-white flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              Go / No-Go Bid Scorecard
            </h3>
            {scorecard && (
              <Badge tone={scorecard.verdict === 'GO' ? 'good' : scorecard.verdict === 'CONDITIONAL' ? 'warn' : 'bad'}>
                {scorecard.verdict} · {scorecard.score}% Fit
              </Badge>
            )}
          </div>
          {loadingScore ? (
            <p className="text-xs text-slate-400">Evaluating eligibility, timeline &amp; scope fit…</p>
          ) : scorecard ? (
            <div className="grid sm:grid-cols-2 gap-2">
              {scorecard.checks.map((c) => (
                <div key={c.name} className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-white">{c.name}</span>
                    {c.status === 'pass' ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <AlertTriangle className={`h-3.5 w-3.5 ${c.status === 'warn' ? 'text-amber-400' : 'text-rose-400'}`} />
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 leading-snug">{c.detail}</p>
                </div>
              ))}
            </div>
          ) : null}
        </Card>

        {/* Notice Scope */}
        <div className="p-3.5 rounded-xl bg-slate-900/50 border border-slate-800 text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
          {tender.description || 'No detailed description provided in notice summary.'}
        </div>

        {/* 1-Click Compliance & Requirements Matrix */}
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button small variant="secondary" disabled={loadingMatrix} onClick={parseCompliance}>
              <ClipboardCheck className="h-3.5 w-3.5 text-indigo-400" />
              {loadingMatrix ? 'Parsing Tender Docs…' : 'Parse Tender Docs / Compliance Matrix'}
            </Button>
            {matrix.length > 0 && (
              <Button small variant="secondary" onClick={exportMatrixCsv}>
                <Download className="h-3.5 w-3.5" />
                Export Checklist CSV
              </Button>
            )}
          </div>

          {matrix.length > 0 && (
            <div className="rounded-xl border border-slate-800 divide-y divide-slate-800/80 bg-slate-900/40">
              {matrix.map((m) => (
                <div key={m.id} className="p-2.5 flex items-start justify-between gap-2 text-xs">
                  <div>
                    <span className="text-[10px] uppercase tracking-wider text-indigo-300 font-semibold">{m.category}</span>
                    <p className="text-slate-200 mt-0.5">{m.requirement}</p>
                  </div>
                  <Badge tone={m.mandatory ? 'warn' : 'neutral'}>{m.weight}</Badge>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Procurement-Specific Bid Studio Actions */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
          <Button small variant="primary" disabled={loadingArtifact} onClick={() => generateBidDoc('executive_summary')}>
            <FileText className="h-3.5 w-3.5" />
            Executive Summary &amp; Bid Outline
          </Button>
          <Button small variant="secondary" disabled={loadingArtifact} onClick={() => generateBidDoc('clarification_qa')}>
            <HelpCircle className="h-3.5 w-3.5 text-amber-400" />
            Draft Clarification Q&amp;A
          </Button>
          <Button small variant="secondary" onClick={addToBidPipeline}>
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            Add to Bid Pipeline
          </Button>
        </div>

        {artifact && (
          <Card className="!bg-slate-900/80 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">{artifact.title}</span>
              <Button
                small
                variant="secondary"
                onClick={() => {
                  navigator.clipboard?.writeText(artifact.content);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
              >
                <Copy className="h-3.5 w-3.5" />
                {copied ? 'Copied!' : 'Copy'}
              </Button>
            </div>
            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-sans leading-relaxed max-h-64 overflow-y-auto">
              {artifact.content}
            </pre>
          </Card>
        )}

        {notice && <p className="text-xs text-emerald-400">{notice}</p>}
        {error && <p className="text-xs text-rose-400">{error}</p>}
      </div>
    </div>
  );
};
