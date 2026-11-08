import { useState } from 'react';
import type { FC } from 'react';
import { Shield, CheckCircle2, AlertCircle, FileCheck, ExternalLink, RefreshCw } from 'lucide-react';
import { Badge, Card, Skeletons, Button } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useApi } from '../../lib/hooks';
import type { Surface } from '../../types';
import type { Me } from '../../lib/api';
import { apiFetch } from '../../lib/api';
import type { TodaySummary } from '../today/TodayOverview';

interface Lead {
  id: number;
  company_name: string;
  domain: string;
  created_at?: string;
  stage?: string;
  audit?: { score?: number; mobile_friendly?: boolean; slow?: boolean };
}

export const AuditorDashboard: FC<{
  identity: Me;
  onGo: (s: Surface) => void;
  onOpenClient: (leadId: number) => void;
}> = ({ identity, onGo, onOpenClient }) => {
  const sum = useApi<TodaySummary>('/api/today/summary');
  const leads = useApi<Lead[]>('/api/leads');
  const d = sum.data;

  // Live Suppression Checker State
  const [checkEmail, setCheckEmail] = useState('');
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<{ email: string; is_suppressed: boolean } | null>(null);
  const [error, setError] = useState('');

  const handleCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    const em = checkEmail.trim();
    if (!em || !em.includes('@')) {
      setError('Please enter a valid email address.');
      return;
    }
    setChecking(true);
    setError('');
    try {
      const res = await apiFetch(`/api/compliance/suppression/check?email=${encodeURIComponent(em)}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || 'Lookup failed');
      setResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lookup failed');
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Role Identity Banner */}
      <div className="rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-5 backdrop-blur-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold text-white">Compliance & Quality Control</h1>
                <Badge tone="good">Auditor · Read-Only</Badge>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Logged in as <strong className="text-slate-200">{identity.user_id}</strong> ({identity.org_id}).
                Enforces CAN-SPAM/GDPR suppression, reviews technical site audits, and validates outreach safety.
              </p>
            </div>
          </div>
          <Button small onClick={() => { sum.reload(); leads.reload(); }}>
            <RefreshCw className={`h-3.5 w-3.5 ${sum.loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </div>

      <ErrorBanner message={sum.error} />

      {/* 4 Clean, Focused Auditor Metric Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Websites Audited</div>
          <div className="text-2xl font-semibold text-white tabular mt-1">{d?.kpis.audits.now ?? '–'}</div>
          <div className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" /> Technical evaluations
          </div>
          <div className="text-[11px] text-slate-500">PageSpeed, SEO & mobile health</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Suppression Vault</div>
          <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">ACTIVE</div>
          <div className="text-[11px] text-slate-400 mt-1">CAN-SPAM & GDPR rules</div>
          <div className="text-[11px] text-slate-500">All outbound checked prior to send</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Audit Trail Events</div>
          <div className="text-2xl font-semibold text-indigo-300 tabular mt-1">{d?.activity.length ?? 0}</div>
          <div className="text-[11px] text-slate-400 mt-1">System & user actions</div>
          <div className="text-[11px] text-slate-500">Immutable governance trail</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Companies In Scope</div>
          <div className="text-2xl font-semibold text-white tabular mt-1">{leads.data?.length ?? 0}</div>
          <div className="text-[11px] text-slate-400 mt-1">Evaluated for disclosures</div>
          <div className="text-[11px] text-slate-500">Read-only verification</div>
        </div>
      </div>

      {/* Primary Tool 1: Live CAN-SPAM & Suppression Search */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Shield className="h-4 w-4 text-emerald-400" /> Live Suppression Vault Lookup
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Enter any recipient email to instantly check suppression status against legal opt-out and blacklist databases.
            </p>
          </div>
        </div>

        <form onSubmit={handleCheck} className="flex flex-wrap gap-2.5">
          <input
            type="email"
            placeholder="e.g. prospect@example.com"
            value={checkEmail}
            onChange={(e) => {
              setCheckEmail(e.target.value);
              setResult(null);
              setError('');
            }}
            className="flex-1 min-w-64 bg-slate-900 border border-slate-700 rounded-lg px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition"
          />
          <Button variant="primary" disabled={checking}>
            {checking ? 'Checking Vault…' : 'Check Status'}
          </Button>
        </form>

        <ErrorBanner message={error} />

        {result && (
          <div
            className={`mt-3.5 p-3.5 rounded-xl border text-xs flex items-center gap-2.5 animate-fade-up ${
              result.is_suppressed
                ? 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
            }`}
          >
            {result.is_suppressed ? (
              <>
                <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
                <span>
                  <strong>{result.email}</strong> is <strong>SUPPRESSED / OPTED-OUT</strong>. Outbound dispatch is
                  strictly blocked to this address.
                </span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                <span>
                  <strong>{result.email}</strong> is <strong>CLEAR & VERIFIED</strong>. Address is eligible for
                  compliance-approved communication.
                </span>
              </>
            )}
          </div>
        )}
      </Card>

      {/* Primary Tool 2: Audited Sites & Deliverability Scores */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <FileCheck className="h-4 w-4 text-indigo-400" /> Audited Company Sites
            </h2>
            <button onClick={() => onGo('clients')} className="text-xs text-indigo-400 hover:underline">
              Inspect in Clients
            </button>
          </div>

          {leads.loading && !leads.data ? (
            <Skeletons rows={3} />
          ) : (leads.data ?? []).length === 0 ? (
            <p className="text-xs text-slate-400">No audited companies in scope yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-500 border-b border-slate-800">
                    <th className="py-2">Company</th>
                    <th className="py-2">Domain</th>
                    <th className="py-2 text-right">Audit Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {(leads.data ?? []).slice(0, 5).map((l) => (
                    <tr key={l.id} className="hover:bg-slate-900/40">
                      <td className="py-2 font-medium text-slate-200">{l.company_name}</td>
                      <td className="py-2 text-slate-400">{l.domain || '–'}</td>
                      <td className="py-2 text-right">
                        <button
                          onClick={() => onOpenClient(l.id)}
                          className="inline-flex items-center gap-1 text-[11px] text-emerald-400 hover:underline"
                        >
                          View Audit <ExternalLink className="h-3 w-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Audit Activity Trail */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Immutable Audit Trail</h2>
            <Badge tone="neutral">Last 6 Events</Badge>
          </div>
          {sum.loading && !d ? (
            <Skeletons rows={3} />
          ) : (d?.activity ?? []).length === 0 ? (
            <p className="text-xs text-slate-400">Audit trail log is clear.</p>
          ) : (
            <ul className="space-y-2.5">
              {(d?.activity ?? []).slice(0, 6).map((a, i) => (
                <li key={`${a.at}-${i}`} className="flex gap-2 text-xs">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" aria-hidden="true" />
                  <span className="flex-1 min-w-0 text-slate-300 truncate">
                    {a.what} {a.company ? `· ${a.company}` : ''}
                  </span>
                  <time className="text-slate-500 shrink-0 tabular" dateTime={a.at}>
                    {new Date(a.at.replace(' ', 'T') + (a.at.includes('Z') || a.at.includes('+') ? '' : 'Z')).toLocaleString(
                      undefined,
                      { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }
                    )}
                  </time>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
};
