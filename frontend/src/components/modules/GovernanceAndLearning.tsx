import { useState, useEffect } from 'react';
import type { FC } from 'react';
import {
  ShieldAlert, ShieldCheck, CheckCircle2, AlertTriangle,
  Mail, Award, Lock, HelpCircle, ArrowRight
} from 'lucide-react';

import { apiFetch, apiErrorMessage } from '../../lib/api';

interface PolicyRule {
  rule_name: string;
  level: string;
  description: string;
  is_hard_invariant: boolean;
}

interface PolicyDecision {
  id: number;
  rule_name: string;
  allowed: number;
  reason: string;
  created_at: string;
}

interface Mailbox {
  id: number;
  email: string;
  display_name: string;
  provider_type: string;
  daily_cap: number;
  effective_daily_cap: number;
  sent_last_24h: number;
  esp: string | null;
  has_credentials: boolean;
  reputation_status: string;
  is_active: number;
}

export const GovernanceAndLearning: FC = () => {
  const [subTab, setSubTab] = useState<'policy' | 'learning' | 'mailboxes'>('policy');

  // Policy State
  const [rules, setRules] = useState<PolicyRule[]>([
    { rule_name: 'marketplace_submit', level: 'NEVER', description: 'Upwork & Freelancer proposals: human review & submission required.', is_hard_invariant: true },
    { rule_name: 'linkedin_action', level: 'NEVER', description: 'LinkedIn automation & scrapers: strictly prohibited by platform rules.', is_hard_invariant: true },
    { rule_name: 'outbound_first_touch', level: 'L1', description: 'First cold touch to new companies: requires human review in Approval Inbox.', is_hard_invariant: false },
    { rule_name: 'sequence_followup', level: 'L2', description: 'Automated cadence follow-ups: runs only if verified, not replied, and unsuppressed.', is_hard_invariant: false },
    { rule_name: 'reply_dispatch', level: 'L1', description: 'Responses to inbound prospect replies: draft prepared for human approval.', is_hard_invariant: false },
    { rule_name: 'crm_sync', level: 'L3', description: 'HubSpot / Pipedrive meeting sync: autonomous background execution.', is_hard_invariant: false },
  ]);
  const [decisions, setDecisions] = useState<PolicyDecision[]>([]);
  const [evalAction, setEvalAction] = useState('outbound_first_touch');
  const [evalResult, setEvalResult] = useState<any>(null);

  // Learning Loop State
  const [learningReport, setLearningReport] = useState<any>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  // Mailbox State
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [verifyEmail, setVerifyEmail] = useState('alex@resend.com');
  const [verifyResult, setVerifyResult] = useState<any>(null);
  const [verifying, setVerifying] = useState(false);

  const [newMailboxEmail, setNewMailboxEmail] = useState('');
  const [newMailboxType, setNewMailboxType] = useState('smtp');
  const [newMailboxCap, setNewMailboxCap] = useState(35);
  const [smtp, setSmtp] = useState({ host: '', port: 587, username: '', password: '' });
  const [alreadyWarmed, setAlreadyWarmed] = useState(false);
  const [mailboxError, setMailboxError] = useState('');

  const loadData = async () => {
    try {
      // 1. Load decisions
      const decRes = await apiFetch('/api/policy/decisions?limit=15');
      if (decRes.ok) setDecisions(await decRes.json());

      // 2. Load learning report
      setLoadingReport(true);
      const repRes = await apiFetch('/api/analytics/learning_report');
      if (repRes.ok) setLearningReport(await repRes.json());
      setLoadingReport(false);

      // 3. Load mailboxes
      const mbRes = await apiFetch('/api/outbound/mailboxes');
      if (mbRes.ok) setMailboxes(await mbRes.json());
    } catch {
      setLoadingReport(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(loadData, 0);
    return () => clearTimeout(t);
  }, []);

  const handleUpdatePolicyLevel = async (ruleName: string, newLevel: string) => {
    try {
      await apiFetch('/api/policy/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rule_name: ruleName, level: newLevel })
      });
      setRules(prev => prev.map(r => r.rule_name === ruleName ? { ...r, level: newLevel } : r));
    } catch (e) {
      console.error(e);
    }
  };

  const handleEvaluateTest = async () => {
    try {
      const res = await apiFetch('/api/policy/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_type: evalAction,
          context: {
            email_verification_status: 'verified',
            is_suppressed: false,
            deal_value: 3500,
            jurisdiction_allowed: true
          }
        })
      });
      if (res.ok) {
        setEvalResult(await res.json());
        // Refresh decision log
        const decRes = await apiFetch('/api/policy/decisions?limit=15');
        if (decRes.ok) setDecisions(await decRes.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleVerifyEmail = async () => {
    setVerifying(true);
    try {
      const res = await apiFetch('/api/outbound/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: verifyEmail })
      });
      if (res.ok) setVerifyResult(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setVerifying(false);
    }
  };

  const handleRegisterMailbox = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMailboxEmail) return;
    try {
      const res = await apiFetch('/api/outbound/mailboxes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: newMailboxEmail,
          provider_type: newMailboxType,
          daily_cap: Number(newMailboxCap),
          skip_warmup: alreadyWarmed,
          smtp_host: smtp.host || null,
          smtp_port: Number(smtp.port),
          smtp_username: smtp.username || null,
          smtp_password: smtp.password || null
        })
      });
      setMailboxError('');
      if (!res.ok) {
        setMailboxError(apiErrorMessage(res.status, await res.json()));
        return;
      }
      if (res.ok) {
        setNewMailboxEmail('');
        setSmtp({ host: '', port: 587, username: '', password: '' });
        const mbRes = await apiFetch('/api/outbound/mailboxes');
        if (mbRes.ok) setMailboxes(await mbRes.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2.5">
            <span>Autonomy Policy, Learning & Dispatch Fleet</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
              PHASE 4 & 5 GOVERNANCE
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Enforces policy-governed hybrid autonomy (L0–L3), monitors real win/loss proposal learning loops, and oversees mailbox deliverability fleets.
          </p>
        </div>

        {/* Sub-Tabs */}
        <div className="flex items-center gap-1 p-1 bg-slate-900/90 border border-slate-800 rounded-xl backdrop-blur-md self-start">
          <button
            onClick={() => setSubTab('policy')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              subTab === 'policy'
                ? 'bg-gradient-to-r from-amber-600 to-amber-500 text-white shadow-md shadow-amber-600/25'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <Lock className="h-3.5 w-3.5" />
            <span>Autonomy Policies</span>
          </button>
          <button
            onClick={() => setSubTab('learning')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              subTab === 'learning'
                ? 'bg-gradient-to-r from-amber-600 to-amber-500 text-white shadow-md shadow-amber-600/25'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <Award className="h-3.5 w-3.5" />
            <span>Learning Loop & A/B</span>
          </button>
          <button
            onClick={() => setSubTab('mailboxes')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              subTab === 'mailboxes'
                ? 'bg-gradient-to-r from-amber-600 to-amber-500 text-white shadow-md shadow-amber-600/25'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <Mail className="h-3.5 w-3.5" />
            <span>Mailbox Fleet & Gate</span>
          </button>
        </div>
      </div>

      {/* ==================== SUB-TAB 1: AUTONOMY POLICY ==================== */}
      {subTab === 'policy' && (
        <div className="space-y-6">
          {/* Policy Invariant Alert */}
          <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-950/20 flex items-start space-x-3">
            <ShieldAlert className="h-5 w-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div className="text-xs text-slate-300 space-y-1">
              <span className="font-semibold text-amber-300">Enterprise Guardrail Policy (Section 5):</span>
              <p>
                Autonomy is a strict policy per tenant, never an unguarded switch. Upwork proposal submissions and LinkedIn actions are hard-coded to <strong className="text-white">NEVER AUTO</strong> to protect platform standing. All outbound sends fail-closed unless email verification is <strong className="text-white">verified</strong>.
              </p>
            </div>
          </div>

          {/* Policy Matrix Table */}
          <div className="bento-tile specular-border rounded-2xl border border-slate-800 p-6 space-y-4">
            <h2 className="text-sm font-semibold text-white flex items-center space-x-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <span>Tenant Autonomy Matrix</span>
            </h2>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-mono">
                    <th className="py-2.5 px-3">Action Type</th>
                    <th className="py-2.5 px-3">Current Level</th>
                    <th className="py-2.5 px-3">Description & Guardrails</th>
                    <th className="py-2.5 px-3 text-right">Policy Control</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-850">
                  {rules.map((rule) => (
                    <tr key={rule.rule_name} className="hover:bg-slate-900/40">
                      <td className="py-3 px-3 font-mono font-medium text-white">{rule.rule_name}</td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                          rule.level === 'NEVER'
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            : rule.level === 'L1'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : rule.level === 'L2'
                            ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}>
                          {rule.level === 'NEVER' ? 'NEVER (Hard Block)' : `${rule.level} ${rule.level === 'L1' ? 'Draft + Approve' : rule.level === 'L2' ? 'Guarded Auto' : 'Delegated'}`}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-300">{rule.description}</td>
                      <td className="py-3 px-3 text-right">
                        {rule.is_hard_invariant ? (
                          <span className="text-[10px] text-slate-400 font-mono italic">Platform Lock</span>
                        ) : (
                          <select
                            value={rule.level}
                            onChange={(e) => handleUpdatePolicyLevel(rule.rule_name, e.target.value)}
                            className="bg-slate-850 border border-slate-750 text-white rounded-lg px-2 py-1 text-xs font-mono focus:border-amber-500 focus:outline-none"
                          >
                            <option value="L0">L0 (Observe)</option>
                            <option value="L1">L1 (Draft + Human)</option>
                            <option value="L2">L2 (Guarded Auto)</option>
                            <option value="L3">L3 (Delegated)</option>
                          </select>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Workbench & Live Decisions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Interactive Policy Tester */}
            <div className="bento-tile specular-border rounded-2xl border border-slate-800 p-6 space-y-4">
              <h3 className="text-sm font-semibold text-white">Policy Decision Tester</h3>
              <p className="text-xs text-slate-400">
                Simulates real runtime policy decisions against verified contact states and deal values.
              </p>

              <div className="space-y-3">
                <div>
                  <label className="text-xs text-slate-400 font-medium">Test Action Type</label>
                  <select
                    value={evalAction}
                    onChange={(e) => setEvalAction(e.target.value)}
                    className="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-white"
                  >
                    <option value="outbound_first_touch">outbound_first_touch</option>
                    <option value="sequence_followup">sequence_followup</option>
                    <option value="marketplace_submit">marketplace_submit</option>
                    <option value="linkedin_action">linkedin_action</option>
                    <option value="crm_sync">crm_sync</option>
                  </select>
                </div>

                <button
                  onClick={handleEvaluateTest}
                  className="w-full py-2 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-slate-950 font-semibold text-xs rounded-xl transition-all shadow-sm flex items-center justify-center space-x-1.5"
                >
                  <span>Evaluate Action Policy</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>

                {evalResult && (
                  <div className={`p-3 rounded-xl border text-xs font-mono space-y-1 ${
                    evalResult.allowed && !evalResult.requires_human_approval
                      ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
                      : evalResult.allowed
                      ? 'bg-amber-950/20 border-amber-500/30 text-amber-300'
                      : 'bg-rose-950/20 border-rose-500/30 text-rose-300'
                  }`}>
                    <div><strong>Allowed:</strong> {String(evalResult.allowed)}</div>
                    <div><strong>Requires Human Approval:</strong> {String(evalResult.requires_human_approval)}</div>
                    <div><strong>Autonomy Level:</strong> {evalResult.autonomy_level}</div>
                    <div><strong>Reason:</strong> {evalResult.reason}</div>
                  </div>
                )}
              </div>
            </div>

            {/* Live Decision Audit Log */}
            <div className="bento-tile specular-border rounded-2xl border border-slate-800 p-6 space-y-4">
              <h3 className="text-sm font-semibold text-white">Policy Decision Audit Trail</h3>
              <p className="text-xs text-slate-400">
                Every action execution attempts are logged with reason and timestamp.
              </p>

              <div className="space-y-2 max-h-60 overflow-y-auto">
                {decisions.length === 0 ? (
                  <div className="text-xs text-slate-400 py-4 text-center">No logged decisions yet.</div>
                ) : (
                  decisions.map((d) => (
                    <div key={d.id} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs flex items-center justify-between">
                      <div className="space-y-0.5">
                        <div className="font-mono text-white font-medium">{d.rule_name}</div>
                        <div className="text-[11px] text-slate-400 truncate max-w-xs">{d.reason}</div>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                        d.allowed ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                      }`}>
                        {d.allowed ? 'ALLOWED' : 'BLOCKED'}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================== SUB-TAB 2: LEARNING LOOP ==================== */}
      {subTab === 'learning' && (
        <div className="space-y-6">
          {loadingReport ? (
            <div className="p-8 text-center text-slate-400 text-xs font-mono">Synthesizing learning loop report...</div>
          ) : learningReport ? (
            <div className="space-y-6">
              {/* Deliverability Health Card */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
                  <div className="text-xs text-slate-400">Total Sent / Replies</div>
                  <div className="text-xl font-bold text-white mt-1">
                    {learningReport.summary.total_outreach_sent} / {learningReport.summary.total_replies}
                  </div>
                  <div className="text-[11px] text-cyan-400 mt-0.5">
                    {learningReport.summary.reply_rate_percent}% Reply Rate
                  </div>
                </div>

                <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
                  <div className="text-xs text-slate-400">Bounce Rate (&lt;2.0% Gate)</div>
                  <div className={`text-xl font-bold mt-1 ${learningReport.summary.bounce_rate_percent > 2.0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                    {learningReport.summary.bounce_rate_percent}%
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    Spam Complaints: {learningReport.summary.complaint_rate_percent}%
                  </div>
                </div>

                <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
                  <div className="text-xs text-slate-400">Meetings Booked</div>
                  <div className="text-xl font-bold text-white mt-1">
                    {learningReport.summary.meetings_booked}
                  </div>
                  <div className="text-[11px] text-indigo-400 mt-0.5">
                    ${learningReport.summary.cost_per_meeting_usd} / meeting
                  </div>
                </div>

                <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
                  <div className="text-xs text-slate-400">Deliverability State</div>
                  <div className="text-lg font-bold text-emerald-300 mt-1 flex items-center space-x-1.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    <span>{learningReport.deliverability_health}</span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    {learningReport.summary.evidence_records_stored} Stored Proof Facts
                  </div>
                </div>
              </div>

              {/* Proposal Variant Performance */}
              <div className="bento-tile specular-border rounded-2xl border border-slate-800 p-6 space-y-4">
                <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                  <Award className="h-4 w-4 text-amber-400" />
                  <span>Proposal Studio A/B Multi-Armed Bandit</span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-950/20 space-y-2">
                    <div className="font-bold text-indigo-300">VARIANT A (Technical Architecture)</div>
                    <div className="text-slate-300">Total Drafts: {learningReport.proposal_variant_performance?.A?.total || 0}</div>
                    <div className="text-emerald-400">Won Sprints: {learningReport.proposal_variant_performance?.A?.won || 0}</div>
                    <div className="text-slate-400">Lost: {learningReport.proposal_variant_performance?.A?.lost || 0}</div>
                  </div>

                  <div className="p-4 rounded-xl border border-cyan-500/30 bg-cyan-950/20 space-y-2">
                    <div className="font-bold text-cyan-300">VARIANT B (Velocity & Guaranteed Milestone ROI)</div>
                    <div className="text-slate-300">Total Drafts: {learningReport.proposal_variant_performance?.B?.total || 0}</div>
                    <div className="text-emerald-400">Won Sprints: {learningReport.proposal_variant_performance?.B?.won || 0}</div>
                    <div className="text-slate-400">Lost: {learningReport.proposal_variant_performance?.B?.lost || 0}</div>
                  </div>
                </div>
              </div>

              {/* AI Strategic Recommendations */}
              <div className="bento-tile specular-border rounded-2xl border border-slate-800 p-6 space-y-3">
                <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                  <HelpCircle className="h-4 w-4 text-emerald-400" />
                  <span>Autonomous Strategic Recommendations</span>
                </h3>
                <div className="space-y-2">
                  {learningReport.strategic_recommendations.map((rec: string, idx: number) => (
                    <div key={idx} className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300 flex items-start space-x-2">
                      <ArrowRight className="h-4 w-4 text-amber-400 flex-shrink-0 mt-0.5" />
                      <span>{rec}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-400">Failed to load learning report.</div>
          )}
        </div>
      )}

      {/* ==================== SUB-TAB 3: MAILBOX FLEET & GATE ==================== */}
      {subTab === 'mailboxes' && (
        <div className="space-y-6">
          {/* Fail-Closed Verification Gate Tester */}
          <div className="bento-tile specular-border rounded-2xl border border-slate-800 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
              <Lock className="h-4 w-4 text-emerald-400" />
              <span>Fail-Closed Email Verification Gate</span>
            </h3>
            <p className="text-xs text-slate-400">
              Only addresses verified as 100% deliverable are allowed to receive outbound messages. Disposable domains and spam traps are hard-blocked.
            </p>

            <div className="flex gap-2">
              <input
                type="email"
                value={verifyEmail}
                onChange={(e) => setVerifyEmail(e.target.value)}
                placeholder="Enter prospect email..."
                className="flex-1 bg-slate-900 border border-slate-750 text-white rounded-xl px-3 py-2 text-xs font-mono focus:border-amber-500 focus:outline-none"
              />
              <button
                onClick={handleVerifyEmail}
                disabled={verifying}
                className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-500 text-white font-medium text-xs rounded-xl hover:opacity-90 transition-all"
              >
                {verifying ? 'Checking...' : 'Run Gate Check'}
              </button>
            </div>

            {verifyResult && (
              <div className={`p-3.5 rounded-xl border text-xs font-mono space-y-1 ${
                verifyResult.is_deliverable
                  ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-950/20 border-rose-500/30 text-rose-300'
              }`}>
                <div><strong>Status:</strong> {verifyResult.status} ({verifyResult.is_deliverable ? 'DELIVERABLE' : 'BLOCKED'})</div>
                <div><strong>Confidence:</strong> {Math.round(verifyResult.confidence * 100)}%</div>
                <div><strong>Reason:</strong> {verifyResult.reason}</div>
              </div>
            )}
          </div>

          {/* Mailbox Fleet Table */}
          <div className="bento-tile specular-border rounded-2xl border border-slate-800 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
              <Mail className="h-4 w-4 text-cyan-400" />
              <span>Active Sender Mailboxes (Anti-Clustering Pacing)</span>
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-mono">
                    <th className="py-2.5 px-3">Inbox Email</th>
                    <th className="py-2.5 px-3">Provider ESP</th>
                    <th className="py-2.5 px-3">Sent Today / Cap</th>
                    <th className="py-2.5 px-3">Reputation</th>
                    <th className="py-2.5 px-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-850">
                  {mailboxes.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-slate-400 font-mono">No mailboxes registered. Add your first inbox below.</td>
                    </tr>
                  ) : (
                    mailboxes.map((mb) => (
                      <tr key={mb.id} className="hover:bg-slate-900/40">
                        <td className="py-3 px-3 font-mono font-medium text-white">{mb.email}</td>
                        <td className="py-3 px-3 font-mono text-cyan-300">
                          {mb.provider_type}{mb.esp ? ` · ${mb.esp}` : ''}
                          {!mb.has_credentials && <div className="text-amber-300 text-[10px]">no SMTP credentials: cannot send</div>}
                        </td>
                        <td className="py-3 px-3 font-mono">
                          <span className={mb.sent_last_24h >= mb.effective_daily_cap ? 'text-rose-400 font-bold' : 'text-slate-300'}>
                            {mb.sent_last_24h} / {mb.effective_daily_cap}
                          </span>
                          {mb.effective_daily_cap < mb.daily_cap && <span className="text-slate-500"> (warm-up; cap {mb.daily_cap})</span>}
                        </td>
                        <td className="py-3 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                            mb.reputation_status === 'healthy' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                          }`}>
                            {mb.reputation_status.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <span className={`text-[10px] font-mono ${mb.is_active ? 'text-emerald-400' : 'text-slate-500'}`}>{mb.is_active ? 'ACTIVE' : 'INACTIVE'}</span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Add Mailbox Form */}
            <form onSubmit={handleRegisterMailbox} className="pt-4 border-t border-slate-800 flex flex-wrap gap-2 items-center">
              <input
                type="email"
                placeholder="new-inbox@secondary-domain.com"
                value={newMailboxEmail}
                onChange={(e) => setNewMailboxEmail(e.target.value)}
                className="bg-slate-900 border border-slate-750 text-white rounded-lg px-3 py-1.5 text-xs font-mono focus:border-amber-500 focus:outline-none flex-1 min-w-[200px]"
                required
              />
              <select
                value={newMailboxType}
                onChange={(e) => setNewMailboxType(e.target.value)}
                className="bg-slate-900 border border-slate-750 text-white rounded-lg px-2 py-1.5 text-xs font-mono"
              >
                <option value="smtp">SMTP (Google Workspace, Microsoft 365, any relay)</option>
                <option value="smartlead">Smartlead API</option>
              </select>
              <input type="text" placeholder="SMTP host, e.g. smtp.gmail.com" value={smtp.host} onChange={(e) => setSmtp({ ...smtp, host: e.target.value })}
                className="bg-slate-900 border border-slate-750 text-white rounded-lg px-3 py-1.5 text-xs font-mono flex-1 min-w-[180px]" />
              <input type="number" placeholder="Port" value={smtp.port} onChange={(e) => setSmtp({ ...smtp, port: Number(e.target.value) })}
                className="bg-slate-900 border border-slate-750 text-white rounded-lg px-2 py-1.5 text-xs font-mono w-20" />
              <input type="text" placeholder="SMTP username" autoComplete="off" value={smtp.username} onChange={(e) => setSmtp({ ...smtp, username: e.target.value })}
                className="bg-slate-900 border border-slate-750 text-white rounded-lg px-3 py-1.5 text-xs font-mono flex-1 min-w-[160px]" />
              <input type="password" placeholder="SMTP password / app password" autoComplete="new-password" value={smtp.password} onChange={(e) => setSmtp({ ...smtp, password: e.target.value })}
                className="bg-slate-900 border border-slate-750 text-white rounded-lg px-3 py-1.5 text-xs font-mono flex-1 min-w-[160px]" />
              <label className="flex items-center space-x-1.5 text-[11px] text-slate-300">
                <input type="checkbox" checked={alreadyWarmed} onChange={(e) => setAlreadyWarmed(e.target.checked)} />
                <span>Already warmed up (skip the 21-day ramp)</span>
              </label>
              <input
                type="number"
                value={newMailboxCap}
                onChange={(e) => setNewMailboxCap(Number(e.target.value))}
                placeholder="Daily Cap"
                className="bg-slate-900 border border-slate-750 text-white rounded-lg px-2 py-1.5 text-xs font-mono w-20"
                min={1}
                max={200}
              />
              <button
                type="submit"
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-slate-950 font-semibold text-xs rounded-lg transition-all"
              >
                Add Inbox
              </button>
              {mailboxError && <div role="alert" className="w-full text-xs text-rose-300">{mailboxError}</div>}
              <p className="w-full text-[11px] text-slate-500">The password is encrypted on the server and is never shown again. New mailboxes follow a 21-day ramp-up unless marked warmed.</p>
            </form>
          </div>

          {/* Organic Ramp-Up Guide per Product Plan */}
          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 text-xs space-y-2">
            <div className="font-semibold text-amber-300 flex items-center space-x-1.5">
              <AlertTriangle className="h-4 w-4" />
              <span>Organic Ramp-Up vs Synthetic Warmup Pools (Product Plan Directive)</span>
            </div>
            <p className="text-slate-300 leading-relaxed">
              Google Postmaster and Microsoft SNDS actively detect and penalize synthetic peer-to-peer warmup rings. AgencyBD enforces a genuine 21-day organic sending ramp (Day 1–3: 5 sends/day, Day 4–7: 10 sends/day, Day 8–14: 20 sends/day, Day 15–21: 30 sends/day) combined with ESP matching to protect domain health.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
