import { useState } from 'react';
import type { FC } from 'react';
import { Radio, RefreshCw, Search, Users, Wrench, Shield, CheckCircle2, AlertCircle } from 'lucide-react';
import { FollowupsPanel } from '../components/clients/FollowupsPanel';
import { Button, Card, EmptyState, PageHeader, Skeletons } from '../components/ui';
import { ErrorBanner } from '../components/shared/ErrorBanner';
import { DigestPanel } from '../components/shared/DigestPanel';
import { TodayOverview } from '../components/today/TodayOverview';
import type { Surface } from '../types';
import { DiscoveryPanel } from '../components/today/DiscoveryPanel';
import { InboxItem } from '../components/today/InboxItem';
import type { InboxEntry } from '../components/today/InboxItem';
import { useApi } from '../lib/hooks';
import type { Me } from '../lib/api';
import { apiFetch } from '../lib/api';

interface Inbox { count: number; items: InboxEntry[] }

export const Today: FC<{
  onOpenClient: (leadId: number) => void;
  onSettings: (section?: string) => void;
  onGo: (s: Surface) => void;
  identity?: Me | null;
}> = ({ onOpenClient, onSettings, onGo, identity }) => {
  const inbox = useApi<Inbox>('/api/inbox');
  const items = inbox.data?.items ?? [];
  const role = identity?.role || 'super_admin';

  // State for auditor live suppression check
  const [checkEmail, setCheckEmail] = useState('');
  const [checkingSuppression, setCheckingSuppression] = useState(false);
  const [suppressionResult, setSuppressionResult] = useState<{ email: string; is_suppressed: boolean } | null>(null);
  const [suppressionError, setSuppressionError] = useState('');

  const handleCheckSuppression = async (e: React.FormEvent) => {
    e.preventDefault();
    const em = checkEmail.trim();
    if (!em || !em.includes('@')) {
      setSuppressionError('Enter a valid email address to verify.');
      return;
    }
    setCheckingSuppression(true);
    setSuppressionError('');
    try {
      const res = await apiFetch(`/api/compliance/suppression/check?email=${encodeURIComponent(em)}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || 'Lookup failed');
      setSuppressionResult(body);
    } catch (err) {
      setSuppressionError(err instanceof Error ? err.message : 'Lookup failed');
    } finally {
      setCheckingSuppression(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Today"
        subtitle={
          role === 'auditor'
            ? 'Compliance, regulatory disclosures, and verification log trail.'
            : role === 'sdr_rep'
            ? 'Prospecting, opportunity intake, proposals, and communication follow-ups.'
            : role === 'growth_lead'
            ? 'Pipeline acceleration, sequence performance, incoming replies, and draft approvals.'
            : 'What needs you, in order. Everything else runs on its own and stops when it would otherwise have to guess.'
        }
        actions={
          <Button small onClick={inbox.reload}>
            <RefreshCw className={`h-3.5 w-3.5 ${inbox.loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      <TodayOverview
        identity={identity}
        onGo={(surface, opts) => {
          if (opts?.leadId) onOpenClient(opts.leadId);
          else if (surface === 'settings') onSettings(opts?.section);
          else if (surface !== 'today') onGo(surface);
        }}
      />

      {/* Role-Specific Quick Actions (Kept Very Simple & Focused) */}
      <div className="flex flex-wrap gap-2" aria-label="Role quick actions">
        {role === 'sdr_rep' && (
          <>
            <Button small variant="primary" onClick={() => onGo('find')}>
              <Search className="h-3.5 w-3.5" />Find opportunities
            </Button>
            <Button small onClick={() => onGo('channels')}>
              <Radio className="h-3.5 w-3.5" />Channel inbox
            </Button>
            <Button small onClick={() => onGo('clients')}>
              <Users className="h-3.5 w-3.5" />Prospects & Leads
            </Button>
            <Button small onClick={() => onGo('tools')}>
              <Wrench className="h-3.5 w-3.5" />Copy & Battlecards
            </Button>
          </>
        )}

        {role === 'growth_lead' && (
          <>
            <Button small variant="primary" onClick={() => onGo('clients')}>
              <Users className="h-3.5 w-3.5" />Pipeline deals
            </Button>
            <Button small onClick={() => onGo('find')}>
              <Search className="h-3.5 w-3.5" />Launch radar scan
            </Button>
            <Button small onClick={() => onGo('channels')}>
              <Radio className="h-3.5 w-3.5" />Outreach channels
            </Button>
            <Button small onClick={() => onGo('tools')}>
              <Wrench className="h-3.5 w-3.5" />Sequences & Copy
            </Button>
          </>
        )}

        {role === 'auditor' && (
          <>
            <Button small variant="primary" onClick={() => onGo('clients')}>
              <Shield className="h-3.5 w-3.5" />Review site audits
            </Button>
            <Button small onClick={() => onGo('tools')}>
              <Wrench className="h-3.5 w-3.5" />Suppression vault
            </Button>
            <Button small onClick={() => onGo('tools')}>
              <Radio className="h-3.5 w-3.5" />DNS deliverability
            </Button>
          </>
        )}

        {role === 'super_admin' && (
          <>
            <Button small variant="primary" onClick={() => onSettings('setup')}>
              <Wrench className="h-3.5 w-3.5" />Workspace setup
            </Button>
            <Button small onClick={() => onGo('clients')}>
              <Users className="h-3.5 w-3.5" />Pipeline & deals
            </Button>
            <Button small onClick={() => onGo('find')}>
              <Search className="h-3.5 w-3.5" />Find prospects
            </Button>
            <Button small onClick={() => onGo('channels')}>
              <Radio className="h-3.5 w-3.5" />Channels
            </Button>
            <Button small onClick={() => onGo('tools')}>
              <Wrench className="h-3.5 w-3.5" />Tools & API
            </Button>
          </>
        )}
      </div>

      {/* Role-Tailored Body Surfaces */}
      {role === 'auditor' ? (
        <>
          {/* Dedicated Auditor Live Compliance Tool */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Shield className="h-4 w-4 text-emerald-400" /> Live Suppression & CAN-SPAM Verification
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Check if an email or recipient is suppressed across the organization.
                </p>
              </div>
            </div>

            <form onSubmit={handleCheckSuppression} className="flex flex-wrap gap-2">
              <input
                type="email"
                placeholder="name@company.com"
                value={checkEmail}
                onChange={(e) => {
                  setCheckEmail(e.target.value);
                  setSuppressionResult(null);
                  setSuppressionError('');
                }}
                className="flex-1 min-w-64 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <Button small disabled={checkingSuppression}>
                {checkingSuppression ? 'Checking…' : 'Check Vault'}
              </Button>
            </form>

            <ErrorBanner message={suppressionError} />

            {suppressionResult && (
              <div
                className={`mt-3 p-3 rounded-xl border text-xs flex items-center gap-2 ${
                  suppressionResult.is_suppressed
                    ? 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                    : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                }`}
              >
                {suppressionResult.is_suppressed ? (
                  <>
                    <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
                    <span>
                      <strong>{suppressionResult.email}</strong> is <strong>SUPPRESSED</strong>. No outreach may be
                      dispatched to this address.
                    </span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                    <span>
                      <strong>{suppressionResult.email}</strong> is <strong>CLEAR</strong>. Recipient is eligible for
                      compliance-approved outreach.
                    </span>
                  </>
                )}
              </div>
            )}
          </Card>

          <Card>
            <h2 className="text-sm font-semibold text-white mb-1">Audit Findings & Notes Queue</h2>
            <ErrorBanner message={inbox.error} />
            {inbox.loading && !inbox.data ? (
              <Skeletons rows={3} />
            ) : items.length === 0 && !inbox.error ? (
              <EmptyState
                title="All audits clear"
                hint="No pending compliance flags or review items requiring manual auditor inspection."
              />
            ) : (
              <ul className="divide-y divide-slate-800">
                {items.map((i) => (
                  <InboxItem
                    key={`${i.type}-${i.id}`}
                    item={i}
                    onChanged={inbox.reload}
                    onOpenClient={onOpenClient}
                    onSettings={onSettings}
                  />
                ))}
              </ul>
            )}
          </Card>
        </>
      ) : (
        <>
          <FollowupsPanel onOpenClient={onOpenClient} />

          {role !== 'auditor' && <DiscoveryPanel onDone={inbox.reload} onOpenClient={onOpenClient} />}

          <Card>
            <h2 className="text-sm font-semibold text-white mb-1">
              {role === 'growth_lead' ? 'Actionable approvals & inbox' : 'Your inbox'}
            </h2>
            <ErrorBanner message={inbox.error} />
            {inbox.loading && !inbox.data ? (
              <Skeletons rows={3} />
            ) : items.length === 0 && !inbox.error ? (
              <EmptyState
                title="You're all caught up"
                hint={
                  role === 'growth_lead'
                    ? 'No drafts currently awaiting approval. Campaign sequences are running smoothly.'
                    : 'Run a search above to find prospects. Drafts and tasks will appear here.'
                }
              />
            ) : (
              <ul className="divide-y divide-slate-800">
                {items.map((i) => (
                  <InboxItem
                    key={`${i.type}-${i.id}`}
                    item={i}
                    onChanged={inbox.reload}
                    onOpenClient={onOpenClient}
                    onSettings={onSettings}
                  />
                ))}
              </ul>
            )}
          </Card>
        </>
      )}

      {role === 'super_admin' && <DigestPanel />}
    </div>
  );
};
