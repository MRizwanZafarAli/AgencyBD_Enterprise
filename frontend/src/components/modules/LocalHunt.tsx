import { useEffect, useState } from 'react';
import type { FC, FormEvent } from 'react';
import { MapPin, Phone, Star, ExternalLink, Search, BookmarkPlus, Check, ShieldAlert } from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';

interface Result {
  provider: 'google' | 'osm';
  place_id: string;
  name: string;
  website: string | null;
  domain: string | null;
  address: string | null;
  phone: string | null;
  rating: number | null;
  reviews: number;
  maps_url: string | null;
  classification: string;
  verified_absence: boolean;
  issues: string[];
  reasons: string[];
  score: number;
}
interface HuntResponse { provider: string; count: number; results: Result[]; notes: string[] }

const LABELS: Record<string, { text: string; tone: string }> = {
  no_website_listed: { text: 'No website', tone: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  no_website_in_osm: { text: 'No website recorded', tone: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  social_only: { text: 'Social page only', tone: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  domain_unreachable: { text: 'Domain dead', tone: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  tls_broken: { text: 'Certificate error', tone: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  domain_parked: { text: 'Parked domain', tone: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  has_site: { text: 'Has a website', tone: 'bg-slate-700/40 text-slate-300 border-slate-600/50' },
};

const scoreTone = (s: number) => (s >= 65 ? 'bg-emerald-500' : s >= 40 ? 'bg-indigo-500' : 'bg-slate-600');

export const LocalHunt: FC = () => {
  const [category, setCategory] = useState('');
  const [city, setCity] = useState('');
  const [provider, setProvider] = useState<'' | 'google' | 'osm'>('');
  const [limit, setLimit] = useState(20);
  const [google, setGoogle] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<HuntResponse | null>(null);
  const [saved, setSaved] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let active = true;
    apiFetch('/api/hunt/local/providers').then(async (r) => {
      if (active && r.ok) setGoogle((await r.json()).google);
    });
    return () => {
      active = false;
    };
  }, []);

  const search = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    setData(null);
    try {
      const res = await apiFetch('/api/hunt/local', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category, city, limit, provider: provider || null }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      setData(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const save = async (r: Result) => {
    setError('');
    const res = await apiFetch('/api/hunt/local/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: r.name, city, domain: r.domain, phone: r.phone, address: r.address, rating: r.rating ?? 0,
        reviews: r.reviews, classification: r.classification, place_id: r.place_id, category,
      }),
    });
    if (res.ok) setSaved((s) => ({ ...s, [r.place_id]: true }));
    else setError(apiErrorMessage(res.status, await res.json().catch(() => ({}))));
  };

  const field = 'w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500';

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-white tracking-tight">Local Client Hunt</h1>
        <p className="text-sm text-slate-400 mt-1">
          Find businesses in a city, see who has no website or a broken one, and rank them by how winnable they are.
        </p>
      </div>

      <form onSubmit={search} className="glass-panel rounded-2xl p-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5 items-end">
        <label className="space-y-1 text-xs text-slate-400 lg:col-span-1">
          Business type
          <input className={field} required minLength={2} placeholder="dentist, plumber, restaurant" value={category} onChange={(e) => setCategory(e.target.value)} />
        </label>
        <label className="space-y-1 text-xs text-slate-400">
          City
          <input className={field} required minLength={2} placeholder="Austin, TX" value={city} onChange={(e) => setCity(e.target.value)} />
        </label>
        <label className="space-y-1 text-xs text-slate-400">
          Source
          <select className={field} value={provider} onChange={(e) => setProvider(e.target.value as '' | 'google' | 'osm')}>
            <option value="">{google ? 'Google (default)' : 'OpenStreetMap (free)'}</option>
            {google && <option value="google">Google Maps</option>}
            <option value="osm">OpenStreetMap (free)</option>
          </select>
        </label>
        <label className="space-y-1 text-xs text-slate-400">
          Results
          <select className={field} value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            {[10, 20, 40].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <button disabled={loading} className="flex items-center justify-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2">
          <Search className="h-4 w-4" /> {loading ? 'Searching…' : 'Hunt'}
        </button>
      </form>

      {!google && (
        <div className="flex items-start gap-2 text-xs text-slate-400 bg-slate-900/60 border border-slate-800 rounded-xl p-3">
          <ShieldAlert className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
          <span>Google results (ratings, review counts, verified "no website") need <code className="font-mono text-slate-300">GOOGLE_PLACES_API_KEY</code> in .env. Until then you are searching OpenStreetMap, which is free but incomplete.</span>
        </div>
      )}

      <ErrorBanner message={error} />

      {loading && (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-24" />)}
        </div>
      )}

      {data && (
        <div className="space-y-3">
          <div className="text-xs text-slate-400 tabular">
            {data.count} businesses via {data.provider === 'google' ? 'Google Maps' : 'OpenStreetMap'}, best opportunities first
          </div>
          {data.notes.map((n) => <div key={n} className="text-xs text-amber-300 bg-amber-950/30 border border-amber-500/30 rounded-lg p-2.5">{n}</div>)}
          <div className="stagger space-y-3">
            {data.results.map((r) => {
              const label = LABELS[r.classification] ?? LABELS.has_site;
              return (
                <article key={r.place_id} className="glass-panel-interactive rounded-2xl p-4 flex flex-col lg:flex-row gap-4">
                  <div className="lg:w-24 shrink-0">
                    <div className="text-2xl font-semibold text-white tabular font-mono">{Math.round(r.score)}</div>
                    <div className="h-1.5 rounded-full bg-slate-800 mt-1 overflow-hidden">
                      <div className={`h-full rounded-full bar-grow ${scoreTone(r.score)}`} style={{ width: `${r.score}%` }} />
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-1">win score</div>
                  </div>
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-medium text-white truncate">{r.name}</h3>
                      <span className={`px-2 py-0.5 rounded-md text-[11px] border ${label.tone}`}>{label.text}</span>
                      {r.classification.startsWith('no_website') && !r.verified_absence && (
                        <span className="text-[11px] text-amber-300">verify before pitching</span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                      {r.address && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{r.address}</span>}
                      {r.phone && <span className="flex items-center gap-1 font-mono"><Phone className="h-3 w-3" />{r.phone}</span>}
                      {r.rating != null && <span className="flex items-center gap-1"><Star className="h-3 w-3 text-amber-400" />{r.rating} ({r.reviews})</span>}
                      {r.website && <a href={r.website} target="_blank" rel="noreferrer noopener" className="flex items-center gap-1 text-indigo-300 hover:text-indigo-200 truncate"><ExternalLink className="h-3 w-3" />{r.domain ?? r.website}</a>}
                    </div>
                    <ul className="flex flex-wrap gap-1.5">
                      {r.reasons.map((x) => (
                        <li key={x} className="text-[11px] text-slate-300 bg-slate-800/70 rounded-md px-2 py-0.5">{x}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="flex lg:flex-col gap-2 shrink-0">
                    <button
                      onClick={() => save(r)}
                      disabled={saved[r.place_id]}
                      className="flex items-center justify-center gap-1.5 rounded-lg border border-slate-700 hover:border-indigo-500 disabled:opacity-60 text-xs text-slate-200 px-3 py-2"
                    >
                      {saved[r.place_id] ? <><Check className="h-3.5 w-3.5 text-emerald-400" />Saved</> : <><BookmarkPlus className="h-3.5 w-3.5" />Save lead</>}
                    </button>
                    {r.maps_url && (
                      <a href={r.maps_url} target="_blank" rel="noreferrer noopener" className="flex items-center justify-center gap-1.5 rounded-lg border border-slate-700 hover:border-slate-500 text-xs text-slate-300 px-3 py-2">
                        <MapPin className="h-3.5 w-3.5" />Map
                      </a>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
