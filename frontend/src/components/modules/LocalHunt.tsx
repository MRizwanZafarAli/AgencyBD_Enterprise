import { useEffect, useRef, useState } from 'react';
import type { FC, FormEvent } from 'react';
import {
  MapPin, Phone, Star, ExternalLink, Search, BookmarkPlus, Check, Sparkles,
  Globe, Compass, Copy, SlidersHorizontal, Zap, Building2,
  ShieldCheck, X, Layers, AlertTriangle, Download, Send, CheckCircle2
} from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useTheme } from '../../lib/useTheme';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface PitchStrategy {
  angle: string;
  value_estimate: string;
  deliverables: string[];
  cold_pitch_hook: string;
  actionable_teardown: string[];
}

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
  lat?: number | null;
  lon?: number | null;
  pitch_strategy?: PitchStrategy;
}

interface CityCoords {
  lat: number;
  lon: number;
  bbox?: number[];
  display_name?: string;
}

interface HuntResponse {
  provider: string;
  category: string;
  city: string;
  city_coords?: CityCoords | null;
  count: number;
  results: Result[];
  notes: string[];
}

const LABELS: Record<string, { text: string; tone: string }> = {
  no_website_listed: { text: 'No website listed', tone: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  no_website_in_osm: { text: 'No website recorded', tone: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  social_only: { text: 'Social page only', tone: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  domain_unreachable: { text: 'Domain dead', tone: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  tls_broken: { text: 'Security/SSL error', tone: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  domain_parked: { text: 'Parked domain', tone: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
  has_site: { text: 'Has website', tone: 'bg-slate-700/40 text-slate-300 border-slate-600/50' },
};

const scoreBadgeTone = (s: number) => (s >= 65 ? 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10' : s >= 40 ? 'text-indigo-400 border-indigo-500/40 bg-indigo-500/10' : 'text-slate-400 border-slate-600/40 bg-slate-800/40');

const GLOBAL_CITIES = [
  { name: 'Austin, TX', flag: '🇺🇸' },
  { name: 'London, UK', flag: '🇬🇧' },
  { name: 'New York, NY', flag: '🇺🇸' },
  { name: 'San Francisco, CA', flag: '🇺🇸' },
  { name: 'Singapore', flag: '🇸🇬' },
  { name: 'Berlin, Germany', flag: '🇩🇪' },
  { name: 'Toronto, Canada', flag: '🇨🇦' },
  { name: 'Dubai, UAE', flag: '🇦🇪' },
  { name: 'Sydney, Australia', flag: '🇦🇺' },
];

const POPULAR_CATEGORIES = [
  'dentist',
  'software agency',
  'medical clinic',
  'law firm',
  'restaurant',
  'real estate',
  'accounting',
  'plumber',
];

export const LocalHunt: FC = () => {
  const { theme } = useTheme();
  const [category, setCategory] = useState('dentist');
  const [city, setCity] = useState('Austin, TX');
  const [provider, setProvider] = useState<'' | 'google' | 'osm'>('');
  const [limit, setLimit] = useState(20);
  const [google, setGoogle] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<HuntResponse | null>(null);
  const [saved, setSaved] = useState<Record<string, boolean>>({});
  const [selectedResult, setSelectedResult] = useState<Result | null>(null);
  const [copiedPitch, setCopiedPitch] = useState(false);
  const [batchSaving, setBatchSaving] = useState(false);
  const [batchMessage, setBatchMessage] = useState('');
  const [viewMode, setViewMode] = useState<'split' | 'map' | 'cards'>('split');
  const [filterType, setFilterType] = useState<string>('all');
  const [minScore, setMinScore] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [scanRadiusKm, setScanRadiusKm] = useState<number>(15);
  const [enrolling, setEnrolling] = useState<Record<string, boolean>>({});
  const [enrolled, setEnrolled] = useState<Record<string, boolean>>({});
  const [enrollMessage, setEnrollMessage] = useState('');

  // Leaflet Map state
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const radiusCircleRef = useRef<L.Circle | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  useEffect(() => {
    let active = true;
    apiFetch('/api/hunt/local/providers').then(async (r) => {
      if (active && r.ok) {
        const prov = await r.json();
        setGoogle(Boolean(prov.google));
      }
    });
    return () => {
      active = false;
    };
  }, []);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [30.2672, -97.7431], // Default Austin
      zoom: 12,
      zoomControl: true,
      attributionControl: false,
    });

    const isInitialLight = typeof document !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'light';
    const tileUrl = isInitialLight
      ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

    const tiles = L.tileLayer(tileUrl, {
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);
    tileLayerRef.current = tiles;

    const markersLayer = L.layerGroup().addTo(map);
    markersLayerRef.current = markersLayer;
    mapInstanceRef.current = map;

    return () => {
      if (radiusCircleRef.current) {
        radiusCircleRef.current.remove();
        radiusCircleRef.current = null;
      }
      map.remove();
      mapInstanceRef.current = null;
      markersLayerRef.current = null;
      tileLayerRef.current = null;
    };
  }, []);

  // Update map tiles dynamically when user switches Theme
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;
    if (tileLayerRef.current) {
      tileLayerRef.current.remove();
    }
    const tileUrl = theme === 'light'
      ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
    const tiles = L.tileLayer(tileUrl, {
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);
    tileLayerRef.current = tiles;
  }, [theme]);

  // Update map pins when data changes or filter changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layer = markersLayerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    if (radiusCircleRef.current) {
      radiusCircleRef.current.remove();
      radiusCircleRef.current = null;
    }

    if (data?.city_coords && data.city_coords.lat != null && data.city_coords.lon != null) {
      const circle = L.circle([data.city_coords.lat, data.city_coords.lon], {
        radius: scanRadiusKm * 1000,
        color: '#6366f1',
        fillColor: '#6366f1',
        fillOpacity: 0.08,
        weight: 1.5,
        dashArray: '6, 8',
      }).addTo(map);
      radiusCircleRef.current = circle;
    }

    if (!data || !data.results || data.results.length === 0) {
      if (data?.city_coords && data.city_coords.lat != null && data.city_coords.lon != null) {
        map.flyTo([data.city_coords.lat, data.city_coords.lon], 12);
      }
      return;
    }

    const filtered = data.results.filter((r) => {
      if (filterType === 'nowebsite' && !r.classification.startsWith('no_website')) return false;
      if (filterType === 'broken' && !['domain_unreachable', 'tls_broken', 'domain_parked'].includes(r.classification)) return false;
      if (filterType === 'social' && r.classification !== 'social_only') return false;
      if (filterType === 'working' && r.classification !== 'has_site') return false;
      if (r.score < minScore) return false;
      if (searchQuery && !r.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });

    const bounds: L.LatLngExpression[] = [];
    const pinBg = theme === 'light' ? '#ffffff' : '#090d16';
    const popupText = theme === 'light' ? '#0f172a' : '#f1f5f9';
    const popupSubtext = theme === 'light' ? '#64748b' : '#94a3b8';

    filtered.forEach((r) => {
      if (r.lat == null || r.lon == null) return;
      const point: [number, number] = [r.lat, r.lon];
      bounds.push(point);

      const isHighWin = r.score >= 65;
      const color = isHighWin ? '#10b981' : r.score >= 40 ? '#6366f1' : '#64748b';
      const label = Math.round(r.score);

      const html = `
        <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; cursor: pointer;">
          ${isHighWin ? `<div style="position: absolute; width: 36px; height: 36px; border-radius: 50%; background-color: ${color}40; animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>` : ''}
          <div style="width: 28px; height: 28px; border-radius: 50%; background-color: ${pinBg}; border: 2px solid ${color}; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 14px rgba(0,0,0,0.35); font-family: monospace; font-size: 11px; font-weight: bold; color: ${color};">
            ${label}
          </div>
        </div>
      `;

      const icon = L.divIcon({
        html,
        className: 'custom-map-pin',
        iconSize: [36, 36],
        iconAnchor: [18, 18],
      });

      const marker = L.marker(point, { icon });
      marker.on('click', () => {
        setSelectedResult(r);
      });

      const popupContent = `
        <div style="font-family: inherit; color: ${popupText}; padding: 6px; min-width: 190px;">
          <div style="font-weight: 700; font-size: 13px; margin-bottom: 2px; color: ${popupText};">${r.name}</div>
          <div style="font-size: 11px; color: ${popupSubtext}; margin-bottom: 6px;">${r.address || 'Local Business'}</div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 6px; font-size: 11px;">
            <span style="color: ${color}; font-weight: bold;">Win Score: ${label}</span>
            <span style="background: ${color}20; border: 1px solid ${color}40; color: ${color}; padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;">${r.classification.replace(/_/g, ' ')}</span>
          </div>
        </div>
      `;
      marker.bindPopup(popupContent);
      layer.addLayer(marker);
    });

    if (bounds.length > 0) {
      map.fitBounds(L.latLngBounds(bounds), { padding: [50, 50], maxZoom: 15 });
    } else if (data.city_coords) {
      map.flyTo([data.city_coords.lat, data.city_coords.lon], 12);
    }
  }, [data, filterType, minScore, searchQuery, scanRadiusKm, theme]);

  const search = async (e?: FormEvent) => {
    if (e) e.preventDefault();
    setError('');
    setLoading(true);
    setData(null);
    setSelectedResult(null);
    setBatchMessage('');
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
        name: r.name,
        city,
        domain: r.domain,
        phone: r.phone,
        address: r.address,
        rating: r.rating ?? 0,
        reviews: r.reviews,
        classification: r.classification,
        place_id: r.place_id,
        category,
        provider: r.provider,
        pitch_strategy: r.pitch_strategy,
      }),
    });
    if (res.ok) setSaved((s) => ({ ...s, [r.place_id]: true }));
    else setError(apiErrorMessage(res.status, await res.json().catch(() => ({}))));
  };

  const batchSaveAll = async () => {
    if (!data || data.results.length === 0) return;
    setBatchSaving(true);
    setBatchMessage('');
    try {
      const payload = data.results.map((r) => ({
        name: r.name,
        city,
        domain: r.domain,
        phone: r.phone,
        address: r.address,
        rating: r.rating ?? 0,
        reviews: r.reviews,
        classification: r.classification,
        place_id: r.place_id,
        category,
        provider: r.provider,
        pitch_strategy: r.pitch_strategy,
      }));
      const res = await apiFetch('/api/hunt/local/batch_save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const resBody = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, resBody));

      const newSaved: Record<string, boolean> = { ...saved };
      data.results.forEach((r) => {
        newSaved[r.place_id] = true;
      });
      setSaved(newSaved);
      setBatchMessage(`Successfully pushed ${resBody.saved_count} leads & pitch strategies into Outreach Pipeline!`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Batch save failed');
    } finally {
      setBatchSaving(false);
    }
  };

  const copyPitch = (hook: string) => {
    navigator.clipboard.writeText(hook);
    setCopiedPitch(true);
    setTimeout(() => setCopiedPitch(false), 2200);
  };

  const filteredResults = (data?.results || []).filter((r) => {
    if (filterType === 'nowebsite' && !r.classification.startsWith('no_website')) return false;
    if (filterType === 'broken' && !['domain_unreachable', 'tls_broken', 'domain_parked'].includes(r.classification)) return false;
    if (filterType === 'social' && r.classification !== 'social_only') return false;
    if (filterType === 'working' && r.classification !== 'has_site') return false;
    if (r.score < minScore) return false;
    if (searchQuery && !r.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const enrollInCadence = async (r: Result) => {
    setError('');
    setEnrolling((prev) => ({ ...prev, [r.place_id]: true }));
    try {
      const saveRes = await apiFetch('/api/hunt/local/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: r.name,
          city,
          domain: r.domain,
          phone: r.phone,
          address: r.address,
          rating: r.rating ?? 0,
          reviews: r.reviews,
          classification: r.classification,
          place_id: r.place_id,
          category,
          provider: r.provider,
          pitch_strategy: r.pitch_strategy,
        }),
      });
      if (!saveRes.ok) {
        throw new Error(apiErrorMessage(saveRes.status, await saveRes.json().catch(() => ({}))));
      }
      const savedLead = await saveRes.json();
      setSaved((s) => ({ ...s, [r.place_id]: true }));

      let dealVal: number | undefined = undefined;
      if (r.pitch_strategy?.value_estimate) {
        const match = r.pitch_strategy.value_estimate.match(/\$?([0-9,]+)/);
        if (match) {
          dealVal = parseFloat(match[1].replace(/,/g, ''));
        }
      }

      const enrollRes = await apiFetch('/api/sequences/enroll_lead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_id: savedLead.id,
          country_code: 'US',
          deal_value: dealVal || 4500,
        }),
      });
      if (!enrollRes.ok) {
        throw new Error(apiErrorMessage(enrollRes.status, await enrollRes.json().catch(() => ({}))));
      }
      const enrollData = await enrollRes.json();
      setEnrolled((e) => ({ ...e, [r.place_id]: true }));
      setEnrollMessage(`Enrolled "${r.name}" into outreach cadence (Enrollment #${enrollData.id})!`);
      setTimeout(() => setEnrollMessage(''), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cadence enrollment failed');
    } finally {
      setEnrolling((prev) => ({ ...prev, [r.place_id]: false }));
    }
  };

  const exportCSV = () => {
    if (!filteredResults.length) return;
    const headers = ['Business Name', 'Category', 'City', 'Win Score', 'Classification', 'Phone', 'Website', 'Address', 'Pitch Angle', 'Estimated Value', 'Cold Outreach Hook'];
    const rows = filteredResults.map((r) => [
      `"${(r.name || '').replace(/"/g, '""')}"`,
      `"${(category || '').replace(/"/g, '""')}"`,
      `"${(city || '').replace(/"/g, '""')}"`,
      r.score != null ? Math.round(r.score) : '',
      `"${(r.classification || '').replace(/"/g, '""')}"`,
      `"${(r.phone || '').replace(/"/g, '""')}"`,
      `"${(r.website || '').replace(/"/g, '""')}"`,
      `"${(r.address || '').replace(/"/g, '""')}"`,
      `"${(r.pitch_strategy?.angle || '').replace(/"/g, '""')}"`,
      `"${(r.pitch_strategy?.value_estimate || '').replace(/"/g, '""')}"`,
      `"${(r.pitch_strategy?.cold_pitch_hook || '').replace(/"/g, '""')}"`,
    ]);
    const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `leads_${category.replace(/\s+/g, '_')}_${city.replace(/[^a-zA-Z0-9]/g, '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const field = 'w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500';

  return (
    <div className="space-y-5">
      {/* Header and Universal Badge */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-white tracking-tight flex items-center gap-2">
              <Compass className="h-5 w-5 text-indigo-400" />
              Universal Global Map Hunt
            </h1>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center gap-1">
              <Globe className="h-3 w-3" /> 100% Free Engine • Zero API Cost
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Scan any city on Earth via OpenStreetMap & Nominatim. Pinpoint businesses lacking modern websites, and instantly generate tailored BD pitch strategies with zero manual typing.
          </p>
        </div>

        {/* View Mode Controls */}
        <div className="flex items-center gap-1 bg-slate-900/80 p-1 border border-slate-800 rounded-xl self-start">
          <button
            onClick={() => setViewMode('split')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${viewMode === 'split' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            <Layers className="h-3.5 w-3.5" /> Split View
          </button>
          <button
            onClick={() => setViewMode('map')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${viewMode === 'map' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            <Compass className="h-3.5 w-3.5" /> Map Only
          </button>
          <button
            onClick={() => setViewMode('cards')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${viewMode === 'cards' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            <Building2 className="h-3.5 w-3.5" /> Cards Only
          </button>
        </div>
      </div>

      {/* Quick Global Markets & Preset Pills */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <span className="text-slate-500">Popular Global Markets:</span>
          {GLOBAL_CITIES.map((c) => (
            <button
              key={c.name}
              onClick={() => {
                setCity(c.name);
              }}
              className={`px-2.5 py-1 rounded-lg border text-xs transition flex items-center gap-1 ${city === c.name ? 'border-indigo-500 bg-indigo-500/15 text-indigo-200' : 'border-slate-800 bg-slate-900/60 text-slate-300 hover:border-slate-700'}`}
            >
              <span>{c.flag}</span>
              <span>{c.name}</span>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <span className="text-slate-500">Target Categories:</span>
          {POPULAR_CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => {
                setCategory(cat);
              }}
              className={`px-2.5 py-1 rounded-lg border text-xs capitalize transition ${category === cat ? 'border-indigo-500 bg-indigo-500/15 text-indigo-200' : 'border-slate-800 bg-slate-900/60 text-slate-300 hover:border-slate-700'}`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Search Form */}
      <form onSubmit={search} className="glass-panel rounded-2xl p-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5 items-end">
        <label className="space-y-1 text-xs text-slate-400 lg:col-span-1">
          Industry / Keyword
          <input className={field} required minLength={2} placeholder="dentist, software agency, clinic" value={category} onChange={(e) => setCategory(e.target.value)} />
        </label>
        <label className="space-y-1 text-xs text-slate-400">
          Global City / Region
          <input className={field} required minLength={2} placeholder="Austin, TX or London, UK" value={city} onChange={(e) => setCity(e.target.value)} />
        </label>
        <label className="space-y-1 text-xs text-slate-400">
          Geo Provider
          <select className={field} value={provider} onChange={(e) => setProvider(e.target.value as '' | 'google' | 'osm')}>
            <option value="">OpenStreetMap (Free • Worldwide)</option>
            {google && <option value="google">Google Places (API Key Configured)</option>}
            <option value="osm">OpenStreetMap Nominatim (Free)</option>
          </select>
        </label>
        <label className="space-y-1 text-xs text-slate-400">
          Volume Limit
          <select className={field} value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            {[10, 20, 30, 40].map((n) => <option key={n} value={n}>{n} Businesses</option>)}
          </select>
        </label>
        <button disabled={loading} className="flex items-center justify-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 shadow-lg shadow-indigo-600/20 transition">
          <Search className="h-4 w-4" /> {loading ? 'Scanning Map…' : 'Hunt Opportunities'}
        </button>
      </form>

      <ErrorBanner message={error} />
      {batchMessage && (
        <div className="flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs text-emerald-300">
          <Check className="h-4 w-4 text-emerald-400 shrink-0" />
          <span>{batchMessage}</span>
        </div>
      )}
      {enrollMessage && (
        <div className="flex items-center gap-2 p-3 bg-purple-500/10 border border-purple-500/30 rounded-xl text-xs text-purple-300">
          <CheckCircle2 className="h-4 w-4 text-purple-400 shrink-0" />
          <span>{enrollMessage}</span>
        </div>
      )}

      {/* Main Content Area */}
      <div className={`grid gap-5 ${viewMode === 'split' ? 'lg:grid-cols-12' : 'grid-cols-1'}`}>
        {/* Interactive Leaflet Map Container */}
        {(viewMode === 'split' || viewMode === 'map') && (
          <div className={`${viewMode === 'split' ? 'lg:col-span-7' : 'w-full'} space-y-3`}>
            <div className="relative rounded-2xl overflow-hidden border border-slate-800 bg-slate-950/70" style={{ height: viewMode === 'map' ? '700px' : '580px' }}>
              <div ref={mapContainerRef} className="w-full h-full" />
              {/* Map floating control badge */}
              <div className="absolute top-3 right-3 z-[1000] flex items-center gap-2 bg-slate-950/85 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-800 text-xs text-slate-300 shadow-xl">
                <Compass className="h-3.5 w-3.5 text-indigo-400" />
                <span>{city}</span>
                <span className="text-slate-500">•</span>
                <span className="font-mono text-emerald-400">{filteredResults.length} pins</span>
                <span className="text-slate-500">•</span>
                <select
                  value={scanRadiusKm}
                  onChange={(e) => setScanRadiusKm(Number(e.target.value))}
                  className="bg-slate-900 border border-slate-700/60 rounded px-1.5 py-0.5 text-[11px] text-indigo-300 focus:outline-none"
                  title="Adjust visual scan radius"
                >
                  <option value={5}>5 km radius</option>
                  <option value={10}>10 km radius</option>
                  <option value={15}>15 km radius</option>
                  <option value={25}>25 km radius</option>
                  <option value={50}>50 km radius</option>
                </select>
              </div>
            </div>
            <div className="flex items-center justify-between text-xs text-slate-400 px-1">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" /> High Urgency (70+ Win)</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-indigo-500" /> Medium (40–69)</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-slate-600" /> Low (&lt;40)</span>
              </div>
              <span>Click any pin to inspect BD pitch strategy</span>
            </div>
          </div>
        )}

        {/* Results & Action Panel */}
        {(viewMode === 'split' || viewMode === 'cards') && (
          <div className={`${viewMode === 'split' ? 'lg:col-span-5' : 'w-full'} space-y-3`}>
            {/* Filter and Batch Action Bar */}
            {data && data.results.length > 0 && (
              <div className="glass-panel rounded-2xl p-3 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-medium text-white flex items-center gap-1.5">
                    <SlidersHorizontal className="h-3.5 w-3.5 text-indigo-400" /> Filter Leads
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={exportCSV}
                      disabled={!filteredResults.length}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-medium border border-slate-700 transition"
                      title="Export all discovered leads and pitch hooks to CSV"
                    >
                      <Download className="h-3 w-3 text-slate-400" />
                      <span>Export CSV</span>
                    </button>
                    <button
                      onClick={batchSaveAll}
                      disabled={batchSaving}
                      className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-medium shadow-md shadow-emerald-600/20 transition"
                    >
                      <Zap className="h-3 w-3" />
                      {batchSaving ? 'Saving…' : '⚡ 1-Click Save All'}
                    </button>
                  </div>
                </div>

                {/* Filter Pills */}
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { id: 'all', label: 'All' },
                    { id: 'nowebsite', label: 'No Website' },
                    { id: 'broken', label: 'Dead/SSL Error' },
                    { id: 'social', label: 'Social Only' },
                    { id: 'working', label: 'Has Site' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setFilterType(tab.id)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${filterType === tab.id ? 'bg-indigo-600 text-white' : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'}`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Search within results & Min Score filter */}
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <input
                    type="text"
                    placeholder="Search name…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                  <select
                    value={minScore}
                    onChange={(e) => setMinScore(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value={0}>Any Score</option>
                    <option value={40}>Score 40+ (Warm)</option>
                    <option value={65}>Score 65+ (Top Opportunity)</option>
                  </select>
                </div>
              </div>
            )}

            {/* Loading Skeleton */}
            {loading && (
              <div className="space-y-3">
                {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-24 rounded-2xl" />)}
              </div>
            )}

            {/* List of Business Cards */}
            {data && (
              <div className="space-y-3 max-h-[580px] overflow-y-auto pr-1">
                <div className="text-xs text-slate-400 tabular flex items-center justify-between">
                  <span>Showing {filteredResults.length} of {data.count} businesses</span>
                  <span className="text-indigo-400">{data.city}</span>
                </div>

                {data.notes.map((n) => (
                  <div key={n} className="text-xs text-amber-300 bg-amber-950/30 border border-amber-500/30 rounded-lg p-2.5">
                    {n}
                  </div>
                ))}

                {filteredResults.map((r) => {
                  const label = LABELS[r.classification] ?? LABELS.has_site;
                  const isSelected = selectedResult?.place_id === r.place_id;
                  return (
                    <article
                      key={r.place_id}
                      onClick={() => {
                        setSelectedResult(r);
                        if (r.lat && r.lon && mapInstanceRef.current) {
                          mapInstanceRef.current.flyTo([r.lat, r.lon], 15, { duration: 1.2 });
                        }
                      }}
                      className={`glass-panel-interactive rounded-2xl p-4 flex flex-col gap-3 cursor-pointer transition ${isSelected ? 'border-indigo-500 bg-indigo-950/20 ring-1 ring-indigo-500/50' : ''}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold text-white truncate text-sm">{r.name}</h3>
                            <span className={`px-2 py-0.5 rounded-md text-[10px] border ${label.tone}`}>{label.text}</span>
                          </div>
                          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-400 mt-1">
                            {r.address && <span className="flex items-center gap-1 truncate max-w-xs"><MapPin className="h-3 w-3 shrink-0" />{r.address}</span>}
                            {r.phone && <span className="flex items-center gap-1 font-mono"><Phone className="h-3 w-3 shrink-0" />{r.phone}</span>}
                            {r.rating != null && (
                              <span className="flex items-center gap-1 text-amber-400 font-mono">
                                <Star className="h-3 w-3 shrink-0 fill-amber-400" />{r.rating} ({r.reviews})
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Win Score Pill */}
                        <div className="shrink-0 text-right">
                          <div className={`px-2.5 py-1 rounded-lg border text-xs font-mono font-bold ${scoreBadgeTone(r.score)}`}>
                            {Math.round(r.score)} Win
                          </div>
                        </div>
                      </div>

                      {/* Autonomous Pitch Angle Banner */}
                      {r.pitch_strategy && (
                        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-2.5 flex items-center justify-between text-xs">
                          <div className="flex items-center gap-1.5 text-indigo-300 font-medium truncate">
                            <Sparkles className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                            <span className="truncate">{r.pitch_strategy.angle}</span>
                          </div>
                          <span className="font-mono text-emerald-400 shrink-0 ml-2">{r.pitch_strategy.value_estimate}</span>
                        </div>
                      )}

                      {/* Card Action Buttons */}
                      <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedResult(r);
                          }}
                          className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                        >
                          <Zap className="h-3.5 w-3.5" /> View Pitch Strategy
                        </button>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              enrollInCadence(r);
                            }}
                            disabled={enrolling[r.place_id] || enrolled[r.place_id]}
                            className={`flex items-center justify-center gap-1 rounded-lg border text-xs px-2.5 py-1 transition ${
                              enrolled[r.place_id]
                                ? 'border-purple-500/40 bg-purple-500/15 text-purple-300'
                                : 'border-indigo-500/40 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300'
                            }`}
                            title="1-Click enroll lead into 3-stage executive outreach sequence"
                          >
                            {enrolled[r.place_id] ? (
                              <><CheckCircle2 className="h-3 w-3 text-purple-400" /> Enrolled</>
                            ) : enrolling[r.place_id] ? (
                              <><Zap className="h-3 w-3 animate-spin text-indigo-400" /> Enrolling…</>
                            ) : (
                              <><Send className="h-3 w-3" /> Enroll</>
                            )}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              save(r);
                            }}
                            disabled={saved[r.place_id]}
                            className="flex items-center justify-center gap-1 rounded-lg border border-slate-700 hover:border-indigo-500 disabled:opacity-60 text-xs text-slate-200 px-2.5 py-1"
                          >
                            {saved[r.place_id] ? (
                              <><Check className="h-3 w-3 text-emerald-400" /> Saved</>
                            ) : (
                              <><BookmarkPlus className="h-3 w-3" /> Save Lead</>
                            )}
                          </button>
                          {r.website && (
                            <a
                              href={r.website}
                              target="_blank"
                              rel="noreferrer noopener"
                              onClick={(e) => e.stopPropagation()}
                              className="p-1 rounded-lg border border-slate-800 hover:border-slate-600 text-slate-400 hover:text-slate-200"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          )}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Slide-over Pitch Strategy & Teardown Modal */}
      {selectedResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="glass-panel w-full max-w-2xl rounded-2xl border border-slate-800 p-6 space-y-5 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-mono border border-indigo-500/40 bg-indigo-500/10 text-indigo-400">
                    AUTONOMOUS BD BLUEPRINT
                  </span>
                  <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono border ${LABELS[selectedResult.classification]?.tone || ''}`}>
                    {selectedResult.classification.replace(/_/g, ' ')}
                  </span>
                </div>
                <h2 className="text-xl font-bold text-white mt-1">{selectedResult.name}</h2>
                <div className="text-xs text-slate-400 flex items-center gap-3 mt-1">
                  <span>{selectedResult.address || city}</span>
                  {selectedResult.phone && <span className="font-mono">{selectedResult.phone}</span>}
                </div>
              </div>
              <button
                onClick={() => setSelectedResult(null)}
                className="p-1.5 rounded-lg border border-slate-800 text-slate-400 hover:text-white hover:border-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Pitch Strategy Section */}
            {selectedResult.pitch_strategy ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-indigo-950/30 border border-indigo-500/30">
                  <div>
                    <div className="text-[11px] uppercase tracking-wider text-indigo-400 font-mono">Proposed Strategic Angle</div>
                    <div className="text-sm font-semibold text-white mt-0.5">{selectedResult.pitch_strategy.angle}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[11px] uppercase tracking-wider text-slate-400 font-mono">Estimated Deal Value</div>
                    <div className="text-base font-bold font-mono text-emerald-400 mt-0.5">{selectedResult.pitch_strategy.value_estimate}</div>
                  </div>
                </div>

                {/* Teardown Bullet Points */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-400" /> Technical Teardown Observations
                  </div>
                  <div className="space-y-1.5">
                    {selectedResult.pitch_strategy.actionable_teardown.map((pt, i) => (
                      <div key={i} className="text-xs text-slate-300 bg-slate-900/70 border border-slate-800/80 rounded-lg p-2.5 flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0 mt-1.5" />
                        <span>{pt}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Proposed Deliverables */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-indigo-400" /> Concrete Proposed Deliverables
                  </div>
                  <div className="grid sm:grid-cols-2 gap-2">
                    {selectedResult.pitch_strategy.deliverables.map((del, i) => (
                      <div key={i} className="text-xs text-slate-300 bg-slate-900/60 border border-slate-800 rounded-lg p-2.5 flex items-center gap-2">
                        <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                        <span>{del}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 1-Click Lavender-Graded Cold Pitch Hook */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-purple-400" /> Tailored Cold Outreach Hook (Ready to Dispatch)
                    </div>
                    <button
                      onClick={() => copyPitch(selectedResult.pitch_strategy!.cold_pitch_hook)}
                      className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300"
                    >
                      {copiedPitch ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                      {copiedPitch ? 'Copied to Clipboard!' : 'Copy Hook'}
                    </button>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 leading-relaxed font-sans">
                    {selectedResult.pitch_strategy.cold_pitch_hook}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-400">No pitch strategy generated for this candidate.</div>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-4 border-t border-slate-800">
              <div className="text-xs text-slate-500 font-mono">
                {selectedResult.lat && selectedResult.lon ? `Lat: ${selectedResult.lat.toFixed(4)}, Lon: ${selectedResult.lon.toFixed(4)}` : 'Coordinates via Nominatim'}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => enrollInCadence(selectedResult)}
                  disabled={enrolling[selectedResult.place_id] || enrolled[selectedResult.place_id]}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-60 text-white text-xs font-semibold shadow-lg shadow-purple-600/30 transition"
                >
                  {enrolled[selectedResult.place_id] ? (
                    <><CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> Cadence Active</>
                  ) : enrolling[selectedResult.place_id] ? (
                    <><Zap className="h-3.5 w-3.5 animate-spin" /> Enrolling…</>
                  ) : (
                    <><Send className="h-3.5 w-3.5" /> 🚀 1-Click Enroll Cadence</>
                  )}
                </button>
                <button
                  onClick={() => save(selectedResult)}
                  disabled={saved[selectedResult.place_id]}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition"
                >
                  {saved[selectedResult.place_id] ? <><Check className="h-4 w-4 text-emerald-400" /> Lead Saved</> : <><BookmarkPlus className="h-4 w-4" /> Save Lead</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
