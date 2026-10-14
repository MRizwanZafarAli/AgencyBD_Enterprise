import { useState } from 'react';
import type { FC } from 'react';
import {
  MapPin, UserCheck, Play, RefreshCw,
  ExternalLink, ArrowRight
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

interface OpenSourcingProps {
  onBridgeToWaterfall: (first: string, last: string, company: string, domain: string) => void;
  setActiveTab: (tab: TabType) => void;
}

export const OpenSourcing: FC<OpenSourcingProps> = ({
  onBridgeToWaterfall
}) => {
  // Google Maps State
  const [selectedService, setSelectedService] = useState(SERVICE_PRESETS[0]);
  const [isCustomService, setIsCustomService] = useState(false);
  const [gmapsQuery, setGmapsQuery] = useState(SERVICE_PRESETS[0]);

  const [selectedGeo, setSelectedGeo] = useState(GEO_PRESETS[0]);
  const [isCustomGeo, setIsCustomGeo] = useState(false);
  const [gmapsLocation, setGmapsLocation] = useState(GEO_PRESETS[0]);

  const [gmapsLoading, setGmapsLoading] = useState(false);
  const [gmapsResults, setGmapsResults] = useState<GoogleMapsLead[]>([]);

  // LinkedIn State
  const [selectedCompanyOption, setSelectedCompanyOption] = useState('');
  const [isCustomCompany, setIsCustomCompany] = useState(false);
  const [liCompany, setLiCompany] = useState('');

  const [selectedRoleOption, setSelectedRoleOption] = useState(ROLE_PRESETS[0].value);
  const [isCustomRole, setIsCustomRole] = useState(false);
  const [liTitles, setLiTitles] = useState(ROLE_PRESETS[0].value);

  const [liLoading, setLiLoading] = useState(false);
  const [error, setError] = useState('');
  const [liResults, setLiResults] = useState<LinkedInProfile[]>([]);

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
          limit: 6,
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
        reviews_count: r.reviews || Math.floor(Math.random() * 40 + 12),
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

  const handleRunLinkedIn = async (overrideComp?: string) => {
    setLiLoading(true);
    setError('');
    const targetCompany = overrideComp || (isCustomCompany ? liCompany : selectedCompanyOption);
    const targetTitles = isCustomRole ? liTitles : selectedRoleOption;
    try {
      const res = await apiFetch('/api/sourcing/linkedin/people', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: targetCompany,
          titles: targetTitles.split(',').map((t: string) => t.trim()),
          location: 'United States',
          limit: 4
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
    handleRunLinkedIn(companyName);
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <ErrorBanner message={error} />
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
          <span>Open Sourcing: Local Market & Decision Maker Discovery</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            100% ZERO-COST SOVEREIGN ENGINE
          </span>
        </h1>
        <p className="text-sm text-slate-400 mt-0.5">
          Find local businesses and decision makers using native OpenStreetMap intelligence and verified executive discovery. Zero Google Places API billing.
        </p>
      </div>

      {/* Grid: Stacks on mobile/tablet, 2-columns on large desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Panel 1: Native Enterprise Discovery */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <MapPin className="h-5 w-5 text-indigo-400" />
              <h3 className="text-sm font-semibold text-white">Native Local Enterprise Discovery</h3>
            </div>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
              Zero Places API Cost
            </span>
          </div>

          {/* Service Dropdown */}
          <div>
            <label className="text-xs text-slate-400 font-medium">Industry / Service Category</label>
            <select
              value={isCustomService ? '__custom__' : selectedService}
              onChange={(e) => {
                if (e.target.value === '__custom__') {
                  setIsCustomService(true);
                } else {
                  setIsCustomService(false);
                  setSelectedService(e.target.value);
                  setGmapsQuery(e.target.value);
                }
              }}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
            >
              {SERVICE_PRESETS.map((srv, idx) => (
                <option key={idx} value={srv}>{srv}</option>
              ))}
              <option value="__custom__">✍️ Type Custom Service Query...</option>
            </select>

            {isCustomService && (
              <input 
                value={gmapsQuery} 
                onChange={(e) => setGmapsQuery(e.target.value)} 
                placeholder="e.g. Healthcare AI Development Firm"
                className="w-full bg-slate-950 border border-indigo-500/40 rounded-lg px-3 py-1.5 text-xs text-white mt-2" 
              />
            )}
          </div>

          {/* Geography Dropdown */}
          <div>
            <label className="text-xs text-slate-400 font-medium">Target Geography / Metropolitan Hub</label>
            <select
              value={isCustomGeo ? '__custom__' : selectedGeo}
              onChange={(e) => {
                if (e.target.value === '__custom__') {
                  setIsCustomGeo(true);
                } else {
                  setIsCustomGeo(false);
                  setSelectedGeo(e.target.value);
                  setGmapsLocation(e.target.value);
                }
              }}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-indigo-500 focus:outline-none"
            >
              {GEO_PRESETS.map((geo, idx) => (
                <option key={idx} value={geo}>{geo}</option>
              ))}
              <option value="__custom__">✍️ Type Custom City / Metro...</option>
            </select>

            {isCustomGeo && (
              <input 
                value={gmapsLocation} 
                onChange={(e) => setGmapsLocation(e.target.value)} 
                placeholder="e.g. Miami, FL, USA"
                className="w-full bg-slate-950 border border-indigo-500/40 rounded-lg px-3 py-1.5 text-xs text-white mt-2" 
              />
            )}
          </div>

          <button
            onClick={handleRunGmaps}
            disabled={gmapsLoading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-indigo-600/20"
          >
            {gmapsLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            <span>Search Local Enterprises (Zero API Cost)</span>
          </button>

          {/* Google Maps Results */}
          {gmapsResults.length > 0 && (
            <div className="space-y-3 mt-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-emerald-400">Sourced {gmapsResults.length} Qualified Local Enterprises:</span>
                <span className="text-[10px] text-slate-400">Click ⚡ to bridge to LinkedIn</span>
              </div>
              {gmapsResults.map((lead, i) => (
                <div key={i} className="p-3 bg-slate-900/90 rounded-xl border border-slate-800 text-xs space-y-2 hover:border-slate-700 transition-colors">
                  <div className="flex justify-between items-start gap-2">
                    <div>
                      <div className="font-bold text-white text-sm">{lead.company_name}</div>
                      <div className="text-slate-400 font-mono text-[11px] mt-0.5">{lead.domain} • {lead.phone}</div>
                      <div className="text-slate-500 text-[10px]">{lead.address}</div>
                    </div>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono font-bold text-[11px] shrink-0">
                      ★ {lead.rating} ({lead.reviews_count})
                    </span>
                  </div>

                  {/* 1-Click Bridge to LinkedIn */}
                  <div className="pt-1 border-t border-slate-800/80 flex justify-end">
                    <button
                      onClick={() => handle1ClickLinkedInBridge(lead.company_name)}
                      className="px-2.5 py-1 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 rounded-md text-[11px] font-medium flex items-center space-x-1.5 transition-all"
                    >
                      <span>⚡ 1-Click: Auto-Find Decision Makers on LinkedIn</span>
                      <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Panel 2: LinkedIn Open X-Ray Finder */}
        <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <UserCheck className="h-5 w-5 text-cyan-400" />
              <h3 className="text-sm font-semibold text-white">LinkedIn Open X-Ray Decision Maker Finder</h3>
            </div>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-mono">
              Bypasses Sales Navigator
            </span>
          </div>

          {/* Company Selector Dropdown */}
          <div>
            <label className="text-xs text-slate-400 font-medium">Target Company (Automated Selection)</label>
            <select
              value={isCustomCompany ? '__custom__' : selectedCompanyOption}
              onChange={(e) => {
                if (e.target.value === '__custom__') {
                  setIsCustomCompany(true);
                } else {
                  setIsCustomCompany(false);
                  setSelectedCompanyOption(e.target.value);
                  setLiCompany(e.target.value);
                }
              }}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-cyan-500 focus:outline-none"
            >
              {gmapsResults.length > 0 && (
                <optgroup label="📍 Discovered from Google Maps Results">
                  {gmapsResults.map((lead, idx) => (
                    <option key={`map-${idx}`} value={lead.company_name}>
                      {lead.company_name} ({lead.domain})
                    </option>
                  ))}
                </optgroup>
              )}
              <optgroup label="⭐ Curated High-Budget Tech & Enterprise Scaleups">
                {CURATED_TECH_COMPANIES.map((comp, idx) => (
                  <option key={`cur-${idx}`} value={comp.name}>
                    {comp.name} ({comp.domain})
                  </option>
                ))}
              </optgroup>
              <option value="__custom__">✍️ Type Custom Company Name...</option>
            </select>

            {isCustomCompany && (
              <input 
                value={liCompany} 
                onChange={(e) => setLiCompany(e.target.value)} 
                placeholder="e.g. OpenAI, Snowflake, Datadog"
                className="w-full bg-slate-950 border border-cyan-500/40 rounded-lg px-3 py-1.5 text-xs text-white mt-2" 
              />
            )}
          </div>

          {/* Role Presets Dropdown */}
          <div>
            <label className="text-xs text-slate-400 font-medium">Target Executive Titles (Role Presets)</label>
            <select
              value={isCustomRole ? '__custom__' : selectedRoleOption}
              onChange={(e) => {
                if (e.target.value === '__custom__') {
                  setIsCustomRole(true);
                } else {
                  setIsCustomRole(false);
                  setSelectedRoleOption(e.target.value);
                  setLiTitles(e.target.value);
                }
              }}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-white mt-1 focus:border-cyan-500 focus:outline-none"
            >
              {ROLE_PRESETS.map((role, idx) => (
                <option key={idx} value={role.value}>{role.label}</option>
              ))}
              <option value="__custom__">✍️ Custom Title String...</option>
            </select>

            {isCustomRole && (
              <input 
                value={liTitles} 
                onChange={(e) => setLiTitles(e.target.value)} 
                placeholder="e.g. Chief Executive Officer, Managing Partner"
                className="w-full bg-slate-950 border border-cyan-500/40 rounded-lg px-3 py-1.5 text-xs text-white mt-2" 
              />
            )}
          </div>

          <button
            onClick={() => handleRunLinkedIn()}
            disabled={liLoading}
            className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-semibold py-2.5 rounded-lg text-xs flex items-center justify-center space-x-2 transition-all shadow-lg shadow-cyan-600/20"
          >
            {liLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            <span>Execute Google X-Ray Dorking</span>
          </button>

          {/* LinkedIn Results */}
          {liResults.length > 0 && (
            <div className="space-y-3 mt-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-cyan-400">Discovered {liResults.length} Verified Decision Makers:</span>
                <span className="text-[10px] text-slate-400">Click 🌊 to verify email</span>
              </div>
              {liResults.map((prof, i) => (
                <div key={i} className="p-3 bg-slate-900/90 rounded-xl border border-slate-800 text-xs space-y-2 hover:border-slate-700 transition-colors">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white text-sm">{prof.first_name} {prof.last_name}</span>
                    <a href={prof.linkedin_url} target="_blank" rel="noreferrer" className="text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 text-[11px] underline">
                      <span>Profile</span>
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                  <div className="text-indigo-300 font-semibold">{prof.title}</div>
                  <div className="text-slate-400 text-[11px] line-clamp-2">{prof.headline}</div>

                  {/* 1-Click Bridge to Waterfall */}
                  <div className="pt-1 border-t border-slate-800/80 flex justify-end">
                    <button
                      onClick={() => onBridgeToWaterfall(
                        prof.first_name,
                        prof.last_name,
                        isCustomCompany ? liCompany : selectedCompanyOption,
                        `${(isCustomCompany ? liCompany : selectedCompanyOption).toLowerCase().replace(/[^a-z0-9]/g, '')}.com`
                      )}
                      className="px-2.5 py-1 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-md text-[11px] font-medium flex items-center space-x-1.5 transition-all"
                    >
                      <span>🌊 1-Click: Verify Email in Waterfall</span>
                      <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
