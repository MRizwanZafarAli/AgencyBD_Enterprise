import { useState } from 'react';
import type { FC } from 'react';
import { PageHeader } from '../components/ui';
import { SetupWizard } from '../components/settings/SetupWizard';
import { Tour } from '../components/settings/Tour';
import { IntegrationsPanel } from '../components/settings/IntegrationsPanel';
import { PortfolioManager } from '../components/modules/PortfolioManager';
import { GovernanceAndLearning } from '../components/modules/GovernanceAndLearning';
import { DnsStudio } from '../components/modules/DnsStudio';
import { CanSpamVault } from '../components/modules/CanSpamVault';
import { FleetRouter } from '../components/modules/FleetRouter';
import { EnterpriseRbac } from '../components/modules/EnterpriseRbac';
import { ApiExplorer } from '../components/modules/ApiExplorer';

const SECTIONS = [
  { id: 'setup', label: 'Setup' }, { id: 'keys', label: 'Integrations and keys' }, { id: 'services', label: 'Services and proof' }, { id: 'sending', label: 'Sending and policy' },
  { id: 'dns', label: 'Domain DNS' }, { id: 'unsub', label: 'Unsubscribe list' }, { id: 'team', label: 'Team and keys' }, { id: 'api', label: 'Developer' }, { id: 'tour', label: 'How it works' },
];

export const Settings: FC<{ orgId: string; section: string; setSection: (s: string) => void }> = ({ orgId, section, setSection }) => {
  const [routing, setRouting] = useState(false);
  return (
    <div>
      <PageHeader title="Settings" subtitle="Set up once. Most days you will not need this page." />
      <div className="grid gap-6 lg:grid-cols-[200px_1fr]">
        <nav aria-label="Settings sections" className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible">
          {SECTIONS.map((s) => (
            <button key={s.id} onClick={() => setSection(s.id)} aria-current={section === s.id ? 'page' : undefined}
              className={`text-left whitespace-nowrap px-3 py-2 rounded-lg text-sm ${section === s.id ? 'bg-indigo-500/10 text-white font-medium' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'}`}>{s.label}</button>))}
        </nav>
        <div className="min-w-0">
          {section === 'setup' && <SetupWizard onGo={setSection} />}
          {section === 'keys' && <IntegrationsPanel />}
          {section === 'services' && <PortfolioManager />}
          {section === 'sending' && (<div className="space-y-6"><GovernanceAndLearning />
            <button onClick={() => setRouting((v) => !v)} className="text-xs text-indigo-300 hover:text-indigo-200 underline">{routing ? 'Hide' : 'Show'} sender-routing tools</button>{routing && <FleetRouter />}</div>)}
          {section === 'dns' && <DnsStudio />}
          {section === 'unsub' && <CanSpamVault />}
          {section === 'team' && <EnterpriseRbac selectedTenant={orgId} />}
          {section === 'api' && <ApiExplorer />}
          {section === 'tour' && <Tour />}
        </div>
      </div>
    </div>
  );
};
