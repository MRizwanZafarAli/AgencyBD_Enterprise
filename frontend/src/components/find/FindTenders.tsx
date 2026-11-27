import { useEffect, useMemo, useState } from 'react';
import type { FC } from 'react';
import { BellPlus, Languages, RefreshCw, Search, ShieldCheck, Sparkles, Zap } from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { TENDER_SOURCE_LABELS, TenderDrawer } from './TenderDrawer';
import type { TenderOpportunity } from './TenderDrawer';

function deadlineCountdown(deadline?: string | null, stage?: string): { label: string; tone: 'good' | 'warn' | 'bad' | 'neutral' } {
  if (stage === 'pin') return { label: 'Pre-Market PIN', tone: 'good' };
  if (stage === 'award') return { label: 'Award / Renewal', tone: 'neutral' };
  if (!deadline) return { label: 'Rolling / Portal', tone: 'neutral' };
  const ms = Date.parse(deadline);
  if (Number.isNaN(ms)) return { label: deadline.slice(0, 10), tone: 'neutral' };
  const days = Math.ceil((ms - Date.now()) / 86_400_000);
  if (days < 0) return { label: 'Expired', tone: 'bad' };
  if (days <= 5) return { label: `Closes in ${days}d`, tone: 'bad' };
  if (days <= 14) return { label: `${days}d left`, tone: 'warn' };
  return { label: `${days}d left`, tone: 'good' };
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
  const [translatedTitles, setTranslatedTitles] = useState<Record<number, string>>({});
  const [selected, setSelected] = useState<TenderOpportunity | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const loadTenders = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/opportunities?limit=250');
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      const all: TenderOpportunity[] = body.opportunities || [];
      setRows(all.filter((o) => o.type === 'tender' || ['ted', 'uk_fts', 'uk_cf', 'sam_gov', 'ungm'].includes(o.source)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTenders();
  }, []);

  useEffect(() => {
    if (preset?.q) setQ(preset.q);
  }, [preset]);

  // Auto-translate non-English TED titles when enabled
  useEffect(() => {
    if (!autoTranslate) return;
    const nonEng = rows.filter((r) => r.risk_flags?.includes('non_english_notice') && !translatedTitles[r.id]).slice(0, 15);
    nonEng.forEach((r) => {
      apiFetch(`/api/tenders/${r.id}/translate`, { method: 'POST' })
        .then((res) => (res.ok ? res.json() : null))
        .then((d) => {
          if (d?.translated && d.translated !== r.title) {
            setTranslatedTitles((prev) => ({ ...prev, [r.id]: d.translated }));
          }
        })
        .catch(() => {});
    });
  }, [autoTranslate, rows, translatedTitles]);

  const scanPortals = async () => {
    setScanning(true);
    setNotice('');
    setError('');
    try {
      const res = await apiFetch('/api/radar/scan', { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      await loadTenders();
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
      if (countryFilter !== 'all' && (r.metadata?.country || '') !== countryFilter) return false;
      if (cpvFilter !== 'all') {
        const codes = (r.metadata?.cpv_codes || r.skills_required || []).join(' ');
        if (!codes.includes(cpvFilter)) return false;
      }
      if (valueTier !== 'all') {
        const val = Number(r.budget_max || 0);
        if (valueTier === 'sme' && (val <= 0 || val >= 100_000)) return false;
        if (valueTier === 'mid' && (val < 100_000 || val > 1_000_000)) return false;
        if (valueTier === 'enterprise' && val <= 1_000_000) return false;
      }
      if (q.trim()) {
        const low = q.trim().toLowerCase();
        const hay = `${r.title} ${translatedTitles[r.id] || ''} ${r.company_name || ''} ${r.description || ''}`.toLowerCase();
        if (!hay.includes(low)) return false;
      }
      return true;
    });
  }, [rows, sourceFilter, stageFilter, countryFilter, cpvFilter, valueTier, q, translatedTitles]);

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
          <select className={field} value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} aria-label="Procurement portal">
            <option value="all">All Portals</option>
            <option value="ted">TED (EU)</option>
            <option value="uk_fts">UK Find a Tender</option>
            <option value="uk_cf">UK Contracts Finder</option>
            <option value="sam_gov">SAM.gov (US)</option>
          </select>
          <select className={field} value={cpvFilter} onChange={(e) => setCpvFilter(e.target.value)} aria-label="CPV or NAICS code">
            <option value="all">All CPV / NAICS</option>
            <option value="72000000">CPV 72000000 (IT Services)</option>
            <option value="72200000">CPV 72200000 (Software Dev)</option>
            <option value="72400000">CPV 72400000 (Web / Internet)</option>
            <option value="79340000">CPV 79340000 (Marketing)</option>
            <option value="541511">NAICS 541511 (US Programming)</option>
            <option value="541512">NAICS 541512 (US Systems)</option>
          </select>
          <select className={field} value={valueTier} onChange={(e) => setValueTier(e.target.value as 'all' | 'sme' | 'mid' | 'enterprise')} aria-label="Value tier">
            <option value="all">All Value Tiers</option>
            <option value="sme">Micro / SME (&lt; £100k)</option>
            <option value="mid">Mid-Market (£100k–£1M)</option>
            <option value="enterprise">Enterprise / Framework (£1M+)</option>
          </select>
          <select className={field} value={countryFilter} onChange={(e) => setCountryFilter(e.target.value)} aria-label="Country">
            <option value="all">All Countries</option>
            {countries.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
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
                {filtered.map((t) => {
                  const stage = t.metadata?.notice_stage || 'rfp';
                  const dl = deadlineCountdown(t.deadline, stage);
                  const isMega = Boolean(t.budget_max && Number(t.budget_max) >= 2_000_000);
                  const displayTitle = autoTranslate && translatedTitles[t.id] ? translatedTitles[t.id] : t.title;
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
                        <div className="font-semibold text-white">{displayTitle}</div>
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
