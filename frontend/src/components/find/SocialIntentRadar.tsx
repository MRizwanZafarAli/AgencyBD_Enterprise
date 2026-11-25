import { useState } from 'react';
import type { FC } from 'react';
import { Cpu, ExternalLink, MessageSquare, Radio, RefreshCw, Search } from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';

export interface SocialSignal {
  source: string;
  type: string;
  external_id: string;
  title: string;
  description: string;
  url: string;
  posted_at?: string | null;
  platform: string;
  author?: string;
  intent_phrase?: string;
}

export const SocialIntentRadar: FC<{
  onOpenScraper?: (url: string, mode?: 'general' | 'client_audit' | 'job_spec' | 'local_audit', title?: string) => void;
}> = ({ onOpenScraper }) => {
  const [query, setQuery] = useState('');
  const [signals, setSignals] = useState<SocialSignal[]>([]);
  const [selected, setSelected] = useState<SocialSignal | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasScanned, setHasScanned] = useState(false);

  const scan = async () => {
    setLoading(true);
    setError('');
    try {
      const qs = query.trim() ? `?query=${encodeURIComponent(query.trim())}` : '';
      const res = await apiFetch(`/api/leadfinder/social${qs}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      const rows: SocialSignal[] = body.signals || [];
      setSignals(rows);
      setSelected(rows[0] || null);
      setHasScanned(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Radio className="h-4 w-4 text-indigo-400" />
              Social Media Buying-Intent Radar
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Scans Reddit (r/smallbusiness, r/entrepreneur, r/SaaS) and Hacker News Ask HN for buyers actively asking for agencies, developers, or redesigns.
            </p>
          </div>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            scan();
          }}
          className="flex flex-wrap gap-2"
        >
          <div className="relative flex-1 min-w-60">
            <Search className="h-4 w-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              className={`${field} pl-9`}
              placeholder="Optional topic filter (e.g. react, shopify, seo, website, ai)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <Button type="submit" variant="primary" disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Scanning Feeds…' : 'Scan Social Intent'}
          </Button>
        </form>
        {error && <p className="text-xs text-rose-400 mt-2">{error}</p>}
      </Card>

      {hasScanned && signals.length === 0 && !loading && (
        <Card>
          <p className="text-xs text-slate-400">No matching social buying-intent posts found right now. Try clearing the topic filter or scanning again.</p>
        </Card>
      )}

      {signals.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[400px_1fr]">
          {/* Left Split-Pane Queue */}
          <Card className="!p-2 max-h-[620px] overflow-y-auto space-y-1">
            {signals.map((sig) => {
              const active = selected?.external_id === sig.external_id && selected?.source === sig.source;
              return (
                <button
                  key={`${sig.source}-${sig.external_id}`}
                  type="button"
                  onClick={() => setSelected(sig)}
                  className={`w-full text-left p-3 rounded-xl border transition ${
                    active
                      ? 'bg-indigo-500/15 border-indigo-500/50 text-white'
                      : 'bg-slate-900/40 border-slate-800/80 text-slate-300 hover:bg-slate-900'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <Badge tone="accent">{sig.platform}</Badge>
                    {sig.intent_phrase && <Badge tone="good">{sig.intent_phrase}</Badge>}
                  </div>
                  <div className="text-xs font-semibold line-clamp-2 text-white">{sig.title}</div>
                  <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between">
                    <span>{sig.author ? `u/${sig.author}` : sig.source}</span>
                    {sig.posted_at && <span>{sig.posted_at.slice(0, 10)}</span>}
                  </div>
                </button>
              );
            })}
          </Card>

          {/* Right Split-Pane Detail Preview */}
          <Card>
            {selected ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="accent">{selected.platform}</Badge>
                  <Badge>{selected.source}</Badge>
                  {selected.intent_phrase && <Badge tone="good">Intent: &quot;{selected.intent_phrase}&quot;</Badge>}
                </div>
                <h3 className="text-base font-semibold text-white">{selected.title}</h3>
                {selected.author && (
                  <div className="text-xs text-slate-400 font-mono">Author: {selected.author}</div>
                )}
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
                  {selected.description || 'No post body text.'}
                </div>
                <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
                  {selected.url && (
                    <a
                      href={selected.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      Open Thread &amp; Reply
                    </a>
                  )}
                  {onOpenScraper && selected.url && (
                    <Button
                      small
                      variant="secondary"
                      onClick={() => onOpenScraper(selected.url, 'general', selected.title)}
                    >
                      <Cpu className="h-3.5 w-3.5 text-amber-400" />
                      Inspect Thread in Scraper
                    </Button>
                  )}
                </div>
                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 flex items-start gap-2">
                  <MessageSquare className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-slate-200">BD Tip:</strong> Answer their question technically first in the thread (no generic pitch), then offer a free 5-point Site Clinic audit link.
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400">Select a social signal on the left to inspect its context.</p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};
