import type { FC } from 'react';
import type { Surface } from '../../types';
import type { Me } from '../../lib/api';
import { TodayCommandCenter } from '../today/TodayCommandCenter';

export const AdminDashboard: FC<{
  identity: Me;
  onGo: (s: Surface) => void;
  onSettings: (section?: string) => void;
  onOpenClient?: (leadId: number) => void;
  onSendEmail?: (params: { recipient: string; recipientName?: string; companyName?: string; subject?: string; body?: string; leadId?: number }) => void;
}> = ({ onGo, onSettings, onOpenClient, onSendEmail }) => {
  return (
    <TodayCommandCenter
      roleLabel="Super Admin"
      onGo={onGo}
      onSettings={onSettings}
      onOpenClient={(id) => (onOpenClient ? onOpenClient(id) : onGo('clients'))}
      onSendEmail={onSendEmail}
    />
  );
};
