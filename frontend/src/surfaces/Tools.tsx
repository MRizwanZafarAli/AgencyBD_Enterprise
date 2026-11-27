import { useState } from 'react';
import type { ReactNode } from 'react';
import type { FC } from 'react';
import {
  ArrowLeft,
  Calculator,
  CheckCircle2,
  Copy,
  Cpu,
  Download,
  ExternalLink,
  FileText,
  GitCompare,
  HelpCircle,
  ListOrdered,
  Mail,
  Phone,
  Radar,
  Shield,
  Sparkles,
  Stethoscope,
  Video,
  X,
} from 'lucide-react';
import { Badge, Button, Card, PageHeader, SearchInput, field } from '../components/ui';
import { SiteClinic } from '../components/clinic/SiteClinic';
import { parseTarget } from '../components/clinic/types';
import { WaterfallEnrich } from '../components/modules/WaterfallEnrich';
import { CopyCoach } from '../components/modules/CopyCoach';
import { CallIntel } from '../components/modules/CallIntel';
import { MultimodalStudio } from '../components/modules/MultimodalStudio';
import { SequencesManager } from '../components/modules/SequencesManager';
import { CompareSites, ClientReportTool } from '../components/tools/QuickTools';
import { AgencyRoiCalculator, DomainDnsStudio } from '../components/tools/EnterpriseUtilities';
import { AgentSwarmMissionControl } from '../components/modules/AgentSwarmMissionControl';
import { VisitorRadar } from '../components/today/VisitorRadar';
import { DiscoveryPanel } from '../components/today/DiscoveryPanel';
import { useApi } from '../lib/hooks';

const noop = () => undefined;
type Seed = { text: string; n: number } | null;

interface Tool {
  id: string;
  label: string;
  desc: string;
  idea: string;
  keywords: string;
  group: string;
  badge?: string;
  icon: FC<{ className?: string }>;
}

interface ToolsOverview {
  telemetry: {
    swarm_agents: number;
    active_swarm_runs: number;
    queued_discovery_runs: number;
  };
  recent_runs: Array<{
    id: string;
    kind: string;
    target: string;
    score: number | null;
    status: string;
    share_url: string;
    pdf_url: string | null;
    created_at: string;
  }>;
}

const TOOLS: Tool[] = [
  { id: 'swarm', label: 'Autonomous Agent Swarm', desc: 'Real-time telemetry, lifecycle event bus, and controls for the 8 BD agents.', idea: 'Toggle autonomous lead waterfall and inspect live events.', keywords: 'swarm agent autonomous telemetry hook waterfall skills', group: 'Autonomous Systems', icon: Cpu },
  { id: 'autopilot', label: 'Autopilot Prospector', desc: 'Launch autonomous sourcing runs across engineering hiring, local businesses, or SEC filings.', idea: 'Queue automated sourcing runs and review outcomes.', keywords: 'autopilot sourcing discovery sec hiring pipeline', group: 'Autonomous Systems', icon: Sparkles },
  { id: 'doctor', label: 'Site Clinic', desc: 'Paste a website, or a business and its place. Triage, examine, diagnose, then a surgery plan you tick off.', idea: 'Re-examine after a fix to see the score move.', keywords: 'website doctor audit surgery seo security speed accessibility scan', group: 'Research a prospect', icon: Stethoscope },
  { id: 'compare', label: 'Compare two sites', desc: 'Same checks on a prospect and a competitor; measured differences only.', idea: 'Open with the competitor gap as your hook.', keywords: 'competitor versus head to head', group: 'Research a prospect', icon: GitCompare },
  { id: 'report', label: 'Client report', desc: 'A printable health report (PDF and web) for any website with white-label branding.', idea: 'Send it as the free first deliverable.', keywords: 'pdf teardown deliverable lead magnet', group: 'Research a prospect', icon: FileText },
  { id: 'roi', label: 'Agency Pricing & ROI Calculator', desc: 'Turn a prospect’s traffic and conversion gap into a 1-click monthly revenue projection.', idea: 'Include the recovered revenue hook in your first email.', keywords: 'roi pricing calculator revenue conversion', group: 'Research a prospect', icon: Calculator },
  { id: 'dns', label: 'Domain & Deliverability DNS Studio', desc: '1-click SPF, DKIM, DMARC, and MX audit for sending or prospect domains.', idea: 'Verify DNS health before launching outbound.', keywords: 'dns spf dkim dmarc mx deliverability', group: 'Research a prospect', icon: Shield },
  { id: 'email', label: 'Find an email address', desc: 'Likely addresses for a person, with the evidence they exist. Not a verification.', idea: 'Run it on the person you found on LinkedIn.', keywords: 'contact lead enrich waterfall', group: 'Research a prospect', icon: Mail },
  { id: 'intent', label: 'Visitor Intent Radar', desc: 'Deanonymize visiting companies and convert high-intent traffic into qualified leads.', idea: 'Convert inbound accounts before they bounce.', keywords: 'visitor intent deanonymize radar tracking ip analytics', group: 'Research a prospect', icon: Radar },
  { id: 'copy', label: 'Email draft checker', desc: 'Readability, spam words and tone for a draft before you send it.', idea: 'Check every first touch before approving.', keywords: 'copy coach spam writing', group: 'Write and follow up', icon: Sparkles },
  { id: 'sequences', label: 'Email sequences', desc: 'Multi-step follow-ups with delays; every first touch waits for your approval.', idea: 'Manage sequences here or in Clients → Email sequences.', keywords: 'follow up drip cadence', group: 'Write and follow up', badge: 'Also in Clients', icon: ListOrdered },
  { id: 'call', label: 'Call notes to scope of work', desc: 'Paste a call transcript; get objections, needs and a draft scope.', idea: 'Paste it straight after the call.', keywords: 'transcript scope intel objections', group: 'Write and follow up', icon: Phone },
  { id: 'video', label: 'Video pitch script', desc: 'A short script built only from facts you supply.', idea: 'Record it in one take, under a minute.', keywords: 'loom script pitch', group: 'Write and follow up', icon: Video },
];

const WHATS_NEW = [
  ['Mission Control', 'Today (counts, inbox, daily digest)'],
  ['Swarm Auto-Pilot', 'Today, "Find and prepare new prospects"'],
  ['Opportunity Radar', 'Find → Jobs and projects / Tenders'],
  ['Local Client Hunt', 'Find → Local businesses (list and map)'],
  ['Website Doctor', 'Tools → Site Clinic'],
  ['Deal Pipeline & CRM', 'Clients'],
  ['Proof & Services / Policy / RBAC', 'Settings'],
];

const RECENT_KEY = 'agencybd.tools.recent';
const loadRecent = (): string[] => {
  try {
    const v = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
    return Array.isArray(v) ? v.filter((x) => TOOLS.some((t) => t.id === x)).slice(0, 3) : [];
  } catch {
    return [];
  }
};

export const Tools: FC<{
  onOpenClient: (leadId: number) => void;
  onOpenScraper?: (url: string, mode?: 'general' | 'client_audit' | 'job_spec' | 'local_audit', title?: string) => void;
}> = ({ onOpenClient, onOpenScraper }) => {
  const [active, setActive] = useState<string | null>(null);
  const [find, setFind] = useState('');
  const [paste, setPaste] = useState('');
  const [pasteError, setPasteError] = useState('');
  const [domain, setDomain] = useState('');
  const [seed, setSeed] = useState<Seed>(null);
  const [recent, setRecent] = useState<string[]>(loadRecent);
  const [whatsNewOpen, setWhatsNewOpen] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const overview = useApi<ToolsOverview>('/api/tools/overview');
  const telemetry = overview.data?.telemetry;
  const recentRuns = overview.data?.recent_runs ?? [];

  const open = (id: string) => {
    setActive(id);
    const next = [id, ...recent.filter((r) => r !== id)].slice(0, 3);
    setRecent(next);
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

  const examine = () => {
    if (!parseTarget(paste)) {
      setPasteError('Paste a website (acme.com) or type a business and its place (Acme Plumbing, Austin).');
      return;
    }
    setPasteError('');
    setSeed({ text: paste, n: Date.now() });
    open('doctor');
  };

  const handoff = (tool: 'compare' | 'report' | 'email', d: string) => {
    setDomain(d);
    open(tool === 'email' ? 'email' : tool);
  };

  const tool = TOOLS.find((t) => t.id === active);
  if (tool) {
    const body: Record<string, ReactNode> = {
      swarm: <AgentSwarmMissionControl />,
      doctor: <SiteClinic key={seed?.n ?? 0} initial={seed?.text ?? ''} autoRun={!!seed} onOpenClient={onOpenClient} onHandoff={handoff} onOpenScraper={onOpenScraper} />,
      compare: <CompareSites initialA={domain} />,
      report: <ClientReportTool initialDomain={domain} />,
      roi: <AgencyRoiCalculator />,
      dns: <DomainDnsStudio initialDomain={domain} />,
      email: <WaterfallEnrich initialFirst="" initialLast="" initialCompany="" initialDomain={domain} onBridgeToCopyCoach={noop} setActiveTab={noop} />,
      copy: <CopyCoach initialSubject="" initialBody="" />,
      sequences: <SequencesManager />,
      call: <CallIntel />,
      video: <MultimodalStudio />,
      intent: <VisitorRadar onOpenClient={onOpenClient} />,
      autopilot: <DiscoveryPanel onDone={overview.reload} onOpenClient={onOpenClient} />,
    };
    return (
      <div className="space-y-4">
        <button onClick={() => setActive(null)} className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white">
          <ArrowLeft className="h-4 w-4" />
          All tools
        </button>
        <PageHeader title={tool.label} subtitle={tool.desc} />
        {body[tool.id]}
      </div>
    );
  }

  const q = find.trim().toLowerCase();
  const visible = TOOLS.filter((t) => !q || `${t.label} ${t.desc} ${t.keywords}`.toLowerCase().includes(q));
  const groups = Array.from(new Set(visible.map((t) => t.group)));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tools"
        subtitle="Audit any prospect, calculate ROI, check DNS deliverability, and export white-label lead magnets without cluttering your CRM."
        actions={
          <Button small variant="ghost" onClick={() => setWhatsNewOpen(true)}>
            <HelpCircle className="h-3.5 w-3.5" /> What&apos;s New
          </Button>
        }
      />

      <Card>
        <div className="flex items-center gap-2 mb-2">
          <Stethoscope className="h-5 w-5 text-indigo-400" />
          <h2 className="text-sm font-semibold text-white">Examine a site</h2>
        </div>
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            examine();
          }}
        >
          <input
            className={`${field} flex-1 min-w-64`}
            aria-label="Paste a website or a business and place"
            autoComplete="off"
            spellCheck={false}
            placeholder="Paste a website, or a business and place: acme.com  ·  Acme Plumbing, Austin"
            value={paste}
            onChange={(e) => {
              setPaste(e.target.value);
              setPasteError('');
            }}
          />
          <Button type="submit" variant="primary" disabled={!paste.trim()}>
            <Sparkles className="h-3.5 w-3.5" /> Run Instant Audit
          </Button>
        </form>
        {pasteError && (
          <p role="alert" className="text-xs text-amber-300 mt-2">
            {pasteError}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-1.5 mt-2.5 text-xs text-slate-400">
          <span className="text-slate-500 text-[11px]">Quick try:</span>
          {[
            { label: 'stripe.com', val: 'stripe.com' },
            { label: 'github.com', val: 'github.com' },
            { label: 'dental.net', val: 'dental.net' },
            { label: 'Acme Plumbing, Austin', val: 'Acme Plumbing, Austin' },
          ].map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => {
                setPaste(ex.val);
                setPasteError('');
                setSeed({ text: ex.val, n: Date.now() });
                open('doctor');
              }}
              className="px-2 py-0.5 rounded-md text-[11px] font-mono bg-slate-800/80 hover:bg-slate-700 text-indigo-300 hover:text-white border border-slate-700/60 transition"
            >
              {ex.label}
            </button>
          ))}
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <SearchInput className="w-full sm:w-72" label="Search tools" placeholder="Search tools (try: dns, roi, competitor, pdf)" value={find} onChange={setFind} />
        {!q && recent.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs" aria-label="Recent tools">
            <span className="text-slate-500">Recent:</span>
            {recent.map((id) => {
              const t = TOOLS.find((x) => x.id === id)!;
              return (
                <button key={id} onClick={() => open(id)} className="px-2 py-1 rounded-md border border-slate-800 text-slate-300 hover:text-white hover:border-slate-600">
                  {t.label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {visible.length === 0 && <p className="text-sm text-slate-400">No tool matches &quot;{find}&quot;.</p>}

      {groups.map((g) => (
        <section key={g}>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">{g}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visible
              .filter((t) => t.group === g)
              .map((t) => {
                let liveBadge: { label: string; tone: 'good' | 'info' | 'neutral' | 'accent' } | null = null;
                if (t.id === 'swarm' && telemetry) {
                  liveBadge = telemetry.active_swarm_runs > 0
                    ? { label: `● ${telemetry.active_swarm_runs} Active`, tone: 'good' }
                    : { label: `● ${telemetry.swarm_agents} Agents Idle`, tone: 'neutral' };
                } else if (t.id === 'autopilot' && telemetry) {
                  liveBadge = telemetry.queued_discovery_runs > 0
                    ? { label: `● ${telemetry.queued_discovery_runs} Queued`, tone: 'info' }
                    : { label: '● Ready', tone: 'neutral' };
                } else if (t.badge) {
                  liveBadge = { label: t.badge, tone: 'accent' };
                }
                return (
                  <button
                    key={t.id}
                    onClick={() => open(t.id)}
                    className="text-left bento-tile-interactive rounded-2xl p-4 border border-slate-800 hover:border-indigo-500/50 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <t.icon className="h-5 w-5 text-indigo-400 shrink-0" />
                        {liveBadge && <Badge tone={liveBadge.tone}>{liveBadge.label}</Badge>}
                      </div>
                      <div className="text-sm font-semibold text-white">{t.label}</div>
                      <p className="text-xs text-slate-400 mt-1">{t.desc}</p>
                    </div>
                    <p className="text-[11px] text-indigo-300 mt-2">Idea: {t.idea}</p>
                  </button>
                );
              })}
          </div>
        </section>
      ))}

      {/* Recent Runs & Shareable Lead-Magnet Reports History */}
      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Recent Tool Runs &amp; Shareable Reports</h2>
            <p className="text-xs text-slate-400">Copy white-label web links or download branded PDF deliverables from your recent audits and proposals.</p>
          </div>
          <Badge tone="neutral">{recentRuns.length} runs</Badge>
        </div>
        {recentRuns.length === 0 ? (
          <p className="text-xs text-slate-500">No recent Site Clinic or Client Report runs yet. Run an audit above to generate your first shareable deliverable.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 pr-3 font-medium">Tool</th>
                  <th className="py-2 px-3 font-medium">Target</th>
                  <th className="py-2 px-3 font-medium">Score</th>
                  <th className="py-2 px-3 font-medium">Status</th>
                  <th className="py-2 pl-3 text-right font-medium">Deliverables</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {recentRuns.map((r) => (
                  <tr key={r.id}>
                    <td className="py-2 pr-3 text-slate-300 font-medium">{r.kind}</td>
                    <td className="py-2 px-3 text-white font-semibold">{r.target}</td>
                    <td className="py-2 px-3">{r.score != null ? <Badge tone={r.score >= 70 ? 'good' : r.score >= 45 ? 'warn' : 'bad'}>{r.score}/100</Badge> : '—'}</td>
                    <td className="py-2 px-3"><Badge tone="neutral">{r.status}</Badge></td>
                    <td className="py-2 pl-3 text-right whitespace-nowrap">
                      <div className="inline-flex items-center gap-1.5">
                        <Button
                          small
                          variant="secondary"
                          onClick={() => {
                            const full = `${window.location.origin}${r.share_url}`;
                            navigator.clipboard?.writeText(full);
                            setCopiedId(r.id);
                            setTimeout(() => setCopiedId(null), 1500);
                          }}
                        >
                          {copiedId === r.id ? <CheckCircle2 className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                          {copiedId === r.id ? 'Copied' : 'Copy Link'}
                        </Button>
                        {r.pdf_url && (
                          <a href={r.pdf_url} target="_blank" rel="noopener noreferrer" className="px-2 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white inline-flex items-center gap-1">
                            <Download className="h-3 w-3" /> PDF
                          </a>
                        )}
                        <a href={r.share_url} target="_blank" rel="noopener noreferrer" className="px-2 py-1 rounded-lg bg-slate-900 border border-slate-800 text-indigo-300 hover:text-white inline-flex items-center gap-1">
                          <ExternalLink className="h-3 w-3" /> Open
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Dismissible What's New Modal */}
      {whatsNewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <Card className="w-full max-w-lg space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">What&apos;s New — Navigation Guide</h3>
              <button type="button" onClick={() => setWhatsNewOpen(false)} aria-label="Close what's new">
                <X className="h-4 w-4 text-slate-400 hover:text-white" />
              </button>
            </div>
            <table className="w-full text-xs">
              <tbody>
                {WHATS_NEW.map(([from, to]) => (
                  <tr key={from} className="border-b border-slate-800/70">
                    <td className="py-2 pr-4 text-slate-300 font-medium">{from}</td>
                    <td className="py-2 text-slate-400">{to}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
    </div>
  );
};
