import type { FC } from 'react';
import type { Surface } from '../types';
import type { Me } from '../lib/api';
import { AuditorDashboard } from '../components/dashboards/AuditorDashboard';
import { SdrDashboard } from '../components/dashboards/SdrDashboard';
import { GrowthLeadDashboard } from '../components/dashboards/GrowthLeadDashboard';
import { AdminDashboard } from '../components/dashboards/AdminDashboard';
import { ErrorBoundary } from '../components/shared/ErrorBoundary';
import { TodayOverview } from '../components/today/TodayOverview';
import { Scorecard } from '../components/today/Scorecard';
import { FollowupsPanel } from '../components/clients/FollowupsPanel';

export const Today: FC<{
  onOpenClient: (leadId: number) => void;
  onSettings: (section?: string) => void;
  onGo: (s: Surface) => void;
  onSearch?: (q: string) => void;
  identity?: Me | null;
}> = ({ onOpenClient, onSettings, onGo, onSearch, identity }) => {
  const role = identity?.role || 'super_admin';

  if (!identity) {
    return <div className="text-slate-400 text-sm">Loading workspace identity…</div>;
  }

  let dashboard;
  if (role === 'auditor') {
    dashboard = (
      <ErrorBoundary fallbackTitle="Auditor Dashboard Error">
        <AuditorDashboard identity={identity} onGo={onGo} onOpenClient={onOpenClient} />
      </ErrorBoundary>
    );
  } else if (role === 'sdr_rep') {
    dashboard = (
      <ErrorBoundary fallbackTitle="SDR Dashboard Error">
        <SdrDashboard identity={identity} onGo={onGo} onOpenClient={onOpenClient} onSearch={onSearch} />
      </ErrorBoundary>
    );
  } else if (role === 'growth_lead') {
    dashboard = (
      <ErrorBoundary fallbackTitle="Growth Lead Dashboard Error">
        <GrowthLeadDashboard identity={identity} onGo={onGo} onOpenClient={onOpenClient} onSettings={onSettings} />
      </ErrorBoundary>
    );
  } else {
    dashboard = (
      <ErrorBoundary fallbackTitle="Admin Dashboard Error">
        <AdminDashboard identity={identity} onGo={onGo} onSettings={onSettings} />
      </ErrorBoundary>
    );
  }

  // Every tier sees the same ranked "what matters" strip first (client messages waiting, clients to chase, approvals), then its own
  // dashboard, then the weekly scorecard and the follow-ups that are due.
  return (
    <div className="space-y-6">
      <ErrorBoundary fallbackTitle="Focus list error">
        <TodayOverview focusOnly onGo={(surface, opts) => { if (opts?.leadId) onOpenClient(opts.leadId); else if (opts?.section) onSettings(opts.section); else onGo(surface); }} />
      </ErrorBoundary>
      {dashboard}
      <ErrorBoundary fallbackTitle="Scorecard error">
        <Scorecard />
      </ErrorBoundary>
      <FollowupsPanel onOpenClient={onOpenClient} />
    </div>
  );
};
