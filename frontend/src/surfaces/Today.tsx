import type { FC } from 'react';
import type { Surface } from '../types';
import type { Me } from '../lib/api';
import { AuditorDashboard } from '../components/dashboards/AuditorDashboard';
import { SdrDashboard } from '../components/dashboards/SdrDashboard';
import { GrowthLeadDashboard } from '../components/dashboards/GrowthLeadDashboard';
import { AdminDashboard } from '../components/dashboards/AdminDashboard';

export const Today: FC<{
  onOpenClient: (leadId: number) => void;
  onSettings: (section?: string) => void;
  onGo: (s: Surface) => void;
  identity?: Me | null;
}> = ({ onOpenClient, onSettings, onGo, identity }) => {
  const role = identity?.role || 'super_admin';

  if (!identity) {
    return <div className="text-slate-400 text-sm">Loading workspace identity…</div>;
  }

  if (role === 'auditor') {
    return <AuditorDashboard identity={identity} onGo={onGo} onOpenClient={onOpenClient} />;
  }

  if (role === 'sdr_rep') {
    return <SdrDashboard identity={identity} onGo={onGo} onOpenClient={onOpenClient} />;
  }

  if (role === 'growth_lead') {
    return (
      <GrowthLeadDashboard
        identity={identity}
        onGo={onGo}
        onOpenClient={onOpenClient}
        onSettings={onSettings}
      />
    );
  }

  return <AdminDashboard identity={identity} onGo={onGo} onSettings={onSettings} />;
};
