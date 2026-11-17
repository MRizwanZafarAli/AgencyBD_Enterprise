import { useState, useEffect } from 'react';
import type { FC } from 'react';
import { 
  Globe, 
  ExternalLink, 
  RotateCw, 
  ShieldAlert, 
  CheckCircle2, 
  FileText, 
  Eye, 
  Copy, 
  Check, 
  X, 
  Cpu, 
  Zap, 
  Sparkles,
  Radar,
  ShieldCheck,
  AlertTriangle,
  Layers
} from 'lucide-react';
import { Button } from '../ui';
import { apiFetch } from '../../lib/api';

export type ScraperMode = 'general' | 'client_audit' | 'job_spec' | 'local_audit';

export interface InteractiveBrowserSidepanelProps {
  isOpen: boolean;
  onClose: () => void;
  initialUrl?: string;
  mode?: ScraperMode;
  contextTitle?: string;
}

interface NavigationData {
  status: string;
  session_id: string;
  current_url: string;
  current_domain: string;
  title: string;
  detected_stack: string[];
  emails: string[];
  phones: string[];
  viewport_screenshot: string | null;
  challenge_detected: boolean;
  challenge_type: string | null;
}

interface ScrapeData {
  url: string;
  domain: string;
  title: string;
  fit_markdown: string;
  compression_ratio: number;
  extracted_data: {
    emails?: string[];
    phones?: string[];
    detected_stack?: string[];
    leadership_mentions?: string[];
    pricing_signals?: string[];
    open_roles?: string[];
  };
  developer_audit?: {
    health_score?: number;
    cms_frameworks?: string[];
    seo_audit?: {
      has_title?: boolean;
      title_length?: number;
      has_meta_description?: boolean;
      has_og_image?: boolean;
      has_viewport?: boolean;
      has_canonical?: boolean;
    };
    technical_gaps?: string[];
    recommended_hook?: string;
  };
}

const MODE_CONFIG: Record<ScraperMode, { label: string; badge: string; color: string; desc: string }> = {
  general: {
    label: 'Universal Scraper',
    badge: '⚡ UNIVERSAL SCRAPER',
    color: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    desc: 'Sovereign Chromium engine · Crawl4AI Fit-Markdown · Human-in-the-Loop bridge',
  },
  client_audit: {
    label: 'Client Technical Audit',
    badge: '🔬 CLIENT SITE AUDIT',
    color: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40',
    desc: 'Deep scraping client site for full developer technical audit (tech stack, architecture, broken elements, Fit-Markdown).',
  },
  job_spec: {
    label: 'Job & RFP Spec Scraper',
    badge: '💼 JOB & RFP SPECS',
    color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
    desc: 'Scraping job requirements, candidate tech stack, compensation signals, and company pain points.',
  },
  local_audit: {
    label: 'Local Business Scan',
    badge: '📍 LOCAL BUSINESS SCAN',
    color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    desc: 'Scraping local website for booking flows, phone numbers, contact info, and website absence/gaps.',
  },
};

export const InteractiveBrowserSidepanel: FC<InteractiveBrowserSidepanelProps> = ({
  isOpen,
  onClose,
  initialUrl = 'stripe.com',
  mode = 'general',
  contextTitle,
}) => {
  const [url, setUrl] = useState(initialUrl);
  const [loading, setLoading] = useState(false);
  const [launchingHeaded, setLaunchingHeaded] = useState(false);
  const [activeTab, setActiveTab] = useState<'preview' | 'markdown' | 'entities' | 'expert_audit'>(
    mode === 'client_audit' ? 'expert_audit' : mode === 'job_spec' ? 'markdown' : 'preview'
  );
  const [navData, setNavData] = useState<NavigationData | null>(null);
  const [scrapeData, setScrapeData] = useState<ScrapeData | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedHook, setCopiedHook] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [radarActive, setRadarActive] = useState(false);
  const [radarState, setRadarState] = useState<'idle' | 'watching' | 'cleared' | 'resuming' | 'completed' | 're_challenged'>('idle');
  const [challengeCount, setChallengeCount] = useState(1);

  // Auto-navigate and sync whenever opened or target changed
  useEffect(() => {
    if (isOpen && initialUrl && initialUrl.trim()) {
      setUrl(initialUrl);
      if (mode === 'client_audit') setActiveTab('expert_audit');
      else if (mode === 'job_spec') setActiveTab('markdown');
      else if (mode === 'local_audit') setActiveTab('entities');
      handleNavigate(initialUrl);
    }
  }, [isOpen, initialUrl, mode]);

  // Intelligent Bot Barrier Clearance & Auto-Resume Poller
  useEffect(() => {
    let interval: number | null = null;
    const isChallenged = navData?.challenge_detected;
    if (isChallenged && isOpen) {
      setRadarActive(true);
      setRadarState('watching');
      interval = window.setInterval(async () => {
        try {
          const targetUrl = navData?.current_url || `https://${url}`;
          const res = await apiFetch(`/api/v1/browser/session/clearance-status?session_id=default_session&target=${encodeURIComponent(targetUrl)}&auto_resume=true`);
          if (res.ok) {
            const data = await res.json();
            if (data.cleared && data.resumed) {
              if (data.re_challenged) {
                setRadarState('re_challenged');
                setChallengeCount(data.challenge_count || 2);
                setStatusMessage(`Subsequent barrier detected (${data.resume_result?.challenge_type || 'Bot Wall'}). Please solve second barrier.`);
              } else {
                setRadarState('completed');
                setRadarActive(false);
                setStatusMessage('Bot barrier cleared and verified by backend! Scrape completed automatically.');
                if (data.resume_result?.result) {
                  setScrapeData(data.resume_result.result);
                  setActiveTab('markdown');
                }
                setNavData((prev) => prev ? { ...prev, challenge_detected: false, challenge_type: null } : null);
                if (interval) clearInterval(interval);
              }
            }
          }
        } catch (err) {
          console.error('Clearance radar error', err);
        }
      }, 2500);
    } else {
      setRadarActive(false);
      setRadarState('idle');
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [navData?.challenge_detected, isOpen, url]);

  const handleNavigate = async (targetOverride?: string) => {
    const target = (targetOverride || url).trim();
    if (!target) return;
    setLoading(true);
    setStatusMessage(null);

    try {
      // 1. Trigger Headless Navigation & Screenshot
      const navRes = await apiFetch('/api/v1/browser/session/navigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, session_id: 'default_session', viewport: 'desktop' }),
      });
      if (navRes.ok) {
        const data = await navRes.json();
        setNavData(data.navigation);
      }

      // 2. Trigger Sovereign Fit-Markdown Scraper
      const scrapeRes = await apiFetch('/api/v1/browser/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, mode, context_title: contextTitle }),
      });
      if (scrapeRes.ok) {
        const sData = await scrapeRes.json();
        setScrapeData(sData.result);
      }
    } catch (e: any) {
      console.error('Error during browser navigation', e);
      setStatusMessage('Navigation failed: ' + (e?.message || 'Network error'));
    } finally {
      setLoading(false);
    }
  };

  const handleLaunchNativeHeaded = async () => {
    setLaunchingHeaded(true);
    try {
      const res = await apiFetch('/api/v1/browser/session/launch-headed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: navData?.current_url || `https://${url}`, session_id: 'default_session' }),
      });
      if (res.ok) {
        setStatusMessage('Launched physical Chromium window on host for manual human intervention.');
      }
    } catch (e: any) {
      setStatusMessage('Failed to launch native window: ' + e?.message);
    } finally {
      setLaunchingHeaded(false);
    }
  };

  const handleResumeAutopilot = async () => {
    setResuming(true);
    try {
      const res = await apiFetch('/api/v1/browser/session/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: 'default_session' }),
      });
      if (res.ok) {
        setStatusMessage('Challenge marked resolved. Session state persisted to vault.');
        if (navData) {
          setNavData({ ...navData, challenge_detected: false, challenge_type: null });
        }
      }
    } catch (e: any) {
      setStatusMessage('Error resolving challenge: ' + e?.message);
    } finally {
      setResuming(false);
    }
  };

  const handleCopyMarkdown = () => {
    if (!scrapeData?.fit_markdown) return;
    navigator.clipboard.writeText(scrapeData.fit_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[560px] lg:w-[680px] bg-slate-950/95 border-l border-amber-500/30 backdrop-blur-2xl shadow-2xl flex flex-col font-sans transition-all duration-300">
      {/* Header Bar */}
      <div className="p-4 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2 flex-wrap">
              {contextTitle ? <span>{contextTitle}</span> : null}
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border flex items-center gap-1 ${MODE_CONFIG[mode]?.color || MODE_CONFIG.general.color}`}>
                {MODE_CONFIG[mode]?.badge || MODE_CONFIG.general.badge}
              </span>
              {navData?.challenge_detected ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 flex items-center gap-1">
                  <ShieldAlert className="w-3 h-3 text-rose-400" />
                  CHALLENGE DETECTED
                </span>
              ) : (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1">
                  <Zap className="w-3 h-3 text-emerald-400" />
                  HEADLESS LIVE
                </span>
              )}
            </h3>
            <p className="text-[11px] text-slate-400">
              {MODE_CONFIG[mode]?.desc || MODE_CONFIG.general.desc}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {/* Arrow Button to pop out native headed window */}
          <button
            onClick={handleLaunchNativeHeaded}
            disabled={launchingHeaded}
            title="Pop out in Native Chromium Window (for manual 2FA, Captchas or Human Touch)"
            className="p-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-amber-400 hover:text-amber-300 transition-colors flex items-center gap-1 text-xs px-2.5 font-medium shadow-sm"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Popout Window</span>
          </button>

          {/* Close drawer button */}
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* URL & Action Bar */}
      <div className="p-3 bg-slate-900/40 border-b border-slate-800/80 flex flex-col gap-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleNavigate();
          }}
          className="flex items-center gap-2"
        >
          <div className="relative flex-1">
            <Globe className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Paste website or domain (e.g. stripe.com)"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white font-mono focus:border-amber-400 outline-none"
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            disabled={loading}
            className="text-xs py-1.5 px-3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold flex items-center gap-1"
          >
            <RotateCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Scraping…' : 'Navigate'}
          </Button>

          {navData?.challenge_detected && (
            <Button
              type="button"
              variant="secondary"
              onClick={handleResumeAutopilot}
              disabled={resuming}
              className="text-xs py-1.5 px-3 bg-emerald-600/80 hover:bg-emerald-500 text-white font-bold flex items-center gap-1 border border-emerald-400/50"
            >
              <CheckCircle2 className="w-3 h-3" />
              {resuming ? 'Saving…' : 'Resume Autopilot'}
            </Button>
          )}
        </form>

        {statusMessage && (
          <div className="text-[11px] font-mono text-amber-300 px-2 py-1 rounded bg-amber-500/10 border border-amber-500/20">
            {statusMessage}
          </div>
        )}

        {/* Intelligent Bot Barrier & Live Clearance Radar Banner */}
        {navData?.challenge_detected && (
          <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/40 text-rose-200 text-xs space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-white flex items-center gap-1.5">
                    {radarState === 're_challenged' ? (
                      <span className="text-amber-300">⚠️ Subsequent Bot Barrier Detected (Attempt #{challengeCount})</span>
                    ) : (
                      <span>🛡️ AI Bot Barrier Detected: {navData.challenge_type || 'Bot Challenge'}</span>
                    )}
                  </div>
                  <p className="text-[11px] text-rose-300/80 mt-0.5">
                    Solve the challenge in the Headed Chromium window. The backend is continuously monitoring the session via native CDP and will automatically detect when the barrier is cleared, verify authentic DOM, and resume scraping.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={handleLaunchNativeHeaded}
                  className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-rose-500 text-white hover:bg-rose-400 flex items-center gap-1 shadow-sm transition"
                >
                  <ExternalLink className="w-3 h-3" />
                  Popout Window
                </button>
              </div>
            </div>

            {/* Live Clearance Radar Telemetry Strip */}
            <div className="flex items-center justify-between pt-1 border-t border-rose-900/60 text-[11px] font-mono text-slate-300">
              <div className="flex items-center gap-1.5">
                <Radar className={`w-3.5 h-3.5 text-amber-400 ${radarActive ? 'animate-spin' : ''}`} />
                <span className="text-amber-300">Clearance Radar:</span>
                <span className="text-slate-300">
                  {radarState === 'watching' && 'Monitoring CDP tab for Turnstile/Captcha clearance…'}
                  {radarState === 're_challenged' && 'Waiting for secondary challenge clearance…'}
                  {radarState === 'resuming' && 'Barrier cleared! Resuming sovereign scrape…'}
                  {radarState === 'completed' && 'Clearance verified & scrape finished.'}
                  {radarState === 'idle' && 'Idle'}
                </span>
              </div>

              <button
                type="button"
                onClick={async () => {
                  setResuming(true);
                  try {
                    const targetUrl = navData?.current_url || `https://${url}`;
                    const res = await apiFetch(`/api/v1/browser/session/clearance-status?session_id=default_session&target=${encodeURIComponent(targetUrl)}&auto_resume=true`);
                    const data = await res.json();
                    if (data.cleared && data.resumed) {
                      setStatusMessage('Barrier cleared! Scrape completed automatically.');
                      if (data.resume_result?.result) {
                        setScrapeData(data.resume_result.result);
                        setActiveTab('markdown');
                      }
                      setNavData((prev) => prev ? { ...prev, challenge_detected: false, challenge_type: null } : null);
                    } else {
                      setStatusMessage('Barrier still detected in session. Please complete challenge in the window.');
                    }
                  } finally {
                    setResuming(false);
                  }
                }}
                disabled={resuming}
                className="text-[10px] text-amber-400 hover:text-amber-200 underline font-sans"
              >
                {resuming ? 'Checking…' : 'Check Clearance Now'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-4 border-b border-slate-800 bg-slate-950/40 pt-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab('expert_audit')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'expert_audit'
              ? 'border-indigo-400 text-indigo-300 font-bold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
          Developer Audit {scrapeData?.developer_audit?.health_score ? `(${scrapeData.developer_audit.health_score}/100)` : ''}
        </button>

        <button
          onClick={() => setActiveTab('preview')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'preview'
              ? 'border-amber-400 text-amber-300 font-bold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Eye className="w-3.5 h-3.5" />
          Live View
        </button>

        <button
          onClick={() => setActiveTab('markdown')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'markdown'
              ? 'border-amber-400 text-amber-300 font-bold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          Fit-Markdown ({scrapeData ? `${scrapeData.compression_ratio}%` : '0%'})
        </button>

        <button
          onClick={() => setActiveTab('entities')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 transition-all whitespace-nowrap ${
            activeTab === 'entities'
              ? 'border-amber-400 text-amber-300 font-bold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          Entities
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* TAB 0: Expert Developer Technical Audit */}
        {activeTab === 'expert_audit' && (
          <div className="space-y-4 text-xs">
            {/* Health Score & Architecture Header */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between gap-4">
              <div>
                <span className="text-[10px] text-slate-400 uppercase font-mono tracking-wider block">
                  Developer Health Grade
                </span>
                <div className="text-2xl font-bold text-white flex items-center gap-2 mt-0.5">
                  <span className={
                    (scrapeData?.developer_audit?.health_score || 0) >= 80 ? 'text-emerald-400' :
                    (scrapeData?.developer_audit?.health_score || 0) >= 60 ? 'text-amber-400' : 'text-rose-400'
                  }>
                    {scrapeData?.developer_audit?.health_score ?? 'Pending'}
                  </span>
                  <span className="text-xs text-slate-500 font-normal">/ 100</span>
                </div>
              </div>

              <div className="text-right">
                <span className="text-[10px] text-slate-400 uppercase font-mono tracking-wider block">
                  Detected Frameworks
                </span>
                <div className="flex flex-wrap gap-1 mt-1 justify-end">
                  {scrapeData?.developer_audit?.cms_frameworks?.map((f, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 text-[11px] font-mono">
                      {f}
                    </span>
                  )) || <span className="text-slate-400 italic">None detected</span>}
                </div>
              </div>
            </div>

            {/* Recommended Cold Pitch Hook (Facts from Developer Audit) */}
            {scrapeData?.developer_audit?.recommended_hook && (
              <div className="p-3.5 rounded-xl bg-indigo-950/30 border border-indigo-500/40 text-indigo-200">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-semibold text-white flex items-center gap-1.5 text-xs">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                    Recommended Developer Hook (Facts Only)
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(scrapeData.developer_audit?.recommended_hook || '');
                      setCopiedHook(true);
                      setTimeout(() => setCopiedHook(false), 2000);
                    }}
                    className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-900/60 hover:bg-indigo-800 text-indigo-300 flex items-center gap-1 transition"
                  >
                    {copiedHook ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    {copiedHook ? 'Copied!' : 'Copy Hook'}
                  </button>
                </div>
                <p className="text-xs text-slate-300 bg-slate-950/80 p-2.5 rounded-lg border border-indigo-900/50 leading-relaxed font-mono">
                  "{scrapeData.developer_audit.recommended_hook}"
                </p>
              </div>
            )}

            {/* Identified Technical Gaps & Code Issues */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
              <h4 className="font-semibold text-white flex items-center gap-1.5 text-xs">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                Technical Gaps & Issues ({scrapeData?.developer_audit?.technical_gaps?.length || 0})
              </h4>
              {scrapeData?.developer_audit?.technical_gaps?.length ? (
                <ul className="space-y-1.5">
                  {scrapeData.developer_audit.technical_gaps.map((gap, i) => (
                    <li key={i} className="flex items-start gap-2 p-2 rounded-lg bg-slate-950/60 border border-slate-800/80 text-slate-300 text-[11px]">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0 mt-1.5" />
                      <span>{gap}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-400 italic">No critical technical gaps detected on initial scan.</p>
              )}
            </div>

            {/* Meta & SEO Architecture */}
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
              <h4 className="font-semibold text-white flex items-center gap-1.5 text-xs">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                Meta, Mobile & SEO Hygiene Checklist
              </h4>
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div className="p-2 rounded bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">Meta Title Tag:</span>
                  <span className={scrapeData?.developer_audit?.seo_audit?.has_title ? 'text-emerald-400' : 'text-rose-400'}>
                    {scrapeData?.developer_audit?.seo_audit?.has_title ? '✓ Present' : '✗ Missing'}
                  </span>
                </div>
                <div className="p-2 rounded bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">Meta Description:</span>
                  <span className={scrapeData?.developer_audit?.seo_audit?.has_meta_description ? 'text-emerald-400' : 'text-rose-400'}>
                    {scrapeData?.developer_audit?.seo_audit?.has_meta_description ? '✓ Present' : '✗ Missing'}
                  </span>
                </div>
                <div className="p-2 rounded bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">OpenGraph Image:</span>
                  <span className={scrapeData?.developer_audit?.seo_audit?.has_og_image ? 'text-emerald-400' : 'text-rose-400'}>
                    {scrapeData?.developer_audit?.seo_audit?.has_og_image ? '✓ Present' : '✗ Missing'}
                  </span>
                </div>
                <div className="p-2 rounded bg-slate-950/60 border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">Mobile Viewport:</span>
                  <span className={scrapeData?.developer_audit?.seo_audit?.has_viewport ? 'text-emerald-400' : 'text-rose-400'}>
                    {scrapeData?.developer_audit?.seo_audit?.has_viewport ? '✓ Present' : '✗ Missing'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 1: Live View */}
        {activeTab === 'preview' && (
          <div className="space-y-4">
            {navData?.viewport_screenshot ? (
              <div className="space-y-3">
                <div className="rounded-xl overflow-hidden border border-slate-800 bg-slate-950 shadow-inner relative group">
                  <img
                    src={navData.viewport_screenshot}
                    alt="Live Viewport Render"
                    className="w-full h-auto object-contain max-h-[460px]"
                  />
                  <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={handleLaunchNativeHeaded}
                      className="p-1.5 rounded-lg bg-slate-900/90 text-amber-300 border border-amber-500/40 text-xs flex items-center gap-1 backdrop-blur"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Open Full Native Chrome
                    </button>
                  </div>
                </div>

                {/* Quick Page Summary */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                    <span className="text-[10px] text-slate-400 uppercase font-mono block">Page Title</span>
                    <span className="text-white font-medium line-clamp-1">{navData.title || 'Untitled'}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                    <span className="text-[10px] text-slate-400 uppercase font-mono block">Detected Tech Stack</span>
                    <span className="text-amber-300 font-mono">
                      {navData.detected_stack?.join(', ') || 'Standard Web Stack'}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 text-slate-400 text-xs">
                {loading ? 'Rendering virtual DOM and capturing live viewport…' : 'Enter a URL and click Navigate to begin.'}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Fit-Markdown */}
        {activeTab === 'markdown' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-mono">
                Cleaned Markdown (token-optimized for LLM context windows)
              </span>
              <button
                onClick={handleCopyMarkdown}
                className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 font-mono px-2 py-1 rounded bg-slate-900 border border-slate-800 hover:border-amber-500/40"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied!' : 'Copy Markdown'}
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 max-h-[500px] overflow-y-auto whitespace-pre-wrap leading-relaxed">
              {scrapeData?.fit_markdown || 'No markdown generated yet.'}
            </div>
          </div>
        )}

        {/* TAB 3: Structured Entities */}
        {activeTab === 'entities' && (
          <div className="space-y-4 text-xs">
            {/* Leadership & Contacts */}
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <h4 className="font-semibold text-white mb-2 flex items-center gap-1.5 text-xs">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                Leadership & Team Mentions ({scrapeData?.extracted_data?.leadership_mentions?.length || 0})
              </h4>
              {scrapeData?.extracted_data?.leadership_mentions?.length ? (
                <ul className="space-y-1 text-slate-300 font-mono text-[11px]">
                  {scrapeData.extracted_data.leadership_mentions.map((lead, i) => (
                    <li key={i} className="py-1 px-2 rounded bg-slate-950/60 border border-slate-800/80">
                      {lead}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-400 italic">No direct leadership names on home page.</p>
              )}
            </div>

            {/* Pricing Tiers */}
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <h4 className="font-semibold text-white mb-2 text-xs">Pricing & Commercial Signals</h4>
              {scrapeData?.extracted_data?.pricing_signals?.length ? (
                <div className="flex flex-wrap gap-2">
                  {scrapeData.extracted_data.pricing_signals.map((p, i) => (
                    <span key={i} className="px-2 py-1 rounded bg-amber-500/10 text-amber-300 font-mono border border-amber-500/30">
                      {p}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-slate-400 italic">No standard public pricing numbers found.</p>
              )}
            </div>

            {/* Careers & Tech Signals */}
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <h4 className="font-semibold text-white mb-2 text-xs">Hiring & Engineering Pain Points</h4>
              {scrapeData?.extracted_data?.open_roles?.length ? (
                <ul className="space-y-1 text-slate-300 font-mono text-[11px]">
                  {scrapeData.extracted_data.open_roles.map((r, i) => (
                    <li key={i} className="py-1 px-2 rounded bg-slate-950/60 border border-slate-800/80">
                      {r}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-400 italic">No careers links detected on landing page.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
