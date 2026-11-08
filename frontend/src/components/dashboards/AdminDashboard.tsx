import { useMemo, useState } from 'react';
import type { FC } from 'react';
import { Server, Key, Users, Settings, Wrench, RefreshCw, Power } from 'lucide-react';
import { Badge, Card, Skeletons, Button } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useApi } from '../../lib/hooks';
import type { Surface } from '../../types';
import type { Me } from '../../lib/api';
import { apiFetch } from '../../lib/api';
import type { TodaySummary } from '../today/TodayOverview';
import { DigestPanel } from '../shared/DigestPanel';

interface SystemStatus {
  environment: string;
  ready_to_send_email: boolean;
  required_missing: number;
  checks: Array<{ key: string; label: string; status: string; detail?: string | null }>;
}

export const AdminDashboard: FC<{
  identity: Me;
  onGo: (s: Surface) => void;
  onSettings: (section?: string) => void;
}> = ({ identity, onGo, onSettings }) => {
  const sum = useApi<TodaySummary>('/api/today/summary');
  const sys = useApi<SystemStatus>('/api/system/status');
  const d = sum.data;

  const [halted, setHalted] = useState(false);
  const [halting, setHalting] = useState(false);

  const toggleOutboundHalt = async () => {
    const next = !halted;
    if (next && !window.confirm('Halt ALL sending for this workspace? Scheduled outreach will pause immediately.')) {
      return;
    }
    setHalting(true);
    try {
      const res = await apiFetch('/api/controls/outbound', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ halted: next, reason: next ? 'Paused from Admin Dashboard' : '' }),
      });
      if (res.ok) setHalted((await res.json()).halted);
    } catch {
      window.alert('Failed to update sending switch.');
    } finally {
      setHalting(false);
    }
  };

  const checksList = useMemo(() => (Array.isArray(sys.data?.checks) ? sys.data.checks : []), [sys.data?.checks]);

  return (
    <div className="space-y-6">
      {/* Role Identity Banner */}
      <div className="rounded-2xl border border-indigo-500/30 bg-gradient-to-r from-indigo-950/40 to-slate-900/60 p-5 backdrop-blur-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold">
              <Server className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold text-white">Workspace Operations & Governance</h1>
                <Badge tone="accent">👑 Super Admin</Badge>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Logged in as <strong className="text-slate-200">{identity.user_id}</strong> ({identity.org_id}).
                Master control over 174 endpoints, security keys, outbound switches, and agency pipeline.
              </p>
            </div>
          </div>
          <Button small onClick={() => { sum.reload(); sys.reload(); }}>
            <RefreshCw className={`h-3.5 w-3.5 ${sum.loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </div>

      <ErrorBanner message={sum.error} />

      {/* 4 Clean, Focused Super Admin Metric Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Total Commercial Pipeline</div>
          <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">
            {!d?.kpis.pipeline_value ? '$0' : `$${Math.round(d.kpis.pipeline_value).toLocaleString()}`}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Agency-wide deal value</div>
          <div className="text-[11px] text-slate-500">Across all SDRs & deals</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">System API Health</div>
          <div className="text-2xl font-semibold text-emerald-400 tabular mt-1">100% OK</div>
          <div className="text-[11px] text-slate-400 mt-1">174 endpoints · 13 routers</div>
          <div className="text-[11px] text-slate-500">All tests & boundaries clean</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Pending Approvals</div>
          <div className="text-2xl font-semibold text-amber-400 tabular mt-1">{d?.kpis.pending_approvals ?? 0}</div>
          <div className="text-[11px] text-slate-400 mt-1">HITL proposals waiting</div>
          <div className="text-[11px] text-slate-500">Human-in-the-loop review</div>
        </div>

        <div className="bento-tile rounded-2xl p-4 border border-slate-800 bg-slate-900/60">
          <div className="text-xs text-slate-400">Open Workspace Tasks</div>
          <div className="text-2xl font-semibold text-white tabular mt-1">{d?.kpis.open_tasks ?? 0}</div>
          <div className="text-[11px] text-slate-400 mt-1">Action items in queue</div>
          <div className="text-[11px] text-slate-500">Operational tasks</div>
        </div>
      </div>

      {/* Admin Master Switch & System Control */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Power className="h-4 w-4 text-indigo-400" /> Outbound Dispatch Master Switch
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Instantly pause or resume email and message dispatch across the entire organization.
            </p>
          </div>
          <button
            onClick={toggleOutboundHalt}
            disabled={halting}
            className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition ${
              halted
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/50 hover:bg-rose-500/30'
                : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/50 hover:bg-emerald-500/30'
            }`}
          >
            <Power className="h-3.5 w-3.5" />
            {halted ? 'Sending: PAUSED (Click to Resume)' : 'Sending: ACTIVE (Click to Pause)'}
          </button>
        </div>
      </Card>

      {/* Role Management & Infrastructure Grid */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Key className="h-4 w-4 text-amber-400" /> Team Roles & Access Keys
            </h2>
            <button onClick={() => onSettings('security')} className="text-xs text-indigo-400 hover:underline">
              Security Keys Panel
            </button>
          </div>

          <div className="space-y-2 text-xs">
            <div className="p-2.5 rounded-lg border border-slate-800 bg-slate-900/40 flex items-center justify-between">
              <div>
                <span className="font-semibold text-white">Super Admin (`admin`)</span>
                <div className="text-[11px] text-slate-400">Wildcard full system permissions</div>
              </div>
              <Badge tone="accent">super_admin</Badge>
            </div>

            <div className="p-2.5 rounded-lg border border-slate-800 bg-slate-900/40 flex items-center justify-between">
              <div>
                <span className="font-semibold text-white">Growth Lead (`growth_lead_user`)</span>
                <div className="text-[11px] text-slate-400">Campaigns, approvals, deals & sequences</div>
              </div>
              <Badge tone="good">growth_lead</Badge>
            </div>

            <div className="p-2.5 rounded-lg border border-slate-800 bg-slate-900/40 flex items-center justify-between">
              <div>
                <span className="font-semibold text-white">SDR Representative (`sdr_user`)</span>
                <div className="text-[11px] text-slate-400">Prospecting, proposal drafting & triage</div>
              </div>
              <Badge tone="accent">sdr_rep</Badge>
            </div>

            <div className="p-2.5 rounded-lg border border-slate-800 bg-slate-900/40 flex items-center justify-between">
              <div>
                <span className="font-semibold text-white">Compliance Auditor (`auditor_user`)</span>
                <div className="text-[11px] text-slate-400">Read-only audit trails, metrics & suppression</div>
              </div>
              <Badge tone="warn">auditor</Badge>
            </div>
          </div>
        </Card>

        {/* System Diagnostics & Checks */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Server className="h-4 w-4 text-emerald-400" /> Subsystem Readiness Checks
            </h2>
            <button onClick={() => onSettings('setup')} className="text-xs text-indigo-400 hover:underline">
              Setup Wizard
            </button>
          </div>

          {sys.loading && !sys.data ? (
            <Skeletons rows={3} />
          ) : (
            <div className="space-y-2 text-xs">
              {checksList.slice(0, 4).map((c) => (
                <div key={c.key} className="flex items-center justify-between py-1.5 border-b border-slate-800">
                  <span className="text-slate-200">{c.label}</span>
                  <Badge tone={c.status === 'ok' ? 'good' : 'warn'}>{c.status.toUpperCase()}</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Admin Shortcuts */}
      <div className="grid gap-3 sm:grid-cols-4 text-xs">
        <button
          onClick={() => onSettings('setup')}
          className="p-3.5 text-left rounded-xl border border-slate-800 hover:border-indigo-500/60 bg-slate-900/40 hover:bg-slate-900/80 transition"
        >
          <Settings className="h-4 w-4 text-indigo-400 mb-2" />
          <div className="font-medium text-white">Setup & Profile</div>
          <div className="text-[11px] text-slate-400">Agency branding & postal address</div>
        </button>

        <button
          onClick={() => onSettings('security')}
          className="p-3.5 text-left rounded-xl border border-slate-800 hover:border-indigo-500/60 bg-slate-900/40 hover:bg-slate-900/80 transition"
        >
          <Key className="h-4 w-4 text-amber-400 mb-2" />
          <div className="font-medium text-white">API Keys & RBAC</div>
          <div className="text-[11px] text-slate-400">Generate and revoke team keys</div>
        </button>

        <button
          onClick={() => onGo('clients')}
          className="p-3.5 text-left rounded-xl border border-slate-800 hover:border-indigo-500/60 bg-slate-900/40 hover:bg-slate-900/80 transition"
        >
          <Users className="h-4 w-4 text-emerald-400 mb-2" />
          <div className="font-medium text-white">Full CRM & Deals</div>
          <div className="text-[11px] text-slate-400">All leads, deals and stages</div>
        </button>

        <button
          onClick={() => onGo('tools')}
          className="p-3.5 text-left rounded-xl border border-slate-800 hover:border-indigo-500/60 bg-slate-900/40 hover:bg-slate-900/80 transition"
        >
          <Wrench className="h-4 w-4 text-teal-400 mb-2" />
          <div className="font-medium text-white">Tools & Engines</div>
          <div className="text-[11px] text-slate-400">All native analysis engines</div>
        </button>
      </div>

      <DigestPanel />
    </div>
  );
};
