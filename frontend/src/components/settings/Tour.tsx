import type { FC } from 'react';
import { Card } from '../ui';

const STEPS = [
  { title: 'Today', body: 'Your daily starting point. Run a search to find prospects: the app verifies each company\'s website, audits it, scores it and drafts a first email. Drafts and tasks wait in your inbox; nothing is sent without you.' },
  { title: 'Find', body: 'Search for local businesses by type and city, or read job, project and tender feeds. Every result shows why it was ranked. "No website" is only stated when the source can prove it.' },
  { title: 'Clients', body: 'Everyone you work with. Open a client for its audit, what to recommend, contacts (stored unverified until an email verifier confirms them), a printable report, and a draft first email.' },
  { title: 'Settings', body: 'Your services and proof, mailboxes and DNS, the unsubscribe list, who can sign in, and the setup checklist. The red STOP button in the header halts all sending instantly.' },
  { title: 'What the app will not do', body: 'It does not invent contacts, measurements, results or prices. When something real is missing it creates a task for you. It reads public pages only and never tests a site intrusively.' },
];

export const Tour: FC = () => (
  <div className="space-y-3 max-w-3xl">
    {STEPS.map((s, i) => (
      <Card key={s.title}><div className="flex gap-3"><div className="h-6 w-6 rounded-full bg-indigo-500/15 text-indigo-300 text-xs flex items-center justify-center shrink-0 tabular">{i + 1}</div>
        <div><h3 className="text-sm font-semibold text-white">{s.title}</h3><p className="text-sm text-slate-300 mt-1 leading-relaxed">{s.body}</p></div></div></Card>))}
    <p className="text-xs text-slate-500">Press ⌘K (Ctrl+K) anywhere to jump to a screen.</p>
  </div>
);
