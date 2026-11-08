import { useState } from 'react';
import type { FC } from 'react';
import { ExternalLink, Pause, Play, Plus, RefreshCw, Trash2, X } from 'lucide-react';
import { Badge, Button, Card, EmptyState, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';
import { apiFetch, apiErrorMessage } from '../../lib/api';

interface Search { id: number; name: string; source: string; params: Record<string, any>; notify: boolean; active: boolean; every_hours: number; last_run_at: string | null; last_status: string | null; last_detail: string | null; new_hits: number }
interface Hit { id: number; search_name: string; title: string; detail: string; url: string | null; status: 'new' | 'saved' | 'dismissed'; lead_id: number | null; first_seen_at: string }
interface Source { id: string; label: string; about: string; needs_key: string | null; ready: boolean }
interface Signal { id: string; label: string }
interface Place { region: string; label: string; url: string; note: string }
interface Link { label: string; url: string; note: string }

const EVERY = [{ h: 6, t: 'every 6 hours' }, { h: 24, t: 'every day' }, { h: 72, t: 'every 3 days' }, { h: 168, t: 'every week' }];
const ago = (at: string | null) => { if (!at) return 'not yet'; const m = Math.max(0, Math.round((Date.now() - new Date(at.replace(' ', 'T') + 'Z').getTime()) / 60000)); return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`; };
const words = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);

/** Saved searches that watch for new leads on their own, the leads they found, and search links for people on LinkedIn. */
export const LeadFinder: FC<{ onOpenClient: (leadId: number) => void; onAddKey: () => void }> = ({ onOpenClient, onAddKey }) => {
  const searches = useApi<{ searches: Search[] }>('/api/leadfinder/searches');
  const hits = useApi<{ hits: Hit[] }>('/api/leadfinder/hits?status=new');
  const kept = useApi<{ hits: Hit[] }>('/api/leadfinder/hits?status=saved');
  const places = useApi<{ places: Place[] }>('/api/leadfinder/places');
  const meta = useApi<{ sources: Source[]; signals: Signal[] }>('/api/leadfinder/sources');
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ source: 'hiring', name: '', keywords: '', days: '7', sic: '', location: '', signals: [] as string[], every: 24, notify: true });
  const [site, setSite] = useState<Record<number, string>>({});
  const [x, setX] = useState({ role: '', industry: '', location: '' });
  const [links, setLinks] = useState<Link[]>([]);

  const all = () => { searches.reload(); hits.reload(); kept.reload(); };
  const run = async (fn: () => Promise<unknown>) => { setError(''); setNote(''); try { await fn(); } catch (e) { setError((e as Error).message); } };
  const source = meta.data?.sources.find((s) => s.id === f.source);
  const params = () => f.source === 'hiring' ? { keywords: words(f.keywords) } : (f.source === 'new_companies' || f.source === 'new_companies_ie') ? { days: Number(f.days), sic_codes: words(f.sic), location: f.location } : { signals: f.signals };
  const create = () => run(async () => {
    const made = await send<Search>('/api/leadfinder/searches', 'POST', { name: f.name, source: f.source, params: params(), notify: f.notify, every_hours: f.every });
    const r = await send<{ total: number; new: number; status: string; detail: string }>(`/api/leadfinder/searches/${made.id}/run`);
    setNote(r.status === 'ok' ? `Saved. First look found ${r.total} match${r.total === 1 ? '' : 'es'}.` : `Saved, but the first look could not finish: ${r.detail}`);
    setAdding(false); setF({ ...f, name: '', keywords: '', sic: '', location: '', signals: [] }); all();
  });
  const runNow = (s: Search) => run(async () => { const r = await send<{ total: number; new: number; status: string; detail: string }>(`/api/leadfinder/searches/${s.id}/run`); setNote(r.status === 'ok' ? `${s.name}: ${r.new} new, ${r.total} in all.` : `${s.name}: ${r.detail}`); all(); });
  const save = (h: Hit) => run(async () => { const r = await send<{ lead_id: number | null }>(`/api/leadfinder/hits/${h.id}/save`, 'POST', site[h.id] ? { website: site[h.id] } : {}); setNote(r.lead_id ? `${h.title} is now in Clients.` : `${h.title} is kept. Add its website later to work on it as a client.`); all(); });
  const findLinks = () => run(async () => {
    const res = await apiFetch(`/api/leadfinder/xray?${new URLSearchParams(x)}`);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
    setLinks((body as { links: Link[] }).links);
  });

  return (
    <div className="space-y-5">
      <ErrorBanner message={error || searches.error || hits.error} />
      {note && <p role="status" className="text-xs text-emerald-300">{note}</p>}
      <Card>
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <h2 className="text-sm font-semibold text-white mr-auto">Watching for you</h2>
          <Button small onClick={() => setAdding((v) => !v)}><Plus className="h-3.5 w-3.5" />New watch</Button>
        </div>
        <p className="text-xs text-slate-400 mb-3">A watch looks again by itself and tells you on your phone (Telegram or ntfy, set in Settings, Message alerts) only about things it has not shown you before.</p>
        {adding && (
          <form className="grid gap-3 mb-4 p-3 rounded-xl border border-slate-800" onSubmit={(e) => { e.preventDefault(); create(); }}>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="text-xs text-slate-400">What to watch<select className={`${field} mt-1`} value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })}>{(meta.data?.sources ?? []).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
              <label className="text-xs text-slate-400">Name<input className={`${field} mt-1`} required maxLength={80} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="For example: Shopify jobs" /></label>
            </div>
            {source && <p className="text-xs text-slate-400">{source.about}{source.needs_key && !source.ready && <> It needs a free key. <button type="button" className="text-indigo-400 hover:underline" onClick={onAddKey}>Add it in Settings</button>.</>}</p>}
            {f.source === 'hiring' && <label className="text-xs text-slate-400">Words to look for, separated by commas<input className={`${field} mt-1`} required value={f.keywords} onChange={(e) => setF({ ...f, keywords: e.target.value })} placeholder="shopify, react developer, wordpress" /></label>}
            {(f.source === 'new_companies' || f.source === 'new_companies_ie') && (
              <div className="grid gap-2 sm:grid-cols-3">
                <label className="text-xs text-slate-400">Registered in the last (days)<input className={`${field} mt-1`} type="number" min={1} max={30} value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })} /></label>
                <label className="text-xs text-slate-400">Place (optional)<input className={`${field} mt-1`} value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} placeholder="Leeds" /></label>
                <label className="text-xs text-slate-400">Business type codes (optional)<input className={`${field} mt-1`} value={f.sic} onChange={(e) => setF({ ...f, sic: e.target.value })} placeholder={f.source === 'new_companies_ie' ? '6201, 4791' : '86230, 47910'} /></label>
              </div>)}
            {f.source === 'site_signals' && (
              <fieldset className="grid gap-1.5 sm:grid-cols-2"><legend className="text-xs text-slate-400 mb-1">Tell me when a checked website has</legend>
                {(meta.data?.signals ?? []).map((s) => <label key={s.id} className="flex items-center gap-2 text-sm text-slate-200"><input type="checkbox" checked={f.signals.includes(s.id)} onChange={(e) => setF({ ...f, signals: e.target.checked ? [...f.signals, s.id] : f.signals.filter((v) => v !== s.id) })} />{s.label}</label>)}
              </fieldset>)}
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-xs text-slate-400">Look again<select className={`${field} ml-2`} value={f.every} onChange={(e) => setF({ ...f, every: Number(e.target.value) })}>{EVERY.map((o) => <option key={o.h} value={o.h}>{o.t}</option>)}</select></label>
              <label className="flex items-center gap-2 text-sm text-slate-200"><input type="checkbox" checked={f.notify} onChange={(e) => setF({ ...f, notify: e.target.checked })} />Tell me on my phone</label>
              <Button variant="primary" type="submit" className="ml-auto">Save and look now</Button>
            </div>
          </form>)}
        {(searches.data?.searches ?? []).length === 0 ? <EmptyState title="Nothing is being watched yet" hint="Try: newly registered companies in your city, or jobs that mention the skills you sell." /> : (
          <ul className="divide-y divide-slate-800">{searches.data!.searches.map((s) => (
            <li key={s.id} className="py-2.5 flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-white">{s.name}</span>
              <Badge tone={s.active ? 'good' : 'neutral'}>{s.active ? 'Watching' : 'Paused'}</Badge>
              {s.new_hits > 0 && <Badge tone="warn">{s.new_hits} new</Badge>}
              <span className={`text-xs ${s.last_status === 'error' ? 'text-amber-300' : 'text-slate-400'}`}>Last look {ago(s.last_run_at)}{s.last_detail ? ` · ${s.last_detail}` : ''}</span>
              <span className="ml-auto flex gap-1.5">
                <Button small variant="ghost" onClick={() => runNow(s)} aria-label={`Look now: ${s.name}`}><RefreshCw className="h-3.5 w-3.5" /></Button>
                <Button small variant="ghost" onClick={() => run(async () => { await send(`/api/leadfinder/searches/${s.id}`, 'PUT', { active: !s.active }); searches.reload(); })} aria-label={`${s.active ? 'Pause' : 'Resume'} ${s.name}`}>{s.active ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}</Button>
                <Button small variant="ghost" onClick={() => run(async () => { await send(`/api/leadfinder/searches/${s.id}`, 'DELETE'); all(); })} aria-label={`Delete ${s.name}`}><Trash2 className="h-3.5 w-3.5" /></Button>
              </span>
            </li>))}</ul>)}
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-2">New leads</h2>
        {(hits.data?.hits ?? []).length === 0 ? <EmptyState title="No new leads" hint="They appear here when a watch finds something it has not shown you." /> : (
          <ul className="divide-y divide-slate-800">{hits.data!.hits.map((h) => (
            <li key={h.id} className="py-3 space-y-1.5">
              <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium text-white">{h.title}</span><Badge>{h.search_name}</Badge>
                {h.url && <a href={h.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:underline">Open <ExternalLink className="h-3 w-3" /></a>}
                <Button small variant="ghost" className="ml-auto" onClick={() => run(async () => { await send(`/api/leadfinder/hits/${h.id}/dismiss`); all(); })} aria-label={`Dismiss ${h.title}`}><X className="h-3.5 w-3.5" /></Button></div>
              <p className="text-xs text-slate-400">{h.detail}</p>
              <div className="flex flex-wrap gap-2">
                <input className={`${field} max-w-[16rem]`} aria-label={`Website of ${h.title} (optional)`} placeholder="Their website, if you know it" value={site[h.id] ?? ''} onChange={(e) => setSite({ ...site, [h.id]: e.target.value })} />
                <Button small variant="primary" onClick={() => save(h)} aria-label={`Keep ${h.title}`}>Keep</Button>
              </div>
            </li>))}</ul>)}
        {(kept.data?.hits ?? []).length > 0 && <details className="mt-3"><summary className="text-xs text-slate-400 cursor-pointer">Kept ({kept.data!.hits.length})</summary>
          <ul className="mt-2 space-y-1">{kept.data!.hits.map((h) => <li key={h.id} className="text-xs text-slate-300">{h.title} · {h.search_name}{h.lead_id ? <> · <button type="button" className="text-indigo-400 hover:underline" onClick={() => onOpenClient(h.lead_id!)}>open client</button></> : ' · no website yet'}</li>)}</ul></details>}
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-1">Find people on LinkedIn</h2>
        <p className="text-xs text-slate-400 mb-3">Builds search links that you open yourself, in your own browser. Nothing is read from LinkedIn for you, so your account stays safe.</p>
        <form className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr_auto]" onSubmit={(e) => { e.preventDefault(); findLinks(); }}>
          <input className={field} aria-label="Who (job title)" required placeholder="Who: owner, practice manager" value={x.role} onChange={(e) => setX({ ...x, role: e.target.value })} />
          <input className={field} aria-label="Industry" placeholder="Industry: dental" value={x.industry} onChange={(e) => setX({ ...x, industry: e.target.value })} />
          <input className={field} aria-label="Place" placeholder="Place: Dublin" value={x.location} onChange={(e) => setX({ ...x, location: e.target.value })} />
          <Button variant="primary" type="submit">Make links</Button>
        </form>
        {links.length > 0 && <ul className="mt-3 space-y-2">{links.map((l) => <li key={l.url}><a href={l.url} target="_blank" rel="noopener noreferrer" className="text-sm text-indigo-400 hover:underline inline-flex items-center gap-1">{l.label}<ExternalLink className="h-3 w-3" /></a><span className="block text-xs text-slate-400">{l.note}</span></li>)}</ul>}
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-1">Where else to look</h2>
        <p className="text-xs text-slate-400 mb-3">Official places that publish no feed we may read. You open and search them yourself; the app never scrapes them.</p>
        <ul className="space-y-2">{(places.data?.places ?? []).map((p) => (
          <li key={p.url}><span className="text-xs text-slate-500 mr-2">{p.region}</span><a href={p.url} target="_blank" rel="noopener noreferrer" className="text-sm text-indigo-400 hover:underline inline-flex items-center gap-1">{p.label}<ExternalLink className="h-3 w-3" /></a>
            <span className="block text-xs text-slate-400">{p.note}</span></li>))}</ul>
      </Card>
    </div>
  );
};
