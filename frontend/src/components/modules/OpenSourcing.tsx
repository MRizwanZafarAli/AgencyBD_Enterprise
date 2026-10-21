import { useState } from 'react';
import type { FC } from 'react';
import {
  MapPin, UserCheck, Play, RefreshCw,
  ArrowRight, Rocket, Flame,
  Building2, Check, Search, Sparkles
} from 'lucide-react';
import {
  SERVICE_PRESETS,
  GEO_PRESETS,
  CURATED_TECH_COMPANIES,
  ROLE_PRESETS
} from '../../constants/presets';
import type { GoogleMapsLead, LinkedInProfile, TabType } from '../../types';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from '../shared/ErrorBanner';
import { ExternalLink, CopyablePhone, CopyableEmail } from '../shared/ClickableContact';

interface OpenSourcingProps {
  onBridgeToWaterfall: (first: string, last: string, company: string, domain: string) => void;
  setActiveTab: (tab: TabType) => void;
}

interface VentureLead {
  id?: number;
  company_name: string;
  domain: string;
  form_type: string;
  cik: string;
  filing_url: string;
  filing_date: string;
  notes?: string;
}

interface HiringLead {
  id?: number;
  company_name: string;
  domain: string;
  opportunity_title: string;
  skills_required: string[];
  application_url: string;
  posted_at?: string;
  notes?: string;
}

interface ExecutiveProfile extends LinkedInProfile {
  company?: string;
  domain?: string;
  xray_url?: string;
  email_candidates?: string[];
  discovery_source?: string;
}

export const OpenSourcing: FC<OpenSourcingProps> = ({
  onBridgeToWaterfall,
  setActiveTab
}) => {
  const [activeTab, setSubTab] = useState<'local' | 'venture' | 'hiring' | 'executives'>('local');
  const [error, setError] = useState('');
  const [savedDeals, setSavedDeals] = useState<Record<string, boolean>>({});

  // 1. Google Maps / OSM State
  const [selectedService, setSelectedService] = useState(SERVICE_PRESETS[0]);
  const [isCustomService, setIsCustomService] = useState(false);
  const [gmapsQuery, setGmapsQuery] = useState(SERVICE_PRESETS[0]);

  const [selectedGeo, setSelectedGeo] = useState(GEO_PRESETS[0]);
  const [isCustomGeo, setIsCustomGeo] = useState(false);
  const [gmapsLocation, setGmapsLocation] = useState(GEO_PRESETS[0]);

  const [gmapsLoading, setGmapsLoading] = useState(false);
  const [gmapsResults, setGmapsResults] = useState<GoogleMapsLead[]>([]);

  // 2. SEC EDGAR Venture State
  const [ventureLoading, setVentureLoading] = useState(false);
  const [ventureResults, setVentureResults] = useState<VentureLead[]>([]);

  // 3. Hacker News & Tech Hiring State
  const [hiringKeyword, setHiringKeyword] = useState('React');
  const [hiringLoading, setHiringLoading] = useState(false);
  const [hiringResults, setHiringResults] = useState<HiringLead[]>([]);

  // 4. Executive & LinkedIn X-Ray State
  const [selectedCompanyOption, setSelectedCompanyOption] = useState('');
  const [isCustomCompany, setIsCustomCompany] = useState(false);
  const [liCompany, setLiCompany] = useState('');

  const [selectedRoleOption, setSelectedRoleOption] = useState(ROLE_PRESETS[0].value);
  const [isCustomRole, setIsCustomRole] = useState(false);
  const [liTitles, setLiTitles] = useState(ROLE_PRESETS[0].value);

  const [liLoading, setLiLoading] = useState(false);
  const [liResults, setLiResults] = useState<ExecutiveProfile[]>([]);

  // Save deal directly into Sovereign CRM Kanban
  const saveToCRM = async (companyName: string, domain: string, dealVal: number, notes: string, keyId: string) => {
    try {
      const res = await apiFetch('/api/pipeline/deals/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: companyName,
          domain: domain || `${companyName.toLowerCase().replace(/[^a-z0-9]/g, '')}.com`,
          deal_value: dealVal || 4500,
          stage: 'sourced',
          notes: notes || 'Sourced via Sovereign Multi-Source Engine'
        })
      });
      if (res.ok) {
        setSavedDeals((prev) => ({ ...prev, [keyId]: true }));
      }
    } catch {
      // Ignore
    }
  };

  // Handlers
  const handleRunGmaps = async () => {
    setGmapsLoading(true);
    setError('');
    const targetQuery = isCustomService ? gmapsQuery : selectedService;
    const targetLoc = isCustomGeo ? gmapsLocation : selectedGeo;
    try {
      const res = await apiFetch('/api/hunt/local', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: targetQuery,
          city: targetLoc,
          limit: 8,
          provider: 'osm'
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      const mappedLeads: GoogleMapsLead[] = (data.results || []).map((r: any) => ({
        company_name: r.name,
        domain: r.domain || (r.website ? r.website.replace(/^https?:\/\//, '').split('/')[0] : `${r.name.toLowerCase().replace(/[^a-z0-9]/g, '')}.com`),
        phone: r.phone || 'Local Business',
        address: r.address || targetLoc,
        rating: r.rating || (r.score ? Number((r.score / 20).toFixed(1)) : 4.8),
        reviews_count: r.reviews || 15,
        place_id: r.place_id,
        website: r.website
      }));
      setGmapsResults(mappedLeads);
    } catch (e) {
      setGmapsResults([]);
      setError(e instanceof Error ? e.message : 'Could not reach the API.');
    } finally {
      setGmapsLoading(false);
    }
  };

  const handleFetchVentureRounds = async () => {
    setVentureLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/sourcing/venture/sec_edgar?limit=15');
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setVentureResults(data.leads || []);
    } catch (e) {
      setVentureResults([]);
      setError(e instanceof Error ? e.message : 'Could not reach the SEC EDGAR API.');
    } finally {
      setVentureLoading(false);
    }
  };

  const handleFetchHiringSignals = async () => {
    setHiringLoading(true);
    setError('');
    try {
      const res = await apiFetch(`/api/sourcing/hiring/signals?query=${encodeURIComponent(hiringKeyword)}&limit=15`);
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setHiringResults(data.leads || []);
    } catch (e) {
      setHiringResults([]);
      setError(e instanceof Error ? e.message : 'Could not reach the hiring signals API.');
    } finally {
      setHiringLoading(false);
    }
  };

  const handleRunLinkedIn = async (overrideComp?: string) => {
    setLiLoading(true);
    setError('');
    const targetCompany = overrideComp || (isCustomCompany ? liCompany : selectedCompanyOption);
    const targetTitles = isCustomRole ? liTitles : selectedRoleOption;
    try {
      const res = await apiFetch('/api/sourcing/xray_people', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: targetCompany,
          titles: targetTitles.split(',').map((t: string) => t.trim()),
          location: 'United States',
          limit: 5
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      setLiResults(data.profiles || []);
    } catch (e) {
      setLiResults([]);
      setError(e instanceof Error ? e.message : 'Could not reach the API.');
    } finally {
      setLiLoading(false);
    }
  };

  const handle1ClickLinkedInBridge = (companyName: string) => {
    setSelectedCompanyOption(companyName);
    setIsCustomCompany(false);
    setLiCompany(companyName);
    setSubTab('executives');
    handleRunLinkedIn(companyName);
  };

  const inputClass = 'w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500';

  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />

      {/* Header and Sub-Tab Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Sovereign Multi-Channel Lead Ingestion</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              ZERO-COST OSINT
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Ingest local businesses, venture-funded startups, engineering hiring bottlenecks, and decision makers with zero paid APIs.
          </p>
        </div>

        {/* Mode Switcher Tabs */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-900/90 border border-slate-800 self-start md:self-auto overflow-x-auto">
          <button
            onClick={() => setSubTab('local')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition whitespace-nowrap ${
              activeTab === 'local' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <MapPin className="h-3.5 w-3.5" />
            <span>Local Market</span>
          </button>
          <button
            onClick={() => {
              setSubTab('venture');
              if (ventureResults.length === 0) handleFetchVentureRounds();
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition whitespace-nowrap ${
              activeTab === 'venture' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Rocket className="h-3.5 w-3.5 text-amber-400" />
            <span>SEC Form D Venture</span>
          </button>
          <button
            onClick={() => {
              setSubTab('hiring');
              if (hiringResults.length === 0) handleFetchHiringSignals();
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition whitespace-nowrap ${
              activeTab === 'hiring' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Flame className="h-3.5 w-3.5 text-rose-400" />
            <span>HN Hiring Intent</span>
          </button>
          <button
            onClick={() => setSubTab('executives')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition whitespace-nowrap ${
              activeTab === 'executives' ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <UserCheck className="h-3.5 w-3.5" />
            <span>Decision Makers</span>
          </button>
        </div>
      </div>

      {/* ==================== TAB 1: LOCAL BUSINESS HUNT ==================== */}
      {activeTab === 'local' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bento-tile specular-border rounded-2xl p-5 border border-slate-800 space-y-4">
            <div className="flex items-center space-x-2">
              <MapPin className="h-5 w-5 text-emerald-400" />
              <h3 className="text-sm font-semibold text-white">Local Target Search Parameters</h3>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 font-medium">Industry Niche</label>
                <div className="flex gap-2 mt-1">
                  <select
                    value={isCustomService ? '__custom__' : selectedService}
                    onChange={(e) => {
                      if (e.target.value === '__custom__') setIsCustomService(true);
                      else {
                        setIsCustomService(false);
                        setSelectedService(e.target.value);
                      }
                    }}
                    className={inputClass}
                  >
                    {SERVICE_PRESETS.map((s) => <option key={s} value={s}>{s}</option>)}
                    <option value="__custom__">+ Custom Industry Query…</option>
                  </select>
                </div>
                {isCustomService && (
                  <input
                    value={gmapsQuery}
                    onChange={(e) => setGmapsQuery(e.target.value)}
                    placeholder="e.g. Commercial Roofing or Dental Clinic"
                    className={`${inputClass} mt-2`}
                  />
                )}
              </div>

              <div>
                <label className="text-xs text-slate-400 font-medium">City / Territory</label>
                <div className="flex gap-2 mt-1">
                  <select
                    value={isCustomGeo ? '__custom__' : selectedGeo}
                    onChange={(e) => {
                      if (e.target.value === '__custom__') setIsCustomGeo(true);
                      else {
                        setIsCustomGeo(false);
                        setSelectedGeo(e.target.value);
                      }
                    }}
                    className={inputClass}
                  >
                    {GEO_PRESETS.map((g) => <option key={g} value={g}>{g}</option>)}
                    <option value="__custom__">+ Custom City…</option>
                  </select>
                </div>
                {isCustomGeo && (
                  <input
                    value={gmapsLocation}
                    onChange={(e) => setGmapsLocation(e.target.value)}
                    placeholder="e.g. Chicago, IL or Manchester, UK"
                    className={`${inputClass} mt-2`}
                  />
                )}
              </div>

              <button
                onClick={handleRunGmaps}
                disabled={gmapsLoading}
                className="w-full flex items-center justify-center space-x-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-2.5 text-xs shadow-lg shadow-emerald-600/20 transition disabled:opacity-50 mt-2"
              >
                {gmapsLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                <span>{gmapsLoading ? 'Ingesting Local Market…' : 'Hunt Local Enterprises'}</span>
              </button>
            </div>
          </div>

          {/* Results Column */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                Discovered Accounts ({gmapsResults.length})
              </span>
              <span className="text-xs text-slate-500 font-mono">OpenStreetMap + Nominatim</span>
            </div>

            {gmapsResults.length === 0 ? (
              <div className="bento-tile specular-border rounded-2xl p-8 border border-slate-800 text-center text-xs text-slate-500">
                Configure your industry niche and click "Hunt Local Enterprises" to stream live accounts.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[580px] overflow-y-auto pr-1">
                {gmapsResults.map((lead, idx) => (
                  <div key={idx} className="bento-tile-interactive specular-border rounded-xl p-3.5 border border-slate-800/90 bg-slate-950/70 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="text-xs font-bold text-white">{lead.company_name}</h4>
                        <div className="text-[11px] text-slate-400 truncate">{lead.address}</div>
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                          {lead.domain && <ExternalLink href={lead.domain} className="text-[11px] font-mono" />}
                          {lead.phone && lead.phone !== 'Local Business' && <CopyablePhone phone={lead.phone} />}
                        </div>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 shrink-0">
                        ⭐ {lead.rating} ({lead.reviews_count} reviews)
                      </span>
                    </div>

                    <div className="flex items-center gap-2 pt-2 border-t border-slate-800/80 text-[11px]">
                      <button
                        onClick={() => saveToCRM(lead.company_name, lead.domain, 4500, `Address: ${lead.address}`, `local_${idx}`)}
                        disabled={savedDeals[`local_${idx}`]}
                        className={`flex items-center gap-1 px-2.5 py-1 rounded-lg border text-xs font-medium transition ${
                          savedDeals[`local_${idx}`]
                            ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                            : 'bg-indigo-600/20 border-indigo-500/40 text-indigo-200 hover:bg-indigo-600/30'
                        }`}
                      >
                        {savedDeals[`local_${idx}`] ? <><Check className="h-3 w-3" /> In CRM</> : <><Building2 className="h-3 w-3" /> Save to CRM</>}
                      </button>

                      <button
                        onClick={() => {
                          onBridgeToWaterfall('Founder', 'Owner', lead.company_name, lead.domain);
                          setActiveTab('waterfall');
                        }}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs transition"
                      >
                        <span>Waterfall</span>
                        <ArrowRight className="h-3 w-3" />
                      </button>

                      <button
                        onClick={() => handle1ClickLinkedInBridge(lead.company_name)}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-xs transition ml-auto"
                      >
                        <UserCheck className="h-3 w-3" />
                        <span>Find Execs</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================== TAB 2: SEC EDGAR FORM D VENTURE ==================== */}
      {activeTab === 'venture' && (
        <div className="space-y-4">
          <div className="bento-tile specular-border rounded-2xl p-4 border border-amber-500/20 bg-amber-500/5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Rocket className="h-5 w-5 text-amber-400" />
                <h3 className="text-sm font-bold text-white">Live SEC EDGAR Form D Venture Capital Stream</h3>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Private funding rounds filed with the US Securities and Exchange Commission within the last 15 days. Zero-cost sovereign stream.
              </p>
            </div>
            <button
              onClick={handleFetchVentureRounds}
              disabled={ventureLoading}
              className="px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow-md shadow-amber-500/20 transition disabled:opacity-50 shrink-0 self-start sm:self-auto"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${ventureLoading ? 'animate-spin' : ''}`} />
              <span>{ventureLoading ? 'Fetching Filings…' : 'Refresh SEC Filings'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {ventureResults.map((round, idx) => (
              <div key={idx} className="bento-tile-interactive specular-border rounded-xl p-4 border border-slate-800 bg-slate-950/70 space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-xs font-bold text-white truncate" title={round.company_name}>
                    {round.company_name}
                  </h4>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-300 border border-amber-500/30 shrink-0">
                    Form {round.form_type}
                  </span>
                </div>

                <div className="text-[11px] text-slate-400 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Domain:</span>
                    <ExternalLink href={round.domain} className="font-mono text-indigo-400" />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">CIK:</span>
                    <span className="font-mono text-slate-300">{round.cik || 'Registered'}</span>
                  </div>
                  {round.filing_date && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">Filed:</span>
                      <span className="font-mono text-slate-300">{round.filing_date.split('T')[0]}</span>
                    </div>
                  )}
                  {round.filing_url && (
                    <div className="pt-0.5">
                      <ExternalLink href={round.filing_url} className="text-[10px] font-mono text-cyan-400">
                        View SEC Edgar Filing ↗
                      </ExternalLink>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-slate-800/80">
                  <button
                    onClick={() => saveToCRM(round.company_name, round.domain, 7500, `SEC Form D Round | CIK: ${round.cik}`, `sec_${idx}`)}
                    disabled={savedDeals[`sec_${idx}`]}
                    className={`flex-1 flex items-center justify-center gap-1 py-1 rounded-lg border text-xs font-medium transition ${
                      savedDeals[`sec_${idx}`]
                        ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                        : 'bg-indigo-600/20 border-indigo-500/40 text-indigo-200 hover:bg-indigo-600/30'
                    }`}
                  >
                    {savedDeals[`sec_${idx}`] ? <><Check className="h-3 w-3" /> In CRM</> : <><Building2 className="h-3 w-3" /> Save CRM</>}
                  </button>

                  <button
                    onClick={() => {
                      onBridgeToWaterfall('Founder', 'CEO', round.company_name, round.domain);
                      setActiveTab('waterfall');
                    }}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs transition"
                    title="Bridge to Waterfall"
                  >
                    <ArrowRight className="h-3 w-3" />
                  </button>

                  {round.filing_url && (
                    <a
                      href={round.filing_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-white transition"
                      title="View Official SEC Filing Document"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ==================== TAB 3: HACKER NEWS TECH HIRING ==================== */}
      {activeTab === 'hiring' && (
        <div className="space-y-4">
          <div className="bento-tile specular-border rounded-2xl p-4 border border-rose-500/20 bg-rose-500/5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Flame className="h-5 w-5 text-rose-400" />
                <h3 className="text-sm font-bold text-white">Live Hacker News Engineering Intent Stream</h3>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Real engineering bottlenecks and hiring needs posted directly by founders and CTOs on "Who is hiring?".
              </p>
            </div>

            <div className="flex items-center gap-2">
              <input
                value={hiringKeyword}
                onChange={(e) => setHiringKeyword(e.target.value)}
                placeholder="Filter by skill, e.g. React, Python"
                className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
              <button
                onClick={handleFetchHiringSignals}
                disabled={hiringLoading}
                className="px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-md shadow-rose-600/20 transition disabled:opacity-50 shrink-0"
              >
                <Search className="h-3.5 w-3.5" />
                <span>Filter</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {hiringResults.map((job, idx) => (
              <div key={idx} className="bento-tile-interactive specular-border rounded-xl p-4 border border-slate-800 bg-slate-950/70 space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="text-xs font-bold text-white">{job.company_name}</h4>
                    <div className="flex flex-wrap items-center gap-2 mt-0.5">
                      <ExternalLink href={job.domain} className="text-[11px] font-mono" />
                      {job.application_url && (
                        <ExternalLink href={job.application_url} className="text-[10px] text-cyan-400 font-mono">
                          View Post ↗
                        </ExternalLink>
                      )}
                    </div>
                    <div className="text-[11px] text-indigo-400 font-medium mt-1">{job.opportunity_title}</div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/10 text-rose-300 border border-rose-500/30 shrink-0">
                    Hiring Pain
                  </span>
                </div>

                {job.skills_required && job.skills_required.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {job.skills_required.slice(0, 5).map((sk, sidx) => (
                      <span key={sidx} className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-900 border border-slate-800 text-slate-300">
                        {sk}
                      </span>
                    ))}
                  </div>
                )}

                <div className="flex items-center gap-2 pt-2 border-t border-slate-800/80">
                  <button
                    onClick={() => saveToCRM(job.company_name, job.domain, 6000, `Hiring Intent: ${job.opportunity_title}`, `hn_${idx}`)}
                    disabled={savedDeals[`hn_${idx}`]}
                    className={`flex-1 flex items-center justify-center gap-1 py-1 rounded-lg border text-xs font-medium transition ${
                      savedDeals[`hn_${idx}`]
                        ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                        : 'bg-indigo-600/20 border-indigo-500/40 text-indigo-200 hover:bg-indigo-600/30'
                    }`}
                  >
                    {savedDeals[`hn_${idx}`] ? <><Check className="h-3 w-3" /> In CRM</> : <><Building2 className="h-3 w-3" /> Save CRM</>}
                  </button>

                  <button
                    onClick={() => {
                      onBridgeToWaterfall('VP', 'Engineering', job.company_name, job.domain);
                      setActiveTab('waterfall');
                    }}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs transition"
                  >
                    <span>Waterfall</span>
                    <ArrowRight className="h-3 w-3" />
                  </button>

                  {job.application_url && (
                    <a
                      href={job.application_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-white transition"
                      title="View Job Post"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ==================== TAB 4: EXECUTIVE DISCOVERY ==================== */}
      {activeTab === 'executives' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bento-tile specular-border rounded-2xl p-5 border border-slate-800 space-y-4">
            <div className="flex items-center space-x-2">
              <UserCheck className="h-5 w-5 text-indigo-400" />
              <h3 className="text-sm font-semibold text-white">Target Executive Criteria</h3>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 font-medium">Company Name</label>
                <div className="flex gap-2 mt-1">
                  <select
                    value={isCustomCompany ? '__custom__' : selectedCompanyOption}
                    onChange={(e) => {
                      if (e.target.value === '__custom__') setIsCustomCompany(true);
                      else {
                        setIsCustomCompany(false);
                        setSelectedCompanyOption(e.target.value);
                      }
                    }}
                    className={inputClass}
                  >
                    <option value="">Select Curated Tech Company…</option>
                    {CURATED_TECH_COMPANIES.map((c) => (
                      <option key={c.domain} value={c.name}>
                        {c.name} ({c.domain})
                      </option>
                    ))}
                    <option value="__custom__">+ Enter Custom Company…</option>
                  </select>
                </div>
                {isCustomCompany && (
                  <input
                    value={liCompany}
                    onChange={(e) => setLiCompany(e.target.value)}
                    placeholder="e.g. Acme Corp or Deel"
                    className={`${inputClass} mt-2`}
                  />
                )}
              </div>

              <div>
                <label className="text-xs text-slate-400 font-medium">Decision Maker Titles</label>
                <div className="flex gap-2 mt-1">
                  <select
                    value={isCustomRole ? '__custom__' : selectedRoleOption}
                    onChange={(e) => {
                      if (e.target.value === '__custom__') setIsCustomRole(true);
                      else {
                        setIsCustomRole(false);
                        setSelectedRoleOption(e.target.value);
                      }
                    }}
                    className={inputClass}
                  >
                    {ROLE_PRESETS.map((r) => <option key={r.label} value={r.value}>{r.label}</option>)}
                    <option value="__custom__">+ Enter Custom Roles…</option>
                  </select>
                </div>
                {isCustomRole && (
                  <input
                    value={liTitles}
                    onChange={(e) => setLiTitles(e.target.value)}
                    placeholder="e.g. CTO, VP Engineering, Founder"
                    className={`${inputClass} mt-2`}
                  />
                )}
              </div>

              <button
                onClick={() => handleRunLinkedIn()}
                disabled={liLoading || (!selectedCompanyOption && !liCompany)}
                className="w-full flex items-center justify-center space-x-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 text-xs shadow-lg shadow-indigo-600/20 transition disabled:opacity-50 mt-2"
              >
                {liLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                <span>{liLoading ? 'Discovering Leadership Team…' : 'Discover Executives'}</span>
              </button>
            </div>
          </div>

          {/* Results Column */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                Leadership Team &amp; X-Ray Profiles ({liResults.length})
              </span>
              <span className="text-xs text-slate-500 font-mono">1-Click Google X-Ray</span>
            </div>

            {liResults.length === 0 ? (
              <div className="bento-tile specular-border rounded-2xl p-8 border border-slate-800 text-center text-xs text-slate-500">
                Select a target company and run discovery to extract executive profiles and email permutations.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[580px] overflow-y-auto pr-1">
                {liResults.map((prof, idx) => (
                  <div key={idx} className="bento-tile-interactive specular-border rounded-xl p-3.5 border border-slate-800/90 bg-slate-950/70 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                          <span>{prof.first_name} {prof.last_name}</span>
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                            {prof.discovery_source === 'website_dom_crawler' ? 'DOM Verified' : 'X-Ray Target'}
                          </span>
                        </h4>
                        <div className="text-[11px] text-slate-300 mt-0.5">{prof.title}</div>
                        <div className="text-[10px] text-slate-500">{prof.location}</div>
                      </div>

                      {prof.linkedin_url && (
                        <ExternalLink
                          href={prof.linkedin_url}
                          className="px-2 py-1 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-800 text-indigo-400 hover:text-indigo-300 text-[10px] font-mono shrink-0"
                          title="Open 1-Click Profile on Google"
                        >
                          Profile
                        </ExternalLink>
                      )}
                    </div>

                    {prof.email_candidates && prof.email_candidates.length > 0 && (
                      <div className="flex items-center gap-1.5 pt-0.5">
                        <span className="text-[10px] font-mono text-slate-500">Email:</span>
                        <CopyableEmail email={prof.email_candidates[0]} />
                      </div>
                    )}

                    <div className="flex items-center gap-2 pt-2 border-t border-slate-800/80">
                      <button
                        onClick={() => {
                          onBridgeToWaterfall(prof.first_name, prof.last_name, prof.company || '', prof.domain || '');
                          setActiveTab('waterfall');
                        }}
                        className="flex-1 flex items-center justify-center gap-1 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition"
                      >
                        <Sparkles className="h-3 w-3" />
                        <span>Enrich in Waterfall</span>
                        <ArrowRight className="h-3 w-3 ml-0.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
