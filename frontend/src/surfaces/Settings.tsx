import { useState } from 'react';
import type { FC } from 'react';
import { Badge, Button, PageHeader, SearchInput } from '../components/ui';
import { SetupWizard } from '../components/settings/SetupWizard';
import type { Status } from '../components/settings/SetupWizard';
import { AgencyProfile } from '../components/settings/AgencyProfile';
import { SecurityPanel } from '../components/settings/SecurityPanel';
import { DataPanel } from '../components/settings/DataPanel';
import { Preferences } from '../components/settings/Preferences';
import { SETTINGS_SECTIONS } from '../components/settings/sections';
import { Tour } from '../components/settings/Tour';
import { IntegrationsPanel } from '../components/settings/IntegrationsPanel';
import { WebhooksPanel } from '../components/settings/WebhooksPanel';
import { PortfolioManager } from '../components/modules/PortfolioManager';
import { GovernanceAndLearning } from '../components/modules/GovernanceAndLearning';
import { DnsStudio } from '../components/modules/DnsStudio';
import { CanSpamVault } from '../components/modules/CanSpamVault';
import { FleetRouter } from '../components/modules/FleetRouter';
import { EnterpriseRbac } from '../components/modules/EnterpriseRbac';
import { ApiExplorer } from '../components/modules/ApiExplorer';
import { useApi } from '../lib/hooks';
import type { Me } from '../lib/api';

export const Settings: FC<{ me: Me; section: string; setSection: (s: string) => void; onSignOut: () => void }> = ({ me, section, setSection, onSignOut }) => {
  const [routing, setRouting] = useState(false);
  const [find, setFind] = useState('');
  const status = useApi<Status>('/api/system/status');
  const current = SETTINGS_SECTIONS.find((s) => s.id === section) ?? SETTINGS_SECTIONS[0];

  const tokens = find.toLowerCase().split(/\s+/).filter(Boolean);
  const matches = tokens.length ? SETTINGS_SECTIONS.filter((s) => tokens.every((t) => `${s.label} ${s.hint} ${s.keywords}`.toLowerCase().includes(t))) : SETTINGS_SECTIONS;
  const groups = Array.from(new Set(matches.map((s) => s.group)));
  const pick = (id: string) => { setSection(id); setFind(''); };
  const s = status.data;
  const done = s ? s.checks.filter((c) => c.status === 'ok').length : 0;

  return (
    <div>
      <PageHeader title="Settings" subtitle="Set up once. Most days you will not need this page."
        actions={s && <Button small onClick={() => pick('setup')} aria-label="Open setup checklist"><Badge tone={s.required_missing ? 'warn' : 'good'}>{s.required_missing ? `${s.required_missing} required left` : 'Setup complete'}</Badge><span className="text-slate-400 tabular">{done}/{s.checks.length}</span></Button>} />
      <div className="grid gap-6 lg:grid-cols-[236px_1fr]">
        <div className="min-w-0 lg:sticky lg:top-24 lg:self-start space-y-3">
          <div onKeyDown={(e) => { if (e.key === 'Enter' && matches[0]) { e.preventDefault(); pick(matches[0].id); } }}>
            <SearchInput label="Find a setting" placeholder="Find a setting (try: dns, price, export)" value={find} onChange={setFind} />
          </div>
          <nav aria-label="Settings sections" className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible pb-1 lg:pb-0">
            {matches.length === 0 && <p className="text-xs text-slate-400 px-3 py-2">No setting matches &quot;{find}&quot;.</p>}
            {groups.map((g) => (
              <div key={g} className="flex lg:flex-col gap-1 lg:mb-2">
                <div className="hidden lg:block px-3 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{g}</div>
                {matches.filter((x) => x.group === g).map((x) => (
                  <button key={x.id} onClick={() => pick(x.id)} aria-current={section === x.id ? 'page' : undefined} title={x.hint}
                    className={`text-left whitespace-nowrap flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm transition-colors ${section === x.id ? 'bg-indigo-500/10 text-white font-medium' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'}`}>
                    <x.icon className={`h-4 w-4 shrink-0 ${section === x.id ? 'text-indigo-400' : 'text-slate-500'}`} aria-hidden="true" />{x.label}</button>))}
              </div>))}
          </nav>
        </div>
        <div className="min-w-0">
          <div className="mb-4"><h2 className="text-base font-semibold text-white">{current.label}</h2><p className="text-sm text-slate-400">{current.hint}</p></div>
          {section === 'setup' && <SetupWizard status={status} onGo={pick} />}
          {section === 'profile' && <AgencyProfile />}
          {section === 'keys' && <IntegrationsPanel />}
          {section === 'webhooks' && <WebhooksPanel />}
          {section === 'services' && <PortfolioManager />}
          {section === 'sending' && (<div className="space-y-6"><GovernanceAndLearning />
            <button onClick={() => setRouting((v) => !v)} className="text-xs text-indigo-300 hover:text-indigo-200 underline">{routing ? 'Hide' : 'Show'} sender-routing tools</button>{routing && <FleetRouter />}</div>)}
          {section === 'dns' && <DnsStudio />}
          {section === 'unsub' && <CanSpamVault />}
          {section === 'team' && <EnterpriseRbac selectedTenant={me.org_id} />}
          {section === 'security' && <SecurityPanel me={me} onSignOut={onSignOut} />}
          {section === 'data' && <DataPanel />}
          {section === 'prefs' && <Preferences />}
          {section === 'api' && <ApiExplorer />}
          {section === 'tour' && <Tour />}
        </div>
      </div>
    </div>
  );
};
