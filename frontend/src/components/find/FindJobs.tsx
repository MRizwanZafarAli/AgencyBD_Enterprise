import { matchesQuery } from '../../lib/textMatch';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { FC } from 'react';
import {
  RefreshCw,
  ExternalLink,
  Sparkles,
  Send,
  Mail,
  Copy,
  Check,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Compass,
  Building2,
  UserPlus,
  Cpu,
  ThumbsUp,
  ThumbsDown,
  Flame,
  Bell,
  Download,
  ChevronDown,
  ChevronRight,
  Video,
  Server,
} from 'lucide-react';
import { Badge, Button, Card, Drawer, EmptyState, Pager, ScoreBar, Select, Skeletons, SuggestInput, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { normalizeUrl } from '../../lib/urls';
import {
  buildLoomScript,
  detectCompanyStage,
  detectEngagementType,
  detectNoAgenciesRedFlag,
  extractCompanyIntel,
  formatBudgetOrEstimate,
  getFreshness,
} from './jobIntel';
import type { CompanyStageFilter, EngagementFilter, OppItem, PitchAngle } from './jobIntel';

type Opp = OppItem;

interface Source {
  source: string;
  status: string;
  detail?: string;
  requires_api_key: boolean;
  last_run: { status: string; fetched: number; stored: number; detail?: string } | null;
}

interface Variant {
  proposal_id?: number;
  body: string;
  focus?: string;
  verification?: { ok: boolean; violations?: string[] };
}

interface Draft {
  status: string;
  proposal_id?: number;
  proposal_ids?: { A?: number; B?: number };
  variant_a: Variant;
  variant_b: Variant;
  no_relevant_proof: boolean;
}

interface Fit {
  verdict: string;
  summary: string;
  reasons: Array<{ point: string; quote: string }>;
  risks: Array<{ point: string; quote: string }>;
  questions_to_ask: string[];
  unsupported_points_dropped: number;
  deterministic_fit_score?: number | null;
}

export interface BusinessOwner {
  name: string;
  title: string;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  verification_status?: string;
  rank?: number;
  source?: string;
}

export interface RelatedReadData {
  opportunity_id: number;
  company_name: string;
  domain: string;
  website_url?: string | null;
  business_owner: BusinessOwner;
  contacts: BusinessOwner[];
  detected_emails: string[];
  detected_phones: string[];
  detected_linkedins: string[];
  summary: string;
}

const PAGE = 15;
const TYPE_LABEL: Record<string, string> = {
  marketplace: 'Project',
  tender: 'Tender',
  hiring_signal: 'Hiring',
  inbound: 'Request',
  outbound: 'Outbound',
};

export interface JobsPreset {
  q: string;
  min_budget?: number | null;
  max_budget?: number | null;
  remote?: boolean;
  nonce: number;
}

export const FindJobs: FC<{
  mode?: 'jobs' | 'tender';
  types?: string[];
  preset?: JobsPreset | null;
  onSendEmail?: (params: {
    recipient: string;
    recipientName?: string;
    companyName?: string;
    subject?: string;
    body?: string;
    leadId?: number;
  }) => void;
  onOpenClient?: (leadId: number) => void;
  onOpenScraper?: (url: string, mode?: 'general' | 'client_audit' | 'job_spec' | 'local_audit', title?: string) => void;
}> = ({ mode = 'jobs', types = ['marketplace', 'hiring_signal', 'inbound', 'outbound'], preset, onSendEmail, onOpenClient, onOpenScraper }) => {
  const opps = useApi<Opp[]>('/api/opportunities?limit=200');
  const sources = useApi<Source[]>('/api/connectors');
  const [q, setQ] = useState('');
  const [source, setSource] = useState('');
  const [minFit, setMinFit] = useState(0);
  const [minBudget, setMinBudget] = useState('');
  const [maxBudget, setMaxBudget] = useState('');
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [engagement, setEngagement] = useState<EngagementFilter>('all');
  const [companyStage, setCompanyStage] = useState<CompanyStageFilter>('all');
  const [hideSeen, setHideSeen] = useState(false);
  const [groupCompanies, setGroupCompanies] = useState(mode !== 'tender');
  const [expandedCompanies, setExpandedCompanies] = useState<Set<string>>(new Set());
  const [showSources, setShowSources] = useState(false);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [watchNotice, setWatchNotice] = useState('');
  const [votes, setVotes] = useState<Record<number, 'up' | 'down' | null>>({});
  const [pitchAngle, setPitchAngle] = useState<PitchAngle>('staff_aug');
  const [loomScript, setLoomScript] = useState('');
  const [page, setPage] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [scanNote, setScanNote] = useState('');
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);
  const [error, setError] = useState('');
  const [open, setOpen] = useState<Opp | null>(null);
  const [fit, setFit] = useState<Fit | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState('');
  const [panelError, setPanelError] = useState('');

  // Proposal send state
  const [selectedVariant, setSelectedVariant] = useState<'A' | 'B'>('A');
  const [editedBody, setEditedBody] = useState('');
  const [sendChannel, setSendChannel] = useState<'email' | 'platform'>('platform');
  const [toEmail, setToEmail] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [sendSuccess, setSendSuccess] = useState('');
  const [copied, setCopied] = useState(false);

  // Related Read: Business Owner Details state
  const [relatedRead, setRelatedRead] = useState<RelatedReadData | null>(null);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedError, setRelatedError] = useState('');
  const [convertingLead, setConvertingLead] = useState(false);
  const [convertedLeadId, setConvertedLeadId] = useState<number | null>(null);
  const [convertSuccess, setConvertSuccess] = useState('');

  const seen = useRef(0);
  useEffect(() => {
    if (!preset || preset.nonce === seen.current) return;
    seen.current = preset.nonce;
    setQ(preset.q);
    setMinBudget(preset.min_budget ? String(preset.min_budget) : '');
    setMaxBudget(preset.max_budget ? String(preset.max_budget) : '');
    setRemoteOnly(!!preset.remote);
    setSource('');
    setMinFit(0);
    setPage(0);
  }, [preset]);

  const rows = useMemo(() => (opps.data ?? []).filter((o) => {
    const v = votes[o.id] !== undefined ? votes[o.id] : o.user_vote;
    if (types && !types.includes(o.type)) return false;
    if (source && o.source !== source) return false;
    if ((o.fit_score ?? 0) * 100 < minFit) return false;
    if (minBudget && (o.budget_max ?? -1) < Number(minBudget)) return false;
    if (maxBudget && (o.budget_max == null || o.budget_max > Number(maxBudget))) return false;
    if (remoteOnly && !/remote|anywhere|worldwide/i.test(`${o.title} ${o.description ?? ''}`)) return false;
    if (engagement !== 'all' && detectEngagementType(o) !== engagement) return false;
    if (companyStage !== 'all' && detectCompanyStage(o) !== companyStage) return false;
    if (hideSeen && (o.crm_status || v === 'down')) return false;
    return matchesQuery(`${o.title} ${o.company_name ?? ''} ${o.description ?? ''}`, q);
  }), [opps.data, types, source, minFit, q, minBudget, maxBudget, remoteOnly, engagement, companyStage, hideSeen, votes]);

  const companyCounts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const r of rows) {
      const key = (r.company_name || '').trim().toLowerCase();
      if (key && key !== 'unknown') map[key] = (map[key] || 0) + 1;
    }
    return map;
  }, [rows]);

  const groupedRows = useMemo(() => {
    if (!groupCompanies) return rows.map((r) => ({ item: r, siblings: [] as Opp[] }));
    const seenCo = new Map<string, { item: Opp; siblings: Opp[] }>();
    const out: Array<{ item: Opp; siblings: Opp[] }> = [];
    for (const r of rows) {
      const key = (r.company_name || '').trim().toLowerCase();
      if (!key || key === 'unknown') {
        out.push({ item: r, siblings: [] });
        continue;
      }
      const existing = seenCo.get(key);
      if (!existing) {
        const entry = { item: r, siblings: [] as Opp[] };
        seenCo.set(key, entry);
        out.push(entry);
      } else {
        existing.siblings.push(r);
      }
    }
    return out;
  }, [rows, groupCompanies]);

  const voteOpp = async (id: number, vote: 'up' | 'down') => {
    const cur = votes[id] !== undefined ? votes[id] : opps.data?.find((x) => x.id === id)?.user_vote;
    const next = cur === vote ? 'clear' : vote;
    setVotes((prev) => ({ ...prev, [id]: next === 'clear' ? null : next }));
    try {
      await send(`/api/opportunities/${id}/feedback`, 'POST', { vote: next });
    } catch { /* non-blocking */ }
  };

  const watchSearch = async () => {
    setWatchNotice('');
    try {
      await send('/api/leadfinder/searches', 'POST', {
        name: `${q || (mode === 'tender' ? 'Tenders' : 'Jobs & Projects')}${minFit ? ` (${minFit}%+)` : ''}`,
        source: source || 'remoteok',
        params: { query: q || '', min_fit: minFit },
        notify: true,
        every_hours: 1,
      });
      setWatchNotice('Saved to Watching with instant alerts.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save watch');
    }
  };

  const bulkSaveCrm = async () => {
    const ids = Array.from(picked);
    if (ids.length === 0) return;
    let savedCount = 0;
    for (const id of ids) {
      try {
        const res = await apiFetch(`/api/opportunities/${id}/convert_to_lead`, { method: 'POST' });
        if (res.ok) savedCount += 1;
      } catch { /* continue */ }
    }
    setPicked(new Set());
    setWatchNotice(`Saved ${savedCount}/${ids.length} opportunities to Clients CRM.`);
    opps.reload();
  };

  const exportCsv = () => {
    const targets = picked.size > 0 ? rows.filter((r) => picked.has(r.id)) : rows;
    const csvQ = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const csv = [
      ['title', 'company', 'source', 'fit_pct', 'budget', 'posted_at', 'url'],
      ...targets.map((r) => [r.title, r.company_name, r.source, r.fit_score != null ? Math.round(r.fit_score * 100) : '', formatBudgetOrEstimate(r).text, r.posted_at, r.url]),
    ].map((row) => row.map(csvQ).join(',')).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = `opportunities-${mode}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const sourceNames = useMemo(() => Array.from(new Set((opps.data ?? []).filter((o) => !types || types.includes(o.type)).map((o) => o.source))).sort(), [opps.data, types]);

  const detectedEmails = useMemo(() => {
    if (!open) return [];
    const text = `${open.title} ${open.description || ''}`;
    const matches = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g) || [];
    return Array.from(new Set(matches.map((e) => e.toLowerCase())));
  }, [open]);

  const poll = (runId: string) => {
    timer.current = window.setTimeout(async () => {
      try {
        const res = await apiFetch(`/api/autopilot/runs/${runId}`);
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
        const p = body.progress;
        if (p) setScanNote(`${p.processed ?? 0} of ${p.total ?? '?'} sources read. ${p.log?.[p.log.length - 1]?.message ?? ''}`);
        if (body.status === 'running') return poll(runId);
        setScanning(false);
        setScanNote('');
        if (body.status === 'failed') setError(body.error ?? 'The scan failed.');
        else { opps.reload(); sources.reload(); }
      } catch (e) {
        setScanning(false);
        setScanNote('');
        setError(e instanceof Error ? e.message : 'Lost contact with the server.');
      }
    }, 1500);
  };

  const scan = async () => {
    setScanning(true);
    setError('');
    setScanNote('Starting…');
    try {
      poll((await send<{ run_id: string }>('/api/radar/scan/start', 'POST')).run_id);
    } catch (e) {
      setScanning(false);
      setScanNote('');
      setError(e instanceof Error ? e.message : 'Scan failed');
    }
  };

  const connectUpwork = async () => {
    setError('');
    const res = await apiFetch('/api/connectors/upwork/authorize');
    const body = await res.json().catch(() => ({}));
    if (res.ok) window.open(body.authorize_url, '_blank', 'noopener');
    else setError(apiErrorMessage(res.status, body));
  };

  const openRow = (o: Opp) => {
    setOpen(o);
    setFit(null);
    setDraft(null);
    setPanelError('');
    setSendSuccess('');
    setEditedBody('');
    setSelectedVariant('A');
    setRelatedRead(null);
    setRelatedLoading(false);
    setRelatedError('');
    setConvertedLeadId(null);
    setConvertSuccess('');
    setLoomScript('');
    const stg = detectCompanyStage(o);
    const eng = detectEngagementType(o);
    setPitchAngle(stg === 'agency_partner' ? 'white_label' : eng === 'direct_project' || eng === 'contract_c2c' ? 'fixed_scope' : 'staff_aug');
    const text = `${o.title} ${o.description || ''}`;
    const matches = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g) || [];
    const unique = Array.from(new Set(matches.map((e) => e.toLowerCase())));
    setToEmail(unique.length > 0 ? unique[0] : '');
    setEmailSubject(`Proposal: ${o.title}`);
    setSendChannel(unique.length > 0 ? 'email' : 'platform');
    handleRelatedRead(o.id);
  };

  const handleRelatedRead = async (oppId?: number) => {
    const targetId = oppId ?? open?.id;
    if (!targetId) return;
    setRelatedLoading(true);
    setRelatedError('');
    try {
      const res = await apiFetch(`/api/opportunities/${targetId}/related_read`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setRelatedRead(data as RelatedReadData);
      if (data.business_owner?.email && !toEmail) {
        setToEmail(data.business_owner.email);
      }
    } catch (e) {
      setRelatedError(e instanceof Error ? e.message : 'Failed to retrieve business owner details');
    } finally {
      setRelatedLoading(false);
    }
  };

  const handleConvertToLead = async () => {
    if (!open) return;
    setConvertingLead(true);
    setRelatedError('');
    try {
      const res = await apiFetch(`/api/opportunities/${open.id}/convert_to_lead`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setConvertedLeadId(data.lead_id);
      setConvertSuccess(data.message || `✓ Added '${data.company_name}' to Clients pipeline!`);
      opps.reload();
    } catch (e) {
      setRelatedError(e instanceof Error ? e.message : 'Failed to save lead');
    } finally {
      setConvertingLead(false);
    }
  };

  const getCompanyName = (o: Opp) => {
    if (o.company_name && o.company_name.trim() && o.company_name.toLowerCase() !== 'unknown') {
      return o.company_name.trim();
    }
    const match = o.title.match(/(?:at|for|with)\s+([A-Z][A-Za-z0-9&.,'\s]{1,30}?)(?:\s+is|\s+looking|\s+hiring|[-–—|(\[\n]|$)/i)
      || o.title.match(/^\[?([A-Z][A-Za-z0-9&.,'\s]{1,30}?)\]?\s*[-–—:|]/i);
    return match ? match[1].trim() : 'Company detected';
  };

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setPanelError('');
    try {
      await fn();
    } catch (e) {
      setPanelError(e instanceof Error ? e.message : 'Failed');
    } finally {
      setBusy('');
    }
  };

  const handleDraft = async () => {
    if (!open) return;
    await run('draft', async () => {
      const d = await send<Draft>('/api/proposals/draft', 'POST', {
        opportunity_id: open.id,
        client_name: open.company_name,
      });
      setDraft(d);
      setSelectedVariant('A');
      setEditedBody(d.variant_a.body);
      setSendSuccess('');
    });
  };

  const sendViaEmail = async (method: 'system' | 'mailto') => {
    if (!open || !draft) return;
    const currentVariant = selectedVariant === 'B' ? draft.variant_b : draft.variant_a;
    const propId = currentVariant.proposal_id ?? draft.proposal_id;
    if (!propId) {
      setPanelError('Proposal record not found. Try drafting again.');
      return;
    }
    const email = toEmail.trim();
    if (!email || !email.includes('@')) {
      setPanelError('Please enter a valid recipient email address.');
      return;
    }
    setBusy('send_email');
    setPanelError('');
    setSendSuccess('');
    try {
      const textToSend = editedBody || currentVariant.body;
      const res = await send<{ ok: boolean; message: string; followup_date: string }>(
        `/api/proposals/${propId}/send`,
        'POST',
        {
          channel: 'email',
          recipient: email,
          subject: emailSubject || `Proposal: ${open.title}`,
          body: textToSend,
          next_followup_days: 3,
        }
      );
      if (method === 'mailto') {
        const mailtoUrl = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(
          emailSubject || `Proposal: ${open.title}`
        )}&body=${encodeURIComponent(textToSend)}`;
        window.open(mailtoUrl, '_blank');
      }
      setSendSuccess(res.message || `✓ Proposal dispatched to ${email}! Follow-up reminder set.`);
    } catch (e) {
      setPanelError(e instanceof Error ? e.message : 'Failed to send proposal');
    } finally {
      setBusy('');
    }
  };

  const sendViaPlatform = async () => {
    if (!open || !draft) return;
    const currentVariant = selectedVariant === 'B' ? draft.variant_b : draft.variant_a;
    const propId = currentVariant.proposal_id ?? draft.proposal_id;
    if (!propId) {
      setPanelError('Proposal record not found. Try drafting again.');
      return;
    }
    setBusy('send_platform');
    setPanelError('');
    setSendSuccess('');
    try {
      const textToSend = editedBody || currentVariant.body;
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(textToSend);
        setCopied(true);
        setTimeout(() => setCopied(false), 3000);
      }
      const res = await send<{ ok: boolean; message: string; followup_date: string }>(
        `/api/proposals/${propId}/send`,
        'POST',
        {
          channel: open.source || 'other',
          recipient: open.url || '',
          body: textToSend,
          next_followup_days: 3,
        }
      );
      if (open.url) {
        window.open(normalizeUrl(open.url), '_blank', 'noopener,noreferrer');
      }
      setSendSuccess(res.message || `✓ Proposal copied to clipboard! Opened application page on ${open.source}.`);
    } catch (e) {
      setPanelError(e instanceof Error ? e.message : 'Failed to log proposal');
    } finally {
      setBusy('');
    }
  };

  const copyProposal = async () => {
    if (!draft) return;
    const currentVariant = selectedVariant === 'B' ? draft.variant_b : draft.variant_a;
    const textToSend = editedBody || currentVariant.body;
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(textToSend);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const slice = groupedRows.slice(page * PAGE, (page + 1) * PAGE);
  const money = (o: Opp) => {
    const b = formatBudgetOrEstimate(o);
    return <span className={b.estimated ? 'text-slate-400 italic' : 'text-slate-200 font-medium'}>{b.text}</span>;
  };
  const relevantSources = (sources.data ?? []).filter((s) =>
    mode === 'tender' ? ['sam_gov', 'ted', 'uk_fts'].includes(s.source) : !['sam_gov', 'ted', 'uk_fts'].includes(s.source),
  );

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-400 space-y-1 flex-1 min-w-48">
            Search
            <SuggestInput
              kinds={['skill', 'business']}
              placeholder="react, tender, fintech…"
              value={q}
              onChange={(v) => {
                setQ(v);
                setPage(0);
              }}
            />
          </label>
          <label className="text-xs text-slate-400 space-y-1">
            Source
            <Select
              aria-label="Source"
              value={source}
              onChange={(v) => {
                setSource(v);
                setPage(0);
              }}
              options={[{ value: '', label: 'All' }, ...sourceNames.map((s) => ({ value: s, label: s }))]}
            />
          </label>
          <label className="text-xs text-slate-400 space-y-1">
            Minimum fit
            <Select
              aria-label="Minimum fit"
              value={minFit}
              onChange={(v) => {
                setMinFit(Number(v));
                setPage(0);
              }}
              options={[0, 30, 50, 70].map((n) => ({ value: n, label: n ? `${n}%+` : 'Any' }))}
            />
          </label>
          <label className="text-xs text-slate-400 space-y-1">
            Budget from
            <input
              className={`${field} w-24`}
              inputMode="numeric"
              placeholder="any"
              value={minBudget}
              onChange={(e) => {
                setMinBudget(e.target.value.replace(/[^0-9]/g, ''));
                setPage(0);
              }}
            />
          </label>
          <label className="text-xs text-slate-400 space-y-1">
            to
            <input
              className={`${field} w-24`}
              inputMode="numeric"
              placeholder="any"
              value={maxBudget}
              onChange={(e) => {
                setMaxBudget(e.target.value.replace(/[^0-9]/g, ''));
                setPage(0);
              }}
            />
          </label>
          {mode !== 'tender' && (
            <label className="flex items-center gap-2 text-xs text-slate-300 pb-2">
              <input
                type="checkbox"
                checked={remoteOnly}
                onChange={(e) => {
                  setRemoteOnly(e.target.checked);
                  setPage(0);
                }}
              />
              Remote only
            </label>
          )}
          <Button variant="primary" onClick={scan} disabled={scanning}>
            <RefreshCw className={`h-4 w-4 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'Scanning…' : 'Scan sources'}
          </Button>
          <Button type="button" onClick={watchSearch}>
            <Bell className="h-3.5 w-3.5" />
            Watch search
          </Button>
        </div>

        {mode !== 'tender' && (
          <div className="flex flex-wrap items-center gap-3 mt-3 pt-3 border-t border-slate-800/80 text-xs">
            <label className="text-slate-400 inline-flex items-center gap-1.5">
              Engagement
              <Select
                small
                aria-label="Engagement Type"
                className="w-44"
                value={engagement}
                onChange={(v) => { setEngagement(v as EngagementFilter); setPage(0); }}
                options={[
                  { value: 'all', label: 'All engagements' },
                  { value: 'direct_project', label: 'Direct Projects / Freelance' },
                  { value: 'contract_c2c', label: 'Contract / C2C / Staff-Aug' },
                  { value: 'full_time', label: 'Full-Time Hiring Signals' },
                ]}
              />
            </label>
            <label className="text-slate-400 inline-flex items-center gap-1.5">
              Company
              <Select
                small
                aria-label="Company Stage"
                className="w-40"
                value={companyStage}
                onChange={(v) => { setCompanyStage(v as CompanyStageFilter); setPage(0); }}
                options={[
                  { value: 'all', label: 'All company sizes' },
                  { value: 'startup_smb', label: 'Startup / SMB' },
                  { value: 'agency_partner', label: 'Agency Partner' },
                  { value: 'enterprise', label: 'Enterprise ($100M+)' },
                ]}
              />
            </label>
            <label className="inline-flex items-center gap-1.5 text-slate-300 cursor-pointer">
              <input type="checkbox" checked={groupCompanies} onChange={(e) => { setGroupCompanies(e.target.checked); setPage(0); }} />
              Group by company
            </label>
            <label className="inline-flex items-center gap-1.5 text-slate-300 cursor-pointer">
              <input type="checkbox" checked={hideSeen} onChange={(e) => { setHideSeen(e.target.checked); setPage(0); }} />
              Hide in CRM / 👎
            </label>
            {sources.data && (
              <button
                type="button"
                onClick={() => setShowSources((v) => !v)}
                className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-800 bg-slate-900/60 text-slate-300 hover:text-white"
              >
                <Server className="h-3.5 w-3.5 text-indigo-400" />
                Sources ({relevantSources.length})
              </button>
            )}
          </div>
        )}

        {scanning && (
          <p role="status" aria-live="polite" className="mt-3 text-xs text-slate-400">
            {scanNote} Sources are read in parallel; the slowest one (usually the tender feeds) sets the time, about a minute.
          </p>
        )}
        {(minBudget || maxBudget) && (
          <p className="text-[11px] text-slate-500 mt-2">Budget filters show only posts that state a budget.</p>
        )}
        {showSources && sources.data && (
          <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t border-slate-800/80">
            {sources.data.some((x) => x.source === 'upwork' && x.status === 'not_connected') && (
              <Button small onClick={connectUpwork}>
                Connect Upwork
              </Button>
            )}
            {relevantSources.map((s) => (
              <Badge
                key={s.source}
                tone={
                  s.status === 'not_configured' || s.status === 'not_connected'
                    ? 'neutral'
                    : s.last_run?.status === 'ok'
                    ? 'good'
                    : s.last_run
                    ? 'warn'
                    : 'neutral'
                }
                title={s.detail ?? s.last_run?.detail ?? ''}
              >
                {s.source}
                {s.last_run
                  ? s.last_run.stored > 0
                    ? ` · ${s.last_run.stored} kept`
                    : s.last_run.fetched > 0
                      ? ' · filtered by fit'
                      : ' · 0 matched'
                  : s.status === 'not_configured' || s.status === 'not_connected'
                  ? ' · not connected'
                  : ' · ready'}
              </Badge>
            ))}
          </div>
        )}
      </Card>
      {watchNotice && <div role="status" className="p-3 rounded-xl bg-indigo-500/15 border border-indigo-500/40 text-xs text-slate-100">{watchNotice}</div>}
      <ErrorBanner message={error || opps.error} />

      <Card>
        {opps.loading && !opps.data ? (
          <Skeletons rows={5} />
        ) : rows.length === 0 ? (
          <EmptyState
            title="Nothing here yet"
            hint="Press Scan sources to read the free job, project and tender feeds. Add your services and a case study in Settings so fit can be scored."
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400 mb-3">
              <span className="flex items-center gap-1.5 font-medium text-slate-300">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                <span className="tabular font-semibold text-white">{rows.length}</span> opportunities
                {groupCompanies && groupedRows.length < rows.length && (
                  <span className="text-slate-500">({groupedRows.length} companies)</span>
                )}
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <Button small onClick={exportCsv}><Download className="h-3.5 w-3.5" />CSV</Button>
                <Button small variant="primary" disabled={picked.size === 0} onClick={bulkSaveCrm}>
                  Save {picked.size > 0 ? `${picked.size} ` : ''}to CRM
                </Button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b border-slate-800">
                    <th className="py-2 pr-2 w-8"><span className="sr-only">Select</span></th>
                    <th className="py-2 pr-3 w-28">Fit</th>
                    <th className="py-2 pr-3">Opportunity</th>
                    <th className="py-2 pr-3 hidden md:table-cell">Freshness</th>
                    <th className="py-2 pr-3 hidden md:table-cell">Source</th>
                    <th className="py-2 pr-3 hidden md:table-cell">Est. Value / Budget</th>
                    <th className="py-2 pr-3 text-right">Business Details</th>
                  </tr>
                </thead>
                <tbody>
                  {slice.map(({ item: o, siblings }) => {
                    const renderRow = (rowItem: Opp, isChild = false) => {
                      const fresh = getFreshness(rowItem.posted_at);
                      const stage = detectCompanyStage(rowItem);
                      const redFlag = detectNoAgenciesRedFlag(rowItem);
                      const curVote = votes[rowItem.id] !== undefined ? votes[rowItem.id] : rowItem.user_vote;
                      const coKey = (rowItem.company_name || '').trim().toLowerCase();
                      const isExpanded = expandedCompanies.has(coKey);
                      return (
                        <tr
                          key={rowItem.id}
                          className={`border-b border-slate-800/70 hover:bg-slate-900/60 cursor-pointer ${isChild ? 'bg-slate-950/40' : ''}`}
                          onClick={() => openRow(rowItem)}
                        >
                          <td className="py-2.5 pr-2" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              aria-label={`Select ${rowItem.title}`}
                              checked={picked.has(rowItem.id)}
                              onChange={() =>
                                setPicked((prev) => {
                                  const n = new Set(prev);
                                  if (n.has(rowItem.id)) n.delete(rowItem.id);
                                  else n.add(rowItem.id);
                                  return n;
                                })
                              }
                            />
                          </td>
                          <td className="py-2.5 pr-3">
                            <div className="flex items-center gap-1.5">
                              <div className="flex-1">
                                {rowItem.fit_score == null ? (
                                  <span className="text-xs text-slate-500">not scored</span>
                                ) : (
                                  <>
                                    <div className="font-mono tabular text-white">{Math.round(rowItem.fit_score * 100)}%</div>
                                    <ScoreBar value={rowItem.fit_score * 100} />
                                  </>
                                )}
                              </div>
                              <div className="flex flex-col gap-0.5" onClick={(e) => e.stopPropagation()}>
                                <button
                                  type="button"
                                  title="Good fit"
                                  onClick={() => voteOpp(rowItem.id, 'up')}
                                  className={`p-0.5 rounded ${curVote === 'up' ? 'text-emerald-400' : 'text-slate-600 hover:text-slate-300'}`}
                                >
                                  <ThumbsUp className="h-3 w-3" />
                                </button>
                                <button
                                  type="button"
                                  title="Not for us"
                                  onClick={() => voteOpp(rowItem.id, 'down')}
                                  className={`p-0.5 rounded ${curVote === 'down' ? 'text-rose-400' : 'text-slate-600 hover:text-slate-300'}`}
                                >
                                  <ThumbsDown className="h-3 w-3" />
                                </button>
                              </div>
                            </div>
                          </td>
                          <td className="py-2.5 pr-3">
                            <button className="text-left text-slate-100 hover:text-white font-medium line-clamp-1">
                              {isChild ? `↳ ${rowItem.title}` : rowItem.title}
                            </button>
                            <div className="text-xs text-slate-500 flex flex-wrap gap-1.5 items-center mt-0.5">
                              <Badge>{TYPE_LABEL[rowItem.type] ?? rowItem.type}</Badge>
                              <span className="font-medium text-slate-300">{getCompanyName(rowItem)}</span>
                              {rowItem.crm_status && <Badge tone="good">In CRM ({rowItem.crm_status.deal_stage})</Badge>}
                              {stage === 'agency_partner' && <Badge tone="info">Agency Partner</Badge>}
                              {redFlag && <Badge tone="bad">No Agencies</Badge>}
                              {!isChild && siblings.length > 0 && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setExpandedCompanies((prev) => {
                                      const n = new Set(prev);
                                      if (n.has(coKey)) n.delete(coKey);
                                      else n.add(coKey);
                                      return n;
                                    });
                                  }}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/25"
                                >
                                  <Flame className="h-3 w-3" />
                                  {siblings.length + 1} open roles
                                  {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                                </button>
                              )}
                            </div>
                          </td>
                          <td className="py-2.5 pr-3 hidden md:table-cell text-xs whitespace-nowrap">
                            {fresh.isStale ? (
                              <Badge tone="warn">🔥 {fresh.label}</Badge>
                            ) : (
                              <span className="text-slate-400">{fresh.label}</span>
                            )}
                          </td>
                          <td className="py-2.5 pr-3 hidden md:table-cell text-xs text-slate-400">{rowItem.source}</td>
                          <td className="py-2.5 pr-3 hidden md:table-cell text-xs tabular">{money(rowItem)}</td>
                          <td className="py-2.5 pr-3 text-right whitespace-nowrap">
                            <Button
                              small
                              variant="primary"
                              className="whitespace-nowrap"
                              onClick={(e) => {
                                e.stopPropagation();
                                openRow(rowItem);
                                handleRelatedRead(rowItem.id);
                              }}
                            >
                              <Building2 className="h-3.5 w-3.5" />
                              {mode === 'tender' ? 'Agency & Tender Details' : 'See Business Details'}
                            </Button>
                          </td>
                        </tr>
                      );
                    };

                    const coKey = (o.company_name || '').trim().toLowerCase();
                    const isExpanded = expandedCompanies.has(coKey);
                    return (
                      <>
                        {renderRow(o, false)}
                        {isExpanded && siblings.map((sib) => renderRow(sib, true))}
                      </>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={page} pageSize={PAGE} total={groupedRows.length} onPage={setPage} />
          </>
        )}
      </Card>

      <Drawer open={open !== null} title={open?.title ?? ''} onClose={() => setOpen(null)} wide>
        {open && (
          <div className="space-y-5 text-sm">
            <div className="flex flex-wrap gap-2">
              <Badge tone="accent">{open.source}</Badge>
              <Badge>{TYPE_LABEL[open.type] ?? open.type}</Badge>
              {open.fit_score != null && <Badge tone="good">Fit {Math.round(open.fit_score * 100)}%</Badge>}
              {detectCompanyStage(open) === 'agency_partner' && <Badge tone="info">Agency Partner Opportunity</Badge>}
              {getFreshness(open.posted_at).isStale && <Badge tone="warn">🔥 {getFreshness(open.posted_at).label}</Badge>}
              {open.risk_flags.map((f) => (
                <Badge key={f} tone="warn">
                  {f.replace(/_/g, ' ')}
                </Badge>
              ))}
            </div>

            {detectNoAgenciesRedFlag(open) && (
              <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-200 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
                <span><strong>{detectNoAgenciesRedFlag(open)}</strong> — This post explicitly restricts agencies/C2C. Pitch the hiring manager directly only if offering a fractional/advisory angle.</span>
              </div>
            )}

            {(() => {
              const coKey = (open.company_name || '').trim().toLowerCase();
              const intel = extractCompanyIntel(open, companyCounts[coKey] || 1);
              if (!intel.techStack.length && !intel.scaleSignal && !intel.hiringVelocity) return null;
              return (
                <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 space-y-2 text-xs">
                  <div className="font-semibold text-white">Company & Role Intelligence</div>
                  <div className="flex flex-wrap gap-1.5">
                    {intel.scaleSignal && <Badge tone="info">Scale: {intel.scaleSignal}</Badge>}
                    {intel.hiringVelocity && <Badge tone="warn">🔥 {intel.hiringVelocity}</Badge>}
                    {intel.techStack.map((t) => <Badge key={t} tone="neutral">{t}</Badge>)}
                  </div>
                </div>
              );
            })()}

            {open.url && (
              <div className="flex flex-wrap items-center gap-2">
                <a
                  className="inline-flex gap-1.5 text-xs text-indigo-300 hover:text-indigo-200"
                  href={normalizeUrl(open.url)}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  Open original post on {open.source || 'website'}
                </a>
                <button
                  type="button"
                  onClick={() => onOpenScraper?.(open.url!, 'job_spec', open.company_name || open.title)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs bg-amber-500/10 text-amber-300 border border-amber-500/30 hover:bg-amber-500/20 transition font-mono"
                  title="Deep scrape job requirements, tech stack, and budget cues with Universal Scraper"
                >
                  <Cpu className="h-3.5 w-3.5 text-amber-400" />
                  Scrape Job Specs
                </button>
              </div>
            )}

            {open.fit_reasons.length > 0 && (
              <ul className="text-xs text-slate-300 list-disc pl-4 space-y-0.5">
                {open.fit_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}

            <p className="text-xs text-slate-300 whitespace-pre-wrap max-h-52 overflow-auto bg-slate-900 border border-slate-800 rounded-lg p-3 leading-relaxed">
              {open.description || 'No description provided.'}
            </p>

            <ErrorBanner message={panelError} />

            {/* Pitch Angle & Action Buttons */}
            <div className="space-y-3 pt-2 border-t border-slate-800">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="text-slate-400 font-medium">Pitch Angle:</span>
                <Select
                  small
                  aria-label="Agency Pitch Angle"
                  className="w-60"
                  value={pitchAngle}
                  onChange={(v) => setPitchAngle(v as PitchAngle)}
                  options={[
                    { value: 'staff_aug', label: 'Staff Augmentation / Dedicated Pod' },
                    { value: 'fixed_scope', label: 'Fixed-Scope Project Bid' },
                    { value: 'white_label', label: 'White-Label / Agency Overflow' },
                  ]}
                />
                <Button
                  small
                  onClick={() => setLoomScript(buildLoomScript(open, getCompanyName(open), pitchAngle))}
                >
                  <Video className="h-3.5 w-3.5 text-indigo-400" />
                  60s Loom Script
                </Button>
              </div>
              {loomScript && (
                <pre className="rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-3 text-xs text-slate-200 whitespace-pre-wrap font-sans leading-relaxed">
                  {loomScript}
                </pre>
              )}
              <div className="flex flex-wrap items-center gap-2.5">
              <Button
                variant="primary"
                disabled={busy !== '' || relatedLoading}
                onClick={() => handleRelatedRead()}
              >
                <Building2 className="h-4 w-4" />
                {relatedLoading ? 'Reading Business Details…' : relatedRead ? 'Refresh Business Details' : '🏢 See Business Details'}
              </Button>

              <Button
                disabled={busy !== ''}
                onClick={() =>
                  run('fit', async () => setFit(await send<Fit>(`/api/opportunities/${open.id}/analyze`)))
                }
              >
                <Compass className="h-4 w-4" />
                {busy === 'fit' ? 'Analyzing Opportunity…' : fit ? 'Re-analyze Fit' : 'Should we chase this?'}
              </Button>

              <Button
                variant="primary"
                disabled={busy !== ''}
                onClick={handleDraft}
              >
                <Sparkles className="h-4 w-4" />
                {busy === 'draft' ? 'Drafting Proposal…' : draft ? 'Regenerate Proposal' : '✨ Draft & Send Proposal'}
              </Button>
              </div>
            </div>

            {/* Related Read: Business Owner Details Surface */}
            {relatedError && <ErrorBanner message={relatedError} />}
            {relatedRead && (
              <div className="rounded-xl border border-indigo-900/60 bg-slate-900/90 p-4 space-y-3.5 animate-fade-up">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-indigo-400" />
                    <span className="font-semibold text-white text-xs">{relatedRead.company_name}</span>
                    {relatedRead.domain && !relatedRead.domain.endsWith('.invalid') && (
                      <Badge tone="good">🌐 {relatedRead.domain}</Badge>
                    )}
                  </div>
                  <Badge tone="accent">Related Read: Verified Intelligence</Badge>
                </div>

                {convertSuccess && (
                  <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/40 text-xs text-emerald-200 flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5">
                      <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                      {convertSuccess}
                    </span>
                    {onOpenClient && convertedLeadId && (
                      <Button small variant="primary" onClick={() => onOpenClient(convertedLeadId)}>
                        Open in Clients →
                      </Button>
                    )}
                  </div>
                )}

                {/* Primary Business Owner Card */}
                <div className="rounded-lg bg-slate-950 border border-slate-800/80 p-3 space-y-2">
                  <div className="text-[11px] font-semibold text-indigo-300 uppercase tracking-wider flex items-center justify-between">
                    <span>Key Decision Maker / Business Owner</span>
                    <Badge tone={relatedRead.business_owner.verification_status === 'published_on_site' ? 'good' : 'neutral'}>
                      {relatedRead.business_owner.verification_status?.replace(/_/g, ' ') || 'detected'}
                    </Badge>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2 text-xs">
                    <div>
                      <div className="text-slate-400 text-[11px]">Contact Name</div>
                      <div className="font-semibold text-white">{relatedRead.business_owner.name}</div>
                    </div>
                    <div>
                      <div className="text-slate-400 text-[11px]">Role / Title</div>
                      <div className="text-slate-200">{relatedRead.business_owner.title}</div>
                    </div>
                    {relatedRead.business_owner.email && (
                      <div>
                        <div className="text-slate-400 text-[11px]">Direct Email</div>
                        <div className="font-mono text-indigo-300 flex items-center gap-1.5">
                          {relatedRead.business_owner.email}
                          <button
                            type="button"
                            onClick={() => {
                              navigator.clipboard?.writeText(relatedRead.business_owner.email || '');
                            }}
                            className="text-slate-400 hover:text-white"
                            title="Copy email"
                          >
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    )}
                    {relatedRead.business_owner.linkedin_url && (
                      <div>
                        <div className="text-slate-400 text-[11px]">LinkedIn Profile</div>
                        <a
                          href={relatedRead.business_owner.linkedin_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-400 hover:underline flex items-center gap-1"
                        >
                          View Profile <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                {/* Additional Leadership Contacts if present */}
                {relatedRead.contacts.length > 1 && (
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-semibold text-slate-400">Other Organization Contacts Detected:</div>
                    <div className="grid gap-1.5 sm:grid-cols-2">
                      {relatedRead.contacts.slice(1, 5).map((ct, idx) => (
                        <div key={idx} className="p-2 rounded bg-slate-950/60 border border-slate-800 text-[11px] space-y-0.5">
                          <div className="font-medium text-slate-200">{ct.name}</div>
                          <div className="text-slate-400">{ct.title}</div>
                          {ct.email && <div className="text-indigo-300 font-mono">{ct.email}</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Convert & Outreach Actions */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800">
                  <div className="text-[11px] text-slate-400 italic">
                    {relatedRead.summary}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!convertedLeadId && (
                      <Button small variant="primary" disabled={convertingLead} onClick={handleConvertToLead}>
                        <UserPlus className="h-3.5 w-3.5" />
                        {convertingLead ? 'Adding to Clients…' : 'Add to Clients Pipeline'}
                      </Button>
                    )}
                    {relatedRead.business_owner.email && onSendEmail && (
                      <Button
                        small
                        onClick={() => {
                          onSendEmail({
                            recipient: relatedRead.business_owner.email || '',
                            recipientName: relatedRead.business_owner.name,
                            companyName: relatedRead.company_name,
                            subject: `Question regarding your ${open.title} posting`,
                            leadId: convertedLeadId || undefined,
                          });
                          setOpen(null);
                        }}
                      >
                        <Mail className="h-3.5 w-3.5 text-indigo-400" />
                        Send Email to Owner
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Comprehensive Fit Analysis Surface */}
            {fit && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-4 text-xs animate-fade-up">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Badge tone={fit.verdict === 'pursue' ? 'good' : fit.verdict === 'skip' ? 'bad' : 'warn'}>
                      {fit.verdict === 'pursue'
                        ? 'RECOMMENDED: PURSUE'
                        : fit.verdict === 'skip'
                        ? 'SKIP / LOW COMMERCIAL FIT'
                        : 'PITCH SPRINT / CONTRACTING TEAM'}
                    </Badge>
                  </div>
                  {fit.deterministic_fit_score != null && (
                    <span className="text-slate-400 font-mono">
                      Deterministic score: {Math.round(fit.deterministic_fit_score * 100)}%
                    </span>
                  )}
                </div>

                <div className="text-slate-200 leading-relaxed font-medium">
                  {fit.summary}
                </div>

                {/* Match Strengths */}
                {fit.reasons.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Capabilities & Scope Alignment
                    </div>
                    <div className="space-y-2">
                      {fit.reasons.map((r, i) => (
                        <div key={i} className="pl-3 border-l-2 border-emerald-500/50 py-0.5 space-y-0.5">
                          <div className="text-slate-200 font-medium">{r.point}</div>
                          <div className="text-slate-400 italic text-[11px]">&ldquo;{r.quote}&rdquo;</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Risks & Restrictions */}
                {fit.risks.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                      <AlertCircle className="h-3.5 w-3.5" /> Identified Risks & Constraints
                    </div>
                    <div className="space-y-2">
                      {fit.risks.map((r, i) => (
                        <div key={i} className="pl-3 border-l-2 border-amber-500/50 py-0.5 space-y-0.5">
                          <div className="text-slate-200 font-medium">{r.point}</div>
                          <div className="text-slate-400 italic text-[11px]">&ldquo;{r.quote}&rdquo;</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Questions */}
                {fit.questions_to_ask.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <div className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
                      <HelpCircle className="h-3.5 w-3.5" /> Strategic Questions to Ask Client
                    </div>
                    <ul className="list-disc pl-5 space-y-1 text-slate-300">
                      {fit.questions_to_ask.map((q, i) => (
                        <li key={i}>{q}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {!draft && (
                  <div className="pt-2 flex justify-end">
                    <Button small variant="primary" onClick={handleDraft} disabled={busy !== ''}>
                      <Sparkles className="h-3.5 w-3.5" /> Draft Proposal for this Opportunity →
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Proposal Studio & Direct Send Surface */}
            {draft && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-4 animate-fade-up">
                {/* Variant Switcher */}
                <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Angle:</span>
                    <div className="inline-flex rounded-lg bg-slate-950 p-1 border border-slate-800">
                      <button
                        type="button"
                        className={`px-3 py-1 rounded text-xs font-medium transition ${
                          selectedVariant === 'A' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
                        }`}
                        onClick={() => {
                          setSelectedVariant('A');
                          setEditedBody(draft.variant_a.body);
                          setSendSuccess('');
                        }}
                      >
                        Variant A: Technical Depth
                      </button>
                      <button
                        type="button"
                        className={`px-3 py-1 rounded text-xs font-medium transition ${
                          selectedVariant === 'B' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
                        }`}
                        onClick={() => {
                          setSelectedVariant('B');
                          setEditedBody(draft.variant_b.body);
                          setSendSuccess('');
                        }}
                      >
                        Variant B: Business Speed
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {(selectedVariant === 'A' ? draft.variant_a : draft.variant_b).verification?.ok ? (
                      <Badge tone="good">✓ Claims Verified Against Portfolio</Badge>
                    ) : (
                      <Badge tone="bad">Verification Issues</Badge>
                    )}
                  </div>
                </div>

                {/* Proposal Textarea */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span>Proposal Body (editable prior to dispatch):</span>
                    <button
                      type="button"
                      onClick={copyProposal}
                      className="inline-flex items-center gap-1 text-indigo-400 hover:text-indigo-300"
                    >
                      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                      {copied ? 'Copied to clipboard!' : 'Copy proposal text'}
                    </button>
                  </div>
                  <textarea
                    className="w-full h-36 bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 leading-relaxed font-sans focus:outline-none focus:border-indigo-500"
                    value={editedBody}
                    onChange={(e) => setEditedBody(e.target.value)}
                  />
                </div>

                {/* Send Controls */}
                <div className="rounded-lg bg-slate-950 border border-slate-800 p-3.5 space-y-3">
                  <div className="text-xs font-semibold text-white flex items-center gap-2">
                    <Send className="h-4 w-4 text-indigo-400" />
                    Send Proposal by Channel / Source
                  </div>

                  {sendSuccess && (
                    <div
                      role="status"
                      className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-500/40 text-xs text-emerald-200 flex items-center gap-2"
                    >
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                      <span>{sendSuccess}</span>
                    </div>
                  )}

                  {/* Channel Tabs */}
                  <div className="flex gap-4 border-b border-slate-800 pb-2">
                    <button
                      type="button"
                      onClick={() => setSendChannel('platform')}
                      className={`pb-1 text-xs font-medium border-b-2 transition ${
                        sendChannel === 'platform'
                          ? 'border-indigo-500 text-white'
                          : 'border-transparent text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      🌐 Apply / Send on {open.source ? open.source.toUpperCase() : 'Source'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setSendChannel('email')}
                      className={`pb-1 text-xs font-medium border-b-2 transition ${
                        sendChannel === 'email'
                          ? 'border-indigo-500 text-white'
                          : 'border-transparent text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      ✉️ Send via Direct Email
                    </button>
                  </div>

                  {sendChannel === 'platform' ? (
                    <div className="space-y-3 pt-1">
                      <p className="text-xs text-slate-300">
                        Copies the customized proposal text to your clipboard, automatically marks the proposal as submitted, schedules a 3-day follow-up reminder in Channels, and opens the job post URL.
                      </p>
                      <div className="flex flex-wrap gap-2.5">
                        <Button
                          variant="primary"
                          disabled={busy !== ''}
                          onClick={sendViaPlatform}
                        >
                          <ExternalLink className="h-4 w-4" />
                          {busy === 'send_platform'
                            ? 'Submitting…'
                            : `Copy Proposal & Apply on ${open.source || 'Platform'}`}
                        </Button>
                        <Button onClick={copyProposal}>
                          {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                          {copied ? 'Copied!' : 'Copy Proposal Text'}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3 pt-1">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-[11px] text-slate-400">Recipient Email:</label>
                          <input
                            className={`${field} w-full`}
                            placeholder="e.g. recruiting@calabrio.com"
                            value={toEmail}
                            onChange={(e) => setToEmail(e.target.value)}
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[11px] text-slate-400">Subject Line:</label>
                          <input
                            className={`${field} w-full`}
                            value={emailSubject}
                            onChange={(e) => setEmailSubject(e.target.value)}
                          />
                        </div>
                      </div>

                      {detectedEmails.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
                          <span>Detected in opportunity:</span>
                          {detectedEmails.map((em) => (
                            <button
                              key={em}
                              type="button"
                              onClick={() => setToEmail(em)}
                              className="px-2 py-0.5 rounded bg-slate-800 text-indigo-300 hover:bg-slate-700 font-mono text-[10px]"
                            >
                              {em}
                            </button>
                          ))}
                        </div>
                      )}

                      <div className="flex flex-wrap gap-2.5 pt-1">
                        {onSendEmail && (
                          <Button
                            variant="primary"
                            disabled={busy !== ''}
                            onClick={() => {
                              const currentVariant = selectedVariant === 'B' ? draft.variant_b : draft.variant_a;
                              const textToSend = editedBody || currentVariant.body;
                              onSendEmail({
                                recipient: toEmail.trim(),
                                recipientName: open?.company_name ?? '',
                                companyName: open?.company_name ?? '',
                                subject: emailSubject || `Proposal: ${open?.title}`,
                                body: textToSend,
                              });
                              setOpen(null);
                            }}
                          >
                            <Mail className="h-4 w-4" />
                            Open & Verify in Email Hub →
                          </Button>
                        )}
                        <Button
                          variant={onSendEmail ? 'secondary' : 'primary'}
                          disabled={busy !== '' || !toEmail}
                          onClick={() => sendViaEmail('system')}
                        >
                          <Send className="h-4 w-4" />
                          {busy === 'send_email' ? 'Dispatching Email…' : 'Send via System Dispatch'}
                        </Button>
                        <Button
                          disabled={busy !== '' || !toEmail}
                          onClick={() => sendViaEmail('mailto')}
                        >
                          <ExternalLink className="h-4 w-4" />
                          Open in External Mail (mailto:)
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
};
