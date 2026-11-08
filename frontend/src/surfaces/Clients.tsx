import { useState } from 'react';
import type { FC } from 'react';
import { PageHeader, Tabs } from '../components/ui';
import { PipelineBoard } from '../components/clients/Pipeline';
import { ClientPage } from '../components/clients/ClientPage';
import { Partners } from '../components/clients/Partners';
import { SequencesManager } from '../components/modules/SequencesManager';
import type { Me } from '../lib/api';

export const Clients: FC<{
  openLead: number | null;
  setOpenLead: (id: number | null) => void;
  identity?: Me | null;
}> = ({ openLead, setOpenLead, identity }) => {
  const [tab, setTab] = useState('pipeline');
  const isAuditor = identity?.role === 'auditor';
  const tabs = isAuditor
    ? [{ id: 'pipeline', label: 'Pipeline' }]
    : [
        { id: 'pipeline', label: 'Pipeline' },
        { id: 'outreach', label: 'Email sequences' },
        { id: 'partners', label: 'Partners' },
      ];

  return (
    <div>
      <PageHeader
        title="Clients"
        subtitle={
          isAuditor
            ? 'Monitored accounts, technical audits, and lead profiles for compliance inspection.'
            : 'Everyone you are working with, from first look to won or lost. Click a client for its audit, contacts and drafts.'
        }
      />
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === 'pipeline' && <PipelineBoard onOpen={setOpenLead} />}
      {!isAuditor && tab === 'outreach' && <SequencesManager />}
      {!isAuditor && tab === 'partners' && <Partners />}
      <ClientPage leadId={openLead} onClose={() => setOpenLead(null)} />
    </div>
  );
};
