import { useEffect, useMemo, useRef, useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Bell, Cpu, Download, Filter, Search, ShieldAlert, Star } from 'lucide-react';
import { Badge, Button, Card, EmptyState, Pager, ScoreBar, Select, Skeletons, SuggestInput } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { apiFetch } from '../../lib/api';
import { send, useApi } from '../../lib/hooks';
import { ResultsMap } from './ResultsMap';
import { LocalBusinessDrawer, computeOfferScore } from './LocalBusinessDrawer';
import type { AgencyOffer, LocalResult } from './LocalBusinessDrawer';

interface Hunt { provider: string; count: number; results: LocalResult[]; notes: string[] }

const STATUS: Record<string, { text: string; tone: 'bad' | 'warn' | 'neutral' }> = {
  no_website_listed: { text: 'No website', tone: 'bad' },
  no_website_in_osm: { text: 'No website recorded', tone: 'warn' },
  social_only: { text: 'Social page only', tone: 'warn' },
  domain_unreachable: { text: 'Domain dead', tone: 'bad' },
  tls_broken: { text: 'Certificate error', tone: 'bad' },
  domain_parked: { text: 'Parked domain', tone: 'bad' },
  has_site: { text: 'Has a website', tone: 'neutral' },
};
const PAGE = 15;

export interface LocalPreset { category: string; city: string; only_gaps: boolean; nonce: number }

export const FindLocal: FC<{
  onSaved: (leadId: number) => void;
  preset?: LocalPreset | null;
  onAddGoogleKey?: () => void;
  onSendEmail?: (params: {
    recipient: string;
    recipientName?: string;
    companyName?: string;
    subject?: string;
    body?: string;
    leadId?: number;
  }) => void;
  onOpenScraper?: (url: string, mode?: 'general' | 'client_audit' | 'job_spec' | 'local_audit', title?: string) => void;
}> = ({ onSaved, preset, onAddGoogleKey, onSendEmail, onOpenScraper }) => {
  const providers = useApi<{ google: boolean }>('/api/hunt/local/providers');
  const google = providers.data?.google ?? false;
  const [category, setCategory] = useState('');
  const [city, setCity] = useState('');
  const [provider, setProvider] = useState('');
  const [offer, setOffer] = useState<AgencyOffer>('web_design');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<Hunt | null>(null);
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<LocalResult | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Record<string, number>>({});
  const [view, setView] = useState<'list' | 'map'>('list');

  // Money Filters
  const [showFilters, setShowFilters] = useState(false);
  const [presenceFilter, setPresenceFilter] = useState<'all' | 'no_site' | 'broken' | 'has_site'>('all');
  const [hideSaved, setHideSaved] = useState(false);
  const [onlyPhone, setOnlyPhone] = useState(false);
  const [onlyHighPitch, setOnlyHighPitch] = useState(false);
  const [lowRatingOnly, setLowRatingOnly] = useState(false);

  // Territory watch + bulk audit feedback
  const [watchNotice, setWatchNotice] = useState('');
  const [bulkStatus, setBulkStatus] = useState('');
  const [savedNotice, setSavedNotice] = useState<{ count: number; lastId: number | null } | null>(null);

  const rows = useMemo(() => {
    const raw = data?.results ?? [];
    return raw
      .filter((r) => {
        if (presenceFilter === 'no_site' && !r.classification.startsWith('no_website') && r.classification !== 'social_only') return false;
        if (presenceFilter === 'broken' && !['domain_unreachable', 'tls_broken', 'domain_parked'].includes(r.classification)) return false;
        if (presenceFilter === 'has_site' && r.classification !== 'has_site') return false;
        if (hideSaved && (saved[r.place_id] || r.crm_status)) return false;
        if (onlyPhone && !r.phone) return false;
        if (onlyHighPitch && r.pitchability === 'Low') return false;
        if (lowRatingOnly && (r.rating == null || r.rating >= 4.2)) return false;
        return true;
      })
      .sort((a, b) => computeOfferScore(b, offer) - computeOfferScore(a, offer));
  }, [data, presenceFilter, hideSaved, onlyPhone, onlyHighPitch, lowRatingOnly, saved, offer]);

  const hasAnyRatings = useMemo(() => rows.some((r) => r.rating != null), [rows]);

  const runSearch = async (cat: string, cty: string, prov: string) => {
    setBusy(true); setError(''); setData(null); setPage(0); setPicked(new Set()); setWatchNotice(''); setBulkStatus('');
    try { setData(await send<Hunt>('/api/hunt/local', 'POST', { category: cat, city: cty, limit: 40, provider: prov || null })); }
    catch (err) { setError(err instanceof Error ? err.message : 'Search failed'); }
    finally { setBusy(false); }
  };
  const search = (e: FormEvent) => { e.preventDefault(); runSearch(category, city, provider); };

  const seen = useRef(0);
  useEffect(() => {
    if (!preset || preset.nonce === seen.current) return;
    seen.current = preset.nonce;
    const t = window.setTimeout(() => {
      setCategory(preset.category);
      setCity(preset.city);
      if (preset.only_gaps) setPresenceFilter('no_site');
      if (preset.category && preset.city) runSearch(preset.category, preset.city, '');
    }, 0);
    return () => window.clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset]);

  const payload = (r: LocalResult) => ({
    name: r.name, city, domain: r.domain, phone: r.phone, address: r.address, rating: r.rating ?? 0, reviews: r.reviews,
    classification: r.classification, place_id: r.place_id, category, provider: r.provider, pitch_strategy: r.pitch_strategy,
  });

  const save = async (list: LocalResult[]) => {
    setError('');
    setSavedNotice(null);
    try {
      const out = await send<{ leads: Array<{ id: number }> }>('/api/hunt/local/batch_save', 'POST', list.map(payload));
      setSaved((s) => ({ ...s, ...Object.fromEntries(list.map((r, i) => [r.place_id, out.leads[i].id])) }));
      setPicked(new Set());
      setSavedNotice({ count: out.leads.length, lastId: out.leads[0]?.id ?? null });
    } catch (err) { setError(err instanceof Error ? err.message : 'Save failed'); }
  };

  const watchTerritory = async () => {
    if (!category.trim() || !city.trim()) return;
    setWatchNotice('');
    try {
      await send('/api/leadfinder/searches', 'POST', {
        name: `${category.trim()} in ${city.trim()}`,
        source: 'places',
        params: { query: category.trim(), city: city.trim() },
        notify: true,
        every_hours: 168,
      });
      setWatchNotice(`Territory "${category.trim()} in ${city.trim()}" added to Watching (weekly scan).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not watch territory');
    }
  };

  const bulkAudit = async () => {
    const targets = rows.filter((r) => picked.has(r.place_id) && r.website);
    if (targets.length === 0) {
      setBulkStatus('None of the selected businesses have a website to audit.');
      return;
    }
    setBulkStatus(`Auditing ${targets.length} website(s)…`);
    let okCount = 0;
    for (const t of targets) {
      try {
        const res = await apiFetch('/api/v1/browser/scrape', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target: t.website, mode: 'local_audit', context_title: t.name }),
        });
        if (res.ok) okCount += 1;
      } catch { /* continue batch */ }
    }
    setBulkStatus(`Audited and saved ${okCount}/${targets.length} site(s). Click any business to inspect its matrix.`);
  };

  const exportCsv = () => {
    const selectedRows = picked.size > 0 ? rows.filter((r) => picked.has(r.place_id)) : rows;
    const q = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const csv = [
      ['name', 'score', 'status', 'pitchability', 'budget', 'website', 'phone', 'address', 'rating', 'reviews'],
      ...selectedRows.map((r) => [r.name, computeOfferScore(r, offer), r.classification, r.pitchability, r.budget_tier, r.website, r.phone, r.address, r.rating, r.reviews]),
    ].map((row) => row.map(q).join(',')).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = `local-leads-${city || 'export'}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const toggle = (id: string) => setPicked((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const slice = rows.slice(page * PAGE, (page + 1) * PAGE);
  const points = useMemo(
    () => rows.filter((r) => r.lat != null && r.lon != null && !r.coords_approx).map((r) => ({ id: r.place_id, name: r.name, lat: r.lat as number, lon: r.lon as number, score: computeOfferScore(r, offer), label: (STATUS[r.classification] ?? STATUS.has_site).text })),
    [rows, offer],
  );
  const pick = useMemo(() => (id: string) => setOpen(rows.find((r) => r.place_id === id) ?? null), [rows]);

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={search} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6 items-end">
          <label className="text-xs text-slate-400 space-y-1">Business type
            <SuggestInput kinds={['business']} required minLength={2} placeholder="dentist, restaurant, plumber" value={category} onChange={setCategory} /></label>
          <label className="text-xs text-slate-400 space-y-1">City / Postal
            <SuggestInput kinds={['city']} required minLength={2} placeholder="Leeds, UK" value={city} onChange={setCity} /></label>
          <label className="text-xs text-slate-400 space-y-1">Agency Offer
            <Select
              aria-label="Agency Offer"
              value={offer}
              onChange={(v) => setOffer(v as AgencyOffer)}
              options={[
                { value: 'web_design', label: 'Web Design & Redesign' },
                { value: 'local_seo', label: 'Local SEO & Maps' },
                { value: 'ads', label: 'Google / Meta Ads' },
                { value: 'ai_receptionist', label: 'AI Voice / Chat Receptionist' },
                { value: 'reputation', label: 'Reputation Management' },
              ]}
            /></label>
          <label className="text-xs text-slate-400 space-y-1">Data Source
            <Select
              aria-label="Data Source"
              value={provider}
              onChange={setProvider}
              options={
                google
                  ? [
                      { value: '', label: 'Google Maps (default)' },
                      { value: 'google', label: 'Google Maps' },
                      { value: 'osm', label: 'OpenStreetMap (free)' },
                    ]
                  : [{ value: '', label: 'OpenStreetMap (free)' }]
              }
            /></label>
          <Button variant="primary" disabled={busy}><Search className="h-4 w-4" />{busy ? 'Searching…' : 'Search'}</Button>
          <Button type="button" disabled={!category.trim() || !city.trim()} onClick={watchTerritory}>
            <Bell className="h-3.5 w-3.5" /> Watch territory
          </Button>
        </form>

        <div className="flex flex-wrap items-center justify-between gap-2 mt-3">
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-400">
            <span className="text-[11px] text-slate-500">Quick-start:</span>
            {[
              { cat: 'dentist', loc: 'Leeds, UK' },
              { cat: 'plumber', loc: 'Austin, TX' },
              { cat: 'medspa', loc: 'Miami, FL' },
            ].map((ex) => (
              <button
                key={`${ex.cat}-${ex.loc}`}
                type="button"
                onClick={() => {
                  setCategory(ex.cat);
                  setCity(ex.loc);
                  runSearch(ex.cat, ex.loc, provider);
                }}
                className="px-2.5 py-0.5 rounded-full text-[11px] bg-slate-800/80 hover:bg-slate-700 text-indigo-300 hover:text-white border border-slate-700/60 transition"
              >
                {ex.cat} · {ex.loc}
              </button>
            ))}
          </div>
          <Button small onClick={() => setShowFilters((v) => !v)}>
            <Filter className="h-3.5 w-3.5" /> Money Filters
          </Button>
        </div>

        {showFilters && (
          <div className="mt-3 pt-3 border-t border-slate-800 grid gap-3 sm:grid-cols-2 lg:grid-cols-5 items-center text-xs">
            <label className="text-slate-400 space-y-1">Web presence
              <Select
                small
                aria-label="Filter web presence"
                value={presenceFilter}
                onChange={(v) => { setPresenceFilter(v as typeof presenceFilter); setPage(0); }}
                options={[
                  { value: 'all', label: 'All businesses' },
                  { value: 'no_site', label: 'No website / Social only' },
                  { value: 'broken', label: 'SSL / Dead / Parked domain' },
                  { value: 'has_site', label: 'Has working site' },
                ]}
              /></label>
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer"><input type="checkbox" checked={hideSaved} onChange={(e) => { setHideSaved(e.target.checked); setPage(0); }} />Hide already in CRM</label>
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer"><input type="checkbox" checked={onlyHighPitch} onChange={(e) => { setOnlyHighPitch(e.target.checked); setPage(0); }} />High Pitchability (SMB only)</label>
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer"><input type="checkbox" checked={onlyPhone} onChange={(e) => { setOnlyPhone(e.target.checked); setPage(0); }} />Has phone number</label>
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer"><input type="checkbox" checked={lowRatingOnly} onChange={(e) => { setLowRatingOnly(e.target.checked); setPage(0); }} />Rating under 4.2★</label>
          </div>
        )}

        {!google && providers.data && (
          <p className="mt-3 flex items-center gap-2 text-xs text-slate-400">
            <ShieldAlert className="h-4 w-4 text-amber-400 shrink-0" />
            Using Community Map Data (OpenStreetMap). Connect Google Maps in Integrations for verified ratings, review counts, and website checks.
            {onAddGoogleKey && <button type="button" onClick={onAddGoogleKey} className="text-indigo-300 hover:underline font-medium ml-1">Connect Data Source</button>}
          </p>
        )}
      </Card>

      {watchNotice && <div role="status" className="p-3 rounded-xl bg-indigo-500/15 border border-indigo-500/40 text-xs text-slate-100">{watchNotice}</div>}
      {bulkStatus && <div role="status" className="p-3 rounded-xl bg-cyan-500/15 border border-cyan-500/40 text-xs text-slate-100">{bulkStatus}</div>}
      {savedNotice && (
        <div role="status" className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-xs text-slate-100 flex items-center justify-between gap-2">
          <span>Saved {savedNotice.count} business{savedNotice.count === 1 ? '' : 'es'} to Clients without clearing your search results.</span>
          {savedNotice.lastId && (
            <button type="button" onClick={() => onSaved(savedNotice.lastId!)} className="text-indigo-300 hover:underline font-medium shrink-0">
              View in Clients →
            </button>
          )}
        </div>
      )}
      <ErrorBanner message={error || providers.error} />
      {busy && <Skeletons rows={5} />}

      {data && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="text-xs text-slate-400 tabular">{rows.length} businesses via {data.provider === 'google' ? 'Google Maps' : 'OpenStreetMap'}, ranked for {offer.replace('_', ' ')}</div>
            <div className="flex flex-wrap gap-2">
              <Button small variant={view === 'list' ? 'primary' : 'secondary'} onClick={() => setView('list')}>List</Button>
              <Button small variant={view === 'map' ? 'primary' : 'secondary'} onClick={() => setView('map')}>Map ({points.length})</Button>
              <Button small disabled={picked.size === 0} onClick={bulkAudit}><Cpu className="h-3.5 w-3.5" />Bulk Audit</Button>
              <Button small onClick={exportCsv}><Download className="h-3.5 w-3.5" />CSV</Button>
              <Button small variant="primary" disabled={picked.size === 0} onClick={() => save(rows.filter((r) => picked.has(r.place_id)))}>Save {picked.size > 0 ? `${picked.size} ` : ''}selected</Button>
            </div>
          </div>
          {view === 'map' && (points.length ? <div className="mb-3"><ResultsMap points={points} onPick={pick} /><p className="text-[11px] text-slate-500 mt-1">{rows.length - points.length} result(s) have no exact coordinates and are not pinned.</p></div> : <p className="text-xs text-slate-400 mb-3">None of these results has exact coordinates, so there is nothing to pin.</p>)}
          {data.notes.map((n) => <p key={n} className="text-xs text-amber-300 mb-2">{n}</p>)}
          {view === 'list' && (rows.length === 0 ? <EmptyState title="No matches" hint="Try adjusting your Money Filters, another business type, or a larger city." /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-slate-500 border-b border-slate-800">
                  <th className="py-2 pr-2 w-8"><span className="sr-only">Select</span></th>
                  <th className="py-2 pr-3 w-28">Win score</th>
                  <th className="py-2 pr-3">Business</th>
                  <th className="py-2 pr-3">Web presence</th>
                  {hasAnyRatings && <th className="py-2 pr-3 hidden md:table-cell">Reputation</th>}
                  <th className="py-2 text-right">Action</th>
                </tr></thead>
                <tbody>
                  {slice.map((r) => {
                    const st = STATUS[r.classification] ?? STATUS.has_site;
                    const dynScore = computeOfferScore(r, offer);
                    const crm = r.crm_status;
                    return (
                      <tr key={r.place_id} className="border-b border-slate-800/70 hover:bg-slate-900/60">
                        <td className="py-2.5 pr-2"><input type="checkbox" aria-label={`Select ${r.name}`} checked={picked.has(r.place_id)} onChange={() => toggle(r.place_id)} /></td>
                        <td className="py-2.5 pr-3"><div className="font-mono tabular text-white">{dynScore}</div><ScoreBar value={dynScore} /></td>
                        <td className="py-2.5 pr-3">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <button className="text-left text-slate-100 hover:text-white font-medium" onClick={() => setOpen(r)}>{r.name}</button>
                            {crm && <Badge tone="good">In CRM ({crm.deal_stage})</Badge>}
                            {r.pitchability === 'Low' && <Badge tone="warn">{r.entity_type === 'public_sector' ? 'Public Sector' : 'Chain'}</Badge>}
                            {r.budget_tier === 'High' && <Badge tone="info">High Budget</Badge>}
                          </div>
                          <div className="text-xs text-slate-500 truncate max-w-xs">{r.address}</div>
                        </td>
                        <td className="py-2.5 pr-3"><Badge tone={st.tone}>{st.text}</Badge>{r.classification.startsWith('no_website') && !r.verified_absence && <div className="text-[11px] text-amber-300 mt-1">verify first</div>}</td>
                        {hasAnyRatings && (
                          <td className="py-2.5 pr-3 hidden md:table-cell text-xs text-slate-400 tabular">{r.rating != null ? <span className="flex items-center gap-1"><Star className="h-3 w-3 text-amber-400" />{r.rating} ({r.reviews})</span> : '–'}</td>
                        )}
                        <td className="py-2.5 text-right">{saved[r.place_id] || crm ? <Badge tone="good">In CRM</Badge> : <Button small onClick={() => save([r])}>Save</Button>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}
          {view === 'list' && <Pager page={page} pageSize={PAGE} total={rows.length} onPage={setPage} />}
        </Card>
      )}

      <LocalBusinessDrawer
        openItem={open}
        city={city}
        category={category}
        offer={offer}
        savedId={open ? saved[open.place_id] : undefined}
        onClose={() => setOpen(null)}
        onSave={(r) => save([r])}
        onOpenScraper={onOpenScraper}
        onSendEmail={onSendEmail}
      />
    </div>
  );
};
