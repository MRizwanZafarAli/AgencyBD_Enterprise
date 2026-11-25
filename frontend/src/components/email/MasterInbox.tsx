import { useCallback, useEffect, useState } from 'react';
import type { FC } from 'react';
import { Archive, Check, Inbox, Mail, RefreshCw, Send, Sparkles } from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';

export interface InboxMessage {
  id: number;
  org_id: string;
  lead_id: number | null;
  company_name?: string | null;
  direction: string;
  sender_email: string;
  recipient_email: string;
  subject: string;
  body: string;
  category: string;
  sentiment: string;
  auto_reply_draft: string;
  status: 'unread' | 'read' | 'replied' | 'archived';
  received_at: string;
}

export const MasterInbox: FC<{
  onLoadDraftToComposer?: (params: { to: string; subject: string; body: string; leadId?: number }) => void;
}> = ({ onLoadDraftToComposer }) => {
  const [messages, setMessages] = useState<InboxMessage[]>([]);
  const [selected, setSelected] = useState<InboxMessage | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const [loading, setLoading] = useState(false);
  const [syncOpen, setSyncOpen] = useState(false);
  const [imapForm, setImapForm] = useState({ imap_host: '', imap_port: '993', username: '', password: '' });
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');

  const loadInbox = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch(`/api/email/inbox?status=${encodeURIComponent(filter)}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      const list: InboxMessage[] = body.messages || [];
      setMessages(list);
      if (list.length > 0 && !selected) setSelected(list[0]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [filter, selected]);

  useEffect(() => {
    loadInbox();
  }, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateStatus = async (msgId: number, status: 'read' | 'replied' | 'archived') => {
    const res = await apiFetch(`/api/email/inbox/${msgId}/status?status=${status}`, { method: 'POST' });
    if (res.ok) {
      setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, status } : m)));
      if (selected?.id === msgId) setSelected({ ...selected, status });
    }
  };

  const syncImap = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMsg('');
    setError('');
    setLoading(true);
    try {
      const res = await apiFetch('/api/email/inbox/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imap_host: imapForm.imap_host.trim(),
          imap_port: Number(imapForm.imap_port) || 993,
          username: imapForm.username.trim(),
          password: imapForm.password,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      setStatusMsg(`Synced ${body.synced_count ?? 0} unread email(s) from IMAP.`);
      setSyncOpen(false);
      await loadInbox();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Inbox className="h-4 w-4 text-indigo-400" />
              Unified Two-Way Master Inbox
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Incoming prospect replies automatically pause active sequences, classify intent, and draft contextual replies.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-200"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="all">All Messages</option>
              <option value="unread">Unread</option>
              <option value="read">Read</option>
              <option value="replied">Replied</option>
              <option value="archived">Archived</option>
            </select>
            <Button small onClick={() => setSyncOpen((v) => !v)}>
              <Mail className="h-3.5 w-3.5" />
              IMAP Sync
            </Button>
            <Button small onClick={loadInbox} disabled={loading}>
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {syncOpen && (
          <form onSubmit={syncImap} className="mt-4 pt-4 border-t border-slate-800 grid gap-2 sm:grid-cols-4">
            <input className={field} required placeholder="imap.gmail.com" value={imapForm.imap_host} onChange={(e) => setImapForm({ ...imapForm, imap_host: e.target.value })} />
            <input className={field} required placeholder="Username / Email" value={imapForm.username} onChange={(e) => setImapForm({ ...imapForm, username: e.target.value })} />
            <input className={field} required type="password" placeholder="App Password" value={imapForm.password} onChange={(e) => setImapForm({ ...imapForm, password: e.target.value })} />
            <Button type="submit" variant="primary" disabled={loading}>Poll Unread IMAP</Button>
          </form>
        )}

        {statusMsg && <p className="text-xs text-emerald-400 mt-2">{statusMsg}</p>}
        {error && <p className="text-xs text-rose-400 mt-2">{error}</p>}
      </Card>

      {messages.length === 0 ? (
        <Card>
          <p className="text-xs text-slate-400">
            No inbound messages in Master Inbox yet. Click <strong>IMAP Sync</strong> to pull replies from your mailbox or connect your ESP inbound webhook.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
          {/* Left Split-Pane Thread List */}
          <Card className="!p-2 max-h-[600px] overflow-y-auto space-y-1">
            {messages.map((m) => {
              const active = selected?.id === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    setSelected(m);
                    if (m.status === 'unread') updateStatus(m.id, 'read');
                  }}
                  className={`w-full text-left p-3 rounded-xl border transition ${
                    active ? 'bg-indigo-500/15 border-indigo-500/50' : 'bg-slate-900/40 border-slate-800/80 hover:bg-slate-900'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-xs font-semibold text-white truncate">{m.sender_email}</span>
                    <Badge tone={m.category === 'interested' ? 'good' : m.category === 'unsubscribe' ? 'bad' : 'accent'}>
                      {m.category}
                    </Badge>
                  </div>
                  <div className="text-xs text-slate-200 truncate">{m.subject || '(no subject)'}</div>
                  <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between">
                    <span>{m.company_name || 'Prospect'}</span>
                    <span>{m.status}</span>
                  </div>
                </button>
              );
            })}
          </Card>

          {/* Right Split-Pane Thread Reader & AI Draft Reply */}
          <Card>
            {selected ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
                  <div>
                    <h3 className="text-sm font-semibold text-white">{selected.subject || '(no subject)'}</h3>
                    <div className="text-xs text-slate-400 font-mono mt-0.5">
                      From: {selected.sender_email} → {selected.recipient_email}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={selected.sentiment === 'positive' ? 'good' : selected.sentiment === 'negative' ? 'bad' : 'neutral'}>
                      {selected.sentiment}
                    </Badge>
                    <Button small onClick={() => updateStatus(selected.id, 'replied')}>
                      <Check className="h-3.5 w-3.5 text-emerald-400" /> Mark Replied
                    </Button>
                    <Button small onClick={() => updateStatus(selected.id, 'archived')}>
                      <Archive className="h-3.5 w-3.5" /> Archive
                    </Button>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">
                  {selected.body}
                </div>

                {selected.auto_reply_draft && (
                  <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/40 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                        <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                        AI Reply Agent Suggested Draft
                      </span>
                      {onLoadDraftToComposer && (
                        <Button
                          small
                          variant="primary"
                          onClick={() =>
                            onLoadDraftToComposer({
                              to: selected.sender_email,
                              subject: selected.subject.startsWith('Re:') ? selected.subject : `Re: ${selected.subject}`,
                              body: selected.auto_reply_draft,
                              leadId: selected.lead_id ?? undefined,
                            })
                          }
                        >
                          <Send className="h-3.5 w-3.5" />
                          Load into Composer
                        </Button>
                      )}
                    </div>
                    <p className="text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">
                      {selected.auto_reply_draft}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-400">Select a reply on the left to inspect and respond.</p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};
