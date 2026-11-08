import { useState } from 'react';
import type { FC } from 'react';
import { Check, Code, Copy, Eye, Plus, Sparkles, UserPlus } from 'lucide-react';
import { Badge, Button, Card, Drawer, EmptyState } from '../ui';
import { send, useApi } from '../../lib/hooks';

interface VisitorEvent {
  id: number;
  ip_address: string;
  hostname: string | null;
  company_name: string | null;
  domain: string | null;
  page_url: string;
  referrer: string | null;
  intent_score: number;
  converted_lead_id: number | null;
  created_at: string;
}

interface VisitorData {
  events: VisitorEvent[];
  summary: {
    total_visitors: number;
    high_intent_count: number;
    converted_count: number;
  };
  tracking_snippet: string;
}

export const VisitorRadar: FC<{ onOpenClient: (leadId: number) => void }> = ({ onOpenClient }) => {
  const visitors = useApi<VisitorData>('/api/analytics/visitor-intent');
  const [showSnippet, setShowSnippet] = useState(false);
  const [copied, setCopied] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [convertingId, setConvertingId] = useState<number | null>(null);

  const simulate = async () => {
    setSimulating(true);
    try {
      await send('/api/analytics/visitor-intent/simulate', 'POST', {
        company_name: 'Stripe',
        domain: 'stripe.com',
        page_url: '/pricing',
        intent_score: 92
      });
      visitors.reload();
    } catch {
      // ignore
    } finally {
      setSimulating(false);
    }
  };

  const convert = async (eventId: number) => {
    setConvertingId(eventId);
    try {
      const res = await send<{ status: string; lead_id: number }>(`/api/analytics/visitor-intent/${eventId}/convert`, 'POST');
      visitors.reload();
      if (res.lead_id) {
        onOpenClient(res.lead_id);
      }
    } catch {
      // ignore
    } finally {
      setConvertingId(null);
    }
  };

  const copySnippet = () => {
    if (visitors.data?.tracking_snippet) {
      navigator.clipboard.writeText(visitors.data.tracking_snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const events = visitors.data?.events ?? [];
  const summary = visitors.data?.summary;

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-3">
        <div>
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Eye className="h-4 w-4 text-amber-400" />
            <span>Live Visitor Intent Radar</span>
            <span className="relative flex h-2 w-2 ml-1">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Detects enterprise accounts browsing your website and flags high-intent pages without third-party API tax.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {summary && (
            <div className="hidden sm:flex items-center gap-2 font-mono text-xs mr-2">
              <span className="text-slate-400">{summary.total_visitors} visits</span>
              <span className="text-slate-600">&middot;</span>
              <span className="text-amber-400 font-semibold">{summary.high_intent_count} high intent</span>
            </div>
          )}
          <Button small onClick={simulate} disabled={simulating}>
            <Sparkles className="h-3 w-3 text-amber-400" />
            {simulating ? 'Simulating…' : 'Simulate visit'}
          </Button>
          <Button small onClick={() => setShowSnippet(true)}>
            <Code className="h-3.5 w-3.5" />
            Tracker code
          </Button>
        </div>
      </div>

      {events.length === 0 ? (
        <EmptyState
          title="No live visitor events detected yet"
          hint="Embed the lightweight script on your agency landing page, or click Simulate visit above to preview live intent signals."
          action={<Button small variant="primary" onClick={simulate}><Plus className="h-3.5 w-3.5" />Simulate test enterprise visit</Button>}
        />
      ) : (
        <ul className="space-y-2">
          {events.slice(0, 8).map((e) => {
            const isHigh = e.intent_score >= 70;
            return (
              <li
                key={e.id}
                className="flex flex-wrap items-center justify-between gap-3 p-2.5 rounded-xl border border-white/5 bg-slate-900/40 hover:bg-slate-900/70 transition"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="h-8 w-8 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 font-bold text-xs flex items-center justify-center shrink-0">
                    {e.company_name ? e.company_name.slice(0, 2).toUpperCase() : 'IP'}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-white truncate">
                        {e.company_name || e.hostname || e.ip_address}
                      </span>
                      {e.domain && (
                        <span className="text-[11px] font-mono text-slate-400">{e.domain}</span>
                      )}
                      <Badge tone={isHigh ? 'accent' : 'neutral'}>
                        Intent {e.intent_score}
                      </Badge>
                    </div>
                    <div className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                      <span className="font-mono text-indigo-300">{e.page_url}</span>
                      <span className="text-slate-600">&middot;</span>
                      <span>{new Date(e.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {e.converted_lead_id ? (
                    <Badge tone="good">Added to Clients</Badge>
                  ) : (
                    <Button
                      small
                      variant="primary"
                      onClick={() => convert(e.id)}
                      disabled={convertingId === e.id}
                    >
                      <UserPlus className="h-3.5 w-3.5" />
                      {convertingId === e.id ? 'Adding…' : 'Add to Clients'}
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {/* Snippet Drawer */}
      <Drawer open={showSnippet} title="Embed Tracker Script" onClose={() => setShowSnippet(false)}>
        <div className="space-y-4 text-xs text-slate-300">
          <p>
            Paste this single script tag into the <code>&lt;head&gt;</code> of your agency website or documentation.
            It performs zero-cookie, privacy-friendly reverse network lookups and surfaces active accounts directly into this dashboard.
          </p>
          <div className="relative">
            <pre className="p-3 rounded-xl bg-slate-950 border border-white/10 font-mono text-[11px] text-amber-200 overflow-x-auto">
              {visitors.data?.tracking_snippet || '<script defer src="/api/tracker.js"></script>'}
            </pre>
          </div>
          <Button small variant="primary" onClick={copySnippet}>
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied script to clipboard' : 'Copy script'}
          </Button>
        </div>
      </Drawer>
    </Card>
  );
};
