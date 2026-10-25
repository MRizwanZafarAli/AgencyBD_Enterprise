import { useState } from 'react';
import type { FC } from 'react';
import { Check, X, Copy, ArrowRight, Settings as Gear, Mail, ShieldAlert, UserSearch, ClipboardList } from 'lucide-react';
import { Badge, Button } from '../ui';
import { send } from '../../lib/hooks';
import { ErrorBanner } from '../shared/ErrorBanner';

export interface InboxEntry {
  type: 'approval' | 'work_item' | 'setup';
  id: number | string;
  priority: number;
  title: string;
  detail: string;
  kind?: string;
  entity_type?: string | null;
  entity_id?: number | null;
  data?: any;
}

const KIND_ICON: Record<string, FC<{ className?: string }>> = { find_contact: UserSearch, new_cve: ShieldAlert, review_lead: ClipboardList, approval: Mail, setup: Gear };

export const InboxItem: FC<{ item: InboxEntry; onChanged: () => void; onOpenClient: (leadId: number) => void; onSettings: (section?: string) => void }> = ({ item, onChanged, onOpenClient, onSettings }) => {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const Icon = KIND_ICON[item.type === 'work_item' ? item.kind ?? 'review_lead' : item.type] ?? ClipboardList;
  const a = item.data;
  const body: string = a?.draft_body ?? a?.proposal_body ?? '';

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try { await fn(); onChanged(); } catch (e) { setError(e instanceof Error ? e.message : 'Failed'); } finally { setBusy(false); }
  };

  const decide = (decision: 'approved' | 'rejected') => run(async () => {
    await send(`/api/approvals/${item.id}/decide`, 'POST', { decision, reason: `Decided from Today (${decision})` });
    if (decision === 'approved' && a?.subject_type === 'outbound_draft') {
      const res = await send<any>(`/api/outbound/drafts/${a.subject_id}/send`, 'POST');
      setNote(res.status === 'sent' ? `Sent to ${res.recipient_email}.` : `Not sent (${res.status}): ${res.reason ?? ''}`);
    }
  });

  return (
    <li className="py-4 flex gap-3">
      <Icon className="h-4 w-4 mt-1 text-slate-400 shrink-0" />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-white">{item.title}</span>
          {item.type === 'approval' && <Badge tone="accent">{a?.subject_type === 'outbound_draft' ? 'Email draft' : 'Proposal'}</Badge>}
          {item.kind === 'new_cve' && <Badge tone="bad">Security watch</Badge>}
        </div>
        {item.type === 'approval' && a?.draft_recipient && <div className="text-xs text-slate-400">To {a.draft_recipient}{a.draft_step ? ` · step ${a.draft_step}` : ''}</div>}
        {item.detail && item.type !== 'approval' && <p className="text-xs text-slate-400 max-w-2xl">{item.detail}</p>}
        {body && <pre className="text-xs text-slate-300 whitespace-pre-wrap bg-slate-900 border border-slate-800 rounded-lg p-3 max-h-56 overflow-auto font-sans leading-relaxed">{body}</pre>}
        {note && <div role="status" className="text-xs text-slate-300">{note}</div>}
        <ErrorBanner message={error} />
        <div className="flex flex-wrap gap-2">
          {item.type === 'approval' && (
            <>
              <Button small variant="primary" disabled={busy} onClick={() => decide('approved')}><Check className="h-3.5 w-3.5" />{a?.subject_type === 'outbound_draft' ? 'Approve and send' : 'Approve'}</Button>
              <Button small disabled={busy} onClick={() => decide('rejected')}><X className="h-3.5 w-3.5" />Reject</Button>
              {a?.subject_type !== 'outbound_draft' && body && <Button small onClick={() => navigator.clipboard?.writeText(body)}><Copy className="h-3.5 w-3.5" />Copy text</Button>}
            </>
          )}
          {item.type === 'work_item' && (
            <>
              {item.entity_type === 'lead' && item.entity_id != null && <Button small variant="primary" onClick={() => onOpenClient(item.entity_id as number)}>Open client<ArrowRight className="h-3.5 w-3.5" /></Button>}
              <Button small disabled={busy} onClick={() => run(() => send(`/api/inbox/work_items/${item.id}/resolve`, 'POST', { status: 'done' }))}>Done</Button>
              <Button small variant="ghost" disabled={busy} onClick={() => run(() => send(`/api/inbox/work_items/${item.id}/resolve`, 'POST', { status: 'dismissed' }))}>Dismiss</Button>
            </>
          )}
          {item.type === 'setup' && <Button small variant="primary" onClick={() => onSettings(['llm', 'verifier'].includes(String(item.id)) ? 'keys' : ['portfolio', 'services'].includes(String(item.id)) ? 'services' : ['mailbox'].includes(String(item.id)) ? 'sending' : 'setup')}>Fix in Settings<ArrowRight className="h-3.5 w-3.5" /></Button>}
        </div>
      </div>
    </li>
  );
};
