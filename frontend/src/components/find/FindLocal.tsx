import { useEffect, useMemo, useRef, useState } from 'react';
import type { FC, FormEvent } from 'react';
import { MapPin, Phone, Star, ExternalLink, Search, ShieldAlert, Copy, Mail } from 'lucide-react';
import { Badge, Button, Card, Drawer, EmptyState, Pager, ScoreBar, Skeletons, SuggestInput, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';
import { normalizeUrl } from '../../lib/urls';
import { ResultsMap } from './ResultsMap';

interface Pitch { angle: string | null; value_estimate: string | null; deliverables: string[]; cold_pitch_hook: string | null; actionable_teardown: string[] }
interface Result {
  provider: 'google' | 'osm'; place_id: string; name: string; website: string | null; domain: string | null; address: string | null; phone: string | null;
  rating: number | null; reviews: number; maps_url: string | null; classification: string; verified_absence: boolean; issues: string[]; reasons: string[];
  score: number; pitch_strategy: Pitch | null; check_note?: string; lat?: number | null; lon?: number | null; coords_approx?: boolean;
}
interface Hunt { provider: string; count: number; results: Result[]; notes: string[] }

const STATUS: Record<string, { text: string; tone: 'bad' | 'warn' | 'neutral' }> = {
  no_website_listed: { text: 'No website', tone: 'bad' }, no_website_in_osm: { text: 'No website recorded', tone: 'warn' }, social_only: { text: 'Social page only', tone: 'warn' },
  domain_unreachable: { text: 'Domain dead', tone: 'bad' }, tls_broken: { text: 'Certificate error', tone: 'bad' }, domain_parked: { text: 'Parked domain', tone: 'bad' },
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
}> = ({ onSaved, preset, onAddGoogleKey, onSendEmail }) => {
  const providers = useApi<{ google: boolean }>('/api/hunt/local/providers');
  const google = providers.data?.google ?? false;
  const [category, setCategory] = useState('');
  const [city, setCity] = useState('');
  const [provider, setProvider] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<Hunt | null>(null);
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<Result | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [saved, setSaved] = useState<Record<string, number>>({});
  const [onlyGaps, setOnlyGaps] = useState(false);
  const [view, setView] = useState<'list' | 'map'>('list');

  const rows = useMemo(() => (data?.results ?? []).filter((r) => !onlyGaps || r.classification !== 'has_site'), [data, onlyGaps]);

  const runSearch = async (cat: string, cty: string, prov: string) => {
    setBusy(true); setError(''); setData(null); setPage(0); setPicked(new Set());
    try { setData(await send<Hunt>('/api/hunt/local', 'POST', { category: cat, city: cty, limit: 40, provider: prov || null })); }
    catch (err) { setError(err instanceof Error ? err.message : 'Search failed'); }
    finally { setBusy(false); }
  };
  const search = (e: FormEvent) => { e.preventDefault(); runSearch(category, city, provider); };

  // a smart-search request fills the form and runs it
  const seen = useRef(0);
  useEffect(() => {
    if (!preset || preset.nonce === seen.current) return;
    seen.current = preset.nonce;
    const t = window.setTimeout(() => { setCategory(preset.category); setCity(preset.city); setOnlyGaps(preset.only_gaps); if (preset.category && preset.city) runSearch(preset.category, preset.city, ''); }, 0);
    return () => window.clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset]);

  const payload = (r: Result) => ({ name: r.name, city, domain: r.domain, phone: r.phone, address: r.address, rating: r.rating ?? 0, reviews: r.reviews,
    classification: r.classification, place_id: r.place_id, category, provider: r.provider, pitch_strategy: r.pitch_strategy });

  const save = async (list: Result[]) => {
    setError('');
    try {
      const out = await send<{ leads: Array<{ id: number }> }>('/api/hunt/local/batch_save', 'POST', list.map(payload));
      setSaved((s) => ({ ...s, ...Object.fromEntries(list.map((r, i) => [r.place_id, out.leads[i].id])) }));
      setPicked(new Set());
      if (list.length === 1) onSaved(out.leads[0].id);
    } catch (err) { setError(err instanceof Error ? err.message : 'Save failed'); }
  };

  const toggle = (id: string) => setPicked((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const slice = rows.slice(page * PAGE, (page + 1) * PAGE);
  const points = useMemo(() => rows.filter((r) => r.lat != null && r.lon != null && !r.coords_approx).map((r) => ({ id: r.place_id, name: r.name, lat: r.lat as number, lon: r.lon as number, score: r.score, label: (STATUS[r.classification] ?? STATUS.has_site).text })), [rows]);
  const pick = useMemo(() => (id: string) => setOpen(rows.find((r) => r.place_id === id) ?? null), [rows]);

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={search} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 items-end">
          <label className="text-xs text-slate-400 space-y-1">Business type
            <SuggestInput kinds={['business']} required minLength={2} placeholder="dentist, restaurant, plumber" value={category} onChange={setCategory} /></label>
          <label className="text-xs text-slate-400 space-y-1">City
            <SuggestInput kinds={['city']} required minLength={2} placeholder="Leeds, UK" value={city} onChange={setCity} /></label>
          <label className="text-xs text-slate-400 space-y-1">Source
            <select className={field} value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="">{google ? 'Google Maps (default)' : 'OpenStreetMap (free)'}</option>{google && <option value="google">Google Maps</option>}<option value="osm">OpenStreetMap (free)</option>
            </select></label>
          <label className="flex items-center gap-2 text-xs text-slate-300 pb-2"><input type="checkbox" checked={onlyGaps} onChange={(e) => { setOnlyGaps(e.target.checked); setPage(0); }} />Hide businesses with a working site</label>
          <Button variant="primary" disabled={busy}><Search className="h-4 w-4" />{busy ? 'Searching…' : 'Search'}</Button>
        </form>
        {!google && providers.data && (
          <p className="mt-3 flex gap-2 text-xs text-slate-400"><ShieldAlert className="h-4 w-4 text-amber-400 shrink-0" />
            Google ratings, review counts and a verified &quot;no website&quot; need GOOGLE_PLACES_API_KEY in .env. Until then OpenStreetMap is used: free, but incomplete. {onAddGoogleKey && <button type="button" onClick={onAddGoogleKey} className="text-indigo-300 hover:text-indigo-200 underline ml-1">Add a Google key</button>}</p>
        )}
      </Card>
      <ErrorBanner message={error || providers.error} />
      {busy && <Skeletons rows={5} />}

      {data && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="text-xs text-slate-400 tabular">{rows.length} businesses via {data.provider === 'google' ? 'Google Maps' : 'OpenStreetMap'}, best opportunities first</div>
            <div className="flex gap-2">
              <Button small variant={view === 'list' ? 'primary' : 'secondary'} onClick={() => setView('list')}>List</Button>
              <Button small variant={view === 'map' ? 'primary' : 'secondary'} onClick={() => setView('map')}>Map ({points.length})</Button>
            <Button small variant="primary" disabled={picked.size === 0} onClick={() => save(rows.filter((r) => picked.has(r.place_id)))}>Save {picked.size || ''} selected</Button>
            </div>
          </div>
          {view === 'map' && (points.length ? <div className="mb-3"><ResultsMap points={points} onPick={pick} /><p className="text-[11px] text-slate-500 mt-1">{rows.length - points.length} result(s) have no exact coordinates and are not pinned.</p></div> : <p className="text-xs text-slate-400 mb-3">None of these results has exact coordinates, so there is nothing to pin.</p>)}
          {data.notes.map((n) => <p key={n} className="text-xs text-amber-300 mb-2">{n}</p>)}
          {view === 'list' && (rows.length === 0 ? <EmptyState title="No matches" hint="Try another business type, a larger city, or switch the source." /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-slate-500 border-b border-slate-800">
                  <th className="py-2 pr-2 w-8"><span className="sr-only">Select</span></th><th className="py-2 pr-3 w-28">Win score</th><th className="py-2 pr-3">Business</th><th className="py-2 pr-3">Web presence</th><th className="py-2 pr-3 hidden md:table-cell">Reputation</th><th className="py-2 text-right">Action</th>
                </tr></thead>
                <tbody>
                  {slice.map((r) => {
                    const st = STATUS[r.classification] ?? STATUS.has_site;
                    return (
                      <tr key={r.place_id} className="border-b border-slate-800/70 hover:bg-slate-900/60">
                        <td className="py-2.5 pr-2"><input type="checkbox" aria-label={`Select ${r.name}`} checked={picked.has(r.place_id)} onChange={() => toggle(r.place_id)} /></td>
                        <td className="py-2.5 pr-3"><div className="font-mono tabular text-white">{Math.round(r.score)}</div><ScoreBar value={r.score} /></td>
                        <td className="py-2.5 pr-3"><button className="text-left text-slate-100 hover:text-white font-medium" onClick={() => setOpen(r)}>{r.name}</button>
                          <div className="text-xs text-slate-500 truncate max-w-xs">{r.address}</div></td>
                        <td className="py-2.5 pr-3"><Badge tone={st.tone}>{st.text}</Badge>{r.classification.startsWith('no_website') && !r.verified_absence && <div className="text-[11px] text-amber-300 mt-1">verify first</div>}</td>
                        <td className="py-2.5 pr-3 hidden md:table-cell text-xs text-slate-400 tabular">{r.rating != null ? <span className="flex items-center gap-1"><Star className="h-3 w-3 text-amber-400" />{r.rating} ({r.reviews})</span> : '–'}</td>
                        <td className="py-2.5 text-right">{saved[r.place_id] ? <Badge tone="good">Saved</Badge> : <Button small onClick={() => save([r])}>Save</Button>}</td>
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

      <Drawer open={open !== null} title={open?.name ?? ''} onClose={() => setOpen(null)}>
        {open && (
          <div className="space-y-5 text-sm">
            <div className="flex flex-wrap gap-2"><Badge tone={(STATUS[open.classification] ?? STATUS.has_site).tone}>{(STATUS[open.classification] ?? STATUS.has_site).text}</Badge><Badge tone="accent">Win score {Math.round(open.score)}</Badge></div>
            <div className="space-y-1.5 text-xs text-slate-300">
              {open.address && <div className="flex gap-2"><MapPin className="h-3.5 w-3.5 mt-0.5 text-slate-500" />{open.address}</div>}
              {open.phone && <div className="flex gap-2 font-mono"><Phone className="h-3.5 w-3.5 mt-0.5 text-slate-500" />{open.phone}</div>}
              {open.website && <a className="flex gap-2 text-indigo-300 hover:text-indigo-200" href={normalizeUrl(open.website)} target="_blank" rel="noreferrer noopener"><ExternalLink className="h-3.5 w-3.5 mt-0.5" />{open.domain ?? open.website}</a>}
              {open.maps_url && <a className="flex gap-2 text-indigo-300 hover:text-indigo-200" href={open.maps_url} target="_blank" rel="noreferrer noopener"><MapPin className="h-3.5 w-3.5 mt-0.5" />Open on the map</a>}
            </div>
            <div><h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Why this score</h3>
              <ul className="space-y-1 text-xs text-slate-300 list-disc pl-4">{open.reasons.map((x) => <li key={x}>{x}</li>)}</ul></div>
            {open.check_note && <p className="text-xs text-amber-300">{open.check_note}</p>}
            {open.pitch_strategy?.cold_pitch_hook ? (
              <div><h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Suggested opener (facts only)</h3>
                <p className="text-xs text-slate-200 bg-slate-900 border border-slate-800 rounded-lg p-3 leading-relaxed">{open.pitch_strategy.cold_pitch_hook}</p>
                <Button small className="mt-2" onClick={() => navigator.clipboard?.writeText(open.pitch_strategy?.cold_pitch_hook ?? '')}><Copy className="h-3.5 w-3.5" />Copy</Button>
                {open.pitch_strategy.value_estimate && <p className="text-xs text-slate-400 mt-2">Your price band for this service: {open.pitch_strategy.value_estimate}</p>}</div>
            ) : <p className="text-xs text-slate-400">Nothing specific and true to say yet. Audit the site from the client page first.</p>}
            <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
              <Button variant="primary" disabled={!!saved[open.place_id]} onClick={() => save([open])}>
                {saved[open.place_id] ? 'Saved to Clients' : 'Save to Clients'}
              </Button>
              {onSendEmail && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    const recipientEmail = open.domain ? `contact@${open.domain}` : '';
                    const hook = open.pitch_strategy?.cold_pitch_hook;
                    const defaultBody = hook
                      ? `Hi,\n\n${hook}\n\nWe prepared a technical teardown and performance review for ${open.name}.\n\nWould you be open to a 5-minute walkthrough this week?\n\nBest regards,\nGrowth Team`
                      : `Hi,\n\nI was reviewing ${open.name} and wanted to share a few observations regarding your digital presence and customer booking flow.\n\nWould you be open to a brief chat this week?\n\nBest regards,\nGrowth Team`;

                    onSendEmail({
                      recipient: recipientEmail,
                      companyName: open.name,
                      subject: `Website & performance audit for ${open.name}`,
                      body: defaultBody,
                      leadId: saved[open.place_id],
                    });
                    setOpen(null);
                  }}
                >
                  <Mail className="h-4 w-4 text-indigo-400" />
                  Pitch via Email Hub →
                </Button>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
};
