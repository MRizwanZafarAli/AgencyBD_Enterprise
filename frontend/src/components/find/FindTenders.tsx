import { useEffect, useMemo, useState } from 'react';
import type { FC } from 'react';
import { BellPlus, Languages, RefreshCw, Search, ShieldCheck, Sparkles, Zap } from 'lucide-react';
import { Badge, Button, Card, Pager, Select, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { TENDER_SOURCE_LABELS, TenderDrawer } from './TenderDrawer';
import type { TenderOpportunity } from './TenderDrawer';

const FX_TO_GBP: Record<string, number> = { GBP: 1, EUR: 0.85, USD: 0.79 };

export function toGbp(amount?: number | null, currency?: string): number | null {
  if (amount == null || Number.isNaN(Number(amount))) return null;
  const rate = FX_TO_GBP[(currency || 'GBP').toUpperCase()] ?? 1;
  return Number(amount) * rate;
}

function parseUtcDeadlineMs(deadline?: string | null): number | null {
  if (!deadline) return null;
  const trimmed = deadline.trim();
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(trimmed) ? `${trimmed}T23:59:59Z` : trimmed;
  const ms = Date.parse(normalized);
  return Number.isNaN(ms) ? null : ms;
}

function deadlineCountdown(deadline?: string | null, stage?: string): { label: string; tone: 'good' | 'warn' | 'bad' | 'neutral'; isExpired: boolean } {
  if (stage === 'pin') return { label: 'Pre-Market PIN', tone: 'good', isExpired: false };
  if (stage === 'award') return { label: 'Award / Renewal', tone: 'neutral', isExpired: false };
  if (!deadline) return { label: 'Rolling / Portal', tone: 'neutral', isExpired: false };
  const ms = parseUtcDeadlineMs(deadline);
  if (ms === null) return { label: deadline.slice(0, 10), tone: 'neutral', isExpired: false };
  const days = Math.ceil((ms - Date.now()) / 86_400_000);
  if (days < 0) return { label: 'Expired', tone: 'bad', isExpired: true };
  if (days <= 5) return { label: `Closes in ${days}d`, tone: 'bad', isExpired: false };
  if (days <= 14) return { label: `${days}d left`, tone: 'warn', isExpired: false };
  return { label: `${days}d left`, tone: 'good', isExpired: false };
}

interface PortalHealth {
  id: string;
  label: string;
  status: 'ok' | 'auth_required' | 'rate_limited' | 'error';
  hits: number;
  detail?: string;
}

const EU_GLOSSARY: [RegExp, string][] = [
  [/procedura aperta/gi, 'Open Procedure'],
  [/procedura ristretta/gi, 'Restricted Procedure'],
  [/affidamento/gi, 'Contract Award'],
  [/servizi di sviluppo/gi, 'Development Services'],
  [/servizi informatici/gi, 'IT Services'],
  [/servizi/gi, 'Services'],
  [/manutenzione/gi, 'Maintenance'],
  [/piattaforma/gi, 'Platform'],
  [/sistema informativo/gi, 'Information System'],
  [/appalto/gi, 'Public Contract'],
  [/avviso di preinformazione/gi, 'Prior Information Notice (PIN)'],
  [/avis de marché/gi, 'Contract Notice'],
  [/services informatiques/gi, 'IT Services'],
  [/développement/gi, 'Development'],
  [/offene verfahren/gi, 'Open Procedure'],
  [/it-dienstleistungen/gi, 'IT Services'],
  [/softwareentwicklung/gi, 'Software Development'],
  [/licitación/gi, 'Public Tender'],
  [/servicios informáticos/gi, 'IT Services'],
];

function translateEuTitleLocal(title: string): string {
  let out = title;
  for (const [re, rep] of EU_GLOSSARY) {
    out = out.replace(re, rep);
  }
  return out;
}

export const FindTenders: FC<{
  preset?: { q?: string; min_budget?: number | null; nonce?: number } | null;
  onOpenClient?: (leadId: number) => void;
  onSendEmail?: (params: {
    recipient: string;
    recipientName?: string;
    companyName?: string;
    subject?: string;
    body?: string;
  }) => void;
}> = ({ preset, onOpenClient, onSendEmail }) => {
  const [rows, setRows] = useState<TenderOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [rescoring, setRescoring] = useState(false);
  const [q, setQ] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState<'all' | 'pin' | 'rfp' | 'framework' | 'award'>('all');
  const [cpvFilter, setCpvFilter] = useState('all');
  const [valueTier, setValueTier] = useState<'all' | 'sme' | 'mid' | 'enterprise'>('all');
  const [countryFilter, setCountryFilter] = useState('all');
  const [autoTranslate, setAutoTranslate] = useState(true);
  const [hideExpired, setHideExpired] = useState(true);
  const [portalHealth, setPortalHealth] = useState<PortalHealth[]>([]);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;
  const [selected, setSelected] = useState<TenderOpportunity | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const loadHealth = () => {
    apiFetch('/api/tenders/source-health')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d?.sources) setPortalHealth(d.sources); })
      .catch(() => {});
  };

  const loadTenders = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/opportunities?type=tender&limit=200');
      const body = await res.json().catch(() => []);
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      const all: TenderOpportunity[] = Array.isArray(body) ? body : (body?.opportunities || []);
      setRows(all.filter((o) => o.type === 'tender' || ['ted', 'uk_fts', 'uk_cf', 'sam_gov', 'ungm'].includes(o.source)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTenders();
    loadHealth();
  }, []);

  useEffect(() => {
    if (preset?.q) setQ(preset.q);
  }, [preset]);

  const scanPortals = async () => {
    setScanning(true);
    setNotice('');
    setError('');
    try {
      const res = await apiFetch('/api/radar/scan', { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      await loadTenders();
      loadHealth();
      setNotice('Scanned TED (EU), UK Find a Tender, UK Contracts Finder & SAM.gov.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setScanning(false);
    }
  };

  const rescoreAll = async () => {
    setRescoring(true);
    setNotice('');
    try {
      const res = await apiFetch('/api/tenders/rescore', { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      if (res.ok) {
        await loadTenders();
        setNotice(`Re-scored ${body.rescored ?? 0} cached tenders with updated fit & stop-word rules.`);
      }
    } finally {
      setRescoring(false);
    }
  };

  const watchCurrentSearch = async () => {
    const label = q.trim() || (cpvFilter !== 'all' ? `CPV ${cpvFilter}` : 'Public IT Tenders');
    const res = await apiFetch('/api/leadfinder/searches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: `Tender Watch: ${label.slice(0, 45)}`,
        source: 'hiring',
        params: { q: label },
        notify: true,
        every_hours: 24,
      }),
    });
    if (res.ok) setNotice(`Watch created for "${label}" in Watching tab.`);
  };

  const countries = useMemo(() => {
    const set = new Set<string>();
    rows.forEach((r) => {
      const c = r.metadata?.country;
      if (c) set.add(c);
    });
    return Array.from(set).sort();
  }, [rows]);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (sourceFilter !== 'all' && r.source !== sourceFilter) return false;
      const stage = r.metadata?.notice_stage || 'rfp';
      if (stageFilter !== 'all' && stage !== stageFilter) return false;
      if (hideExpired && stageFilter !== 'award' && stage !== 'award') {
        const dl = deadlineCountdown(r.deadline, stage);
        if (dl.isExpired) return false;
      }
      if (countryFilter !== 'all' && (r.metadata?.country || '') !== countryFilter) return false;
      if (cpvFilter !== 'all') {
        const codes = (r.metadata?.cpv_codes || r.skills_required || []).join(' ');
        if (!codes.includes(cpvFilter)) return false;
      }
      if (valueTier !== 'all') {
        const gbp = toGbp(r.budget_max, r.currency);
        if (gbp === null || gbp <= 0) return false;
        if (valueTier === 'sme' && gbp >= 100_000) return false;
        if (valueTier === 'mid' && (gbp < 100_000 || gbp > 1_000_000)) return false;
        if (valueTier === 'enterprise' && gbp <= 1_000_000) return false;
      }
      if (q.trim()) {
        const low = q.trim().toLowerCase();
        const hay = `${r.title} ${autoTranslate ? translateEuTitleLocal(r.title) : ''} ${r.company_name || ''} ${r.description || ''}`.toLowerCase();
        if (!hay.includes(low)) return false;
      }
      return true;
    });
  }, [rows, sourceFilter, stageFilter, hideExpired, countryFilter, cpvFilter, valueTier, q, autoTranslate]);

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-indigo-400" />
              Enterprise Procurement &amp; Tender Intelligence
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Live public-sector RFPs, Pre-Market PINs, Frameworks &amp; Award Notices from TED (EU), UK Find a Tender, UK Contracts Finder &amp; SAM.gov (US).
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button small variant="secondary" onClick={watchCurrentSearch}>
              <BellPlus className="h-3.5 w-3.5 text-emerald-400" />
              Watch CPV / Query
            </Button>
            <Button small variant="secondary" disabled={rescoring} onClick={rescoreAll}>
              <Sparkles className="h-3.5 w-3.5 text-amber-400" />
              {rescoring ? 'Re-scoring…' : 'Re-score Cached'}
            </Button>
            <Button small variant="primary" disabled={scanning} onClick={scanPortals}>
              <RefreshCw className={`h-3.5 w-3.5 ${scanning ? 'animate-spin' : ''}`} />
              {scanning ? 'Scanning Portals…' : 'Scan Procurement Portals'}
            </Button>
          </div>
        </div>

        {/* Procurement Filters */}
        <div className="grid gap-2 md:grid-cols-6">
          <div className="relative md:col-span-2">
            <Search className="h-4 w-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              className={`${field} pl-9`}
              placeholder="Search title, authority, CPV/NAICS…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <Select
            value={sourceFilter}
            onChange={setSourceFilter}
            aria-label="Procurement portal"
            options={[
              { value: 'all', label: 'All Portals' },
              { value: 'ted', label: 'TED (EU)' },
              { value: 'uk_fts', label: 'UK Find a Tender' },
              { value: 'uk_cf', label: 'UK Contracts Finder' },
              { value: 'sam_gov', label: 'SAM.gov (US)' },
            ]}
          />
          <Select
            value={cpvFilter}
            onChange={setCpvFilter}
            aria-label="CPV or NAICS code"
            options={[
              { value: 'all', label: 'All CPV / NAICS' },
              { value: '72000000', label: 'CPV 72000000 (IT Services)' },
              { value: '72200000', label: 'CPV 72200000 (Software Dev)' },
              { value: '72400000', label: 'CPV 72400000 (Web / Internet)' },
              { value: '79340000', label: 'CPV 79340000 (Marketing)' },
              { value: '541511', label: 'NAICS 541511 (US Programming)' },
              { value: '541512', label: 'NAICS 541512 (US Systems)' },
            ]}
          />
          <Select
            value={valueTier}
            onChange={(v) => setValueTier(v as 'all' | 'sme' | 'mid' | 'enterprise')}
            aria-label="Value tier"
            options={[
              { value: 'all', label: 'All Value Tiers' },
              { value: 'sme', label: 'Micro / SME (< £100k)' },
              { value: 'mid', label: 'Mid-Market (£100k–£1M)' },
              { value: 'enterprise', label: 'Enterprise / Framework (£1M+)' },
            ]}
          />
          <Select
            value={countryFilter}
            onChange={setCountryFilter}
            aria-label="Country"
            options={[
              { value: 'all', label: 'All Countries' },
              ...countries.map((c) => ({ value: c, label: c })),
            ]}
          />
        </div>

        {/* Notice Stage Filter Pills & Auto-Translate */}
        <div className="flex flex-wrap items-center justify-between gap-2 mt-3 pt-3 border-t border-slate-800/80">
          <div className="flex flex-wrap items-center gap-1.5">
            {(
              [
                ['all', 'All Stages'],
                ['pin', 'Pre-Market / PIN (Early Access)'],
                ['rfp', 'Live Tender / RFP'],
                ['framework', 'Framework / DPS'],
                ['award', 'Award / Re-Tender'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setStageFilter(id)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                  stageFilter === id
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900/70 border-slate-800 text-slate-300 hover:border-slate-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <label className="inline-flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={hideExpired}
                onChange={(e) => setHideExpired(e.target.checked)}
                className="rounded border-slate-700"
              />
              Hide Expired
            </label>
            <label className="inline-flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={autoTranslate}
                onChange={(e) => setAutoTranslate(e.target.checked)}
                className="rounded border-slate-700"
              />
              <Languages className="h-3.5 w-3.5 text-indigo-400" />
              Auto-Translate EU Titles
            </label>
          </div>
        </div>

        {portalHealth.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mt-2.5 pt-2.5 border-t border-slate-800/80">
            <span className="text-[11px] text-slate-500 font-medium">Portal Health:</span>
            {portalHealth.map((ph) => {
              const dot =
                ph.status === 'ok'
                  ? 'bg-emerald-400'
                  : ph.status === 'auth_required' || ph.status === 'rate_limited'
                  ? 'bg-amber-400'
                  : 'bg-rose-400';
              return (
                <span
                  key={ph.id}
                  title={ph.detail}
                  className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] bg-slate-900 border border-slate-800 text-slate-300"
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
                  <span>{ph.label}:</span>
                  <strong className="text-white">
                    {ph.status === 'auth_required'
                      ? 'Auth required'
                      : ph.status === 'rate_limited'
                      ? 'Rate-limited'
                      : ph.status === 'error'
                      ? 'Error'
                      : `${ph.hits} hits`}
                  </strong>
                </span>
              );
            })}
          </div>
        )}

        {notice && <p className="text-xs text-emerald-400 mt-2">{notice}</p>}
        {error && <p className="text-xs text-rose-400 mt-2">{error}</p>}
      </Card>

      {/* Tender Table */}
      <Card className="!p-0 overflow-hidden">
        {loading ? (
          <div className="p-6 text-xs text-slate-400">Loading public-sector tenders…</div>
        ) : filtered.length === 0 ? (
          <div className="p-6 text-xs text-slate-400">
            No matching tenders found. Click <strong>Scan Procurement Portals</strong> above to pull fresh notices.
          </div>
        ) : (
          <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/90 border-b border-slate-800 text-slate-400">
                <tr>
                  <th className="py-2.5 px-3">Portal &amp; Stage</th>
                  <th className="py-2.5 px-3">Contracting Authority &amp; Title</th>
                  <th className="py-2.5 px-3">Deadline</th>
                  <th className="py-2.5 px-3">Est. Value</th>
                  <th className="py-2.5 px-3">Fit</th>
                  <th className="py-2.5 px-3 text-right">Bid Studio</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((t) => {
                  const stage = t.metadata?.notice_stage || 'rfp';
                  const dl = deadlineCountdown(t.deadline, stage);
                  const gbpVal = toGbp(t.budget_max, t.currency);
                  const isMega = gbpVal !== null && gbpVal >= 2_000_000;
                  const displayTitle = autoTranslate ? translateEuTitleLocal(t.title) : t.title;
                  return (
                    <tr key={t.id} className="hover:bg-slate-900/50 transition">
                      <td className="py-3 px-3 align-top whitespace-nowrap space-y-1">
                        <div><Badge tone="accent">{TENDER_SOURCE_LABELS[t.source] || t.source}</Badge></div>
                        <div>
                          {stage === 'pin' && <Badge tone="good"><Zap className="h-3 w-3 inline mr-0.5" />PIN Early Access</Badge>}
                          {stage === 'framework' && <Badge tone="neutral">Framework</Badge>}
                          {stage === 'award' && <Badge tone="warn">Award Notice</Badge>}
                          {stage === 'rfp' && <Badge>Live RFP</Badge>}
                        </div>
                      </td>
                      <td className="py-3 px-3 align-top max-w-md">
                        <div className="font-semibold text-white line-clamp-2">{displayTitle}</div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          {t.company_name || 'Contracting Authority'}
                          {t.metadata?.country ? ` · ${t.metadata.country}` : ''}
                          {isMega && <span className="ml-2 text-amber-300 font-medium">· Teaming / Subcontractor Target</span>}
                        </div>
                        {t.fit_reasons && t.fit_reasons.length > 0 && (
                          <div className="text-[11px] text-indigo-300/80 mt-0.5 line-clamp-1">{t.fit_reasons[0]}</div>
                        )}
                      </td>
                      <td className="py-3 px-3 align-top whitespace-nowrap">
                        <Badge tone={dl.tone}>{dl.label}</Badge>
                      </td>
                      <td className="py-3 px-3 align-top whitespace-nowrap text-slate-200 font-medium">
                        {t.budget_max ? `${t.currency || 'GBP'} ${Number(t.budget_max).toLocaleString()}` : '—'}
                      </td>
                      <td className="py-3 px-3 align-top whitespace-nowrap">
                        {t.fit_score != null ? <Badge tone="good">{Math.round(t.fit_score * 100)}%</Badge> : '—'}
                      </td>
                      <td className="py-3 px-3 align-top text-right whitespace-nowrap">
                        <Button small variant="secondary" onClick={() => setSelected(t)}>
                          Bid / No-Go Studio
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="p-3 border-t border-slate-800/80">
            <Pager page={page} pageSize={PAGE_SIZE} total={filtered.length} onPage={setPage} />
          </div>
          </>
        )}
      </Card>

      <TenderDrawer
        tender={selected}
        onClose={() => setSelected(null)}
        onOpenClient={onOpenClient}
        onSendEmail={onSendEmail}
      />
    </div>
  );
};
