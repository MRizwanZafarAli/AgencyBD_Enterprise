import { useEffect, useState } from 'react';
import type { FC, FormEvent } from 'react';
import { BookOpen, Trash2, Plus } from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';

interface Asset {
  id: number;
  title: string;
  industry?: string;
  services: string[];
  tech: string[];
  body: string;
}

const split = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);

interface Service {
  service_key: string;
  name: string;
  offer: string;
  price_band: string | null;
}

const SERVICE_KEYS: Record<string, string> = {
  performance_engineering: 'Performance engineering',
  seo_optimization: 'SEO optimization',
  security_hardening: 'Security hardening',
  a11y_compliance: 'Accessibility compliance',
  geo_ai_readiness: 'AI-search readiness (GEO)',
  mobile_optimization: 'Mobile optimization',
  devops_sre: 'DevOps / SRE',
  presence_rescue: 'Digital presence build (site + Google profile)'
};

const ServicesSection: FC = () => {
  const [services, setServices] = useState<Service[]>([]);
  const [form, setForm] = useState({ service_key: 'performance_engineering', offer: '', price_band: '' });
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiFetch('/api/services').then(async (res) => {
      if (active && res.ok) setServices(await res.json());
    });
    return () => {
      active = false;
    };
  }, []);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    const res = await apiFetch('/api/services', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_key: form.service_key, name: SERVICE_KEYS[form.service_key], offer: form.offer, price_band: form.price_band || null })
    });
    const data = await res.json();
    if (!res.ok) {
      setError(apiErrorMessage(res.status, data));
      return;
    }
    setServices((prev) => [...prev.filter((s) => s.service_key !== data.service_key), data]);
    setForm({ ...form, offer: '', price_band: '' });
  };

  const remove = async (key: string) => {
    await apiFetch(`/api/services/${key}`, { method: 'DELETE' });
    setServices((prev) => prev.filter((s) => s.service_key !== key));
  };

  const input = 'w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500';
  return (
    <div className="space-y-4 pt-4 border-t border-slate-800/80">
      <div>
        <h2 className="text-lg font-bold text-white tracking-tight">Services &amp; Price Bands</h2>
        <p className="text-xs text-slate-400 mt-0.5">Briefs and presence offers quote only the price bands you enter here. Nothing is estimated for you.</p>
      </div>
      <form onSubmit={save} className="glass-panel rounded-2xl p-5 grid sm:grid-cols-3 gap-3">
        <select className={input} value={form.service_key} onChange={(e) => setForm({ ...form, service_key: e.target.value })}>
          {Object.entries(SERVICE_KEYS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input className={input} placeholder="What you deliver (items separated by ;)" value={form.offer} onChange={(e) => setForm({ ...form, offer: e.target.value })} required />
        <input className={input} placeholder="Price band, e.g. $4,000 - $9,000" value={form.price_band} onChange={(e) => setForm({ ...form, price_band: e.target.value })} />
        {error && <div role="alert" className="sm:col-span-3 text-xs text-rose-300">{error}</div>}
        <button className="sm:col-span-3 justify-self-start rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-sm font-semibold">Save service</button>
      </form>
      {services.map((s) => (
        <div key={s.service_key} className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm flex justify-between gap-3">
          <div>
            <div className="font-semibold text-white">{s.name} <span className="text-emerald-400 font-mono text-xs">{s.price_band || 'no price band'}</span></div>
            <div className="text-slate-400 text-xs">{s.offer}</div>
          </div>
          <button onClick={() => remove(s.service_key)} aria-label={`Delete ${s.name}`} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
    </div>
  );
};

export const PortfolioManager: FC = () => {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [form, setForm] = useState({ title: '', industry: '', services: '', tech: '', body: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const res = await apiFetch('/api/portfolio/assets');
    if (res.ok) setAssets(await res.json());
  };

  useEffect(() => {
    let active = true;
    apiFetch('/api/portfolio/assets').then(async (res) => {
      if (active && res.ok) setAssets(await res.json());
    });
    return () => {
      active = false;
    };
  }, []);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await apiFetch('/api/portfolio/assets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: form.title,
          industry: form.industry || null,
          services: split(form.services),
          tech: split(form.tech),
          body: form.body
        })
      });
      const data = await res.json();
      if (!res.ok) {
        setError(apiErrorMessage(res.status, data));
        return;
      }
      setForm({ title: '', industry: '', services: '', tech: '', body: '' });
      await load();
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    await apiFetch(`/api/portfolio/assets/${id}`, { method: 'DELETE' });
    await load();
  };

  const input = 'w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
          <BookOpen className="h-6 w-6 text-indigo-400" />
          <span>Portfolio &amp; Proof</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Proposals may only cite work you list here. Write what was built and the real result, with real numbers. Anything not in these case studies or the job post is rejected by the verifier.
        </p>
      </div>

      <form onSubmit={add} className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4">
        <div className="grid sm:grid-cols-2 gap-3">
          <input className={input} placeholder="Title, e.g. Logistics booking rebuild" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          <input className={input} placeholder="Industry" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} />
          <input className={input} placeholder="Services (comma separated)" value={form.services} onChange={(e) => setForm({ ...form, services: e.target.value })} />
          <input className={input} placeholder="Tech (comma separated)" value={form.tech} onChange={(e) => setForm({ ...form, tech: e.target.value })} />
        </div>
        <textarea className={input} rows={4} placeholder="What you built for whom, and the measured result (15+ words)." value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} required />
        {error && <div role="alert" className="text-xs text-rose-300">{error}</div>}
        <button disabled={busy} className="flex items-center space-x-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 px-4 py-2.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/25 transition">
          <Plus className="h-4 w-4" />
          <span>{busy ? 'Saving…' : 'Add Case Study'}</span>
        </button>
      </form>

      <div className="space-y-3">
        {assets.length === 0 && (
          <div className="text-sm text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-2xl p-5">
            No case studies yet. Proposal drafting is blocked until you add at least one real one.
          </div>
        )}
        {assets.map((a) => (
          <div key={a.id} className="glass-panel-interactive rounded-2xl p-5 text-sm">
            <div className="flex justify-between items-start gap-3">
              <div>
                <div className="font-bold text-white text-base">{a.title}</div>
                <div className="text-xs text-slate-400 font-mono mt-0.5">
                  {[a.industry, ...a.services, ...a.tech].filter(Boolean).join(' · ')}
                </div>
              </div>
              <button onClick={() => remove(a.id)} aria-label={`Delete ${a.title}`} className="p-1 rounded-lg text-slate-500 hover:text-rose-400 transition">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
            <p className="text-slate-300 mt-2.5 leading-relaxed whitespace-pre-wrap text-xs">{a.body}</p>
          </div>
        ))}
      </div>

      <ServicesSection />
    </div>
  );
};
