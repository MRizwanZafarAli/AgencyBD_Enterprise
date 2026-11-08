import type { FC } from 'react';
import type { Surface } from '../types';
import type { Me } from '../lib/api';
import { AuditorDashboard } from '../components/dashboards/AuditorDashboard';
import { SdrDashboard } from '../components/dashboards/SdrDashboard';
import { GrowthLeadDashboard } from '../components/dashboards/GrowthLeadDashboard';
import { AdminDashboard } from '../components/dashboards/AdminDashboard';
import { ErrorBoundary } from '../components/shared/ErrorBoundary';

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

  if (role === 'auditor') {
    return (
      <ErrorBoundary fallbackTitle="Auditor Dashboard Error">
        <AuditorDashboard identity={identity} onGo={onGo} onOpenClient={onOpenClient} />
      </ErrorBoundary>
    );
  }

  if (role === 'sdr_rep') {
    return (
      <ErrorBoundary fallbackTitle="SDR Dashboard Error">
        <SdrDashboard identity={identity} onGo={onGo} onOpenClient={onOpenClient} onSearch={onSearch} />
      </ErrorBoundary>
    );
  }

  if (role === 'growth_lead') {
    return (
      <ErrorBoundary fallbackTitle="Growth Lead Dashboard Error">
        <GrowthLeadDashboard
          identity={identity}
          onGo={onGo}
          onOpenClient={onOpenClient}
          onSettings={onSettings}
        />
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary fallbackTitle="Admin Dashboard Error">
      <AdminDashboard identity={identity} onGo={onGo} onSettings={onSettings} />
    </ErrorBoundary>
  );
};
