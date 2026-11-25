import { useState, useEffect } from 'react';
import type { FC, FormEvent } from 'react';
import {
  Mail, Send, CheckCircle2, AlertTriangle, XCircle, Shield,
  RefreshCw, Plus, Clock, Server, Eye, FileText, Check, ChevronRight,
  Sparkles, Trash2, Copy, ArrowRight, Search, X,
  Settings, Play, Pause, Zap, RotateCcw
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

  // Sent Email inspection modal state (Delivery Ledger)
  const [selectedEvent, setSelectedEvent] = useState<OutboundEvent | null>(null);
  const [copiedEventBody, setCopiedEventBody] = useState(false);
  const [eventFilter, setEventFilter] = useState<'all' | 'sent' | 'delivered' | 'replied' | 'bounced'>('all');
  const [eventSearch, setEventSearch] = useState('');

  // Draft review & edit modal state (Approval Desk)
  const [selectedDraft, setSelectedDraft] = useState<OutboundDraft | null>(null);
  const [editDraftForm, setEditDraftForm] = useState({
    subject: '',
    body: '',
    recipient_email: '',
    recipient_name: '',
    company_name: '',
  });
  const [savingDraft, setSavingDraft] = useState(false);
  const [draftFilter, setDraftFilter] = useState<'all' | 'pending' | 'sent'>('all');
  const [draftSearch, setDraftSearch] = useState('');

  // Mailbox registration & edit modal state
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

  const [selectedMailboxForEdit, setSelectedMailboxForEdit] = useState<Mailbox | null>(null);
  const [editMailboxForm, setEditMailboxForm] = useState({
    display_name: '',
    daily_cap: 35,
    skip_warmup: true,
    reputation_status: 'healthy',
    is_active: 1,
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    use_tls: true,
  });
  const [savingMailbox, setSavingMailbox] = useState(false);
  const [testingMailboxId, setTestingMailboxId] = useState<number | null>(null);
  const [mailboxTestResults, setMailboxTestResults] = useState<Record<number, { ok: boolean; message: string; latency_ms?: number }>>({});

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
      if (selectedDraft?.id === draftId) setSelectedDraft(null);
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Delete failed.' });
    }
  };

  // Open Draft for Inspection & Editing
  const handleSelectDraft = (d: OutboundDraft) => {
    setSelectedDraft(d);
    setEditDraftForm({
      subject: d.subject || '',
      body: d.body || '',
      recipient_email: d.recipient_email || '',
      recipient_name: d.recipient_name || '',
      company_name: d.company_name || '',
    });
  };

  // Save Edits to Draft
  const handleSaveDraft = async () => {
    if (!selectedDraft) return;
    setSavingDraft(true);
    try {
      const res = await apiFetch(`/api/email/drafts/${selectedDraft.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editDraftForm),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setFeedback({ type: 'success', message: `Draft #${selectedDraft.id} updated successfully.` });
      setSelectedDraft(null);
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to update draft.' });
    } finally {
      setSavingDraft(false);
    }
  };

  // Dispatch Draft directly from the review modal
  const handleDispatchModalDraft = async () => {
    if (!selectedDraft) return;
    setSending(true);
    try {
      await apiFetch(`/api/email/drafts/${selectedDraft.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editDraftForm),
      });
      await handleSendDraft(selectedDraft.id);
      setSelectedDraft(null);
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Dispatch failed.' });
    } finally {
      setSending(false);
    }
  };

  // Transfer Draft to Composer
  const handleLoadDraftIntoComposer = (d: OutboundDraft) => {
    setToEmail(d.recipient_email);
    setRecipientName(d.recipient_name || '');
    setCompanyName(d.company_name || '');
    setSubject(d.subject);
    setBody(d.body);
    setSelectedDraft(null);
    setTab('compose');
  };

  // Initiate Follow-Up from Sent Email
  const handleFollowUpFromEvent = (ev: OutboundEvent) => {
    const p = ev.payload || {};
    setToEmail(ev.recipient_email);
    setRecipientName(p.recipient_name || '');
    setCompanyName(p.company_name || '');
    const baseSubj = p.subject || 'Outbound Discussion';
    const cleanSubj = baseSubj.replace(/^re:\s*/i, '');
    setSubject(`Re: ${cleanSubj}`);
    const firstName = p.recipient_name ? p.recipient_name.split(' ')[0] : 'there';
    setBody(`Hi ${firstName},\n\nFollowing up on my previous note regarding ${cleanSubj}...\n\nBest,\n`);
    setSelectedEvent(null);
    setTab('compose');
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

  // Test live connection of a mailbox
  const handleTestMailbox = async (mbId: number) => {
    setTestingMailboxId(mbId);
    try {
      const res = await apiFetch(`/api/email/mailboxes/${mbId}/test`, { method: 'POST' });
      const data = await res.json();
      setMailboxTestResults((prev) => ({
        ...prev,
        [mbId]: { ok: data.ok, message: data.message, latency_ms: data.latency_ms }
      }));
      setFeedback({
        type: data.ok ? 'success' : 'error',
        message: data.message || (data.ok ? 'Mailbox connection verified.' : 'Connection failed.')
      });
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Test failed.' });
    } finally {
      setTestingMailboxId(null);
    }
  };

  // Toggle mailbox active/paused status
  const handleToggleMailbox = async (mbId: number) => {
    try {
      const res = await apiFetch(`/api/email/mailboxes/${mbId}/toggle`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setFeedback({
        type: 'success',
        message: `Mailbox status switched to ${data.reputation_status.toUpperCase()}.`
      });
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Status update failed.' });
    }
  };

  // Reset mailbox daily dispatches counter
  const handleResetMailboxCap = async (mbId: number) => {
    try {
      const res = await apiFetch(`/api/email/mailboxes/${mbId}/reset-cap`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setFeedback({ type: 'success', message: "Today's send counter reset to 0." });
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Reset failed.' });
    }
  };

  // Delete mailbox
  const handleDeleteMailbox = async (mbId: number) => {
    if (!window.confirm('Are you sure you want to remove this mailbox from outbound rotation?')) return;
    try {
      const res = await apiFetch(`/api/email/mailboxes/${mbId}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setFeedback({ type: 'success', message: 'Mailbox removed from fleet.' });
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Delete failed.' });
    }
  };

  // Open Edit Mailbox Modal
  const handleOpenEditMailbox = (mb: Mailbox) => {
    setSelectedMailboxForEdit(mb);
    setEditMailboxForm({
      display_name: mb.display_name || '',
      daily_cap: mb.daily_cap || 35,
      skip_warmup: Boolean(mb.skip_warmup),
      reputation_status: mb.reputation_status || 'healthy',
      is_active: mb.is_active ?? 1,
      smtp_host: '',
      smtp_port: 587,
      smtp_username: '',
      smtp_password: '',
      use_tls: true,
    });
  };

  // Save changes to mailbox
  const handleSaveMailboxEdit = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedMailboxForEdit) return;
    setSavingMailbox(true);
    try {
      const payload: any = {
        display_name: editMailboxForm.display_name,
        daily_cap: editMailboxForm.daily_cap,
        skip_warmup: editMailboxForm.skip_warmup,
        reputation_status: editMailboxForm.reputation_status,
        is_active: editMailboxForm.is_active,
      };
      if (editMailboxForm.smtp_host && editMailboxForm.smtp_username && editMailboxForm.smtp_password) {
        payload.smtp_host = editMailboxForm.smtp_host;
        payload.smtp_port = editMailboxForm.smtp_port;
        payload.smtp_username = editMailboxForm.smtp_username;
        payload.smtp_password = editMailboxForm.smtp_password;
        payload.use_tls = editMailboxForm.use_tls;
      }
      const res = await apiFetch(`/api/email/mailboxes/${selectedMailboxForEdit.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setSelectedMailboxForEdit(null);
      setFeedback({ type: 'success', message: `Mailbox ${selectedMailboxForEdit.email} updated successfully!` });
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Update failed.' });
    } finally {
      setSavingMailbox(false);
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
            <div className="flex items-center gap-3">
              {feedback.type === 'success' && tab === 'compose' && (
                <button
                  onClick={() => setTab('logs')}
                  className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 underline flex items-center gap-1"
                >
                  <span>View in Delivery Ledger</span>
                  <ArrowRight className="h-3 w-3" />
                </button>
              )}
              <button
                onClick={() => setFeedback(null)}
                className="text-slate-400 hover:text-white text-xs underline ml-2"
              >
                Dismiss
              </button>
            </div>
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
            <span>Approval Desk ({drafts.filter((d) => d.status === 'pending_approval').length})</span>
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
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                  <span>Registered Sending Mailboxes</span>
                  <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                    {mailboxes.length} configured
                  </span>
                </h2>
                <p className="text-xs text-slate-400">
                  Manage sending identities, test live SMTP reachability, calibrate daily quotas, and monitor warmup health.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowAddMailbox(true)}
                  className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition shadow-md shadow-indigo-600/20 whitespace-nowrap"
                >
                  <Plus className="h-4 w-4" />
                  <span>Add Mailbox</span>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {mailboxes.map((mb) => {
                const pct = Math.min(100, Math.round(((mb.sent_today || 0) / (mb.daily_cap || 35)) * 100));
                const testResult = mailboxTestResults[mb.id];
                const isTesting = testingMailboxId === mb.id;
                const isPaused = mb.reputation_status === 'paused' || mb.is_active === 0;

                return (
                  <div
                    key={mb.id}
                    className={`bento-tile specular-border rounded-2xl p-5 border bg-slate-900/60 space-y-4 transition ${
                      isPaused ? 'border-amber-500/30 opacity-80' : 'border-slate-800'
                    }`}
                  >
                    {/* Header: Name, Email & Status */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-white truncate">
                            {mb.display_name || 'Primary Mailbox'}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded uppercase font-mono bg-slate-800 text-slate-300 border border-slate-700/60">
                            {mb.provider_type}
                          </span>
                        </div>
                        <div className="text-xs font-mono text-indigo-300 truncate mt-0.5" title={mb.email}>
                          {mb.email}
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => handleToggleMailbox(mb.id)}
                          title={isPaused ? 'Resume Sending' : 'Pause Sending'}
                          className={`p-1.5 rounded-lg border transition ${
                            isPaused
                              ? 'bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20'
                              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                          }`}
                        >
                          {isPaused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
                        </button>
                        <button
                          onClick={() => handleOpenEditMailbox(mb)}
                          title="Configure Mailbox"
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700/60 text-slate-300 hover:text-white transition"
                        >
                          <Settings className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteMailbox(mb.id)}
                          title="Remove Mailbox"
                          className="p-1.5 rounded-lg hover:bg-rose-500/10 text-slate-500 hover:text-rose-400 transition"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Progress Bar & Counter */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span className="flex items-center gap-1">
                          <span>Today's Dispatches</span>
                          <span
                            className={`text-[9px] px-1 rounded uppercase font-mono ${
                              isPaused ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'
                            }`}
                          >
                            {isPaused ? 'PAUSED' : 'ACTIVE'}
                          </span>
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-white tabular">
                            {mb.sent_today} / {mb.daily_cap}
                          </span>
                          <button
                            onClick={() => handleResetMailboxCap(mb.id)}
                            title="Reset Today's Counter to 0"
                            className="text-slate-500 hover:text-slate-300 transition"
                          >
                            <RotateCcw className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                      <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            isPaused
                              ? 'bg-slate-600'
                              : pct > 90
                              ? 'bg-amber-500'
                              : 'bg-gradient-to-r from-indigo-500 to-cyan-500'
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>

                    {/* Telemetry Detail Chips */}
                    <div className="pt-2 border-t border-slate-800/80 grid grid-cols-2 gap-2 text-[11px] text-slate-400">
                      <div>
                        <span>Warmup: </span>
                        <strong className="text-emerald-400">
                          {mb.skip_warmup ? 'Active (Full Cap)' : 'Ramping Safe'}
                        </strong>
                      </div>
                      <div className="text-right">
                        <span>Credentials: </span>
                        <strong className="text-white font-mono">
                          {mb.has_credentials ? 'Verified' : 'Default Relay'}
                        </strong>
                      </div>
                    </div>

                    {/* Live Test Results Alert (If tested) */}
                    {testResult && (
                      <div
                        className={`p-2 rounded-lg text-[11px] flex items-center justify-between border ${
                          testResult.ok
                            ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-200'
                            : 'bg-rose-950/40 border-rose-500/30 text-rose-200'
                        }`}
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          {testResult.ok ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
                          )}
                          <span className="truncate">{testResult.message}</span>
                        </div>
                        {testResult.latency_ms !== undefined && (
                          <span className="font-mono text-[10px] text-slate-400 shrink-0 ml-1">
                            {testResult.latency_ms}ms
                          </span>
                        )}
                      </div>
                    )}

                    {/* Action Bar on Card */}
                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between gap-2">
                      <button
                        onClick={() => handleTestMailbox(mb.id)}
                        disabled={isTesting}
                        className="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white text-[11px] font-medium transition disabled:opacity-50"
                      >
                        {isTesting ? (
                          <RefreshCw className="h-3 w-3 animate-spin text-cyan-400" />
                        ) : (
                          <Zap className="h-3 w-3 text-cyan-400" />
                        )}
                        <span>{isTesting ? 'Testing…' : 'Test Relay'}</span>
                      </button>

                      <button
                        onClick={() => {
                          setSelectedMailboxId(mb.id);
                          setTab('compose');
                        }}
                        className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 hover:text-white text-[11px] font-medium transition"
                      >
                        <Send className="h-3 w-3" />
                        <span>Compose</span>
                      </button>
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
        {tab === 'queue' && (() => {
          const pendingCount = drafts.filter((d) => d.status === 'pending_approval').length;
          const sentCount = drafts.filter((d) => d.status === 'sent').length;
          const filteredDrafts = drafts.filter((d) => {
            if (draftFilter === 'pending' && d.status !== 'pending_approval') return false;
            if (draftFilter === 'sent' && d.status !== 'sent') return false;
            if (draftSearch.trim()) {
              const q = draftSearch.toLowerCase();
              const matchEmail = d.recipient_email.toLowerCase().includes(q);
              const matchName = (d.recipient_name || '').toLowerCase().includes(q);
              const matchCompany = (d.company_name || '').toLowerCase().includes(q);
              const matchSubj = d.subject.toLowerCase().includes(q);
              if (!matchEmail && !matchName && !matchCompany && !matchSubj) return false;
            }
            return true;
          });

          return (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                    <span>Outbound Approval Desk</span>
                    <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                      {drafts.length} drafts
                    </span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Review, edit, and approve pending cold outreach emails before live dispatch.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setTab('compose')}
                    className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Create New Draft</span>
                  </button>
                </div>
              </div>

              {/* Filter and Search Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/60 border border-slate-800">
                <div className="flex items-center space-x-1.5 overflow-x-auto">
                  <button
                    onClick={() => setDraftFilter('all')}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition whitespace-nowrap ${
                      draftFilter === 'all'
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                    }`}
                  >
                    All Drafts ({drafts.length})
                  </button>
                  <button
                    onClick={() => setDraftFilter('pending')}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition whitespace-nowrap flex items-center gap-1.5 ${
                      draftFilter === 'pending'
                        ? 'bg-amber-600 text-white'
                        : 'bg-slate-950 text-amber-400/80 hover:text-amber-300 border border-slate-800'
                    }`}
                  >
                    <Clock className="h-3 w-3" />
                    <span>Pending Approval ({pendingCount})</span>
                  </button>
                  <button
                    onClick={() => setDraftFilter('sent')}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition whitespace-nowrap flex items-center gap-1.5 ${
                      draftFilter === 'sent'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-slate-950 text-emerald-400/80 hover:text-emerald-300 border border-slate-800'
                    }`}
                  >
                    <CheckCircle2 className="h-3 w-3" />
                    <span>Dispatched ({sentCount})</span>
                  </button>
                </div>

                <div className="relative min-w-[220px]">
                  <Search className="h-3.5 w-3.5 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="Search recipient or subject..."
                    value={draftSearch}
                    onChange={(e) => setDraftSearch(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
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
                    {filteredDrafts.map((d) => (
                      <tr
                        key={d.id}
                        onClick={() => handleSelectDraft(d)}
                        className="hover:bg-slate-800/40 cursor-pointer transition group"
                      >
                        <td className="py-3.5 px-4">
                          <div className="font-medium text-white">{d.recipient_name || d.recipient_email}</div>
                          <div className="text-[11px] font-mono text-indigo-400">{d.recipient_email}</div>
                          {d.company_name && (
                            <div className="text-[10px] text-slate-500">{d.company_name}</div>
                          )}
                        </td>
                        <td className="py-3.5 px-4 max-w-md">
                          <div className="font-medium text-slate-200 truncate group-hover:text-indigo-300 transition">
                            {d.subject}
                          </div>
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
                        <td className="py-3.5 px-4 text-right space-x-2 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => handleSelectDraft(d)}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white text-[11px] font-medium transition"
                          >
                            <Eye className="h-3 w-3 text-indigo-400" />
                            <span>Review & Edit</span>
                          </button>
                          {d.status === 'pending_approval' && (
                            <button
                              onClick={() => handleSendDraft(d.id)}
                              className="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-semibold transition shadow-sm"
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
                    {filteredDrafts.length === 0 && (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-slate-500">
                          {draftSearch ? 'No drafts matching search query.' : 'No drafts waiting in this queue.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })()}

        {/* ==================================================================== */}
        {/* TAB 4: DELIVERY LEDGER & OUTBOUND EVENTS */}
        {/* ==================================================================== */}
        {tab === 'logs' && (() => {
          const filteredEvents = events.filter((ev) => {
            if (eventFilter !== 'all' && ev.event_type !== eventFilter) return false;
            if (eventSearch.trim()) {
              const q = eventSearch.toLowerCase();
              const matchEmail = ev.recipient_email.toLowerCase().includes(q);
              const matchSubj = (ev.payload?.subject || '').toLowerCase().includes(q);
              const matchMailbox = (ev.mailbox_email || '').toLowerCase().includes(q);
              const matchName = (ev.payload?.recipient_name || '').toLowerCase().includes(q);
              const matchCompany = (ev.payload?.company_name || '').toLowerCase().includes(q);
              if (!matchEmail && !matchSubj && !matchMailbox && !matchName && !matchCompany) return false;
            }
            return true;
          });

          return (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                    <span>Outbound Activity & Audit Ledger</span>
                    <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                      {events.length} dispatched
                    </span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Immutable record of sent, delivered, or bounced emails. Click any record to inspect the full body and deliverability diagnostics.
                  </p>
                </div>

                <button
                  onClick={loadData}
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white text-xs font-medium transition self-start sm:self-auto"
                >
                  <RefreshCw className="h-3 w-3 text-indigo-400" />
                  <span>Refresh Ledger</span>
                </button>
              </div>

              {/* Event Filters & Search */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/60 border border-slate-800">
                <div className="flex items-center space-x-1.5 overflow-x-auto">
                  {(['all', 'sent', 'delivered', 'replied', 'bounced'] as const).map((filterVal) => (
                    <button
                      key={filterVal}
                      onClick={() => setEventFilter(filterVal)}
                      className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition whitespace-nowrap ${
                        eventFilter === filterVal
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                      }`}
                    >
                      {filterVal === 'all' ? `All Events (${events.length})` : filterVal}
                    </button>
                  ))}
                </div>

                <div className="relative min-w-[240px]">
                  <Search className="h-3.5 w-3.5 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="Search recipient, subject, or relay..."
                    value={eventSearch}
                    onChange={(e) => setEventSearch(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="bento-tile rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium">
                    <tr>
                      <th className="py-3 px-4">Event</th>
                      <th className="py-3 px-4">Recipient</th>
                      <th className="py-3 px-4">Subject & Excerpt</th>
                      <th className="py-3 px-4">Mailbox Used</th>
                      <th className="py-3 px-4">Message-ID</th>
                      <th className="py-3 px-4">Timestamp</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredEvents.map((ev) => (
                      <tr
                        key={ev.id}
                        onClick={() => setSelectedEvent(ev)}
                        className="hover:bg-slate-800/40 cursor-pointer transition group"
                      >
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
                        <td className="py-3.5 px-4">
                          <div className="font-medium text-white flex items-center gap-1.5">
                            <span>{ev.payload?.recipient_name || ev.recipient_email}</span>
                            {ev.payload?.company_name && (
                              <span className="text-[10px] text-slate-500 font-normal">({ev.payload.company_name})</span>
                            )}
                          </div>
                          <div className="text-[11px] font-mono text-indigo-400">{ev.recipient_email}</div>
                        </td>
                        <td className="py-3.5 px-4 max-w-xs">
                          <div className="font-medium text-slate-200 truncate group-hover:text-indigo-300 transition">
                            {ev.payload?.subject || '(No Subject)'}
                          </div>
                          <div className="text-[11px] text-slate-400 truncate mt-0.5">
                            {ev.payload?.body || '(No preview body recorded)'}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 font-mono text-slate-400 text-[11px]">
                          {ev.mailbox_email || ev.payload?.diagnostics?.sender || 'Default Relay'}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-[10px] text-slate-500 max-w-[140px] truncate" title={ev.message_id || 'n/a'}>
                          {ev.message_id || 'n/a'}
                        </td>
                        <td className="py-3.5 px-4 text-[11px] text-slate-400 whitespace-nowrap">
                          {ev.created_at}
                        </td>
                        <td className="py-3.5 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => setSelectedEvent(ev)}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-300 hover:text-white border border-indigo-500/20 text-[11px] font-medium transition"
                          >
                            <Eye className="h-3 w-3 text-indigo-400" />
                            <span>View Sent Email</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                    {filteredEvents.length === 0 && (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-slate-500">
                          {eventSearch ? 'No outbound dispatches match your filter.' : 'No outbound email events recorded yet.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })()}

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
                        ? 'bg-emerald-500/15 border-emerald-500/40 text-slate-100'
                        : 'bg-rose-500/15 border-rose-500/40 text-slate-100'
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

        {/* ==================================================================== */}
        {/* VIEW SENT EMAIL INSPECTION MODAL (DELIVERY LEDGER) */}
        {/* ==================================================================== */}
        {selectedEvent && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-fadeIn">
            <div className="w-full max-w-2xl bento-tile specular-border rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
              {/* Header */}
              <div className="p-4 sm:p-5 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                    <Mail className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-white">Sent Outbound Email</h3>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-mono uppercase ${
                          selectedEvent.event_type === 'sent' || selectedEvent.event_type === 'delivered'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : selectedEvent.event_type === 'replied'
                            ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                        }`}
                      >
                        {selectedEvent.event_type}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5 font-mono">
                      Event #{selectedEvent.id} · Dispatched {selectedEvent.created_at}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Scrollable Modal Content */}
              <div className="p-5 space-y-4 overflow-y-auto flex-1">
                {/* Email Meta Card */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2.5 text-xs">
                  <div className="flex items-start justify-between border-b border-slate-800/60 pb-2.5">
                    <span className="text-slate-400 font-medium">Subject:</span>
                    <span className="font-semibold text-white text-right max-w-md">
                      {selectedEvent.payload?.subject || 'Outbound Brief'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">From:</span>
                    <span className="font-mono text-indigo-300 font-medium">
                      {selectedEvent.mailbox_email || selectedEvent.payload?.diagnostics?.sender || 'Default Relay'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">To:</span>
                    <span className="font-mono text-slate-200">
                      {selectedEvent.payload?.recipient_name
                        ? `${selectedEvent.payload.recipient_name} <${selectedEvent.recipient_email}>`
                        : selectedEvent.recipient_email}
                      {selectedEvent.payload?.company_name && (
                        <span className="text-slate-500 ml-1">({selectedEvent.payload.company_name})</span>
                      )}
                    </span>
                  </div>
                  {selectedEvent.message_id && (
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-400">Message-ID:</span>
                      <span className="font-mono text-slate-500 truncate max-w-[320px]" title={selectedEvent.message_id}>
                        {selectedEvent.message_id}
                      </span>
                    </div>
                  )}
                </div>

                {/* Deliverability Diagnostics Telemetry */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-mono block">Delivery Telemetry</span>
                    <span className="text-xs font-medium text-emerald-400 flex items-center gap-1.5 mt-1">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      <span>Verified Dispatched</span>
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-mono block">Target DNS MX</span>
                    <span
                      className="text-xs font-mono text-slate-300 truncate block mt-1"
                      title={selectedEvent.payload?.diagnostics?.domain_mx?.[0] || 'Active MX'}
                    >
                      {selectedEvent.payload?.diagnostics?.domain_mx?.[0] || 'Active MX'}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 col-span-2 sm:col-span-1">
                    <span className="text-[10px] text-slate-500 uppercase font-mono block">Confidence Score</span>
                    <span className="text-xs font-semibold text-cyan-400 block mt-1">
                      {Math.round((selectedEvent.payload?.diagnostics?.confidence || 0.95) * 100)}% Deliverable
                    </span>
                  </div>
                </div>

                {/* Formatted Email Body Container */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-300 font-medium">Dispatched Email Content</span>
                    <button
                      onClick={() => {
                        const bodyText = selectedEvent.payload?.body || '';
                        navigator.clipboard.writeText(bodyText);
                        setCopiedEventBody(true);
                        setTimeout(() => setCopiedEventBody(false), 2000);
                      }}
                      className="flex items-center space-x-1 text-[11px] text-slate-400 hover:text-white transition"
                    >
                      <Copy className="h-3 w-3" />
                      <span>{copiedEventBody ? 'Copied to clipboard!' : 'Copy Body'}</span>
                    </button>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 font-mono whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
                    {selectedEvent.payload?.body || 'No message body stored for this historical event.'}
                  </div>
                  <div className="text-[10px] text-slate-500 pt-1 flex items-center gap-1.5">
                    <Shield className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <span>Attached CAN-SPAM physical address & 1-click RFC 8058 unsubscribe header</span>
                  </div>
                </div>
              </div>

              {/* Footer Actions */}
              <div className="p-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300 hover:text-white text-xs font-medium transition"
                >
                  Close
                </button>
                <button
                  onClick={() => handleFollowUpFromEvent(selectedEvent)}
                  className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition"
                >
                  <Send className="h-3.5 w-3.5" />
                  <span>Send Follow-Up Email</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* REVIEW & EDIT DRAFT MODAL (APPROVAL DESK) */}
        {/* ==================================================================== */}
        {selectedDraft && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-fadeIn">
            <div className="w-full max-w-2xl bento-tile specular-border rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
              {/* Header */}
              <div className="p-4 sm:p-5 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
                    <Clock className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-white">Review & Edit Outbound Draft</h3>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-mono uppercase ${
                          selectedDraft.status === 'sent'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                        }`}
                      >
                        {selectedDraft.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5 font-mono">
                      Draft #{selectedDraft.id} · Queued {selectedDraft.created_at}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedDraft(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Form Content - Scrollable */}
              <div className="p-5 space-y-3.5 overflow-y-auto flex-1 text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-400 font-medium">Recipient Email *</label>
                    <input
                      type="email"
                      required
                      value={editDraftForm.recipient_email}
                      onChange={(e) => setEditDraftForm({ ...editDraftForm, recipient_email: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white mt-1 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 font-medium">Recipient Name</label>
                    <input
                      type="text"
                      placeholder="e.g. Sarah Jenkins"
                      value={editDraftForm.recipient_name}
                      onChange={(e) => setEditDraftForm({ ...editDraftForm, recipient_name: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white mt-1 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-slate-400 font-medium">Company Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Acme Corp"
                    value={editDraftForm.company_name}
                    onChange={(e) => setEditDraftForm({ ...editDraftForm, company_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white mt-1 focus:border-indigo-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-400 font-medium">Subject Line *</label>
                  <input
                    type="text"
                    required
                    value={editDraftForm.subject}
                    onChange={(e) => setEditDraftForm({ ...editDraftForm, subject: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white mt-1 focus:border-indigo-500 focus:outline-none"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-slate-400 font-medium">Email Message Body *</label>
                    <span className="text-[11px] text-slate-500">
                      {editDraftForm.body.split(/\s+/).filter(Boolean).length} words · {editDraftForm.body.length} chars
                    </span>
                  </div>
                  <textarea
                    rows={8}
                    required
                    value={editDraftForm.body}
                    onChange={(e) => setEditDraftForm({ ...editDraftForm, body: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-white font-mono mt-1 focus:border-indigo-500 focus:outline-none leading-relaxed"
                  />
                </div>
              </div>

              {/* Actions Footer */}
              <div className="p-4 border-t border-slate-800 bg-slate-950/60 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleLoadDraftIntoComposer(selectedDraft)}
                    className="px-3 py-2 rounded-xl border border-slate-800 text-slate-300 hover:text-white text-xs font-medium transition"
                  >
                    Open in Full Composer
                  </button>
                  <button
                    onClick={() => handleDeleteDraft(selectedDraft.id)}
                    className="px-3 py-2 rounded-xl hover:bg-rose-500/10 text-rose-400 text-xs font-medium transition"
                  >
                    Delete Draft
                  </button>
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleSaveDraft}
                    disabled={savingDraft}
                    className="px-4 py-2 rounded-xl border border-slate-700 bg-slate-900 text-white text-xs font-medium hover:border-slate-600 transition disabled:opacity-50"
                  >
                    {savingDraft ? 'Saving…' : 'Save Changes'}
                  </button>
                  {selectedDraft.status === 'pending_approval' && (
                    <button
                      onClick={handleDispatchModalDraft}
                      disabled={sending}
                      className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 transition disabled:opacity-50"
                    >
                      <Send className="h-3.5 w-3.5" />
                      <span>{sending ? 'Dispatching…' : 'Approve & Dispatch Now'}</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* CONFIGURE / EDIT MAILBOX MODAL */}
        {/* ==================================================================== */}
        {selectedMailboxForEdit && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-fadeIn">
            <div className="w-full max-w-lg bento-tile specular-border rounded-2xl p-6 border border-slate-800 bg-slate-900 space-y-4 shadow-2xl">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center space-x-2">
                  <Settings className="h-4 w-4 text-indigo-400" />
                  <h3 className="text-sm font-semibold text-white">
                    Configure Mailbox ({selectedMailboxForEdit.email})
                  </h3>
                </div>
                <button
                  onClick={() => setSelectedMailboxForEdit(null)}
                  className="text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleSaveMailboxEdit} className="space-y-3">
                <div>
                  <label className="text-[11px] text-slate-300 font-medium">Display Name (Sender Name)</label>
                  <input
                    type="text"
                    placeholder="Alex Mercer (ApexCore)"
                    value={editMailboxForm.display_name}
                    onChange={(e) => setEditMailboxForm({ ...editMailboxForm, display_name: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] text-slate-300 font-medium">Daily Outbound Quota</label>
                    <input
                      type="number"
                      min={1}
                      max={200}
                      value={editMailboxForm.daily_cap}
                      onChange={(e) => setEditMailboxForm({ ...editMailboxForm, daily_cap: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-300 font-medium">Sending State</label>
                    <select
                      value={editMailboxForm.reputation_status}
                      onChange={(e) => setEditMailboxForm({
                        ...editMailboxForm,
                        reputation_status: e.target.value,
                        is_active: e.target.value === 'paused' ? 0 : 1
                      })}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none mt-1"
                    >
                      <option value="healthy">Active / Healthy</option>
                      <option value="paused">Paused (Exclude from rotation)</option>
                    </select>
                  </div>
                </div>

                <div className="pt-1">
                  <label className="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editMailboxForm.skip_warmup}
                      onChange={(e) => setEditMailboxForm({ ...editMailboxForm, skip_warmup: e.target.checked })}
                      className="rounded bg-slate-950 border-slate-800 text-indigo-600 focus:ring-0"
                    />
                    <span>Mailbox is already warmed up (start at full capacity)</span>
                  </label>
                </div>

                {/* Optional Custom SMTP Section */}
                <div className="pt-2 border-t border-slate-800/80">
                  <div className="text-[11px] font-semibold text-slate-400 mb-2">
                    Custom SMTP Relay Credentials (Optional)
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="col-span-2">
                      <label className="text-[10px] text-slate-500 font-medium">SMTP Host</label>
                      <input
                        type="text"
                        placeholder="smtp.gmail.com"
                        value={editMailboxForm.smtp_host}
                        onChange={(e) => setEditMailboxForm({ ...editMailboxForm, smtp_host: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none mt-0.5"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-500 font-medium">Port</label>
                      <input
                        type="number"
                        value={editMailboxForm.smtp_port}
                        onChange={(e) => setEditMailboxForm({ ...editMailboxForm, smtp_port: Number(e.target.value) })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none mt-0.5"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <div>
                      <label className="text-[10px] text-slate-500 font-medium">Username</label>
                      <input
                        type="text"
                        placeholder="user@domain.com"
                        value={editMailboxForm.smtp_username}
                        onChange={(e) => setEditMailboxForm({ ...editMailboxForm, smtp_username: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none mt-0.5"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-500 font-medium">Password</label>
                      <input
                        type="password"
                        placeholder="••••••••••••"
                        value={editMailboxForm.smtp_password}
                        onChange={(e) => setEditMailboxForm({ ...editMailboxForm, smtp_password: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none mt-0.5"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setSelectedMailboxForEdit(null)}
                    className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300 hover:text-white text-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingMailbox}
                    className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition disabled:opacity-50"
                  >
                    {savingMailbox ? 'Saving…' : 'Save Mailbox Settings'}
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
