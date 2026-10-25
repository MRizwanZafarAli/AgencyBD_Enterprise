import { useState } from 'react';
import type { ReactNode } from 'react';
import type { FC } from 'react';
import { ArrowLeft, Stethoscope, GitCompare, FileText, Mail, Sparkles, Phone, Video, ListOrdered } from 'lucide-react';
import { Button, Card, PageHeader, SearchInput, field } from '../components/ui';
import { SiteClinic } from '../components/clinic/SiteClinic';
import { parseTarget } from '../components/clinic/types';
import { WaterfallEnrich } from '../components/modules/WaterfallEnrich';
import { CopyCoach } from '../components/modules/CopyCoach';
import { CallIntel } from '../components/modules/CallIntel';
import { MultimodalStudio } from '../components/modules/MultimodalStudio';
import { SequencesManager } from '../components/modules/SequencesManager';
import { CompareSites, ClientReportTool } from '../components/tools/QuickTools';

const noop = () => undefined;
type Seed = { text: string; n: number } | null;
interface Tool { id: string; label: string; desc: string; idea: string; keywords: string; group: string; icon: FC<{ className?: string }> }

const TOOLS: Tool[] = [
  { id: 'doctor', label: 'Site Clinic', desc: 'Paste a website, or a business and its place. Triage, examine, diagnose, then a surgery plan you tick off.', idea: 'Re-examine after a fix to see the score move.', keywords: 'website doctor audit surgery seo security speed accessibility scan', group: 'Research a prospect', icon: Stethoscope },
  { id: 'compare', label: 'Compare two sites', desc: 'Same checks on a prospect and a competitor; measured differences only.', idea: 'Open with the competitor gap as your hook.', keywords: 'competitor versus head to head', group: 'Research a prospect', icon: GitCompare },
  { id: 'report', label: 'Client report', desc: 'A printable health report (PDF and web) for any website.', idea: 'Send it as the free first deliverable.', keywords: 'pdf teardown deliverable', group: 'Research a prospect', icon: FileText },
  { id: 'email', label: 'Find an email address', desc: 'Likely addresses for a person, with the evidence they exist. Not a verification.', idea: 'Run it on the person you found on LinkedIn.', keywords: 'contact lead enrich waterfall', group: 'Research a prospect', icon: Mail },
  { id: 'copy', label: 'Email draft checker', desc: 'Readability, spam words and tone for a draft before you send it.', idea: 'Check every first touch before approving.', keywords: 'copy coach spam writing', group: 'Write and follow up', icon: Sparkles },
  { id: 'sequences', label: 'Email sequences', desc: 'Multi-step follow-ups with delays; every first touch waits for your approval.', idea: 'Three short touches beat one long one.', keywords: 'follow up drip cadence', group: 'Write and follow up', icon: ListOrdered },
  { id: 'call', label: 'Call notes to scope of work', desc: 'Paste a call transcript; get objections, needs and a draft scope.', idea: 'Paste it straight after the call.', keywords: 'transcript scope intel objections', group: 'Write and follow up', icon: Phone },
  { id: 'video', label: 'Video pitch script', desc: 'A short script built only from facts you supply.', idea: 'Record it in one take, under a minute.', keywords: 'loom script pitch', group: 'Write and follow up', icon: Video },
];

const MOVED = [
  ['Mission Control', 'Today (counts, inbox, daily digest)'], ['Swarm Auto-Pilot', 'Today, "Find and prepare new prospects"'], ['Opportunity Radar', 'Find, Jobs and projects / Tenders'],
  ['Local Client Hunt', 'Find, Local businesses (list and map)'], ['Open Sourcing (SEC, hiring, LinkedIn)', 'Today runs, and a client page: "Find on their website"'], ['Website Doctor', 'Tools, Site Clinic (and a client page)'],
  ['Deal Pipeline & CRM', 'Clients'], ['Proof and services', 'Settings, Services and proof'], ['Visual User Guide', 'Settings, How it works'],
  ['Fleet Deliverability, DNS Studio, CAN-SPAM Vault, Autonomy Policy, RBAC, API console', 'Settings'], ['Copy Coach, Call Intel, Video Pitch, Waterfall, Sequences', 'Tools (this page)'],
];

const RECENT_KEY = 'agencybd.tools.recent';
const loadRecent = (): string[] => { try { const v = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]'); return Array.isArray(v) ? v.filter((x) => TOOLS.some((t) => t.id === x)).slice(0, 3) : []; } catch { return []; } };

export const Tools: FC<{ onOpenClient: (leadId: number) => void }> = ({ onOpenClient }) => {
  const [active, setActive] = useState<string | null>(null);
  const [find, setFind] = useState('');
  const [paste, setPaste] = useState('');
  const [pasteError, setPasteError] = useState('');
  const [domain, setDomain] = useState('');                 // carried from one tool to the next
  const [seed, setSeed] = useState<Seed>(null);
  const [recent, setRecent] = useState<string[]>(loadRecent);

  const open = (id: string) => {
    setActive(id);
    const next = [id, ...recent.filter((r) => r !== id)].slice(0, 3);
    setRecent(next);
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)); } catch { /* recent tools just will not persist */ }
  };
  const examine = () => {
    if (!parseTarget(paste)) { setPasteError('Paste a website (acme.com) or type a business and its place (Acme Plumbing, Austin).'); return; }
    setPasteError(''); setSeed({ text: paste, n: Date.now() }); open('doctor');
  };
  const handoff = (tool: 'compare' | 'report' | 'email', d: string) => { setDomain(d); open(tool === 'email' ? 'email' : tool); };

  const tool = TOOLS.find((t) => t.id === active);
  if (tool) {
    const body: Record<string, ReactNode> = {
      doctor: <SiteClinic key={seed?.n ?? 0} initial={seed?.text ?? ''} autoRun={!!seed} onOpenClient={onOpenClient} onHandoff={handoff} />,
      compare: <CompareSites initialA={domain} />, report: <ClientReportTool initialDomain={domain} />,
      email: <WaterfallEnrich initialFirst="" initialLast="" initialCompany="" initialDomain={domain} onBridgeToCopyCoach={noop} setActiveTab={noop} />,
      copy: <CopyCoach initialSubject="" initialBody="" />, sequences: <SequencesManager />, call: <CallIntel />, video: <MultimodalStudio />,
    };
    return (
      <div className="space-y-4">
        <button onClick={() => setActive(null)} className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white"><ArrowLeft className="h-4 w-4" />All tools</button>
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
      <PageHeader title="Tools" subtitle="Every utility in one place. Use them on any website or draft, without saving anything as a client." />
      <Card>
        <div className="flex items-center gap-2 mb-2"><Stethoscope className="h-5 w-5 text-indigo-400" /><h2 className="text-sm font-semibold text-white">Examine a site</h2></div>
        <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); examine(); }}>
          <input className={`${field} flex-1 min-w-64`} aria-label="Paste a website or a business and place" autoComplete="off" spellCheck={false} placeholder="Paste a website, or a business and place: acme.com  ·  Acme Plumbing, Austin"
            value={paste} onChange={(e) => { setPaste(e.target.value); setPasteError(''); }} />
          <Button type="submit" variant="primary" disabled={!paste.trim()}>Examine</Button>
        </form>
        {pasteError && <p role="alert" className="text-xs text-amber-300 mt-2">{pasteError}</p>}
      </Card>
      <div className="flex flex-wrap items-center gap-3">
        <SearchInput className="w-full sm:w-72" label="Search tools" placeholder="Search tools (try: competitor, pdf, follow up)" value={find} onChange={setFind} />
        {!q && recent.length > 0 && <div className="flex items-center gap-1.5 text-xs" aria-label="Recent tools"><span className="text-slate-500">Recent:</span>
          {recent.map((id) => { const t = TOOLS.find((x) => x.id === id)!; return <button key={id} onClick={() => open(id)} className="px-2 py-1 rounded-md border border-slate-800 text-slate-300 hover:text-white hover:border-slate-600">{t.label}</button>; })}</div>}
      </div>
      {visible.length === 0 && <p className="text-sm text-slate-400">No tool matches &quot;{find}&quot;.</p>}
      {groups.map((g) => (
        <section key={g}><h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">{g}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visible.filter((t) => t.group === g).map((t) => (
              <button key={t.id} onClick={() => open(t.id)} className="text-left bento-tile-interactive rounded-2xl p-4 border border-slate-800 hover:border-indigo-500/50">
                <t.icon className="h-5 w-5 text-indigo-400 mb-2" /><div className="text-sm font-semibold text-white">{t.label}</div><p className="text-xs text-slate-400 mt-1">{t.desc}</p>
                <p className="text-[11px] text-indigo-300 mt-2">Idea: {t.idea}</p>
              </button>))}
          </div></section>))}
      <Card>
        <h2 className="text-sm font-semibold text-white mb-2">Where did my old pages go?</h2>
        <table className="w-full text-xs"><tbody>{MOVED.map(([from, to]) => <tr key={from} className="border-b border-slate-800/70"><td className="py-2 pr-4 text-slate-300 align-top">{from}</td><td className="py-2 text-slate-400">{to}</td></tr>)}</tbody></table>
      </Card>
    </div>
  );
};
