import { useState } from 'react';
import type { FC } from 'react';
import { PageHeader, Tabs } from '../components/ui';
import { PipelineBoard } from '../components/clients/Pipeline';
import { ClientPage } from '../components/clients/ClientPage';
import { SequencesManager } from '../components/modules/SequencesManager';

export const Clients: FC<{ openLead: number | null; setOpenLead: (id: number | null) => void }> = ({ openLead, setOpenLead }) => {
  const [tab, setTab] = useState('pipeline');
  return (
    <div>
      <PageHeader title="Clients" subtitle="Everyone you are working with, from first look to won or lost. Click a client for its audit, contacts and drafts." />
      <Tabs tabs={[{ id: 'pipeline', label: 'Pipeline' }, { id: 'outreach', label: 'Email sequences' }]} active={tab} onChange={setTab} />
      {tab === 'pipeline' && <PipelineBoard onOpen={setOpenLead} />}
      {tab === 'outreach' && <SequencesManager />}
      <ClientPage leadId={openLead} onClose={() => setOpenLead(null)} />
    </div>
  );
};
