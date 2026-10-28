import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Plus, Send, Trash2, Zap } from 'lucide-react';
import { Badge, Button, Card, EmptyState, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';

interface Webhook {
  id: number;
  url: string;
  secret_masked: string;
  events: string[];
  active: boolean;
  last_delivered_at: string | null;
  last_status_code: number | null;
  last_error: string | null;
  created_at: string;
}

interface EventDef {
  id: string;
  label: string;
  description: string;
}

interface WebhookData {
  webhooks: Webhook[];
  available_events: EventDef[];
}

export const WebhooksPanel: FC = () => {
  const data = useApi<WebhookData>('/api/webhooks');
  const [url, setUrl] = useState('');
  const [secret, setSecret] = useState('');
  const [selectedEvents, setSelectedEvents] = useState<string[]>(['deal.won', 'client.created']);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<Record<number, string>>({});

  const toggleEvent = (eventId: string) => {
    setSelectedEvents((prev) =>
      prev.includes(eventId) ? prev.filter((e) => e !== eventId) : [...prev, eventId]
    );
  };

  const addWebhook = async (e: FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setError('');
    setAdding(true);
    try {
      await send('/api/webhooks', 'POST', {
        url: url.trim(),
        secret: secret.trim() || undefined,
        events: selectedEvents
      });
      setUrl('');
      setSecret('');
      data.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add webhook');
    } finally {
      setAdding(false);
    }
  };

  const removeWebhook = async (id: number) => {
    try {
      await send(`/api/webhooks/${id}`, 'DELETE');
      data.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete webhook');
    }
  };

  const testWebhook = async (id: number) => {
    setTestingId(id);
    try {
      const res = await send<{ status: string; status_code: number | null; latency_ms: number; error?: string }>(
        `/api/webhooks/${id}/test`,
        'POST'
      );
      if (res.status === 'delivered') {
        setTestResult((prev) => ({ ...prev, [id]: `Delivered: ${res.status_code} (${res.latency_ms}ms)` }));
      } else {
        setTestResult((prev) => ({ ...prev, [id]: `Failed (${res.status_code}): ${res.error || 'Network error'}` }));
      }
      data.reload();
    } catch (err) {
      setTestResult((prev) => ({ ...prev, [id]: `Test failed: ${err instanceof Error ? err.message : 'Error'}` }));
    } finally {
      setTestingId(null);
    }
  };

  const webhooks = data.data?.webhooks ?? [];
  const events = data.data?.available_events ?? [];

  return (
    <Card className="space-y-5">
      <div>
        <h2 className="text-sm font-semibold text-white flex items-center gap-2">
          <Zap className="h-4 w-4 text-amber-400" />
          <span>Outbound Webhooks &amp; CRM Sync</span>
        </h2>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">
          Dispatches real-time HMAC-signed events to your external tools (HubSpot, Salesforce, Zapier, Make, or custom API endpoints)
          whenever deals are won or clients are enrolled.
        </p>
      </div>

      <ErrorBanner message={error || data.error} />

      {/* Add Webhook Form */}
      <form onSubmit={addWebhook} className="p-4 rounded-xl border border-white/10 bg-slate-900/40 space-y-3">
        <div className="text-xs font-semibold text-white flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5 text-amber-400" />
          <span>Register New Webhook Endpoint</span>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">Target Endpoint URL</label>
            <input
              className={field}
              placeholder="https://hooks.zapier.com/hooks/catch/... or https://api.crm.com/v1"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="text-[11px] font-mono text-slate-400 uppercase block mb-1">HMAC Signing Secret (Optional)</label>
            <input
              className={field}
              placeholder="Leave blank to auto-generate secure secret"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
            />
          </div>
        </div>

        <div>
          <label className="text-[11px] font-mono text-slate-400 uppercase block mb-2">Subscribe to Events</label>
          <div className="grid gap-2 sm:grid-cols-2">
            {events.map((ev) => {
              const checked = selectedEvents.includes(ev.id);
              return (
                <label
                  key={ev.id}
                  className={`flex items-start gap-2 p-2 rounded-lg border text-xs cursor-pointer transition ${
                    checked ? 'border-amber-500/40 bg-amber-500/5 text-slate-200' : 'border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-amber-500"
                    checked={checked}
                    onChange={() => toggleEvent(ev.id)}
                  />
                  <div>
                    <div className="font-semibold text-white">{ev.label}</div>
                    <div className="text-[10px] text-slate-500">{ev.description}</div>
                  </div>
                </label>
              );
            })}
          </div>
        </div>

        <Button small variant="primary" type="submit" disabled={adding || !url.trim()}>
          {adding ? 'Saving…' : 'Save Webhook Endpoint'}
        </Button>
      </form>

      {/* Existing Webhooks List */}
      <div>
        <div className="text-xs font-semibold text-slate-300 mb-2">Active Webhooks ({webhooks.length})</div>
        {webhooks.length === 0 ? (
          <EmptyState
            title="No external webhooks configured"
            hint="Register a webhook above to stream won deals and new client events into your CRM or automation platform."
          />
        ) : (
          <ul className="space-y-2.5">
            {webhooks.map((w) => (
              <li
                key={w.id}
                className="p-3.5 rounded-xl border border-white/5 bg-slate-900/50 space-y-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-white truncate">{w.url}</span>
                      <Badge tone={w.active ? 'good' : 'neutral'}>{w.active ? 'Active' : 'Paused'}</Badge>
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                      Secret: {w.secret_masked} &middot; Subscribed: {w.events.join(', ')}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Button small onClick={() => testWebhook(w.id)} disabled={testingId === w.id}>
                      <Send className="h-3 w-3 text-amber-400" />
                      {testingId === w.id ? 'Testing…' : 'Send test event'}
                    </Button>
                    <button
                      onClick={() => removeWebhook(w.id)}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 transition"
                      aria-label="Delete webhook"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {(testResult[w.id] || w.last_status_code) && (
                  <div className="text-[11px] font-mono flex items-center gap-2 pt-1 border-t border-white/5 text-slate-400">
                    {testResult[w.id] ? (
                      <span className="text-amber-300">{testResult[w.id]}</span>
                    ) : (
                      <>
                        <span>Last delivery: {w.last_status_code ? `HTTP ${w.last_status_code}` : 'Pending'}</span>
                        {w.last_delivered_at && <span>({new Date(w.last_delivered_at).toLocaleTimeString()})</span>}
                        {w.last_error && <span className="text-rose-400 truncate">&middot; {w.last_error}</span>}
                      </>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
};
