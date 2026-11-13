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
  onSendEmail?: (params: { recipient: string; recipientName?: string; companyName?: string; subject?: string; body?: string; leadId?: number }) => void;
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

  // Each role's dashboard is completely differentiated and purpose-built for its workflow
  return (
    <div className="space-y-6">
      {dashboard}
    </div>
  );
};
