import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { ExternalLink, FileText, Presentation, Search, ShieldCheck, Sparkles, UserPlus, Video } from 'lucide-react';
import { Badge, Button, Card, Drawer, EmptyState, ScoreBar, Skeletons, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { VideoStoryboardDrawer } from '../shared/VideoStoryboardDrawer';
import type { VideoStoryboardData } from '../shared/VideoStoryboardDrawer';
import { openProtected } from '../../lib/api';
import { send, useApi } from '../../lib/hooks';
import { normalizeUrl } from '../../lib/urls';
import { ClientNotes } from './ClientNotes';

interface Detail {
  lead: { id: number; company_name: string; domain: string; phone: string | null; address: string | null; notes: string | null; reviews_count: number; rating: number };
  company_id: number; has_website: boolean;
  priority: { score: number; band: string; reasons: string[]; needs: string[]; confidence: string };
  contacts: Array<{ id: number; first_name: string; last_name: string; title: string; email: string; verification_status: string }>;
  audit: { id: number; status: string; overall_score: number | null; created_at: string } | null;
  work_items: Array<{ id: number; title: string; detail: string }>;
}
interface Advice { audit_id: number; recommendations: Array<{ service_key: string; service: string; priority: string; summary: string; price_band: string | null; evidence_ids: number[] }>; ai_recommendations?: Array<{ title: string; why_it_matters: string; service: string; evidence_ids: number[] }> }
interface Candidate { kind: 'person' | 'email' | 'generic_email'; name: string | null; title: string | null; email: string | null; linkedin_url: string | null; source_url: string; evidence: string }
interface Found { pages_checked: string[]; candidates: Candidate[]; limitations: string[]; linkedin_search_url: string; company_linkedin: string | null }
interface Prepared { outcome: string; reason?: string; band?: string; priority?: number }

const CONTACT_TONE: Record<string, 'good' | 'warn' | 'bad'> = { verified: 'good', unverified: 'warn', invalid: 'bad', suppressed: 'bad' };
const OUTCOME: Record<string, string> = {
  draft_pending_approval: 'A first email is waiting for your approval on Today.', needs_contact: 'Add a contact below first; there is no verified contact yet.',
  nothing_to_say: 'The audit found nothing specific enough to base an email on.', blocked_by_policy: 'Blocked by policy', audit_failed: 'The audit failed.',
};

export const ClientPage: FC<{ leadId: number | null; onClose: () => void }> = ({ leadId, onClose }) => {
  const detail = useApi<Detail>(leadId ? `/api/clients/${leadId}` : null);
  const d = detail.data;
  const advice = useApi<Advice>(d && d.audit?.status === 'completed' ? `/api/companies/${d.company_id}/advice` : null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [storyboard, setStoryboard] = useState<VideoStoryboardData | null>(null);
  const [aiAdvice, setAiAdvice] = useState<Advice | null>(null);
  const [country, setCountry] = useState('');
  const [contact, setContact] = useState({ first_name: '', last_name: '', title: '', email: '' });
  const [adding, setAdding] = useState(false);
  const [found, setFound] = useState<Found | null>(null);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setError(''); setNote('');
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : 'Failed'); } finally { setBusy(''); }
  };
  const audit = () => run('audit', async () => { await send(`/api/companies/${d!.company_id}/brief`, 'POST'); detail.reload(); advice.reload(); });
  const prepare = () => run('prepare', async () => {
    const r = await send<Prepared>(`/api/clients/${leadId}/prepare`, 'POST', { country_code: country || null });
    setNote(r.outcome === 'blocked_by_policy' ? `${OUTCOME.blocked_by_policy}: ${r.reason ?? ''}` : OUTCOME[r.outcome] ?? r.outcome);
    detail.reload();
  });
  const report = () => run('report', async () => { const r = await send<{ html_filename: string; pdf_filename: string | null }>('/api/reports/client', 'POST', { domain: d!.lead.domain, output_format: 'both' }); await openProtected(`/api/reports/view/${r.pdf_filename ?? r.html_filename}`); });
  const deck = () => run('deck', async () => { const r = await send<{ html_filename: string; pdf_filename: string | null; view_url: string }>('/api/reports/deck', 'POST', { domain: d!.lead.domain, output_format: 'both' }); await openProtected(r.view_url); });
  const openStoryboard = () => run('storyboard', async () => {
    const r = await send<{ status: string; storyboard: VideoStoryboardData }>('/api/reports/video-storyboard', 'POST', {
      lead_id: leadId!,
      prospect_name: d?.contacts[0]?.first_name ? `${d.contacts[0].first_name} ${d.contacts[0].last_name}` : 'Founder / CTO'
    });
    setStoryboard(r.storyboard);
  });
  const addContact = (e: FormEvent) => { e.preventDefault(); run('contact', async () => { await send(`/api/clients/${leadId}/contacts`, 'POST', contact); setContact({ first_name: '', last_name: '', title: '', email: '' }); setAdding(false); detail.reload(); }); };
  const verify = (cid: number) => run('verify', async () => { const r = await send<{ verified: boolean; reason: string }>(`/api/clients/${leadId}/contacts/${cid}/verify`, 'POST'); setNote(r.verified ? 'Verified.' : `Not verified: ${r.reason}`); detail.reload(); });
  const findContacts = () => run('find', async () => setFound(await send<Found>(`/api/clients/${leadId}/find_contacts`, 'POST')));
  const addCandidate = (c: Candidate) => run('contact', async () => {
    const [first, ...rest] = (c.name ?? 'Team').split(' ');
    await send(`/api/clients/${leadId}/contacts`, 'POST', { first_name: first, last_name: rest.join(' '), title: c.title ?? (c.kind === 'generic_email' ? 'Team inbox' : 'Contact'), email: c.email, linkedin_url: c.linkedin_url });
    detail.reload();
  });
  const askAi = () => run('ai', async () => setAiAdvice(await send<Advice>(`/api/companies/${d!.company_id}/advice/ai`, 'POST')));
  const shownAi = aiAdvice?.ai_recommendations;

  return (
    <Drawer open={leadId !== null} title={d?.lead.company_name ?? 'Client'} onClose={onClose} wide>
      {detail.loading && !d ? <Skeletons rows={4} /> : <ErrorBanner message={detail.error} />}
      {d && (
        <div className="space-y-5 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={d.priority.band === 'hot' ? 'good' : d.priority.band === 'warm' ? 'accent' : 'neutral'}>{d.priority.band} · {d.priority.score}</Badge>
            {d.has_website ? <a className="inline-flex items-center gap-1 text-xs text-indigo-300 hover:text-indigo-200" href={normalizeUrl(d.lead.domain)} target="_blank" rel="noreferrer noopener"><ExternalLink className="h-3.5 w-3.5" />{d.lead.domain}</a> : <Badge tone="warn">No website</Badge>}
            {d.lead.phone && <span className="font-mono text-xs text-slate-300">{d.lead.phone}</span>}
          </div>
          <div><ScoreBar value={d.priority.score} />
            <ul className="mt-2 text-xs text-slate-400 list-disc pl-4 space-y-0.5">{d.priority.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            <p className="text-[11px] text-slate-500 mt-1">A ranking aid built from what was observed, not a chance of winning. Confidence: {d.priority.confidence}.</p></div>

          {d.work_items.map((w) => <div key={w.id} className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-200"><strong>{w.title}</strong> {w.detail}</div>)}
          <ErrorBanner message={error} />
          {note && <div role="status" className="text-xs text-slate-200 rounded-lg border border-slate-700 px-3 py-2">{note}</div>}

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <h3 className="text-sm font-semibold text-white flex items-center gap-1.5"><ShieldCheck className="h-4 w-4 text-slate-400" />Website check</h3>
              <div className="flex gap-2">
                {d.has_website && <Button small variant="primary" disabled={busy !== ''} onClick={audit}>{busy === 'audit' ? 'Checking…' : d.audit ? 'Re-run audit' : 'Run audit'}</Button>}
                {d.audit?.status === 'completed' && <Button small disabled={busy !== ''} onClick={report}><FileText className="h-3.5 w-3.5" />Client report</Button>}
                {d.audit?.status === 'completed' && <Button small disabled={busy !== ''} onClick={deck}><Presentation className="h-3.5 w-3.5 text-amber-400" />Executive deck</Button>}
                {d.audit?.status === 'completed' && <Button small disabled={busy !== ''} onClick={openStoryboard}><Video className="h-3.5 w-3.5 text-purple-400" />Video script</Button>}
              </div>
            </div>
            {!d.has_website ? <p className="text-xs text-slate-400">This business has no website to audit. The pitch is building one; see the opener on its Find result.</p>
              : !d.audit ? <p className="text-xs text-slate-400">Not audited yet. The audit reads the public site (headers, TLS, SEO, accessibility, email DNS, visible software versions) and never tests anything intrusively.</p>
              : d.audit.status === 'blocked' ? <p className="text-xs text-amber-300">This site answered but refuses automated access, so its pages were not graded (only the certificate and email DNS were checked). Review it by hand in your own browser.</p>
              : d.audit.status !== 'completed' ? <p className="text-xs text-amber-300">The site could not be reached from our servers. One failed check is not proof it is down.</p>
              : <p className="text-xs text-slate-300">Health score <strong className="text-white tabular">{d.audit.overall_score}</strong>/100, checked {d.audit.created_at}.</p>}
          </Card>

          {advice.data && advice.data.recommendations.length > 0 && (
            <Card>
              <div className="flex items-center justify-between mb-2"><h3 className="text-sm font-semibold text-white">What to recommend</h3>
                <Button small disabled={busy !== ''} onClick={askAi}><Sparkles className="h-3.5 w-3.5" />{busy === 'ai' ? 'Writing…' : 'Plain-language version'}</Button></div>
              <ul className="space-y-2">{advice.data.recommendations.map((r) => (
                <li key={r.service_key} className="text-xs text-slate-300"><div className="flex items-center gap-2"><Badge tone={r.priority === 'high' ? 'bad' : r.priority === 'medium' ? 'warn' : 'neutral'}>{r.priority}</Badge><strong className="text-slate-100">{r.service}</strong>{r.price_band && <span className="text-slate-500">{r.price_band}</span>}</div><div className="text-slate-400 mt-0.5">{r.summary}</div></li>))}</ul>
              {shownAi && shownAi.length > 0 && <div className="mt-3 pt-3 border-t border-slate-800 space-y-2">{shownAi.map((r) => <div key={r.title} className="text-xs"><div className="text-slate-100 font-medium">{r.title}</div><div className="text-slate-400">{r.why_it_matters}</div></div>)}<p className="text-[11px] text-slate-500">Each point cites this company&apos;s audit evidence; uncited points were removed.</p></div>}
            </Card>
          )}
          {advice.data && advice.data.recommendations.length === 0 && <EmptyState title="No issues to recommend" hint="The audit found nothing above informational level." />}

          <Card>
            <div className="flex items-center justify-between mb-2"><h3 className="text-sm font-semibold text-white">Contacts</h3><div className="flex gap-2">{d.has_website && <Button small disabled={busy !== ''} onClick={findContacts}><Search className="h-3.5 w-3.5" />{busy === 'find' ? 'Reading their site…' : 'Find on their website'}</Button>}<Button small onClick={() => setAdding((v) => !v)}><UserPlus className="h-3.5 w-3.5" />Add contact</Button></div></div>
            {adding && (
              <form onSubmit={addContact} className="grid gap-2 sm:grid-cols-2 mb-3">
                <input className={field} required placeholder="First name" value={contact.first_name} onChange={(e) => setContact({ ...contact, first_name: e.target.value })} />
                <input className={field} placeholder="Last name" value={contact.last_name} onChange={(e) => setContact({ ...contact, last_name: e.target.value })} />
                <input className={field} placeholder="Title" value={contact.title} onChange={(e) => setContact({ ...contact, title: e.target.value })} />
                <input className={field} required type="email" placeholder="Email you found" value={contact.email} onChange={(e) => setContact({ ...contact, email: e.target.value })} />
                <Button variant="primary" className="sm:col-span-2" disabled={busy !== ''}>Save (stored unverified)</Button>
              </form>)}
            {found && (
              <div className="mb-3 rounded-lg border border-slate-800 p-3 space-y-2 animate-fade-up">
                <div className="text-xs text-slate-400">Read {found.pages_checked.length} page(s) on their own site. Only what they publish is shown; nothing is guessed.</div>
                {found.candidates.length === 0 && <p className="text-xs text-slate-300">No people or emails are published on the pages we could read.</p>}
                <ul className="divide-y divide-slate-800">{found.candidates.map((c, i) => (
                  <li key={i} className="py-2 flex flex-wrap items-start justify-between gap-2 text-xs">
                    <span className="min-w-0"><span className="text-slate-100 font-medium">{c.name ?? (c.kind === 'generic_email' ? 'Team inbox' : 'Email')}</span>{c.title && <span className="text-slate-400"> · {c.title}</span>}
                      <br /><span className="font-mono text-slate-400">{c.email ?? 'no email published'}</span>
                      <br /><a className="text-indigo-300 hover:text-indigo-200" href={c.source_url} target="_blank" rel="noreferrer noopener">{c.evidence}</a></span>
                    <span className="flex items-center gap-2 shrink-0">{c.kind === 'generic_email' && <Badge>team inbox</Badge>}
                      {c.linkedin_url && <a className="text-indigo-300 hover:text-indigo-200" href={c.linkedin_url} target="_blank" rel="noreferrer noopener">LinkedIn</a>}
                      {c.email ? <Button small disabled={busy !== ''} onClick={() => addCandidate(c)}>Add</Button> : <span className="text-slate-500">add an email by hand</span>}</span>
                  </li>))}</ul>
                <ul className="text-[11px] text-slate-500 list-disc pl-4">{found.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
                <a className="text-[11px] text-indigo-300 hover:text-indigo-200" href={found.linkedin_search_url} target="_blank" rel="noreferrer noopener">Search LinkedIn yourself</a>
              </div>)}
            {d.contacts.length === 0 ? <p className="text-xs text-slate-400">No contacts yet. Find a decision maker on the company site or LinkedIn, then add them here.</p> : (
              <ul className="divide-y divide-slate-800">{d.contacts.map((c) => (
                <li key={c.id} className="py-2 flex flex-wrap items-center justify-between gap-2 text-xs"><span className="text-slate-200">{c.first_name} {c.last_name} <span className="text-slate-500">{c.title}</span><br /><span className="font-mono text-slate-400">{c.email}</span></span>
                  <span className="flex items-center gap-2"><Badge tone={CONTACT_TONE[c.verification_status] ?? 'warn'}>{c.verification_status}</Badge>{c.verification_status !== 'verified' && <Button small disabled={busy !== ''} onClick={() => verify(c.id)}>Verify</Button>}</span></li>))}</ul>)}
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-white mb-2">Outreach</h3>
            <p className="text-xs text-slate-400 mb-3">Drafts a first email from the audit&apos;s measured findings and puts it in your approval inbox. Nothing is sent from here.</p>
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-xs text-slate-400 space-y-1">Recipient country (required)<input className={`${field} w-28`} maxLength={3} placeholder="US, GB…" value={country} onChange={(e) => setCountry(e.target.value.toUpperCase())} /></label>
              <Button variant="primary" disabled={busy !== '' || !country} onClick={prepare}>{busy === 'prepare' ? 'Preparing…' : 'Prepare first email'}</Button>
            </div>
          </Card>

          <ClientNotes leadId={d.lead.id} />
        </div>
      )}
      <VideoStoryboardDrawer open={storyboard !== null} onClose={() => setStoryboard(null)} storyboard={storyboard} />
    </Drawer>
  );
};
