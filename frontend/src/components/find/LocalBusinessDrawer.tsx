import { useEffect, useState } from 'react';
import type { FC } from 'react';
import {
  CheckCircle2,
  Copy,
  Cpu,
  ExternalLink,
  Globe,
  Mail,
  MapPin,
  MessageCircle,
  PanelRight,
  Phone,
  ShieldAlert,
  Sparkles,
  Wand2,
  XCircle,
} from 'lucide-react';
import { Badge, Button, Drawer, ScoreBar } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { normalizeUrl } from '../../lib/urls';

export type AgencyOffer = 'web_design' | 'local_seo' | 'ads' | 'ai_receptionist' | 'reputation';

export interface LocalPitch {
  angle: string | null;
  value_estimate: string | null;
  deliverables: string[];
  cold_pitch_hook: string | null;
  actionable_teardown: string[];
}

export interface LocalResult {
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
  pitch_strategy: LocalPitch | null;
  check_note?: string;
  lat?: number | null;
  lon?: number | null;
  coords_approx?: boolean;
  entity_type?: 'independent_smb' | 'public_sector' | 'chain_franchise';
  pitchability?: 'High' | 'Low';
  budget_tier?: 'High' | 'Medium' | 'Low';
  crm_status?: { lead_id: number; status: string; deal_stage: string } | null;
}

interface SavedScrape {
  id: number;
  url: string;
  domain: string;
  title: string;
  fit_markdown: string;
  extracted_data: Record<string, any>;
  developer_audit: Record<string, any>;
  status: string;
  created_at: string;
}

interface ProbeOut {
  classification: string;
  domain?: string | null;
  verified?: boolean;
  checks_performed?: string[];
  domain_suggestions?: Array<{ domain: string; status?: 'available' | 'taken' | 'unknown'; likely_available: boolean }>;
}

const STATUS: Record<string, { text: string; tone: 'bad' | 'warn' | 'neutral' }> = {
  no_website_listed: { text: 'No website', tone: 'bad' },
  no_website_in_osm: { text: 'No website recorded', tone: 'warn' },
  social_only: { text: 'Social page only', tone: 'warn' },
  domain_unreachable: { text: 'Domain dead', tone: 'bad' },
  tls_broken: { text: 'Certificate error', tone: 'bad' },
  domain_parked: { text: 'Parked domain', tone: 'bad' },
  has_site: { text: 'Has a website', tone: 'neutral' },
};

export function computeOfferScore(r: LocalResult, offer: AgencyOffer): number {
  let s = r.score;
  if (offer === 'local_seo') {
    if (r.reviews < 25) s += 15;
    if ((r.rating ?? 5) < 4.2) s += 10;
  } else if (offer === 'reputation') {
    if ((r.rating ?? 5) < 4.3) s += 20;
    if (r.reviews < 30) s += 12;
  } else if (offer === 'ai_receptionist') {
    if (r.phone) s += 15;
    if (r.reviews >= 20) s += 10;
  } else if (offer === 'ads') {
    if (r.website && r.classification === 'has_site') s += 12;
    if (r.budget_tier === 'High') s += 10;
  }
  if (r.pitchability === 'Low') s = Math.min(s, 25);
  return Math.max(0, Math.min(100, Math.round(s)));
}

export const LocalBusinessDrawer: FC<{
  openItem: LocalResult | null;
  city: string;
  category: string;
  offer: AgencyOffer;
  savedId?: number;
  onClose: () => void;
  onSave: (r: LocalResult) => void;
  onOpenScraper?: (url: string, mode?: 'general' | 'client_audit' | 'job_spec' | 'local_audit', title?: string) => void;
  onSendEmail?: (params: {
    recipient: string;
    recipientName?: string;
    companyName?: string;
    subject?: string;
    body?: string;
    leadId?: number;
  }) => void;
}> = ({ openItem, city, category, offer, savedId, onClose, onSave, onOpenScraper, onSendEmail }) => {
  const [scrape, setScrape] = useState<SavedScrape | null>(null);
  const [scraping, setScraping] = useState(false);
  const [scrapeErr, setScrapeErr] = useState('');
  const [showMarkdown, setShowMarkdown] = useState(false);
  const [probe, setProbe] = useState<ProbeOut | null>(null);
  const [probing, setProbing] = useState(false);
  const [demoUrl, setDemoUrl] = useState<string | null>(null);
  const [makingDemo, setMakingDemo] = useState(false);
  const [channelTab, setChannelTab] = useState<'email' | 'call' | 'whatsapp' | 'social'>('email');
  const [confirmAction, setConfirmAction] = useState<{
    kind: 'email' | 'call' | 'whatsapp';
    target: string;
    label: string;
  } | null>(null);
  const [emailHealth, setEmailHealth] = useState<Record<string, { deliverable: boolean; role: boolean; label: string }>>({});
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setScrape(null);
    setScrapeErr('');
    setShowMarkdown(false);
    setProbe(null);
    setDemoUrl(null);
    setConfirmAction(null);
    setEmailHealth({});
    if (!openItem?.domain && !openItem?.website) return;
    const target = openItem.domain || openItem.website || '';
    apiFetch(`/api/v1/browser/scraped?domain=${encodeURIComponent(target)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(async (data) => {
        if (data?.found && data.scrape) {
          setScrape(data.scrape);
          const foundEmails: string[] = Array.isArray(data.scrape.extracted_data?.emails) ? data.scrape.extracted_data.emails.slice(0, 5) : [];
          for (const em of foundEmails) {
            try {
              const vRes = await apiFetch('/api/email/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: em }),
              });
              if (vRes.ok) {
                const v = await vRes.json();
                setEmailHealth((prev) => ({
                  ...prev,
                  [em]: {
                    deliverable: Boolean(v.is_deliverable),
                    role: Boolean(v.is_role_account),
                    label: !v.is_deliverable ? 'Invalid / Risky' : v.is_role_account ? 'Role Inbox' : 'MX Valid',
                  },
                }));
              }
            } catch { /* non-blocking */ }
          }
        }
      })
      .catch(() => {});
  }, [openItem]);

  if (!openItem) return <Drawer open={false} title="" onClose={onClose}><div /></Drawer>;

  const st = STATUS[openItem.classification] ?? STATUS.has_site;
  const effectiveScore = computeOfferScore(openItem, offer);
  const crmLeadId = savedId || openItem.crm_status?.lead_id;

  const runFullAudit = async () => {
    if (!openItem.website) return;
    setScraping(true);
    setScrapeErr('');
    try {
      const res = await apiFetch('/api/v1/browser/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: openItem.website, mode: 'local_audit', context_title: openItem.name }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
      const loaded = await apiFetch(`/api/v1/browser/scraped?domain=${encodeURIComponent(openItem.domain || openItem.website)}`).then((r) => r.json());
      if (loaded?.found && loaded.scrape) setScrape(loaded.scrape);
    } catch (e) {
      setScrapeErr((e as Error).message);
    } finally {
      setScraping(false);
    }
  };

  const runDeepVerify = async () => {
    setProbing(true);
    try {
      const res = await apiFetch('/api/hunt/local/probe_presence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: openItem.name, city, website: openItem.website }),
      });
      if (res.ok) setProbe(await res.json());
    } finally {
      setProbing(false);
    }
  };

  const generateDemo = async () => {
    setMakingDemo(true);
    try {
      const res = await apiFetch('/api/hunt/local/demo_site', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: openItem.name,
          category: category || 'Local Business',
          city,
          address: openItem.address,
          phone: openItem.phone,
          offer,
        }),
      });
      if (res.ok) {
        const d = await res.json();
        setDemoUrl(`${window.location.origin}${d.demo_url}`);
      }
    } finally {
      setMakingDemo(false);
    }
  };

  const extracted = scrape?.extracted_data ?? {};
  const emails: string[] = Array.isArray(extracted.emails) ? extracted.emails : [];
  const techStack: string[] = Array.isArray(extracted.tech_stack) ? extracted.tech_stack : [];
  const mdLower = (scrape?.fit_markdown || '').toLowerCase();
  const hasHttps = Boolean(openItem.website?.startsWith('https://')) && openItem.classification !== 'tls_broken';
  const hasBooking = /book|appointment|schedule|calendly|acuity/.test(mdLower);
  const hasChat = /chat|intercom|drift|tidio|zendesk|whatsapp/.test(mdLower);
  const hasAnalytics = /gtag|googletagmanager|facebook\.net|fbq|analytics/.test(JSON.stringify(extracted).toLowerCase());
  const checks = [
    { label: 'SSL / HTTPS', ok: hasHttps },
    { label: 'Online Booking', ok: hasBooking },
    { label: 'Live Chat / Widget', ok: hasChat },
    { label: 'Analytics / Ad Pixel', ok: hasAnalytics },
  ];
  const healthPct = scrape ? Math.round((checks.filter((c) => c.ok).length / checks.length) * 100) : hasHttps ? 50 : 15;

  const baseHook =
    openItem.pitch_strategy?.cold_pitch_hook ||
    `Hi, I noticed ${openItem.name} in ${city || 'your area'} and wanted to share a quick improvement idea.`;
  const demoLine = demoUrl ? `\n\nI mocked up a 1-page preview concept for ${openItem.name} here: ${demoUrl}` : '';
  const channelCopy: Record<typeof channelTab, string> = {
    email: `${baseHook}${demoLine}\n\nHappy to walk through the exact findings in 5 minutes this week.`,
    call: `"Hi, this is [Name] calling for the owner at ${openItem.name}. ${baseHook} Do you have 30 seconds so I can send over the quick breakdown?"`,
    whatsapp: `Hi ${openItem.name} team 👋 ${baseHook}${demoLine}`,
    social: `Hey ${openItem.name}! Saw your page while checking ${category || 'local businesses'} in ${city || 'your area'}. ${baseHook}${demoLine}`,
  };

  const waDigits = (openItem.phone || '').replace(/[^\d]/g, '');

  const executeConfirmed = () => {
    if (!confirmAction) return;
    if (confirmAction.kind === 'email' && onSendEmail) {
      onSendEmail({
        recipient: confirmAction.target,
        companyName: openItem.name,
        subject: `Quick idea for ${openItem.name}`,
        body: channelCopy.email,
        leadId: crmLeadId,
      });
      onClose();
    } else if (confirmAction.kind === 'call') {
      window.open(`tel:${confirmAction.target}`, '_self');
    } else if (confirmAction.kind === 'whatsapp') {
      const msg = encodeURIComponent(channelCopy.whatsapp);
      window.open(`https://wa.me/${waDigits}?text=${msg}`, '_blank', 'noopener,noreferrer');
    }
    setConfirmAction(null);
  };

  return (
    <Drawer open={true} title={openItem.name} onClose={onClose}>
      <div className="space-y-5 text-sm">
        {/* Status + Offer Win Score + Pitchability + Budget */}
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={st.tone}>{st.text}</Badge>
          <Badge tone="accent">Win score {effectiveScore}</Badge>
          <Badge tone={openItem.pitchability === 'Low' ? 'warn' : 'good'}>
            {openItem.entity_type === 'public_sector' ? 'Public Sector' : openItem.entity_type === 'chain_franchise' ? 'Chain / Franchise' : 'Independent SMB'} · {openItem.pitchability || 'High'} Pitchability
          </Badge>
          {openItem.budget_tier && <Badge tone="info">Budget: {openItem.budget_tier}</Badge>}
          {crmLeadId && <Badge tone="good">In CRM #{crmLeadId}</Badge>}
        </div>

        {/* Inline Approval Confirmation Bar */}
        {confirmAction && (
          <div className="rounded-xl border border-indigo-500/40 bg-indigo-500/10 p-3 space-y-2">
            <div className="text-xs font-medium text-white">
              {confirmAction.kind === 'email'
                ? `Do you want to prepare an outreach email to ${confirmAction.target || openItem.name}?`
                : confirmAction.kind === 'whatsapp'
                  ? `Open WhatsApp chat with ${openItem.name} (${confirmAction.target})?`
                  : `Start call to ${openItem.name} (${confirmAction.target})?`}
            </div>
            <div className="flex gap-2">
              <Button small variant="primary" onClick={executeConfirmed}>Approve & Proceed</Button>
              <Button small variant="ghost" onClick={() => setConfirmAction(null)}>Cancel</Button>
            </div>
          </div>
        )}

        {/* Business Details & Approved Contact Actions */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 space-y-2 text-xs text-slate-300">
          {openItem.address && <div className="flex gap-2"><MapPin className="h-3.5 w-3.5 mt-0.5 text-slate-500 shrink-0" /><span>{openItem.address}</span></div>}
          {openItem.phone && (
            <div className="flex flex-wrap items-center gap-2">
              <Phone className="h-3.5 w-3.5 text-slate-500" />
              <span className="font-mono text-slate-100">{openItem.phone}</span>
              <Button small onClick={() => setConfirmAction({ kind: 'call', target: openItem.phone!, label: 'Call' })}>
                <Phone className="h-3 w-3 text-emerald-400" /> Call
              </Button>
              {waDigits.length >= 7 && (
                <Button small onClick={() => setConfirmAction({ kind: 'whatsapp', target: openItem.phone!, label: 'WhatsApp' })}>
                  <MessageCircle className="h-3 w-3 text-emerald-400" /> WhatsApp
                </Button>
              )}
            </div>
          )}
          {openItem.website && (
            <div className="flex flex-wrap items-center gap-2">
              <Globe className="h-3.5 w-3.5 text-slate-500" />
              <a className="text-indigo-300 hover:underline inline-flex items-center gap-1" href={normalizeUrl(openItem.website)} target="_blank" rel="noreferrer noopener">
                {openItem.domain ?? openItem.website} <ExternalLink className="h-3 w-3" />
              </a>
              <Button small variant="primary" disabled={scraping} onClick={runFullAudit}>
                <Cpu className="h-3 w-3" />
                {scraping ? 'Auditing Site…' : scrape ? 'Re-Run Site & Contact Audit' : 'Run Full Site & Contact Audit'}
              </Button>
              {onOpenScraper && (
                <Button small onClick={() => onOpenScraper(openItem.website!, 'local_audit', openItem.name)}>
                  <PanelRight className="h-3 w-3" /> Side Panel
                </Button>
              )}
            </div>
          )}
          {openItem.maps_url && (
            <a className="inline-flex gap-1.5 text-indigo-300 hover:underline" href={openItem.maps_url} target="_blank" rel="noreferrer noopener">
              <MapPin className="h-3.5 w-3.5" /> Open on Map <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>

        {scrapeErr && <p className="text-xs text-rose-400">{scrapeErr}</p>}

        {/* Visual Site Matrix & Saved Scrape Insights (for businesses WITH a site) */}
        {openItem.website && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3.5 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <h3 className="text-xs font-semibold text-white">Visual Site Audit & Saved Scrape Matrix</h3>
                <p className="text-[11px] text-slate-400">
                  {scrape ? `Last scraped: ${scrape.created_at} · ${scrape.title}` : 'Run Full Site & Contact Audit to persist and visualize full site intel.'}
                </p>
              </div>
              <span className="text-xs font-mono font-semibold text-indigo-300">{healthPct}% ready</span>
            </div>
            <ScoreBar value={healthPct} />
            <div className="grid grid-cols-2 gap-2 text-xs">
              {checks.map((c) => (
                <div key={c.label} className="flex items-center gap-1.5 rounded-lg border border-slate-800 px-2.5 py-1.5 bg-slate-950/50">
                  {c.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" /> : <XCircle className="h-3.5 w-3.5 text-rose-400 shrink-0" />}
                  <span className="text-slate-200">{c.label}</span>
                </div>
              ))}
            </div>
            {techStack.length > 0 && (
              <div className="flex flex-wrap gap-1.5 items-center text-[11px]">
                <span className="text-slate-400">Tech stack:</span>
                {techStack.slice(0, 6).map((t) => <Badge key={t} tone="neutral">{t}</Badge>)}
              </div>
            )}
            {emails.length > 0 && (
              <div className="space-y-1">
                <div className="text-[11px] font-medium text-slate-400">Discovered Emails (click to prepare outreach):</div>
                <div className="flex flex-wrap gap-1.5">
                  {emails.map((em) => {
                    const eh = emailHealth[em];
                    return (
                      <button
                        key={em}
                        type="button"
                        onClick={() => setConfirmAction({ kind: 'email', target: em, label: 'Email' })}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/25 cursor-pointer"
                      >
                        <Mail className="h-3 w-3" /> {em}
                        {eh && (
                          <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${eh.deliverable ? (eh.role ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300') : 'bg-rose-500/20 text-rose-300'}`}>
                            {eh.label}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {scrape?.fit_markdown && (
              <div>
                <button type="button" onClick={() => setShowMarkdown((v) => !v)} className="text-xs text-indigo-300 hover:underline">
                  {showMarkdown ? 'Hide scraped site content' : 'View full scraped site description & content'}
                </button>
                {showMarkdown && (
                  <pre className="mt-2 max-h-56 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-[11px] text-slate-300 whitespace-pre-wrap font-mono">
                    {scrape.fit_markdown.slice(0, 4000)}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}

        {/* Deep Verify + Domain Check + Instant Demo Site (especially for businesses WITHOUT a site) */}
        {!openItem.website && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3.5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                <ShieldAlert className="h-4 w-4 text-amber-400" />
                No-Website Verification & Instant Demo
              </div>
              <div className="flex flex-wrap gap-2">
                <Button small disabled={probing} onClick={runDeepVerify}>
                  {probing ? 'Verifying…' : '1-Click Deep Verify'}
                </Button>
                <Button small variant="primary" disabled={makingDemo} onClick={generateDemo}>
                  <Wand2 className="h-3.5 w-3.5" />
                  {makingDemo ? 'Building…' : 'Instant Demo Site'}
                </Button>
              </div>
            </div>
            {probe?.domain_suggestions && (
              <div className="flex flex-wrap gap-1.5">
                {probe.domain_suggestions.map((d) => (
                  <Badge key={d.domain} tone={d.status === 'available' || d.likely_available ? 'good' : d.status === 'unknown' ? 'warn' : 'neutral'}>
                    {d.domain} · {d.status === 'available' || d.likely_available ? 'Available' : d.status === 'unknown' ? 'Check Manually' : 'Taken'}
                  </Badge>
                ))}
              </div>
            )}
            {demoUrl && (
              <div className="text-xs text-emerald-300 flex items-center justify-between gap-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-2">
                <span>Live Demo Ready & injected into opener!</span>
                <a href={demoUrl} target="_blank" rel="noreferrer noopener" className="underline font-medium inline-flex items-center gap-1">
                  Preview Mockup <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
          </div>
        )}

        {/* Why This Score */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Why this score</h3>
          <ul className="space-y-1 text-xs text-slate-300 list-disc pl-4">
            {openItem.reasons.map((x) => <li key={x}>{x}</li>)}
          </ul>
        </div>

        {/* Multi-Channel Opener Box */}
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" /> Multi-Channel Opener ({offer.replace('_', ' ')})
            </h3>
            <div className="flex gap-1">
              {(['email', 'call', 'whatsapp', 'social'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setChannelTab(t)}
                  className={`px-2 py-0.5 rounded-md text-[11px] border ${
                    channelTab === t ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300' : 'border-slate-800 text-slate-400'
                  }`}
                >
                  {t === 'whatsapp' ? 'WhatsApp/SMS' : t[0].toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <p className="text-xs text-slate-200 bg-slate-900 border border-slate-800 rounded-lg p-3 whitespace-pre-wrap leading-relaxed">
            {channelCopy[channelTab]}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              small
              onClick={() => {
                navigator.clipboard?.writeText(channelCopy[channelTab]);
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1500);
              }}
            >
              <Copy className="h-3.5 w-3.5" /> {copied ? 'Copied' : 'Copy Opener'}
            </Button>
          </div>
        </div>

        {/* Bottom Actions */}
        <div className="flex flex-wrap gap-2 pt-3 border-t border-slate-800">
          <Button variant="primary" disabled={!!crmLeadId} onClick={() => onSave(openItem)}>
            {crmLeadId ? 'Saved in Clients' : 'Save to Clients'}
          </Button>
          {onSendEmail && (
            <Button
              variant="secondary"
              onClick={() =>
                setConfirmAction({
                  kind: 'email',
                  target: emails[0] || (openItem.domain ? `contact@${openItem.domain}` : ''),
                  label: 'Email',
                })
              }
            >
              <Mail className="h-4 w-4 text-indigo-400" />
              Pitch via Email Hub →
            </Button>
          )}
        </div>
      </div>
    </Drawer>
  );
};
