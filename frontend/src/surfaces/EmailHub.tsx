import { useState, useEffect } from 'react';
import type { FC, FormEvent } from 'react';
import {
  Mail, Send, CheckCircle2, AlertTriangle, XCircle, Shield,
  RefreshCw, Plus, Clock, Server, Eye, FileText, Check, ChevronRight,
  Sparkles, Trash2
} from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../lib/api';
import type { Me } from '../lib/api';
import { ErrorBoundary } from '../components/shared/ErrorBoundary';

export interface EmailSeed {
  recipient?: string;
  recipientName?: string;
  companyName?: string;
  subject?: string;
  body?: string;
  leadId?: number;
}

interface VerificationResult {
  email: string;
  status: 'verified' | 'invalid' | 'risky' | 'disposable' | 'spamtrap' | 'suppressed' | 'unverified';
  is_deliverable: boolean;
  confidence: number;
  syntax_valid: boolean;
  domain: string;
  mx_records: string[];
  has_mx: boolean;
  is_disposable: boolean;
  is_spamtrap: boolean;
  is_role_account: boolean;
  is_suppressed: boolean;
  provider: string;
  reason: string;
}

interface Mailbox {
  id: number;
  email: string;
  display_name: string;
  provider_type: string;
  daily_cap: number;
  sent_today: number;
  reputation_status: string;
  is_active: number;
  esp?: string;
  skip_warmup?: number;
  has_credentials?: boolean;
}

interface OutboundEvent {
  id: number;
  mailbox_id: number;
  lead_id?: number;
  recipient_email: string;
  event_type: string;
  message_id?: string;
  created_at: string;
  mailbox_email?: string;
  payload?: any;
}

interface OutboundDraft {
  id: number;
  recipient_email: string;
  recipient_name?: string;
  company_name?: string;
  subject: string;
  body: string;
  status: string;
  created_at: string;
}

interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body: string;
  description: string;
}

interface EmailOverview {
  halted: boolean;
  fleet: {
    total_mailboxes: number;
    active_mailboxes: number;
    sent_today: number;
    daily_cap_total: number;
    remaining_capacity_today: number;
  };
  metrics_7d: {
    sent: number;
    delivered: number;
    replied: number;
    bounced: number;
    delivery_rate_pct: number;
  };
  queue: {
    pending_drafts: number;
    suppressed_contacts: number;
  };
}

export const EmailHub: FC<{
  identity: Me;
  seed?: EmailSeed | null;
  onClearSeed?: () => void;
  onOpenClient?: (id: number) => void;
}> = ({ identity: _identity, seed, onClearSeed, onOpenClient: _onOpenClient }) => {
  const [tab, setTab] = useState<'compose' | 'fleet' | 'queue' | 'logs' | 'inspector'>('compose');
  const [overview, setOverview] = useState<EmailOverview | null>(null);
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [events, setEvents] = useState<OutboundEvent[]>([]);
  const [drafts, setDrafts] = useState<OutboundDraft[]>([]);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  
  // Compose form state
  const [toEmail, setToEmail] = useState(seed?.recipient || '');
  const [recipientName, setRecipientName] = useState(seed?.recipientName || '');
  const [companyName, setCompanyName] = useState(seed?.companyName || '');
  const [leadId, setLeadId] = useState<number | undefined>(seed?.leadId);
  const [subject, setSubject] = useState(seed?.subject || '');
  const [body, setBody] = useState(seed?.body || '');
  const [selectedMailboxId, setSelectedMailboxId] = useState<number | undefined>();
  const [countryCode, setCountryCode] = useState('US');
  
  // Verification state for compose
  const [verifyState, setVerifyState] = useState<{
    loading: boolean;
    result: VerificationResult | null;
  }>({ loading: false, result: null });

  // Separate inspector state
  const [inspectEmail, setInspectEmail] = useState('');
  const [inspectResult, setInspectResult] = useState<VerificationResult | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);

  // Status & notifications
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [previewHtml, setPreviewHtml] = useState(false);

  // Mailbox registration modal state
  const [showAddMailbox, setShowAddMailbox] = useState(false);
  const [newMailbox, setNewMailbox] = useState({
    email: '',
    display_name: '',
    provider_type: 'smtp',
    daily_cap: 35,
    skip_warmup: true,
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    use_tls: true,
  });

  // Apply seed whenever seed prop updates
  useEffect(() => {
    if (seed) {
      if (seed.recipient) setToEmail(seed.recipient);
      if (seed.recipientName) setRecipientName(seed.recipientName);
      if (seed.companyName) setCompanyName(seed.companyName);
      if (seed.subject) setSubject(seed.subject);
      if (seed.body) setBody(seed.body);
      if (seed.leadId) setLeadId(seed.leadId);
      setTab('compose');
      if (seed.recipient && seed.recipient.includes('@')) {
        runVerification(seed.recipient);
      }
    }
  }, [seed]);

  // Load all initial data
  const loadData = async () => {
    try {
      const [ovRes, mbRes, evRes, drRes, tmplRes] = await Promise.all([
        apiFetch('/api/email/overview'),
        apiFetch('/api/email/mailboxes'),
        apiFetch('/api/email/history?limit=100'),
        apiFetch('/api/email/drafts'),
        apiFetch('/api/email/templates'),
      ]);

      if (ovRes.ok) setOverview(await ovRes.json());
      if (mbRes.ok) {
        const mbs: Mailbox[] = await mbRes.json();
        setMailboxes(mbs);
        if (mbs.length > 0 && !selectedMailboxId) {
          setSelectedMailboxId(mbs[0].id);
        }
      }
      if (evRes.ok) setEvents(await evRes.json());
      if (drRes.ok) setDrafts(await drRes.json());
      if (tmplRes.ok) setTemplates(await tmplRes.json());
    } catch (err) {
      console.error('Failed to load email hub data:', err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); // 30s auto-refresh
    return () => clearInterval(interval);
  }, []);

  // Pre-flight validation trigger
  const runVerification = async (emailToVerify: string) => {
    const clean = emailToVerify.trim();
    if (!clean || !clean.includes('@')) {
      setVerifyState({ loading: false, result: null });
      return;
    }

    setVerifyState({ loading: true, result: null });
    try {
      const res = await apiFetch('/api/email/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: clean }),
      });
      if (res.ok) {
        const data: VerificationResult = await res.json();
        setVerifyState({ loading: false, result: data });
      } else {
        setVerifyState({ loading: false, result: null });
      }
    } catch {
      setVerifyState({ loading: false, result: null });
    }
  };

  // Debounced auto-verification on email input change
  useEffect(() => {
    const clean = toEmail.trim();
    if (clean.includes('@') && clean.length > 5) {
      const timer = setTimeout(() => {
        runVerification(clean);
      }, 600);
      return () => clearTimeout(timer);
    } else {
      setVerifyState({ loading: false, result: null });
    }
  }, [toEmail]);

  // Execute inspector check
  const handleInspect = async (e: FormEvent) => {
    e.preventDefault();
    if (!inspectEmail.trim()) return;
    setInspectLoading(true);
    setInspectResult(null);
    try {
      const res = await apiFetch('/api/email/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: inspectEmail.trim() }),
      });
      if (res.ok) {
        setInspectResult(await res.json());
      }
    } finally {
      setInspectLoading(false);
    }
  };

  // Dispatch email handler
  const handleSend = async (asDraft = false) => {
    setFeedback(null);
    if (!toEmail.trim() || !subject.trim() || !body.trim()) {
      setFeedback({ type: 'error', message: 'Recipient email, subject, and body are required.' });
      return;
    }

    // Pre-flight deliverability sanity
    if (verifyState.result && !verifyState.result.is_deliverable && !asDraft) {
      if (!window.confirm(`Warning: Deliverability guard flagged this email (${verifyState.result.reason}). Send anyway?`)) {
        return;
      }
    }

    setSending(true);
    try {
      const payload = {
        to_email: toEmail.trim(),
        subject: subject.trim(),
        body: body.trim(),
        from_mailbox_id: selectedMailboxId,
        lead_id: leadId,
        recipient_name: recipientName.trim(),
        company_name: companyName.trim(),
        country_code: countryCode.trim() || 'US',
        as_draft: asDraft,
      };

      const res = await apiFetch('/api/email/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(apiErrorMessage(res.status, data));
      }

      setFeedback({
        type: 'success',
        message: asDraft
          ? `Draft saved for human review (#${data.draft_id}).`
          : `Email successfully dispatched to ${toEmail} via ${data.mailbox || 'primary relay'}! Message-ID: ${data.message_id || 'generated'}.`,
      });

      if (!asDraft) {
        // Clear fields on successful send
        setToEmail('');
        setSubject('');
        setBody('');
        setVerifyState({ loading: false, result: null });
        if (onClearSeed) onClearSeed();
      }

      await loadData();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Outbound dispatch failed.',
      });
    } finally {
      setSending(false);
    }
  };

  // 1-Click Send Draft from Queue
  const handleSendDraft = async (draftId: number) => {
    try {
      const res = await apiFetch(`/api/email/drafts/${draftId}/send`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setFeedback({ type: 'success', message: `Draft #${draftId} approved and dispatched!` });
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Dispatch failed.' });
    }
  };

  // Delete Draft from Queue
  const handleDeleteDraft = async (draftId: number) => {
    try {
      const res = await apiFetch(`/api/email/drafts/${draftId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Could not delete draft');
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Delete failed.' });
    }
  };

  // Load template into composer
  const applyTemplate = (t: EmailTemplate) => {
    let replacedSubject = t.subject;
    let replacedBody = t.body;

    const firstName = recipientName ? recipientName.split(' ')[0] : 'there';
    const comp = companyName || 'your team';

    replacedSubject = replacedSubject.replace(/{{first_name}}/g, firstName).replace(/{{company}}/g, comp);
    replacedBody = replacedBody.replace(/{{first_name}}/g, firstName).replace(/{{company}}/g, comp);

    setSubject(replacedSubject);
    setBody(replacedBody);
  };

  // Insert merge variable chip
  const insertVariable = (tag: string) => {
    setBody((prev) => `${prev} ${tag}`);
  };

  // Register new mailbox
  const handleRegisterMailbox = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const res = await apiFetch('/api/email/mailboxes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newMailbox),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setShowAddMailbox(false);
      setFeedback({ type: 'success', message: `Mailbox ${newMailbox.email} registered successfully!` });
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Registration failed.' });
    }
  };

  return (
    <ErrorBoundary fallbackTitle="Email Hub Error">
      <div className="space-y-6 max-w-7xl mx-auto pb-12 animate-fadeIn">
        {/* Top Header & Overview Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-800">
          <div>
            <div className="flex items-center space-x-3">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20">
                <Mail className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                  <span>Email Dispatch Command Hub</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    BUILT-IN DELIVERABILITY
                  </span>
                </h1>
                <p className="text-xs text-slate-400 mt-0.5">
                  RFC 5322 syntax validation, live DNS MX inspection, anti-spam safeguards, and multi-mailbox rotation.
                </p>
              </div>
            </div>
          </div>

          {/* Quick Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setTab('compose')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                tab === 'compose' ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30' : 'bg-slate-900 border border-slate-800 text-slate-300 hover:text-white'
              }`}
            >
              <Send className="h-3.5 w-3.5" />
              <span>Compose Email</span>
            </button>
            <button
              onClick={() => setShowAddMailbox(true)}
              className="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 border border-slate-800 text-slate-300 hover:text-white transition"
            >
              <Plus className="h-3.5 w-3.5 text-indigo-400" />
              <span>Add Mailbox</span>
            </button>
            <button
              onClick={loadData}
              title="Refresh telemetry"
              className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Global Alert Notification */}
        {feedback && (
          <div
            className={`p-3.5 rounded-xl border text-xs flex items-center justify-between transition animate-fadeIn ${
              feedback.type === 'success'
                ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-200'
                : 'bg-rose-950/40 border-rose-500/40 text-rose-200'
            }`}
          >
            <div className="flex items-center space-x-2">
              {feedback.type === 'success' ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
              ) : (
                <XCircle className="h-4 w-4 text-rose-400 shrink-0" />
              )}
              <span>{feedback.message}</span>
            </div>
            <button
              onClick={() => setFeedback(null)}
              className="text-slate-400 hover:text-white text-xs underline ml-4"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Top 4 KPI Metrics Bento Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
            <div className="text-[11px] font-medium text-slate-400 flex items-center justify-between">
              <span>Mailbox Fleet</span>
              <Server className="h-3.5 w-3.5 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold text-white tabular mt-1">
              {overview?.fleet.active_mailboxes ?? mailboxes.length}
              <span className="text-xs font-normal text-slate-400 ml-1">/ {overview?.fleet.total_mailboxes ?? mailboxes.length} active</span>
            </div>
            <div className="text-[11px] text-slate-500 mt-1">SMTP & Google/MS365 Relays</div>
          </div>

          <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
            <div className="text-[11px] font-medium text-slate-400 flex items-center justify-between">
              <span>Today's Outbound</span>
              <Send className="h-3.5 w-3.5 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-indigo-400 tabular mt-1">
              {overview?.fleet.sent_today ?? 0}
              <span className="text-xs font-normal text-slate-400 ml-1">/ {overview?.fleet.daily_cap_total ?? 100} quota</span>
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {overview?.fleet.remaining_capacity_today ?? 100} sends remaining today
            </div>
          </div>

          <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
            <div className="text-[11px] font-medium text-slate-400 flex items-center justify-between">
              <span>Deliverability Rate</span>
              <Shield className="h-3.5 w-3.5 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-emerald-400 tabular mt-1">
              {overview?.metrics_7d.delivery_rate_pct ?? 100}%
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {overview?.metrics_7d.sent ?? 0} dispatched (7d window)
            </div>
          </div>

          <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
            <div className="text-[11px] font-medium text-slate-400 flex items-center justify-between">
              <span>Approval Queue</span>
              <Clock className="h-3.5 w-3.5 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-amber-400 tabular mt-1">
              {drafts.filter((d) => d.status === 'pending_approval').length}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">Drafts waiting for human send</div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center space-x-1 bg-slate-900/70 p-1 rounded-xl border border-slate-800 overflow-x-auto">
          <button
            onClick={() => setTab('compose')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition shrink-0 ${
              tab === 'compose' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Send className="h-3.5 w-3.5" />
            <span>Compose & Dispatch</span>
          </button>

          <button
            onClick={() => setTab('fleet')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition shrink-0 ${
              tab === 'fleet' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Server className="h-3.5 w-3.5" />
            <span>Mailboxes ({mailboxes.length})</span>
          </button>

          <button
            onClick={() => setTab('queue')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition shrink-0 ${
              tab === 'queue' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            <span>Approval Desk ({drafts.length})</span>
          </button>

          <button
            onClick={() => setTab('logs')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition shrink-0 ${
              tab === 'logs' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Delivery Ledger ({events.length})</span>
          </button>

          <button
            onClick={() => setTab('inspector')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium transition shrink-0 ${
              tab === 'inspector' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Shield className="h-3.5 w-3.5" />
            <span>Pre-Flight Deliverability Inspector</span>
          </button>
        </div>

        {/* ==================================================================== */}
        {/* TAB 1: COMPOSE & DISPATCH DESK */}
        {/* ==================================================================== */}
        {tab === 'compose' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Cols: Main Compose Form */}
            <div className="lg:col-span-2 space-y-4 bento-tile specular-border rounded-2xl p-5 sm:p-6 border border-slate-800 bg-slate-900/60">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center space-x-2">
                  <Mail className="h-4 w-4 text-indigo-400" />
                  <h2 className="text-sm font-semibold text-white">Outbound Composer</h2>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => setPreviewHtml(!previewHtml)}
                    className="flex items-center space-x-1 text-xs text-slate-400 hover:text-white transition"
                  >
                    <Eye className="h-3.5 w-3.5" />
                    <span>{previewHtml ? 'Edit Markdown' : 'Preview HTML'}</span>
                  </button>
                </div>
              </div>

              {/* Recipient Input with Live Deliverability Badge */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <label className="text-slate-300 font-medium">To (Recipient Email) *</label>
                  {/* Dynamic Pre-Flight Verification Badge */}
                  {verifyState.loading && (
                    <span className="text-[11px] text-cyan-400 flex items-center space-x-1 font-mono">
                      <RefreshCw className="h-3 w-3 animate-spin" />
                      <span>Checking DNS MX & RFC 5322…</span>
                    </span>
                  )}
                  {verifyState.result && (
                    <span
                      className={`text-[11px] px-2 py-0.5 rounded-full font-mono flex items-center space-x-1 ${
                        verifyState.result.is_deliverable
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                      }`}
                    >
                      {verifyState.result.is_deliverable ? (
                        <>
                          <CheckCircle2 className="h-3 w-3" />
                          <span>Deliverable (MX Verified)</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="h-3 w-3" />
                          <span>{verifyState.result.reason}</span>
                        </>
                      )}
                    </span>
                  )}
                </div>

                <div className="relative">
                  <input
                    type="email"
                    required
                    placeholder="prospect@company.com"
                    value={toEmail}
                    onChange={(e) => setToEmail(e.target.value)}
                    className={`w-full bg-slate-900 border rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none transition ${
                      verifyState.result
                        ? verifyState.result.is_deliverable
                          ? 'border-emerald-500/50 focus:border-emerald-500'
                          : 'border-rose-500/50 focus:border-rose-500'
                        : 'border-slate-800 focus:border-indigo-500'
                    }`}
                  />
                </div>
                {verifyState.result && verifyState.result.is_role_account && (
                  <p className="text-[11px] text-amber-400 flex items-center space-x-1">
                    <AlertTriangle className="h-3 w-3 shrink-0" />
                    <span>Note: Role-based inbox ({verifyState.result.email.split('@')[0]}@). Reply rates are typically lower than direct executive inboxes.</span>
                  </p>
                )}
              </div>

              {/* Recipient Details & Context Row */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-[11px] text-slate-400 font-medium">Recipient Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Sarah Jenkins"
                    value={recipientName}
                    onChange={(e) => setRecipientName(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none mt-1"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-400 font-medium">Company Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Acme Health"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none mt-1"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-400 font-medium">Country (CAN-SPAM / GDPR)</label>
                  <input
                    type="text"
                    maxLength={3}
                    placeholder="US, GB, DE"
                    value={countryCode}
                    onChange={(e) => setCountryCode(e.target.value.toUpperCase())}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none mt-1"
                  />
                </div>
              </div>

              {/* Mailbox Selector */}
              <div>
                <label className="text-[11px] text-slate-400 font-medium">From (Sending Mailbox)</label>
                <select
                  value={selectedMailboxId || ''}
                  onChange={(e) => setSelectedMailboxId(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                >
                  {mailboxes.map((mb) => (
                    <option key={mb.id} value={mb.id}>
                      {mb.display_name ? `${mb.display_name} <${mb.email}>` : mb.email} — ({mb.sent_today}/{mb.daily_cap} sent today)
                    </option>
                  ))}
                  {mailboxes.length === 0 && (
                    <option value="">Default Auto-Rotated Relay</option>
                  )}
                </select>
              </div>

              {/* Subject Line */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <label className="text-slate-300 font-medium">Subject Line *</label>
                  <span className="text-[11px] text-slate-500">{subject.length}/100 chars</span>
                </div>
                <input
                  type="text"
                  required
                  placeholder="e.g. Quick question regarding Acme's engineering sprint"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              {/* Dynamic Variable Chips */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[11px] text-slate-500 mr-1 flex items-center">
                  <Sparkles className="h-3 w-3 mr-1 text-indigo-400" />
                  Insert tag:
                </span>
                {['{{first_name}}', '{{company}}', '{{domain}}', '{{audit_score}}'].map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => insertVariable(tag)}
                    className="px-2 py-0.5 rounded-md text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700/60 transition"
                  >
                    {tag}
                  </button>
                ))}
              </div>

              {/* Email Body */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <label className="text-slate-300 font-medium">Body *</label>
                  <span className="text-[11px] text-slate-500">{body.split(/\s+/).filter(Boolean).length} words</span>
                </div>

                {!previewHtml ? (
                  <textarea
                    rows={9}
                    required
                    placeholder="Write your email body here. Standard CAN-SPAM physical address and 1-click unsubscribe headers will automatically be appended."
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none font-mono leading-relaxed"
                  />
                ) : (
                  <div className="w-full min-h-[220px] bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs text-slate-200 font-sans leading-relaxed space-y-2">
                    <div className="border-b border-slate-800 pb-2 text-[11px] text-slate-400">
                      <strong>Subject:</strong> {subject || '(no subject)'}
                    </div>
                    <div className="whitespace-pre-wrap">{body || '(empty body)'}</div>
                    <div className="pt-4 border-t border-slate-800/80 text-[10px] text-slate-500 space-y-1">
                      <p>—</p>
                      <p>ApexCore Digital Agency · 100 Example Street, Suite 1, Austin, TX 78701</p>
                      <p className="text-indigo-400 underline">Unsubscribe from future correspondence</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Send Buttons Row */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => handleSend(true)}
                  disabled={sending || !toEmail || !subject || !body}
                  className="px-4 py-2.5 rounded-xl border border-slate-700 hover:border-slate-600 bg-slate-900 text-slate-300 hover:text-white text-xs font-medium transition disabled:opacity-50"
                >
                  Save as Draft for Approval
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleSend(false)}
                    disabled={sending || !toEmail || !subject || !body}
                    className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/25 transition disabled:opacity-50"
                  >
                    {sending ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        <span>Dispatching Outbound…</span>
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4" />
                        <span>Send Outbound Email Now</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Right 1 Col: Templates & High Converting Playbooks */}
            <div className="space-y-4">
              <div className="bento-tile specular-border rounded-2xl p-5 border border-slate-800 bg-slate-900/60 space-y-3">
                <div className="flex items-center space-x-2 pb-2 border-b border-slate-800">
                  <Sparkles className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-xs font-semibold text-white">Proven Outreach Templates</h3>
                </div>
                <p className="text-[11px] text-slate-400">
                  Click any template to auto-populate the subject and body with pre-tested high-deliverability copy:
                </p>

                <div className="space-y-2">
                  {templates.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => applyTemplate(t)}
                      className="w-full text-left p-3 rounded-xl border border-slate-800 bg-slate-950/60 hover:border-indigo-500/50 hover:bg-slate-900 transition group"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-white group-hover:text-indigo-300 transition">
                          {t.name}
                        </span>
                        <ChevronRight className="h-3 w-3 text-slate-500 group-hover:text-indigo-400 transition" />
                      </div>
                      <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">{t.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Pre-Flight Correctness Guard Checklist */}
              <div className="bento-tile rounded-2xl p-5 border border-slate-800 bg-slate-900/60 space-y-2.5">
                <div className="flex items-center space-x-2 pb-1 border-b border-slate-800">
                  <Shield className="h-4 w-4 text-emerald-400" />
                  <h3 className="text-xs font-semibold text-white">Deliverability Assurance</h3>
                </div>
                <ul className="text-[11px] text-slate-400 space-y-1.5">
                  <li className="flex items-center space-x-2">
                    <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <span>RFC 5322 strict syntax verification</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <span>Real-time DNS MX record resolution</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <span>Disposable & honeypot filtering</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <span>CAN-SPAM postal footer & 1-click unsubscribe</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <span>Automatic timeline note logged on client CRM</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* TAB 2: MAILBOX FLEET & CAPACITY */}
        {/* ==================================================================== */}
        {tab === 'fleet' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">Registered Sending Mailboxes</h2>
                <p className="text-xs text-slate-400">
                  Warmup ramps, daily dispatch quotas, and inbox rotation health.
                </p>
              </div>
              <button
                onClick={() => setShowAddMailbox(true)}
                className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition shadow-md shadow-indigo-600/20"
              >
                <Plus className="h-4 w-4" />
                <span>Add SMTP / Workspace Mailbox</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {mailboxes.map((mb) => {
                const pct = Math.min(100, Math.round(((mb.sent_today || 0) / (mb.daily_cap || 35)) * 100));
                return (
                  <div
                    key={mb.id}
                    className="bento-tile specular-border rounded-2xl p-5 border border-slate-800 bg-slate-900/60 space-y-3"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-xs font-semibold text-white">{mb.display_name || 'Primary Mailbox'}</div>
                        <div className="text-xs font-mono text-indigo-300 truncate mt-0.5">{mb.email}</div>
                      </div>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-mono uppercase ${
                          mb.reputation_status === 'healthy'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                        }`}
                      >
                        {mb.reputation_status}
                      </span>
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span>Today's Dispatches</span>
                        <span className="font-mono text-white tabular">
                          {mb.sent_today} / {mb.daily_cap}
                        </span>
                      </div>
                      <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            pct > 90 ? 'bg-amber-500' : 'bg-gradient-to-r from-indigo-500 to-cyan-500'
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                      <span>Provider: <strong className="text-white font-mono uppercase">{mb.provider_type}</strong></span>
                      <span>Warmup: <strong className="text-emerald-400">{mb.skip_warmup ? 'Active' : 'Ramping'}</strong></span>
                    </div>
                  </div>
                );
              })}

              {mailboxes.length === 0 && (
                <div className="col-span-full p-8 text-center border border-dashed border-slate-800 rounded-2xl">
                  <Mail className="h-8 w-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-sm text-slate-400">No sending mailboxes registered yet.</p>
                  <button
                    onClick={() => setShowAddMailbox(true)}
                    className="mt-3 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold"
                  >
                    Register Your First Mailbox
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* TAB 3: DRAFTS & APPROVALS QUEUE */}
        {/* ==================================================================== */}
        {tab === 'queue' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">Outbound Approval Desk</h2>
                <p className="text-xs text-slate-400">
                  Review and approve pending cold outreach emails before they are dispatched.
                </p>
              </div>
            </div>

            <div className="bento-tile rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium">
                  <tr>
                    <th className="py-3 px-4">Recipient</th>
                    <th className="py-3 px-4">Subject & Excerpt</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Created</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {drafts.map((d) => (
                    <tr key={d.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-white">{d.recipient_name || d.recipient_email}</div>
                        <div className="text-[11px] font-mono text-indigo-400">{d.recipient_email}</div>
                        {d.company_name && (
                          <div className="text-[10px] text-slate-500">{d.company_name}</div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 max-w-md">
                        <div className="font-medium text-slate-200 truncate">{d.subject}</div>
                        <div className="text-[11px] text-slate-400 truncate mt-0.5">{d.body}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-full font-mono uppercase ${
                            d.status === 'sent'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                          }`}
                        >
                          {d.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-[11px] text-slate-400 whitespace-nowrap">
                        {d.created_at}
                      </td>
                      <td className="py-3.5 px-4 text-right space-x-2 whitespace-nowrap">
                        {d.status === 'pending_approval' && (
                          <button
                            onClick={() => handleSendDraft(d.id)}
                            className="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-semibold transition"
                          >
                            Approve & Dispatch
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteDraft(d.id)}
                          className="p-1.5 rounded-lg hover:bg-rose-500/10 text-slate-500 hover:text-rose-400 transition"
                          title="Delete draft"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {drafts.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-500">
                        No drafts waiting in queue. Use "Compose Email" and save as draft to test.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* TAB 4: DELIVERY LEDGER & OUTBOUND EVENTS */}
        {/* ==================================================================== */}
        {tab === 'logs' && (
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Outbound Activity & Audit Ledger</h2>
              <p className="text-xs text-slate-400">
                Immutable record of every sent, delivered, or bounced email dispatch.
              </p>
            </div>

            <div className="bento-tile rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium">
                  <tr>
                    <th className="py-3 px-4">Event</th>
                    <th className="py-3 px-4">Recipient</th>
                    <th className="py-3 px-4">Mailbox Used</th>
                    <th className="py-3 px-4">Message-ID</th>
                    <th className="py-3 px-4">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {events.map((ev) => (
                    <tr key={ev.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3.5 px-4">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-full font-mono uppercase ${
                            ev.event_type === 'sent' || ev.event_type === 'delivered'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                              : ev.event_type === 'replied'
                              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                              : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                          }`}
                        >
                          {ev.event_type}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-slate-200">
                        {ev.recipient_email}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-slate-400">
                        {ev.mailbox_email || 'Default Relay'}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[10px] text-slate-500 max-w-[200px] truncate">
                        {ev.message_id || 'n/a'}
                      </td>
                      <td className="py-3.5 px-4 text-[11px] text-slate-400 whitespace-nowrap">
                        {ev.created_at}
                      </td>
                    </tr>
                  ))}
                  {events.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-500">
                        No outbound email events recorded yet. Send your first email from the Compose tab!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* TAB 5: PRE-FLIGHT DELIVERABILITY INSPECTOR */}
        {/* ==================================================================== */}
        {tab === 'inspector' && (
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="bento-tile specular-border rounded-2xl p-6 border border-slate-800 bg-slate-900/60 space-y-4">
              <div>
                <h2 className="text-base font-semibold text-white flex items-center space-x-2">
                  <Shield className="h-5 w-5 text-indigo-400" />
                  <span>Pre-Flight Deliverability & MX Inspector</span>
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Test any target email before outreach. We query live DNS MX records, verify RFC 5322 syntax compliance, detect burner services, and verify suppression vault status.
                </p>
              </div>

              <form onSubmit={handleInspect} className="flex gap-2">
                <input
                  type="email"
                  required
                  placeholder="e.g. founder@company.com"
                  value={inspectEmail}
                  onChange={(e) => setInspectEmail(e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={inspectLoading}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center space-x-1.5 transition disabled:opacity-50"
                >
                  {inspectLoading ? (
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                  <span>Inspect Deliverability</span>
                </button>
              </form>

              {inspectResult && (
                <div className="pt-4 border-t border-slate-800 space-y-4 animate-fadeIn">
                  <div
                    className={`p-4 rounded-xl border flex items-start space-x-3 ${
                      inspectResult.is_deliverable
                        ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-200'
                        : 'bg-rose-950/40 border-rose-500/40 text-rose-200'
                    }`}
                  >
                    {inspectResult.is_deliverable ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                    ) : (
                      <XCircle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
                    )}
                    <div>
                      <div className="font-semibold text-sm">
                        {inspectResult.is_deliverable
                          ? 'Deliverable & Verified Address'
                          : 'Deliverability Risk Detected'}
                      </div>
                      <div className="text-xs mt-0.5">{inspectResult.reason}</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">RFC Syntax</div>
                      <div className="text-xs font-semibold text-white mt-1">
                        {inspectResult.syntax_valid ? 'Valid Standard' : 'Malformed'}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">DNS MX Servers</div>
                      <div className="text-xs font-semibold text-emerald-400 mt-1 truncate">
                        {inspectResult.has_mx ? inspectResult.mx_records[0] || 'Active' : 'No MX Records'}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Burner / Disposable</div>
                      <div className="text-xs font-semibold text-white mt-1">
                        {inspectResult.is_disposable ? 'Yes (Blocked)' : 'Clean Corporate'}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Honeypot / Spam Trap</div>
                      <div className="text-xs font-semibold text-white mt-1">
                        {inspectResult.is_spamtrap ? 'Trap Detected' : 'Clean'}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Suppression Vault</div>
                      <div className="text-xs font-semibold text-white mt-1">
                        {inspectResult.is_suppressed ? 'Suppressed (Opted-out)' : 'Clear to Contact'}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Confidence Score</div>
                      <div className="text-xs font-semibold text-cyan-400 mt-1">
                        {Math.round(inspectResult.confidence * 100)}%
                      </div>
                    </div>
                  </div>

                  {inspectResult.is_deliverable && (
                    <button
                      onClick={() => {
                        setToEmail(inspectResult.email);
                        setTab('compose');
                      }}
                      className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center justify-center space-x-2 transition"
                    >
                      <Send className="h-3.5 w-3.5" />
                      <span>Use this Email in Composer</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* ADD MAILBOX MODAL */}
        {/* ==================================================================== */}
        {showAddMailbox && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-fadeIn">
            <div className="w-full max-w-lg bento-tile specular-border rounded-2xl p-6 border border-slate-800 bg-slate-900 space-y-4 shadow-2xl">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center space-x-2">
                  <Server className="h-4 w-4 text-indigo-400" />
                  <h3 className="text-sm font-semibold text-white">Register Sending Mailbox</h3>
                </div>
                <button
                  onClick={() => setShowAddMailbox(false)}
                  className="text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleRegisterMailbox} className="space-y-3">
                <div>
                  <label className="text-[11px] text-slate-300 font-medium">Mailbox Email Address *</label>
                  <input
                    type="email"
                    required
                    placeholder="outreach@apexcore.ai"
                    value={newMailbox.email}
                    onChange={(e) => setNewMailbox({ ...newMailbox, email: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-300 font-medium">Display Name (Sender Name)</label>
                  <input
                    type="text"
                    placeholder="Alex Mercer (ApexCore)"
                    value={newMailbox.display_name}
                    onChange={(e) => setNewMailbox({ ...newMailbox, display_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] text-slate-300 font-medium">Daily Outbound Cap</label>
                    <input
                      type="number"
                      min={1}
                      max={200}
                      value={newMailbox.daily_cap}
                      onChange={(e) => setNewMailbox({ ...newMailbox, daily_cap: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-300 font-medium">SMTP Host</label>
                    <input
                      type="text"
                      placeholder="smtp.gmail.com"
                      value={newMailbox.smtp_host}
                      onChange={(e) => setNewMailbox({ ...newMailbox, smtp_host: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] text-slate-300 font-medium">SMTP Username</label>
                    <input
                      type="text"
                      placeholder="username / app password"
                      value={newMailbox.smtp_username}
                      onChange={(e) => setNewMailbox({ ...newMailbox, smtp_username: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-300 font-medium">SMTP Password</label>
                    <input
                      type="password"
                      placeholder="••••••••••••"
                      value={newMailbox.smtp_password}
                      onChange={(e) => setNewMailbox({ ...newMailbox, smtp_password: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <label className="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newMailbox.skip_warmup}
                      onChange={(e) => setNewMailbox({ ...newMailbox, skip_warmup: e.target.checked })}
                      className="rounded bg-slate-950 border-slate-800 text-indigo-600 focus:ring-0"
                    />
                    <span>Mailbox is already warmed up (start at full cap)</span>
                  </label>
                </div>

                <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setShowAddMailbox(false)}
                    className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300 hover:text-white text-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20"
                  >
                    Save & Activate Mailbox
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
};
