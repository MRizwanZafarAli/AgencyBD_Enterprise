import { useEffect, useMemo, useState } from 'react';
import type { FC } from 'react';
import {
  BellPlus,
  Building2,
  Check,
  CheckSquare,
  Copy,
  Cpu,
  Download,
  ExternalLink,
  Flame,
  Globe,
  MessageCircle,
  MessageSquare,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  UserCheck,
  UserPlus,
  XCircle,
} from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';

export type IntentType = 'buying_request' | 'competitor_complaint' | 'pain_point' | 'launch_trigger';

export interface SocialSignal {
  source: string;
  type: string;
  external_id: string;
  title: string;
  description: string;
  url: string;
  posted_at?: string | null;
  platform: string;
  community?: string;
  author?: string;
  intent_phrase?: string;
  intent_type?: IntentType;
  intent_score?: number;
  trigger_sentence?: string;
  reply_count?: number;
  upvotes?: number;
  is_comment?: boolean;
  external_urls?: string[];
}

export interface SourceHealth {
  id: string;
  label: string;
  status: 'ok' | 'rate_limited' | 'auth_required' | 'error';
  hits: number;
  detail?: string;
}

interface OfferQuery {
  label: string;
  source_offer: string;
  boolean_query: string;
}

interface ResolvedAuthor {
  author: string;
  display_name: string;
  platform: string;
  profile_url: string;
  company_name: string;
  website_url: string;
  website_domain: string;
  linkedin_url: string;
  x_handle: string;
  bio: string;
  discovered_urls: string[];
}

const INTENT_META: Record<IntentType, { label: string; badge: string; tone: 'good' | 'warn' | 'accent' | 'neutral' }> = {
  buying_request: { label: 'Active Buying Request', badge: 'Buying Request', tone: 'good' },
  competitor_complaint: { label: 'Competitor Complaint', badge: 'Competitor Pain', tone: 'warn' },
  pain_point: { label: 'Operational Pain', badge: 'Pain Point', tone: 'accent' },
  launch_trigger: { label: 'Launch / Growth', badge: 'Launch Trigger', tone: 'neutral' },
};

function formatFreshness(iso?: string | null): { label: string; ageHours: number | null } {
  if (!iso) return { label: 'Recent', ageHours: null };
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return { label: 'Recent', ageHours: null };
  const hours = Math.max(0, (Date.now() - ms) / 3_600_000);
  if (hours < 1) return { label: `${Math.max(1, Math.round(hours * 60))}m ago`, ageHours: hours };
  if (hours < 24) return { label: `${Math.round(hours)}h ago`, ageHours: hours };
  const days = Math.round(hours / 24);
  return { label: `${days}d ago`, ageHours: hours };
}

function competitionBadge(replies = 0, ageHours: number | null): { label: string; tone: 'good' | 'warn' | 'neutral' } {
  if (replies <= 5 && (ageHours === null || ageHours <= 24)) {
    return { label: 'Low-Comp Goldmine', tone: 'good' };
  }
  if (replies <= 20) {
    return { label: 'Active Window', tone: 'neutral' };
  }
  return { label: 'Saturated', tone: 'warn' };
}

function renderHighlightedDescription(text: string, triggerSentence?: string) {
  if (!text) return 'No post body text.';
  if (!triggerSentence || triggerSentence.length < 8) return text;
  const idx = text.toLowerCase().indexOf(triggerSentence.toLowerCase().slice(0, 40));
  if (idx === -1) return text;
  const end = Math.min(text.length, idx + triggerSentence.length);
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-amber-500/25 text-amber-200 px-1 rounded font-medium">{text.slice(idx, end)}</mark>
      {text.slice(end)}
    </>
  );
}

export const SocialIntentRadar: FC<{
  onOpenScraper?: (url: string, mode?: 'general' | 'client_audit' | 'job_spec' | 'local_audit', title?: string) => void;
}> = ({ onOpenScraper }) => {
  const [query, setQuery] = useState('');
  const [timeWindow, setTimeWindow] = useState<'24h' | '7d' | '30d' | 'all'>('7d');
  const [sortBy, setSortBy] = useState<'score' | 'newest'>('score');
  const [intentFilter, setIntentFilter] = useState<'all' | IntentType>('all');
  const [includeComments, setIncludeComments] = useState(true);
  const [showTrackers, setShowTrackers] = useState(false);

  const [communities, setCommunities] = useState(() => localStorage.getItem('social_communities') || 'smallbusiness, entrepreneur, SaaS, shopify');
  const [competitors, setCompetitors] = useState(() => localStorage.getItem('social_competitors') || 'Wix, HubSpot, Webflow');

  const [signals, setSignals] = useState<SocialSignal[]>([]);
  const [sourceHealth, setSourceHealth] = useState<SourceHealth[]>([]);
  const [offerQueries, setOfferQueries] = useState<OfferQuery[]>([]);
  const [selected, setSelected] = useState<SocialSignal | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [hasScanned, setHasScanned] = useState(false);

  // CRM & Triage state
  const [savedIds, setSavedIds] = useState<Record<string, boolean>>({});
  const [repliedIds, setRepliedIds] = useState<Record<string, boolean>>(() => {
    try { return JSON.parse(localStorage.getItem('social_replied_ids') || '{}'); } catch { return {}; }
  });
  const [dismissedIds, setDismissedIds] = useState<Record<string, boolean>>(() => {
    try { return JSON.parse(localStorage.getItem('social_dismissed_ids') || '{}'); } catch { return {}; }
  });
  const [checkedKeys, setCheckedKeys] = useState<Record<string, boolean>>({});

  // Slide-out / Detail Intelligence state
  const [resolvingAuthor, setResolvingAuthor] = useState(false);
  const [resolvedAuthor, setResolvedAuthor] = useState<ResolvedAuthor | null>(null);
  const [replyTone, setReplyTone] = useState<'value_first' | 'soft_case_study' | 'direct_dm'>('value_first');
  const [replyDraft, setReplyDraft] = useState('');
  const [guardrail, setGuardrail] = useState('');
  const [draftingReply, setDraftingReply] = useState(false);
  const [copiedReply, setCopiedReply] = useState(false);

  useEffect(() => {
    apiFetch('/api/leadfinder/social/offer-queries')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.queries) setOfferQueries(d.queries);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    localStorage.setItem('social_communities', communities);
  }, [communities]);

  useEffect(() => {
    localStorage.setItem('social_competitors', competitors);
  }, [competitors]);

  const sigKey = (s: SocialSignal) => `${s.source}-${s.external_id}`;

  const scan = async (overrideQuery?: string) => {
    const activeQ = overrideQuery !== undefined ? overrideQuery : query;
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const params = new URLSearchParams();
      if (activeQ.trim()) params.set('query', activeQ.trim());
      params.set('limit', '50');
      params.set('time_window', timeWindow);
      if (communities.trim()) params.set('communities', communities.trim());
      if (competitors.trim()) params.set('competitors', competitors.trim());
      params.set('include_comments', includeComments ? 'true' : 'false');

      const res = await apiFetch(`/api/leadfinder/social?${params.toString()}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      const rows: SocialSignal[] = body.signals || [];
      setSignals(rows);
      setSourceHealth(body.source_health || []);
      setSelected(rows[0] || null);
      setResolvedAuthor(null);
      setReplyDraft('');
      setGuardrail('');
      setCheckedKeys({});
      setHasScanned(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // Auto-generate reply draft when selecting a signal or changing tone
  useEffect(() => {
    if (!selected) return;
    setResolvedAuthor(null);
    setCopiedReply(false);
    setDraftingReply(true);
    apiFetch('/api/leadfinder/social/draft-reply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: selected.platform,
        community: selected.community || selected.source,
        title: selected.title,
        description: selected.description,
        intent_type: selected.intent_type || 'buying_request',
        trigger_sentence: selected.trigger_sentence || '',
        tone: replyTone,
        offer_hint: offerQueries[0]?.label || '',
      }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) {
          setReplyDraft(d.draft || '');
          setGuardrail(d.guardrail || '');
        }
      })
      .catch(() => {})
      .finally(() => setDraftingReply(false));
  }, [selected, replyTone, offerQueries]);

  const resolveAuthor = async (sig: SocialSignal) => {
    setResolvingAuthor(true);
    try {
      const res = await apiFetch('/api/leadfinder/social/resolve-author', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: sig.platform,
          author: sig.author || '',
          title: sig.title,
          description: sig.description,
          url: sig.url,
        }),
      });
      if (res.ok) {
        const data: ResolvedAuthor = await res.json();
        setResolvedAuthor(data);
      }
    } finally {
      setResolvingAuthor(false);
    }
  };

  const saveSignalToClients = async (sig: SocialSignal, overrideWebsite?: string, overrideCompany?: string) => {
    const key = sigKey(sig);
    const res = await apiFetch('/api/v1/browser/session/capture-leads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        leads: [{
          company_name: (overrideCompany || sig.title).slice(0, 80),
          contact_name: sig.author || '',
          website: overrideWebsite || sig.external_urls?.[0] || '',
          linkedin_url: sig.url || '',
        }],
        source: `social_${sig.platform.toLowerCase().replace(/\s+/g, '_')}`,
      }),
    });
    if (res.ok) setSavedIds((prev) => ({ ...prev, [key]: true }));
  };

  const bulkSaveSelected = async () => {
    const targets = visibleSignals.filter((s) => checkedKeys[sigKey(s)]);
    if (!targets.length) return;
    const res = await apiFetch('/api/v1/browser/session/capture-leads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        leads: targets.map((sig) => ({
          company_name: sig.title.slice(0, 80),
          contact_name: sig.author || '',
          website: sig.external_urls?.[0] || '',
          linkedin_url: sig.url || '',
        })),
        source: 'social_bulk_radar',
      }),
    });
    if (res.ok) {
      const next = { ...savedIds };
      targets.forEach((t) => { next[sigKey(t)] = true; });
      setSavedIds(next);
      setNotice(`Saved ${targets.length} social buyer signals to Clients.`);
    }
  };

  const exportCsv = () => {
    const targets = visibleSignals.filter((s) => checkedKeys[sigKey(s)]);
    const rows = targets.length ? targets : visibleSignals;
    const header = ['Platform', 'Community', 'IntentType', 'Score', 'Author', 'Title', 'TriggerSentence', 'URL'];
    const lines = [header.join(',')].concat(
      rows.map((r) => [
        r.platform,
        r.community || r.source,
        r.intent_type || '',
        String(r.intent_score ?? ''),
        r.author || '',
        `"${(r.title || '').replace(/"/g, '""')}"`,
        `"${(r.trigger_sentence || '').replace(/"/g, '""')}"`,
        r.url || '',
      ].join(',')),
    );
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `social-intent-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const watchThisIntent = async () => {
    const watchQ = query.trim() || offerQueries[0]?.label || 'agency OR redesign';
    const res = await apiFetch('/api/leadfinder/searches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: `Social Intent: ${watchQ.slice(0, 50)}`,
        source: 'social_intent',
        params: { q: watchQ },
        notify: true,
        every_hours: 12,
      }),
    });
    if (res.ok) {
      setNotice(`Watch created for "${watchQ}". Live matches will pipe into your Watching tab.`);
    } else {
      const body = await res.json().catch(() => ({}));
      setError(apiErrorMessage(res.status, body));
    }
  };

  const markReplied = (sig: SocialSignal) => {
    const next = { ...repliedIds, [sigKey(sig)]: true };
    setRepliedIds(next);
    localStorage.setItem('social_replied_ids', JSON.stringify(next));
  };

  const dismissSignal = (sig: SocialSignal) => {
    const next = { ...dismissedIds, [sigKey(sig)]: true };
    setDismissedIds(next);
    localStorage.setItem('social_dismissed_ids', JSON.stringify(next));
    if (selected && sigKey(selected) === sigKey(sig)) {
      const remaining = visibleSignals.filter((s) => sigKey(s) !== sigKey(sig));
      setSelected(remaining[0] || null);
    }
  };

  const intentCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: 0,
      buying_request: 0,
      competitor_complaint: 0,
      pain_point: 0,
      launch_trigger: 0,
    };
    signals.forEach((s) => {
      if (dismissedIds[sigKey(s)]) return;
      counts.all += 1;
      const t = s.intent_type || 'buying_request';
      counts[t] = (counts[t] || 0) + 1;
    });
    return counts;
  }, [signals, dismissedIds]);

  const visibleSignals = useMemo(() => {
    const active = signals.filter((s) => {
      if (dismissedIds[sigKey(s)]) return false;
      if (intentFilter !== 'all' && (s.intent_type || 'buying_request') !== intentFilter) return false;
      return true;
    });
    return [...active].sort((a, b) => {
      if (sortBy === 'newest') {
        return Date.parse(b.posted_at || '1970-01-01') - Date.parse(a.posted_at || '1970-01-01');
      }
      return (b.intent_score || 0) - (a.intent_score || 0);
    });
  }, [signals, dismissedIds, intentFilter, sortBy]);

  const checkedCount = Object.values(checkedKeys).filter(Boolean).length;
  const discoveredWebsite = resolvedAuthor?.website_url || selected?.external_urls?.[0] || '';

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Radio className="h-4 w-4 text-indigo-400" />
              Enterprise Social Buying-Intent Engine
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Multi-source buyer radar across Hacker News (posts + comments), Bluesky, Reddit, GitHub, Dev.to, and Lobsters with offer-aware boolean queries &amp; human-first reply studio.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button small variant="secondary" onClick={() => setShowTrackers((v) => !v)}>
              <SlidersHorizontal className="h-3.5 w-3.5 text-indigo-400" />
              Communities &amp; Competitors
            </Button>
            <Button small variant="secondary" onClick={watchThisIntent}>
              <BellPlus className="h-3.5 w-3.5 text-emerald-400" />
              Watch this Intent
            </Button>
          </div>
        </div>

        {/* Search + Time Window + Sort Controls */}
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
              placeholder='Topic or boolean query, e.g. ("shopify" OR "ecommerce") AND ("agency" OR "redesign")'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <select
            className={`${field} !w-auto text-xs`}
            value={timeWindow}
            onChange={(e) => setTimeWindow(e.target.value as '24h' | '7d' | '30d' | 'all')}
            aria-label="Time window"
          >
            <option value="24h">Last 24h</option>
            <option value="7d">Last 7d</option>
            <option value="30d">Last 30d</option>
            <option value="all">All time</option>
          </select>
          <select
            className={`${field} !w-auto text-xs`}
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'score' | 'newest')}
            aria-label="Sort order"
          >
            <option value="score">Sort: Intent Score</option>
            <option value="newest">Sort: Newest First</option>
          </select>
          <label className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={includeComments}
              onChange={(e) => setIncludeComments(e.target.checked)}
              className="rounded border-slate-700"
            />
            Mine Comments
          </label>
          <Button type="submit" variant="primary" disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Scanning 7 Feeds…' : 'Scan Social Intent'}
          </Button>
        </form>

        {/* Offer-Aware Auto-Query Builder */}
        <div className="flex flex-wrap items-center gap-1.5 mt-3 text-xs">
          <span className="text-[11px] text-indigo-300 font-medium inline-flex items-center gap-1">
            <Sparkles className="h-3 w-3" />
            Offer-Aware Queries:
          </span>
          {offerQueries.map((oq) => (
            <button
              key={oq.label}
              type="button"
              onClick={() => {
                setQuery(oq.boolean_query);
                scan(oq.boolean_query);
              }}
              title={oq.boolean_query}
              className="px-2.5 py-0.5 rounded-full text-[11px] bg-indigo-500/15 hover:bg-indigo-500/30 text-indigo-200 border border-indigo-500/30 transition"
            >
              {oq.label}
            </button>
          ))}
        </div>

        {/* Custom Community & Competitor Tracker */}
        {showTrackers && (
          <div className="grid sm:grid-cols-2 gap-3 mt-3 pt-3 border-t border-slate-800">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Custom Subreddits (comma-separated)</label>
              <input
                className={field}
                value={communities}
                onChange={(e) => setCommunities(e.target.value)}
                placeholder="smallbusiness, entrepreneur, shopify, wordpress"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Tracked Competitors (flags switching intent)</label>
              <input
                className={field}
                value={competitors}
                onChange={(e) => setCompetitors(e.target.value)}
                placeholder="Wix, HubSpot, Webflow, GoDaddy"
              />
            </div>
          </div>
        )}

        {/* Transparent Source Status Bar */}
        {sourceHealth.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-slate-800/80">
            <span className="text-[11px] text-slate-500 font-medium">Live Sources:</span>
            {sourceHealth.map((sh) => {
              const dotColor =
                sh.status === 'ok' && sh.hits > 0
                  ? 'bg-emerald-400'
                  : sh.status === 'ok'
                  ? 'bg-slate-400'
                  : sh.status === 'auth_required' || sh.status === 'rate_limited'
                  ? 'bg-amber-400'
                  : 'bg-rose-400';
              return (
                <span
                  key={sh.id}
                  title={sh.detail}
                  className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] bg-slate-900 border border-slate-800 text-slate-300"
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
                  <span>{sh.label}:</span>
                  <strong className="text-white">
                    {sh.status === 'auth_required'
                      ? 'Auth required'
                      : sh.status === 'rate_limited'
                      ? 'Rate-limited'
                      : `${sh.hits} hits`}
                  </strong>
                </span>
              );
            })}
          </div>
        )}

        {error && <p className="text-xs text-rose-400 mt-2">{error}</p>}
        {notice && <p className="text-xs text-emerald-400 mt-2">{notice}</p>}
      </Card>

      {/* Intent-Type Filter Pills & Bulk Action Bar */}
      {hasScanned && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {(
              [
                ['all', 'All Signals'],
                ['buying_request', 'Buying Requests'],
                ['competitor_complaint', 'Competitor Complaints'],
                ['pain_point', 'Pain Points'],
                ['launch_trigger', 'Launch Triggers'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setIntentFilter(id)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                  intentFilter === id
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900/70 border-slate-800 text-slate-300 hover:border-slate-700'
                }`}
              >
                {label} <span className="opacity-75 ml-1">({intentCounts[id] || 0})</span>
              </button>
            ))}
          </div>

          {visibleSignals.length > 0 && (
            <div className="flex items-center gap-2">
              {checkedCount > 0 && (
                <Button small variant="primary" onClick={bulkSaveSelected}>
                  <CheckSquare className="h-3.5 w-3.5" />
                  Save {checkedCount} to Clients
                </Button>
              )}
              <Button small variant="secondary" onClick={exportCsv}>
                <Download className="h-3.5 w-3.5" />
                Export CSV
              </Button>
            </div>
          )}
        </div>
      )}

      {!hasScanned && !loading && (
        <Card>
          <p className="text-xs text-slate-400">
            Click <strong>Scan Social Intent</strong> or choose an <strong>Offer-Aware Query</strong> chip above to pull live buying-intent threads &amp; comments.
          </p>
        </Card>
      )}

      {hasScanned && visibleSignals.length === 0 && !loading && (
        <Card>
          <p className="text-xs text-slate-400">
            No signals match this filter/window. Try switching Time Window to <strong>Last 30d</strong> or <strong>All time</strong>, or clear the intent filter.
          </p>
        </Card>
      )}

      {visibleSignals.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[430px_1fr]">
          {/* Left Split-Pane Queue */}
          <Card className="!p-2 max-h-[680px] overflow-y-auto space-y-1.5">
            {visibleSignals.map((sig) => {
              const key = sigKey(sig);
              const active = selected && sigKey(selected) === key;
              const fresh = formatFreshness(sig.posted_at);
              const comp = competitionBadge(sig.reply_count, fresh.ageHours);
              const meta = INTENT_META[sig.intent_type || 'buying_request'];
              const isSaved = savedIds[key];
              const isReplied = repliedIds[key];

              return (
                <div
                  key={key}
                  className={`p-3 rounded-xl border transition ${
                    active
                      ? 'bg-indigo-500/15 border-indigo-500/50 text-white'
                      : 'bg-slate-900/40 border-slate-800/80 text-slate-300 hover:bg-slate-900'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={!!checkedKeys[key]}
                      onChange={(e) => setCheckedKeys((p) => ({ ...p, [key]: e.target.checked }))}
                      className="mt-1 rounded border-slate-700"
                      aria-label={`Select ${sig.title}`}
                    />
                    <button
                      type="button"
                      onClick={() => setSelected(sig)}
                      className="flex-1 text-left min-w-0"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-1.5 mb-1">
                        <div className="flex flex-wrap items-center gap-1">
                          <Badge tone="accent">{sig.platform}</Badge>
                          <Badge tone={meta.tone}>{meta.badge}</Badge>
                          {sig.is_comment && <Badge tone="neutral">Comment Mine</Badge>}
                        </div>
                        <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                          {sig.intent_score ?? 65}/100
                        </span>
                      </div>
                      <div className="text-xs font-semibold line-clamp-2 text-white">{sig.title}</div>
                      {sig.trigger_sentence && (
                        <div className="text-[11px] text-amber-200/90 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2 py-1 mt-1.5 line-clamp-2">
                          &ldquo;{sig.trigger_sentence}&rdquo;
                        </div>
                      )}
                      <div className="text-[11px] text-slate-400 mt-1.5 flex flex-wrap items-center justify-between gap-1">
                        <span>{sig.author ? (sig.platform === 'Reddit' ? `u/${sig.author}` : `@${sig.author}`) : sig.community}</span>
                        <div className="flex items-center gap-1.5">
                          {isSaved && <span className="text-emerald-400 font-medium">In CRM</span>}
                          {isReplied && <span className="text-indigo-300 font-medium">Replied</span>}
                          <span className={comp.tone === 'good' ? 'text-emerald-300' : ''}>{sig.reply_count ?? 0} replies</span>
                          <span>· {fresh.label}</span>
                        </div>
                      </div>
                    </button>
                  </div>
                </div>
              );
            })}
          </Card>

          {/* Right Buyer Intelligence & Reply Studio */}
          <Card>
            {selected ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge tone="accent">{selected.platform}</Badge>
                    <Badge>{selected.community || selected.source}</Badge>
                    <Badge tone={INTENT_META[selected.intent_type || 'buying_request'].tone}>
                      {INTENT_META[selected.intent_type || 'buying_request'].label}
                    </Badge>
                    <Badge tone="good">Score: {selected.intent_score ?? 65}/100</Badge>
                  </div>
                  <button
                    type="button"
                    onClick={() => dismissSignal(selected)}
                    className="text-xs text-slate-400 hover:text-rose-400 inline-flex items-center gap-1"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    Dismiss
                  </button>
                </div>

                <h3 className="text-base font-semibold text-white">{selected.title}</h3>

                {/* Thread Context & Competition Meter */}
                {(() => {
                  const fresh = formatFreshness(selected.posted_at);
                  const comp = competitionBadge(selected.reply_count, fresh.ageHours);
                  return (
                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300 bg-slate-900/70 border border-slate-800 rounded-xl px-3 py-2">
                      <span className="inline-flex items-center gap-1">
                        <Flame className="h-3.5 w-3.5 text-amber-400" />
                        Competition: <Badge tone={comp.tone}>{comp.label}</Badge>
                      </span>
                      <span>{selected.reply_count ?? 0} replies</span>
                      <span>{selected.upvotes ?? 0} upvotes</span>
                      <span>Posted {fresh.label}</span>
                      {selected.author && <span className="font-mono text-slate-400">Author: {selected.author}</span>}
                    </div>
                  );
                })()}

                {/* Post Body with Trigger Highlighting */}
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-56 overflow-y-auto">
                  {renderHighlightedDescription(selected.description, selected.trigger_sentence)}
                </div>

                {/* Author-to-Company Identity Resolution & Cross-Tab Enrichment */}
                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                      <UserCheck className="h-4 w-4 text-indigo-400" />
                      Buyer Identity &amp; Cross-Tab Enrichment
                    </span>
                    <Button
                      small
                      variant="secondary"
                      disabled={resolvingAuthor}
                      onClick={() => resolveAuthor(selected)}
                    >
                      <Building2 className="h-3.5 w-3.5 text-indigo-400" />
                      {resolvingAuthor ? 'Resolving Profile…' : 'Resolve Author Identity'}
                    </Button>
                  </div>

                  {resolvedAuthor ? (
                    <div className="grid sm:grid-cols-2 gap-2 text-xs text-slate-300 pt-1">
                      <div>Company: <strong className="text-white">{resolvedAuthor.company_name || 'Not listed'}</strong></div>
                      <div>Website: {resolvedAuthor.website_url ? (
                        <a href={resolvedAuthor.website_url} target="_blank" rel="noreferrer" className="text-indigo-300 underline">{resolvedAuthor.website_domain}</a>
                      ) : 'None found'}</div>
                      {resolvedAuthor.linkedin_url && (
                        <div>LinkedIn: <a href={resolvedAuthor.linkedin_url} target="_blank" rel="noreferrer" className="text-indigo-300 underline">Profile</a></div>
                      )}
                      {resolvedAuthor.x_handle && (
                        <div>X / Twitter: <span className="text-slate-200">{resolvedAuthor.x_handle}</span></div>
                      )}
                      {resolvedAuthor.bio && (
                        <div className="sm:col-span-2 text-[11px] text-slate-400 line-clamp-2">{resolvedAuthor.bio}</div>
                      )}
                    </div>
                  ) : (
                    <p className="text-[11px] text-slate-400">
                      Click <strong>Resolve Author Identity</strong> to scan their public bio/history for company domain, LinkedIn, and X handle.
                    </p>
                  )}

                  {discoveredWebsite && onOpenScraper && (
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <Button
                        small
                        variant="primary"
                        onClick={() => onOpenScraper(discoveredWebsite, 'local_audit', resolvedAuthor?.company_name || selected.title)}
                      >
                        <Globe className="h-3.5 w-3.5" />
                        Run Full Site &amp; Contact Audit ({resolvedAuthor?.website_domain || discoveredWebsite})
                      </Button>
                    </div>
                  )}
                </div>

                {/* Human-First Reply Studio */}
                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                      <MessageCircle className="h-4 w-4 text-emerald-400" />
                      Human-First Reply Studio
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {(
                        [
                          ['value_first', 'Value-First'],
                          ['soft_case_study', 'Soft Case-Study'],
                          ['direct_dm', 'Direct DM'],
                        ] as const
                      ).map(([t, lbl]) => (
                        <button
                          key={t}
                          type="button"
                          onClick={() => setReplyTone(t)}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-medium border transition ${
                            replyTone === t
                              ? 'bg-emerald-600/30 border-emerald-500 text-emerald-200'
                              : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                          }`}
                        >
                          {lbl}
                        </button>
                      ))}
                    </div>
                  </div>

                  {guardrail && (
                    <div className="flex items-start gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/25 text-[11px] text-amber-200">
                      <ShieldAlert className="h-3.5 w-3.5 shrink-0 mt-0.5 text-amber-400" />
                      <span>{guardrail}</span>
                    </div>
                  )}

                  <textarea
                    rows={5}
                    className={`${field} text-xs leading-relaxed`}
                    value={draftingReply ? 'Drafting human-first reply…' : replyDraft}
                    onChange={(e) => setReplyDraft(e.target.value)}
                  />

                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap gap-2">
                      <Button
                        small
                        variant="secondary"
                        onClick={() => {
                          navigator.clipboard?.writeText(replyDraft);
                          setCopiedReply(true);
                          setTimeout(() => setCopiedReply(false), 2000);
                        }}
                      >
                        {copiedReply ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                        {copiedReply ? 'Copied!' : 'Copy Reply'}
                      </Button>
                      <Button
                        small
                        variant="secondary"
                        disabled={!!repliedIds[sigKey(selected)]}
                        onClick={() => markReplied(selected)}
                      >
                        <MessageSquare className="h-3.5 w-3.5 text-indigo-400" />
                        {repliedIds[sigKey(selected)] ? 'Marked Replied' : 'Mark as Replied'}
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Primary Action Bar */}
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
                  <Button
                    small
                    variant="secondary"
                    disabled={!!savedIds[sigKey(selected)]}
                    onClick={() => saveSignalToClients(selected, discoveredWebsite, resolvedAuthor?.company_name)}
                  >
                    {savedIds[sigKey(selected)] ? (
                      <><Check className="h-3.5 w-3.5 text-emerald-400" />Saved to Clients</>
                    ) : (
                      <><UserPlus className="h-3.5 w-3.5 text-indigo-400" />Save to Clients</>
                    )}
                  </Button>
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
