import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { ArrowUpRight, Bell, Calculator, Check, Columns3, Copy, Download, ExternalLink, List, PanelRight, Pencil, Plus, Search, Trash2, Zap } from 'lucide-react';
import { Badge, Button, EmptyState, SearchInput, Select, SuggestInput, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { send } from '../../lib/hooks';
import { openSide } from './browser';
import { Section } from './shared';
import type { Post, Run } from './shared';
import { KIND_LABEL, STATUS_LABEL, localDay } from './types';
import type { Platform, Rec, Summary } from './types';
import type { ScraperMode } from '../browser/InteractiveBrowserSidepanel';

interface Tpl { id: number; name: string; body: string; saved: boolean }
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const openTab = (url: string) => window.open(url, '_blank', 'noopener,noreferrer');
const safeStore = {
  get: (k: string): string | null => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage unavailable: ticks just do not persist */ } },
};

export const Routine: FC<{ id: string; routines: Rec[]; doneToday: Map<number, number>; today: string; run: Run; post: Post; remove: (id: number) => void }> = ({ id, routines, doneToday, today, run, post, remove }) => {
  const [label, setLabel] = useState('');
  return (
    <Section title="Today's routine" hint="Tick items off as you do them in your own browser. A day only counts toward the streak when every item is done.">
      <ul className="space-y-1">
        {routines.map((r) => {
          const doneId = doneToday.get(r.id);
          const done = doneId !== undefined;
          return (
            <li key={r.id} className="flex items-center gap-2 group">
              <button role="checkbox" aria-checked={done} aria-label={`${r.label}: ${done ? 'done' : 'not done'}`}
                onClick={() => run(() => (done ? send(`/api/channels/${id}/records/${doneId}`, 'DELETE') : post('done', { routine_id: r.id, day: today })))}
                className={`h-5 w-5 rounded border flex items-center justify-center shrink-0 ${done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-slate-600'}`}>
                {done && <Check className="h-3.5 w-3.5" />}
              </button>
              <span className={`text-sm flex-1 ${done ? 'text-slate-500 line-through' : 'text-slate-200'}`}>{r.label}</span>
              <button aria-label={`Remove ${r.label}`} onClick={() => remove(r.id)} className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 text-slate-500 hover:text-rose-400"><Trash2 className="h-3.5 w-3.5" /></button>
            </li>);
        })}
      </ul>
      <form className="flex gap-2 mt-3" onSubmit={(e) => { e.preventDefault(); if (label.trim()) run(() => post('routine', { label })).then(() => setLabel('')); }}>
        <input className={field} aria-label="New routine item" placeholder="Add a routine item" value={label} onChange={(e) => setLabel(e.target.value)} />
        <Button small type="submit"><Plus className="h-3.5 w-3.5" />Add</Button>
      </form>
    </Section>
  );
};

export const OpenInBrowser: FC<{
  platform: Platform;
  links: Rec[];
  run: Run;
  post: Post;
  remove: (id: number) => void;
  onOpenScraper?: (url: string, mode?: ScraperMode, title?: string) => void;
}> = ({ platform, links, run, post, remove, onOpenScraper }) => {
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState('');
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [company, setCompany] = useState('');
  const [people, setPeople] = useState<Array<{ label: string; url: string }>>([]);

  const openInPanel = (targetUrl: string, label?: string) => {
    if (onOpenScraper) {
      onOpenScraper(targetUrl, 'job_spec', label || platform.label);
    } else {
      openSide(targetUrl);
    }
  };

  const search = async () => {
    setMsg('');
    const res = await apiFetch(`/api/channels/${platform.id}/search_url?q=${encodeURIComponent(q)}`);
    const body = await res.json().catch(() => ({}));
    if (res.ok) openInPanel(body.url, `${platform.label}: ${q}`); else setMsg(apiErrorMessage(res.status, body));
  };
  const findPeople = async () => {
    setMsg('');
    try { setPeople((await send<{ links: Array<{ label: string; url: string }> }>('/api/channels/linkedin/search_links', 'POST', { company })).links); } catch (e) { setMsg((e as Error).message); }
  };

  return (
    <Section title="Open in Side Panel or Browser" hint="Open directly in the built-in Side Panel (live preview + scraper + lead capture), or pop out to a signed-in browser tab.">
      <div className="flex flex-wrap gap-2 mb-3">
        {platform.home && <Button small variant="primary" onClick={() => openInPanel(platform.home!, platform.label)}><PanelRight className="h-3.5 w-3.5" />Open in Side Panel</Button>}
        {platform.home && <Button small onClick={() => openTab(platform.home!)}><ExternalLink className="h-3.5 w-3.5" />New tab</Button>}
      </div>
      {platform.has_search && (
        <form className="flex gap-2 mb-3" onSubmit={(e) => { e.preventDefault(); if (q.trim()) search(); }}>
          <SuggestInput className="flex-1" kinds={['skill', 'business']} label={`Search ${platform.label}`} placeholder={`Search ${platform.label}`} value={q} onChange={setQ} />
          <Button small type="submit"><Search className="h-3.5 w-3.5" />Search</Button>
        </form>)}
      {platform.id === 'linkedin' && (
        <div className="mb-3 rounded-lg border border-slate-800 p-3">
          <div className="text-xs font-medium text-slate-200 mb-2">Find decision makers at a company</div>
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (company.trim()) findPeople(); }}>
            <input className={field} aria-label="Company name" placeholder="Company name" value={company} onChange={(e) => setCompany(e.target.value)} />
            <Button small type="submit">Build links</Button>
          </form>
          {people.length > 0 && <ul className="mt-2 space-y-1">{people.map((l) => (
            <li key={l.url} className="flex items-center gap-2">
              <button type="button" onClick={() => openInPanel(l.url, l.label)} className="text-xs text-indigo-400 hover:underline inline-flex items-center gap-1 text-left"><PanelRight className="h-3 w-3" />{l.label}</button>
              <a href={l.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${l.label} in new tab`} className="text-slate-500 hover:text-slate-300"><ExternalLink className="h-3 w-3" /></a>
            </li>))}</ul>}
          <p className="text-[11px] text-slate-500 mt-2">Plain search links only. Nothing is fetched from LinkedIn.</p>
        </div>)}
      {msg && <p role="alert" className="text-xs text-rose-300 mb-2">{msg}</p>}
      <div className="text-xs font-medium text-slate-300 mb-1.5">Saved links</div>
      {links.length === 0 ? <p className="text-xs text-slate-500">Save the searches, saved filters and pages you use every day.</p> : (
        <ul className="space-y-1">{links.map((l) => (
          <li key={l.id} className="flex items-center gap-2 group">
            <button type="button" onClick={() => openInPanel(l.url, l.title || l.url)} className="flex-1 min-w-0 truncate text-left text-sm text-indigo-400 hover:underline">{l.title || l.url}</button>
            <a href={l.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${l.title || l.url} in new tab`} className="text-slate-500 hover:text-slate-300"><ExternalLink className="h-3.5 w-3.5" /></a>
            <button aria-label={`Remove ${l.title || l.url}`} onClick={() => remove(l.id)} className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 text-slate-500 hover:text-rose-400"><Trash2 className="h-3.5 w-3.5" /></button>
          </li>))}</ul>)}
      <form className="grid gap-2 sm:grid-cols-[1fr_1.5fr_auto] mt-3" onSubmit={(e) => { e.preventDefault(); run(() => post('link', { title, url })).then(() => { setTitle(''); setUrl(''); }); }}>
        <input className={field} aria-label="Link name" placeholder="Name" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input className={field} aria-label="Link address" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
        <Button small type="submit"><Plus className="h-3.5 w-3.5" />Save</Button>
      </form>
    </Section>
  );
};

const PLATFORM_ACTIVITY: Record<string, string[]> = {
  linkedin: ['invite_sent', 'invite_accepted', 'comment_left', 'message_sent', 'reply_received', 'call_booked'],
  fiverr: ['gig_impressions', 'gig_clicks', 'inquiry_received', 'gig_orders', 'message_sent', 'reply_received'],
  upwork: ['proposal_sent', 'proposal_viewed', 'connects_spent', 'reply_received', 'call_booked'],
  freelancer: ['proposal_sent', 'proposal_viewed', 'bids_spent', 'reply_received', 'call_booked'],
  peopleperhour: ['proposal_sent', 'proposal_viewed', 'credits_spent', 'reply_received', 'call_booked'],
  guru: ['proposal_sent', 'proposal_viewed', 'quotes_spent', 'reply_received', 'call_booked'],
  clutch: ['review_invited', 'review_published', 'inquiry_received', 'profile_view', 'call_booked'],
  contra: ['gig_impressions', 'gig_clicks', 'inquiry_received', 'gig_orders'],
  toptal: ['match_received', 'call_booked', 'trial_started', 'hire_confirmed'],
};
const BID_COST_PLATFORMS = new Set(['upwork', 'freelancer', 'peopleperhour', 'guru']);

const addDays = (iso: string, days: number) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + days);
  return localDay(d);
};

export const Pipeline: FC<{
  platformId?: string;
  statuses: string[];
  items: Rec[];
  run: Run;
  post: Post;
  update: (id: number, d: Record<string, unknown>) => void;
  remove: (id: number) => void;
  promote?: (id: number) => void;
}> = ({ platformId = 'upwork', statuses, items, run, post, update, remove, promote }) => {
  const blank = { title: '', counterparty: '', url: '', value: '', cost: '', next_followup: '', status: 'applied', notes: '' };
  const [f, setF] = useState(blank);
  const [filter, setFilter] = useState('all');
  const [view, setView] = useState<'list' | 'board'>('list');
  const [find, setFind] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ title: '', counterparty: '', value: '', cost: '', next_followup: '', url: '', notes: '' });
  const showCost = BID_COST_PLATFORMS.has(platformId);
  const today = localDay();
  const isDue = (r: Rec) => r.status !== 'won' && r.status !== 'lost' && Boolean(r.next_followup && r.next_followup <= today);
  const dueCount = items.filter(isDue).length;
  const shown = items.filter((r) => {
    const matchFilter = filter === 'all' ? true : filter === 'due' ? isDue(r) : r.status === filter;
    const matchText = !find.trim() || `${r.title} ${r.counterparty ?? ''} ${r.notes ?? ''}`.toLowerCase().includes(find.trim().toLowerCase());
    return matchFilter && matchText;
  });
  const exportCsv = () => {
    const q = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const rows = [['title', 'client', 'status', 'value', 'cost', 'follow_up', 'notes', 'link'], ...items.map((r) => [r.title, r.counterparty, r.status, r.value, r.cost, r.next_followup, r.notes, r.url])];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([rows.map((r) => r.map(q).join(',')).join('\n')], { type: 'text/csv' }));
    a.download = `${platformId}-pipeline.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const set = (k: keyof typeof blank) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Section
      title="Applications and outreach"
      hint="Log every proposal, bid, or outreach thread with a follow-up date. Switch between List and Kanban Board, or push warm deals straight into your CRM."
      aside={
        items.length > 0 ? (
          <div className="inline-flex rounded-lg border border-slate-700 p-0.5 text-xs">
            <button type="button" onClick={() => setView('list')} className={`inline-flex items-center gap-1 px-2 py-1 rounded-md ${view === 'list' ? 'bg-indigo-500/20 text-indigo-300' : 'text-slate-400 hover:text-white'}`}><List className="h-3.5 w-3.5" />List</button>
            <button type="button" onClick={() => setView('board')} className={`inline-flex items-center gap-1 px-2 py-1 rounded-md ${view === 'board' ? 'bg-indigo-500/20 text-indigo-300' : 'text-slate-400 hover:text-white'}`}><Columns3 className="h-3.5 w-3.5" />Board</button>
          </div>
        ) : undefined
      }
    >
      <form className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6 mb-4" onSubmit={(e) => { e.preventDefault(); run(() => post('pipeline', { ...f, value: f.value === '' ? null : Number(f.value), cost: f.cost === '' ? null : Number(f.cost) })).then(() => setF(blank)); }}>
        <input className={`${field} lg:col-span-2`} aria-label="Title" placeholder="Project or person" value={f.title} onChange={set('title')} required />
        <input className={field} aria-label="Client" placeholder="Client" value={f.counterparty} onChange={set('counterparty')} />
        <input className={field} aria-label="Value in dollars" placeholder="Value $" inputMode="decimal" value={f.value} onChange={set('value')} />
        <Select aria-label="Status" value={f.status} onChange={(v) => setF({ ...f, status: v })} options={statuses.map((s) => ({ value: s, label: STATUS_LABEL[s] ?? s }))} />
        <input className={field} type="date" aria-label="Follow up on" value={f.next_followup} onChange={set('next_followup')} />
        <input className={`${field} sm:col-span-2 ${showCost ? 'lg:col-span-2' : 'lg:col-span-3'}`} aria-label="Link" placeholder="Link to post or thread (optional)" value={f.url} onChange={set('url')} />
        <input className={`${field} ${showCost ? 'lg:col-span-2' : 'lg:col-span-2'}`} aria-label="Notes" placeholder="Notes / angle / loss reason" value={f.notes} onChange={set('notes')} />
        {showCost && (
          <input className={field} aria-label="Cost to apply in dollars" inputMode="decimal" placeholder="Cost $ (Connects)" value={f.cost} onChange={set('cost')} />
        )}
        <Button type="submit" variant="primary"><Plus className="h-3.5 w-3.5" />Log it</Button>
      </form>
      {items.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 mb-3" role="group" aria-label="Filter by status">
          {['all', 'due', ...statuses].map((st) => {
            const n = st === 'all' ? items.length : st === 'due' ? dueCount : items.filter((r) => r.status === st).length;
            const label = st === 'all' ? 'All' : st === 'due' ? 'Due today' : STATUS_LABEL[st] ?? st;
            return (
              <button key={st} aria-pressed={filter === st} onClick={() => setFilter(st)}
                className={`px-2.5 py-1 rounded-md text-xs border ${filter === st ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-300' : st === 'due' && dueCount > 0 ? 'border-amber-500/40 text-amber-300' : 'border-slate-700 text-slate-400'}`}>
                {label} <span className="tabular opacity-70">{n}</span>
              </button>
            );
          })}
          <SearchInput className="w-48 ml-auto" label="Search…" value={find} onChange={setFind} />
          <Button small onClick={exportCsv}><Download className="h-3.5 w-3.5" />CSV</Button>
        </div>)}
      {items.length === 0 ? <EmptyState title="Nothing logged yet" hint="Add each application after you send it." /> : shown.length === 0 ? <p className="text-xs text-slate-500 py-3">Nothing matches.</p> : view === 'board' ? (
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          {statuses.map((st) => {
            const col = shown.filter((r) => r.status === st);
            const colVal = col.reduce((sum, r) => sum + (Number(r.value) || 0), 0);
            return (
              <div key={st} className="rounded-xl border border-slate-800 bg-slate-900/40 p-2.5 flex flex-col gap-2 min-h-[140px]">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-200">{STATUS_LABEL[st] ?? st}</span>
                  <span className="text-slate-400 tabular">{col.length}{colVal > 0 ? ` · $${Math.round(colVal).toLocaleString()}` : ''}</span>
                </div>
                <div className="space-y-2">
                  {col.map((r) => (
                    <div key={r.id} className="rounded-lg border border-slate-800 bg-slate-950/70 p-2 space-y-1.5 text-xs">
                      <div className="font-medium text-slate-100 leading-snug">{r.title}</div>
                      {(r.counterparty || r.value) && (
                        <div className="text-[11px] text-slate-400">{[r.counterparty, r.value ? `$${Number(r.value).toLocaleString()}` : null].filter(Boolean).join(' · ')}</div>
                      )}
                      {isDue(r) && <Badge tone="warn">Follow up due</Badge>}
                      <div className="flex items-center gap-1 pt-1">
                        <Select small aria-label={`Move ${r.title}`} className="flex-1" value={r.status} onChange={(v) => update(r.id, { status: v })} options={statuses.map((s) => ({ value: s, label: STATUS_LABEL[s] ?? s }))} />
                        {promote && !r.crm_lead_id && (
                          <button type="button" title="Push to CRM Leads" onClick={() => promote(r.id)} className="px-1.5 py-1 rounded border border-indigo-500/40 text-[11px] text-indigo-300 hover:bg-indigo-500/15">CRM</button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <ul className="divide-y divide-slate-800">
          {[...shown].reverse().map((r) => {
            const overdue = isDue(r);
            const isEditing = editingId === r.id;
            return (
              <li key={r.id} className="py-2.5 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex-1 min-w-[12rem]">
                    <div className="text-sm text-slate-100 flex items-center gap-2">
                      {r.url ? <a href={r.url} target="_blank" rel="noopener noreferrer" className="hover:underline text-indigo-400">{r.title}</a> : <span>{r.title}</span>}
                      {r.crm_lead_id && <Badge tone="good">In CRM #{r.crm_lead_id}</Badge>}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {[r.counterparty, r.value ? `$${Number(r.value).toLocaleString()}` : null, r.cost ? `$${Number(r.cost)} cost` : null, r.notes].filter(Boolean).join(' · ') || 'no client or value'}
                    </div>
                  </div>
                  {overdue && (
                    <>
                      <Badge tone="warn">Follow up</Badge>
                      <Button small onClick={() => update(r.id, { next_followup: addDays(today, 2) })}>+2d</Button>
                    </>
                  )}
                  <Select small aria-label={`Status of ${r.title}`} className="w-32" value={r.status} onChange={(v) => update(r.id, { status: v })} options={statuses.map((s) => ({ value: s, label: STATUS_LABEL[s] ?? s }))} />
                  <input className={`${field} !w-auto`} type="date" aria-label={`Follow up date for ${r.title}`} value={r.next_followup ?? ''} onChange={(e) => update(r.id, { next_followup: e.target.value || null })} />
                  {promote && !r.crm_lead_id && (
                    <Button small onClick={() => promote(r.id)}><ArrowUpRight className="h-3.5 w-3.5" />Push to CRM</Button>
                  )}
                  <Button small variant="ghost" onClick={() => {
                    if (isEditing) setEditingId(null);
                    else {
                      setEditingId(r.id);
                      setEditForm({
                        title: r.title ?? '',
                        counterparty: r.counterparty ?? '',
                        value: r.value != null ? String(r.value) : '',
                        cost: r.cost != null ? String(r.cost) : '',
                        next_followup: r.next_followup ?? '',
                        url: r.url ?? '',
                        notes: r.notes ?? '',
                      });
                    }
                  }}>{isEditing ? 'Cancel' : 'Edit'}</Button>
                  <button aria-label={`Delete ${r.title}`} onClick={() => remove(r.id)} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
                </div>
                {isEditing && (
                  <form className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 p-2.5 rounded-xl bg-slate-900/70 border border-slate-800" onSubmit={(e) => {
                    e.preventDefault();
                    update(r.id, {
                      title: editForm.title.trim() || r.title,
                      counterparty: editForm.counterparty.trim(),
                      value: editForm.value === '' ? null : Number(editForm.value),
                      cost: editForm.cost === '' ? null : Number(editForm.cost),
                      next_followup: editForm.next_followup || null,
                      url: editForm.url.trim(),
                      notes: editForm.notes.trim(),
                    });
                    setEditingId(null);
                  }}>
                    <input className={field} required value={editForm.title} onChange={(e) => setEditForm({ ...editForm, title: e.target.value })} placeholder="Project or person" />
                    <input className={field} value={editForm.counterparty} onChange={(e) => setEditForm({ ...editForm, counterparty: e.target.value })} placeholder="Client" />
                    <input className={field} inputMode="decimal" value={editForm.value} onChange={(e) => setEditForm({ ...editForm, value: e.target.value })} placeholder="Value $" />
                    {showCost ? (
                      <input className={field} inputMode="decimal" value={editForm.cost} onChange={(e) => setEditForm({ ...editForm, cost: e.target.value })} placeholder="Cost $" />
                    ) : (
                      <input className={field} type="date" value={editForm.next_followup} onChange={(e) => setEditForm({ ...editForm, next_followup: e.target.value })} />
                    )}
                    <input className={`${field} lg:col-span-2`} value={editForm.url} onChange={(e) => setEditForm({ ...editForm, url: e.target.value })} placeholder="URL" />
                    <input className={field} value={editForm.notes} onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })} placeholder="Notes / loss reason" />
                    <Button small type="submit" variant="primary">Save changes</Button>
                  </form>
                )}
              </li>);
          })}
        </ul>)}
    </Section>
  );
};

export const Templates: FC<{
  platform: Platform;
  items: Rec[];
  run: Run;
  post: Post;
  update?: (id: number, d: Record<string, unknown>) => void;
  remove: (id: number) => void;
}> = ({ platform, items, run, post, update, remove }) => {
  const [name, setName] = useState('');
  const [body, setBody] = useState('');
  const [copied, setCopied] = useState<string | null>(null);
  const [vars, setVars] = useState({ client: '', company: '', project: '', rate: '', portfolio: '' });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTpl, setEditTpl] = useState({ name: '', body: '' });
  const limit = platform.limits.note_chars;
  const saved = new Set(items.map((i) => i.name));
  const starters = platform.templates.filter((t) => !saved.has(t.name));

  const renderBody = (raw: string) => {
    let out = raw;
    const map: Array<[RegExp, string]> = [
      [/\{client_name\}|\{client\}|\{name\}|\{first_name\}/gi, vars.client],
      [/\{company\}|\{company_name\}/gi, vars.company],
      [/\{project\}|\{project_title\}|\{title\}/gi, vars.project],
      [/\{rate\}|\{budget\}|\{price\}/gi, vars.rate],
      [/\{portfolio\}|\{link\}|\{case_study\}/gi, vars.portfolio],
    ];
    for (const [re, val] of map) {
      if (val.trim()) out = out.replace(re, val.trim());
    }
    return out;
  };

  const copy = async (key: string, text: string) => { try { await navigator.clipboard.writeText(renderBody(text)); setCopied(key); window.setTimeout(() => setCopied(null), 1500); } catch { setCopied(null); } };
  const count = (text: string) => limit ? <span className={`text-[11px] tabular ${text.length > limit ? 'text-rose-400' : 'text-slate-500'}`}>{text.length}/{limit}</span> : null;
  return (
    <Section title="Message templates" hint="Fill the quick variables below to auto-populate {placeholders} across every template before copying.">
      <div className="grid gap-2 sm:grid-cols-5 mb-3 rounded-lg border border-slate-800 bg-slate-900/40 p-2.5">
        <input className={field} aria-label="Variable Client" placeholder="{client}" value={vars.client} onChange={(e) => setVars({ ...vars, client: e.target.value })} />
        <input className={field} aria-label="Variable Company" placeholder="{company}" value={vars.company} onChange={(e) => setVars({ ...vars, company: e.target.value })} />
        <input className={field} aria-label="Variable Project" placeholder="{project}" value={vars.project} onChange={(e) => setVars({ ...vars, project: e.target.value })} />
        <input className={field} aria-label="Variable Rate" placeholder="{rate}" value={vars.rate} onChange={(e) => setVars({ ...vars, rate: e.target.value })} />
        <input className={field} aria-label="Variable Portfolio" placeholder="{portfolio}" value={vars.portfolio} onChange={(e) => setVars({ ...vars, portfolio: e.target.value })} />
      </div>
      <ul className="space-y-2">
        {[...items.map((t): Tpl => ({ id: t.id, name: String(t.name), body: String(t.body), saved: true })), ...starters.map((t, i): Tpl => ({ id: -1 - i, name: t.name, body: t.body, saved: false }))].map((t) => {
          const preview = renderBody(t.body);
          const isEditing = t.saved && editingId === t.id;
          return (
            <li key={`${t.saved}-${t.id}`} className="rounded-lg border border-slate-800 p-2.5">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-slate-100 flex-1">{t.name}</span>{!t.saved && <Badge tone="info">Starter</Badge>}{count(preview)}
                <button aria-label={`Copy ${t.name}`} onClick={() => copy(`${t.id}`, t.body)} className="text-slate-400 hover:text-white">{copied === `${t.id}` ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}</button>
                {t.saved && update && (
                  <button aria-label={`Edit ${t.name}`} onClick={() => { if (isEditing) setEditingId(null); else { setEditingId(t.id); setEditTpl({ name: t.name, body: t.body }); } }} className="text-slate-400 hover:text-white"><Pencil className="h-3.5 w-3.5" /></button>
                )}
                {t.saved ? <button aria-label={`Delete ${t.name}`} onClick={() => remove(t.id)} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
                  : <button aria-label={`Save ${t.name} to my templates`} onClick={() => run(() => post('template', { name: t.name, body: t.body }))} className="text-slate-400 hover:text-white"><Plus className="h-4 w-4" /></button>}
              </div>
              {isEditing ? (
                <form className="space-y-2 mt-2" onSubmit={(e) => { e.preventDefault(); update?.(t.id, editTpl); setEditingId(null); }}>
                  <input className={field} value={editTpl.name} onChange={(e) => setEditTpl({ ...editTpl, name: e.target.value })} required />
                  <textarea className={field} rows={3} value={editTpl.body} onChange={(e) => setEditTpl({ ...editTpl, body: e.target.value })} required />
                  <div className="flex gap-2">
                    <Button small type="submit" variant="primary">Save</Button>
                    <Button small type="button" variant="ghost" onClick={() => setEditingId(null)}>Cancel</Button>
                  </div>
                </form>
              ) : (
                <p className="text-xs text-slate-400 whitespace-pre-wrap">{preview}</p>
              )}
            </li>
          );
        })}
      </ul>
      <form className="space-y-2 mt-3" onSubmit={(e) => { e.preventDefault(); run(() => post('template', { name, body })).then(() => { setName(''); setBody(''); }); }}>
        <input className={field} aria-label="Template name" placeholder="Template name" value={name} onChange={(e) => setName(e.target.value)} required />
        <textarea className={field} rows={3} aria-label="Template text" placeholder="Template text (supports {client}, {company}, {project}, {rate}, {portfolio})" value={body} onChange={(e) => setBody(e.target.value)} required />
        <div className="flex items-center justify-between">{count(body)}<Button small type="submit"><Plus className="h-3.5 w-3.5" />Save template</Button></div>
      </form>
    </Section>
  );
};

export const Messages: FC<{ items: Rec[]; s: Summary | null; run: Run; post: Post; update: (id: number, d: Record<string, unknown>) => void; remove: (id: number) => void }> = ({ items, s, run, post, update, remove }) => {
  const [note, setNote] = useState('');
  const r = s?.response;
  return (
    <Section title="Messages and response time" hint="Log when a client messages you and when you reply. Fast, honest replies are what platforms and clients reward. Nothing is read from the site.">
      {r && <div className="flex flex-wrap gap-2 mb-3">
        <Badge tone={r.unanswered ? 'warn' : 'good'}>{r.unanswered} waiting{r.unanswered ? ` · oldest ${r.oldest_unanswered_hours} h` : ''}</Badge>
        <Badge>{r.within_1h_pct === null ? 'No replies logged yet' : `${r.within_1h_pct}% answered within 1 h`}</Badge>
        {r.within_24h_pct !== null && <Badge>{r.within_24h_pct}% within 24 h</Badge>}
      </div>}
      <form className="flex gap-2 mb-3" onSubmit={(e) => { e.preventDefault(); run(() => post('message', { received_at: new Date().toISOString(), note })).then(() => setNote('')); }}>
        <input className={field} aria-label="Message note" placeholder="Who wrote? (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button small type="submit">Message received now</Button>
      </form>
      {items.length === 0 ? <p className="text-xs text-slate-500">No messages logged.</p> : (
        <ul className="divide-y divide-slate-800">{[...items].reverse().slice(0, 8).map((m) => (
          <li key={m.id} className="py-2 flex items-center gap-2 text-xs">
            <span className="flex-1 min-w-0 truncate text-slate-300">{m.note || 'Message'} · {new Date(m.received_at).toLocaleString()}</span>
            {m.replied_at ? <Badge tone="good">Replied</Badge> : <Button small onClick={() => update(m.id, { replied_at: new Date().toISOString() })}>I replied</Button>}
            <button aria-label="Delete message entry" onClick={() => remove(m.id)} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-3.5 w-3.5" /></button>
          </li>))}</ul>)}
    </Section>
  );
};

export const Activity: FC<{ platformId?: string; kinds: string[]; s: Summary | null; today: string; run: Run; post: Post }> = ({ platformId = 'upwork', kinds, s, today, run, post }) => {
  const allowed = PLATFORM_ACTIVITY[platformId];
  const filteredKinds = allowed ? kinds.filter((k) => allowed.includes(k)) : kinds;
  const activeKinds = filteredKinds.length > 0 ? filteredKinds : kinds;
  const [kind, setKind] = useState(activeKinds[0] ?? 'message_sent');
  const [qty, setQty] = useState('1');
  const week = s?.activity_this_week ?? {};
  return (
    <Section title="Activity this week" hint="Count platform-specific activity to measure conversion and ROI.">
      {Object.keys(week).length === 0 ? <p className="text-xs text-slate-500 mb-3">Nothing logged since Monday.</p> : (
        <div className="flex flex-wrap gap-2 mb-3">{Object.entries(week).map(([k, v]) => <Badge key={k} tone="accent">{KIND_LABEL[k] ?? k}: {v}</Badge>)}</div>)}
      <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); run(() => post('activity', { kind, qty: Number(qty), day: today })); }}>
        <Select small aria-label="Activity" className="flex-1 min-w-[10rem]" value={kind} onChange={setKind} options={activeKinds.map((k) => ({ value: k, label: KIND_LABEL[k] ?? k }))} />
        <input className={`${field} !w-24`} type="number" min={0} aria-label="How many" value={qty} onChange={(e) => setQty(e.target.value)} />
        <Button small type="submit"><Plus className="h-3.5 w-3.5" />Add for today</Button>
      </form>
    </Section>
  );
};

export const Availability: FC<{ platform: Platform; setting: Summary['setting']; s: Summary | null; run: Run; post: Post }> = ({ platform, setting, s, run, post }) => {
  const cfg = setting ?? { work_days: [0, 1, 2, 3, 4], start: '09:00', end: '17:00', remind_minutes: 60, notify: false, weekly_invite_limit: 80 };
  const [perm, setPerm] = useState<string>(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission);
  const save = (patch: Partial<typeof cfg>) => run(() => post('setting', { ...cfg, ...patch }));

  // Check-in reminders: only while this tab is open. They prompt YOU to check the platform; they never touch it.
  useEffect(() => {
    if (!setting?.notify || perm !== 'granted' || !s) return;
    const tick = () => {
      const now = new Date();
      if (!setting.work_days.includes((now.getDay() + 6) % 7)) return;
      const hm = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
      if (hm < setting.start || hm > setting.end) return;
      const [sh, sm] = setting.start.split(':').map(Number);
      const since = now.getHours() * 60 + now.getMinutes() - (sh * 60 + sm);
      const due = setting.remind_minutes === 0 ? since === 0 : since % setting.remind_minutes === 0;
      const todo = [s.response.unanswered ? `${s.response.unanswered} message(s) waiting` : '', s.pipeline.followups_due ? `${s.pipeline.followups_due} follow-up(s) due` : '',
        s.routine.done_today < s.routine.total ? `${s.routine.total - s.routine.done_today} routine item(s) left` : ''].filter(Boolean);
      if (due && todo.length) new Notification('Time to check in', { body: todo.join(' · ') });
    };
    const t = window.setInterval(tick, 60000);
    return () => window.clearInterval(t);
  }, [setting, perm, s]);

  const ask = async () => { if (typeof Notification !== 'undefined') setPerm(await Notification.requestPermission()); };
  return (
    <Section title="Working hours and check-in reminders" hint="Reminders nudge you to check in while this tab is open. They cannot make an account look online. Only being there does that.">
      <div className="flex flex-wrap gap-1.5 mb-3" role="group" aria-label="Working days">
        {DAYS.map((d, i) => { const on = cfg.work_days.includes(i); return (
          <button key={d} aria-pressed={on} onClick={() => save({ work_days: on ? cfg.work_days.filter((x) => x !== i) : [...cfg.work_days, i] })}
            className={`px-2.5 py-1 rounded-md text-xs border ${on ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-300' : 'border-slate-700 text-slate-400'}`}>{d}</button>); })}
      </div>
      <div className="flex flex-wrap items-center gap-2 mb-3 text-xs text-slate-400">
        <label>From <input className={`${field} !w-auto`} type="time" value={cfg.start} onChange={(e) => e.target.value && save({ start: e.target.value })} /></label>
        <label>To <input className={`${field} !w-auto`} type="time" value={cfg.end} onChange={(e) => e.target.value && save({ end: e.target.value })} /></label>
        <label className="inline-flex items-center gap-1.5">Remind <Select small aria-label="Remind interval" className="w-36" value={cfg.remind_minutes} onChange={(v) => save({ remind_minutes: Number(v) })} options={[{ value: 0, label: 'at start only' }, { value: 30, label: 'every 30 min' }, { value: 60, label: 'every hour' }, { value: 120, label: 'every 2 hours' }]} /></label>
      </div>
      {platform.id === 'linkedin' && (
        <label className="flex flex-wrap items-center gap-2 mb-3 text-xs text-slate-400">Weekly invite limit
          <input className={`${field} !w-24`} type="number" min={0} max={500} aria-label="Weekly invite limit" value={cfg.weekly_invite_limit ?? 80} onChange={(e) => e.target.value !== '' && save({ weekly_invite_limit: Number(e.target.value) })} />
          <span>0 turns the pacing meter off</span></label>)}
      {perm === 'unsupported' ? <p className="text-xs text-slate-500">This browser does not support notifications.</p> : perm === 'denied' ? (
        <p className="text-xs text-amber-300">Notifications are blocked for this site in your browser settings.</p>
      ) : perm !== 'granted' ? <Button small onClick={ask}><Bell className="h-3.5 w-3.5" />Allow notifications</Button> : (
        <label className="inline-flex items-center gap-2 text-sm text-slate-200"><input type="checkbox" checked={cfg.notify} onChange={(e) => save({ notify: e.target.checked })} />Remind me during working hours</label>)}
    </Section>
  );
};

export const ProfileHealth: FC<{ platform: Platform }> = ({ platform }) => {
  const key = `agencybd.channels.profile.${platform.id}`;
  const [ticked, setTicked] = useState<string[]>(() => { try { return JSON.parse(safeStore.get(key) ?? '[]'); } catch { return []; } });
  if (platform.profile.length === 0) return null;
  const toggle = (item: string) => { const next = ticked.includes(item) ? ticked.filter((x) => x !== item) : [...ticked, item]; setTicked(next); safeStore.set(key, JSON.stringify(next)); };
  return (
    <Section title="Profile health" hint="A checklist of what makes a profile convert. Ticks are saved in this browser only." aside={<Badge tone={ticked.length === platform.profile.length ? 'good' : 'neutral'}>{ticked.filter((t) => platform.profile.includes(t)).length}/{platform.profile.length}</Badge>}>
      <ul className="grid gap-1 sm:grid-cols-2">{platform.profile.map((p) => (
        <li key={p}><label className="flex items-start gap-2 text-sm text-slate-200 cursor-pointer"><input type="checkbox" className="mt-1" checked={ticked.includes(p)} onChange={() => toggle(p)} />{p}</label></li>))}</ul>
    </Section>
  );
};

export const QuickPages: FC<{
  platform: Platform;
  onOpenScraper?: (url: string, mode?: ScraperMode, title?: string) => void;
}> = ({ platform, onOpenScraper }) => {
  if (platform.pages.length === 0) return null;
  const openPage = (url: string, label: string) => {
    if (onOpenScraper) onOpenScraper(url, 'job_spec', `${platform.label} · ${label}`);
    else openSide(url);
  };
  return (
    <Section title={`${platform.label} pages`} hint="Jump straight to the page you need in the built-in Side Panel (or pop out to a new tab).">
      <div className="flex flex-wrap gap-2">
        {platform.pages.map((p) => (
          <div key={p.url} className="inline-flex items-center rounded-lg border border-slate-700/80 bg-slate-900/50 overflow-hidden">
            <Button small className="!border-0 !rounded-none" onClick={() => openPage(p.url, p.label)}>
              <PanelRight className="h-3.5 w-3.5" />{p.label}
            </Button>
            <a href={p.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${p.label} in new tab`} className="px-2 py-1.5 text-slate-400 hover:text-white border-l border-slate-700/80">
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        ))}
      </div>
    </Section>
  );
};

export const QuickActivityBar: FC<{ platform: Platform; s: Summary | null; today: string; run: Run; post: Post }> = ({ platform, s, today, run, post }) => {
  const actions = platform.quick_actions?.length
    ? platform.quick_actions
    : (PLATFORM_ACTIVITY[platform.id] ?? ['proposal_sent', 'message_sent', 'reply_received']).map((k) => ({ kind: k, label: KIND_LABEL[k] ?? k }));
  const week = s?.activity_this_week ?? {};
  return (
    <Section title="Manual activity fallback" hint="Fallback quick-log when working outside the Side Panel — uses native platform actions & currencies.">
      <div className="flex flex-wrap gap-2">
        {actions.slice(0, 5).map((act) => (
          <Button key={act.kind} small onClick={() => run(() => post('activity', { kind: act.kind, qty: 1, day: today }))}>
            <Zap className="h-3.5 w-3.5 text-amber-400" />
            +1 {act.label}
            <Badge tone="neutral">{week[act.kind] ?? 0}</Badge>
          </Button>
        ))}
      </div>
    </Section>
  );
};

const PLATFORM_FEES: Record<string, { feePct: number; note: string }> = {
  upwork: { feePct: 10, note: 'Upwork flat 10% service fee (+ Connects cost)' },
  fiverr: { feePct: 20, note: 'Fiverr 20% marketplace commission' },
  freelancer: { feePct: 10, note: 'Freelancer 10% project fee (or $5 min)' },
  peopleperhour: { feePct: 20, note: 'PeoplePerHour 20% under $350, 7.5% above' },
  guru: { feePct: 9, note: 'Guru 9% standard fee (lower on paid tiers)' },
  contra: { feePct: 0, note: 'Contra 0% freelancer commission' },
  toptal: { feePct: 0, note: 'Toptal pays your net agreed rate directly' },
  linkedin: { feePct: 0, note: 'Direct B2B invoicing (0% platform cut)' },
  clutch: { feePct: 0, note: 'Direct B2B contract (0% platform cut)' },
};

export const FeeCalculator: FC<{ platform: Platform }> = ({ platform }) => {
  const cfg = PLATFORM_FEES[platform.id] ?? { feePct: 0, note: 'Direct contract (0% platform fee)' };
  const [gross, setGross] = useState('2500');
  const [hours, setHours] = useState('25');
  const [connectsCost, setConnectsCost] = useState('0');
  const g = Math.max(0, Number(gross) || 0);
  const h = Math.max(0, Number(hours) || 0);
  const c = Math.max(0, Number(connectsCost) || 0);
  const fee = (g * cfg.feePct) / 100;
  const net = Math.max(0, g - fee - c);
  const effRate = h > 0 ? net / h : 0;
  return (
    <Section title="Net margin & fee calculator" hint={cfg.note} aside={<Calculator className="h-4 w-4 text-indigo-400" />}>
      <div className="grid gap-2 sm:grid-cols-3 mb-3">
        <label className="text-xs text-slate-400 space-y-1">Client price $
          <input className={field} inputMode="decimal" value={gross} onChange={(e) => setGross(e.target.value)} /></label>
        <label className="text-xs text-slate-400 space-y-1">Est. hours
          <input className={field} inputMode="decimal" value={hours} onChange={(e) => setHours(e.target.value)} /></label>
        <label className="text-xs text-slate-400 space-y-1">Bid / ad cost $
          <input className={field} inputMode="decimal" value={connectsCost} onChange={(e) => setConnectsCost(e.target.value)} /></label>
      </div>
      <div className="grid gap-2 grid-cols-3 text-xs">
        <div className="rounded-lg border border-slate-800 p-2.5"><div className="text-slate-400">Platform fee ({cfg.feePct}%)</div><div className="text-base font-semibold text-rose-300 tabular">-${Math.round(fee).toLocaleString()}</div></div>
        <div className="rounded-lg border border-slate-800 p-2.5"><div className="text-slate-400">Net take-home</div><div className="text-base font-semibold text-emerald-300 tabular">${Math.round(net).toLocaleString()}</div></div>
        <div className="rounded-lg border border-slate-800 p-2.5"><div className="text-slate-400">Effective / hr</div><div className="text-base font-semibold text-white tabular">${effRate.toFixed(0)}/hr</div></div>
      </div>
    </Section>
  );
};

export const Features: FC<{ platform: Platform }> = ({ platform }) => (
  <Section title={`What ${platform.label} offers`} hint="The tools on the site and how to get more from each. Do the work there by hand; log it here.">
    <ul className="grid gap-3 md:grid-cols-2">{platform.features.map((f) => (
      <li key={f.title} className="rounded-lg border border-slate-800 p-3">
        <div className="text-sm font-medium text-slate-100">{f.title}</div>
        <p className="text-xs text-slate-400 mt-1">{f.text}</p>
        <p className="text-xs text-indigo-300 mt-1.5">Tip: {f.tip}</p>
      </li>))}</ul>
  </Section>
);

const pct = (a: number, b: number) => (b > 0 ? `${Math.round((100 * a) / b)}%` : 'n/a');

/** Ratios from the numbers you logged this week. n/a means there is nothing to divide by yet. */
export const Performance: FC<{ platform: Platform; s: Summary | null }> = ({ platform, s }) => {
  const w = s?.activity_this_week ?? {};
  const g = (k: string) => w[k] ?? 0;
  const rows: Array<[string, string, string]> = platform.id === 'fiverr'
    ? [['Click rate', pct(g('gig_clicks'), g('gig_impressions')), 'clicks per impression: thumbnail and title'], ['Order rate', pct(g('gig_orders'), g('gig_clicks')), 'orders per click: description, price, packages']]
    : platform.id === 'linkedin'
      ? [['Invite acceptance', pct(g('invite_accepted'), g('invite_sent')), 'accepted per invite sent'], ['Reply rate', pct(g('reply_received'), g('message_sent')), 'replies per message sent']]
      : platform.id === 'clutch'
        ? [['Inquiry reply rate', pct(g('reply_received'), g('message_sent')), 'replies per message sent'], ['Profile views', String(g('profile_view')), 'directory views logged this week']]
        : [['Proposal reply rate', pct(g('reply_received'), g('proposal_sent')), 'replies per proposal sent'], ['Message reply rate', pct(g('reply_received'), g('message_sent')), 'replies per direct message']];
  if (g('connects_spent')) rows.push(['Connects spent', String(g('connects_spent')), 'this week']);
  const total = Object.values(w).reduce((a, b) => a + b, 0);
  return (
    <Section title="Performance this week" hint="Calculated only from the numbers you log under Activity.">
      {total === 0 ? <p className="text-xs text-slate-500">Log some activity to see ratios.</p> : (
        <div className="grid gap-3 sm:grid-cols-3">{rows.map(([label, value, hint]) => (
          <div key={label} className="rounded-lg border border-slate-800 p-3"><div className="text-xs text-slate-400">{label}</div><div className="text-xl font-semibold text-white tabular">{value}</div><div className="text-[11px] text-slate-500">{hint}</div></div>))}</div>)}
    </Section>
  );
};

export const Funnel: FC<{ s: Summary | null }> = ({ s }) => {
  const f = s?.funnel;
  if (!f || f.applications === 0) return null;
  const pct = (v: number | null) => (v === null ? 'n/a' : `${v}%`);
  const usd = (v: number | null) => (v === null ? 'n/a' : `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`);
  const cells: Array<[string, string, string]> = [['Applications', String(f.applications), 'not counting saved'], ['Reply rate', pct(f.reply_rate_percent), 'replied, interview or won'],
    ['Interview rate', pct(f.interview_rate_percent), 'interview or won'], ['Win rate', pct(f.win_rate_of_applied_percent), 'won per application']];
  if (f.cost_total) cells.push(['Cost per reply', usd(f.cost_per_reply), `${usd(f.cost_total)} spent in total`], ['Cost per win', usd(f.cost_per_win), 'needs a win and a cost']);
  return (
    <Section title="Your funnel" hint="Worked out from the applications you logged, by where each one is now. Fewer, better-fitted applications usually beat volume. Compare your own numbers week to week, not against someone else's.">
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-6">{cells.map(([label, value, hint]) => (
        <div key={label} className="rounded-lg border border-slate-800 p-3"><div className="text-xs text-slate-400">{label}</div><div className="text-xl font-semibold text-white tabular">{value}</div><div className="text-[11px] text-slate-500">{hint}</div></div>))}</div>
    </Section>
  );
};

export const Pacing: FC<{ s: Summary | null }> = ({ s }) => {
  const p = s?.pacing;
  if (!p) return null;
  const pct = p.limit ? Math.min(100, Math.round((100 * p.invites_7d) / p.limit)) : 0;
  return (
    <Section title="Invite pacing" hint="Connection requests sent in the last 7 days (a rolling window), against your own weekly limit. Log them under Activity.">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mb-2">
        <span className="text-2xl font-semibold text-white tabular">{p.invites_7d}</span><span className="text-xs text-slate-400">{p.limit ? `of ${p.limit} this week` : 'sent this week (no limit set)'} · {p.today} today{p.remaining !== null ? ` · ${p.remaining} left` : ''}</span>
        {p.over && <Badge tone="bad">Over your limit: pause new invites</Badge>}
      </div>
      {p.limit > 0 && <div className="h-2 rounded bg-slate-800 overflow-hidden" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Invites used"><div className={`h-full ${p.over ? 'bg-rose-500' : pct > 80 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${pct}%` }} /></div>}
      <p className="text-[11px] text-slate-500 mt-2">{p.note}</p>
    </Section>
  );
};

const EXPERIMENT_HINTS: Record<string, string> = {
  linkedin: 'e.g. Updated headline, Featured case study, or 300-char connection note',
  fiverr: 'e.g. New gig thumbnail, 3-tier pricing update, or FAQ rewrite',
  upwork: 'e.g. New 2-line proposal hook, rate change, or portfolio sample',
  freelancer: 'e.g. Milestone breakdown update, badge exam, or bid timing change',
  peopleperhour: 'e.g. Updated Hourlie package, fixed-price offer, or profile video',
  guru: 'e.g. Updated portfolio workroom sample or SafePay milestone terms',
  contra: 'e.g. Added interactive case study or adjusted project minimum',
  toptal: 'e.g. Updated availability status or specialized vertical profile',
  clutch: 'e.g. Added verified case study or updated service focus %',
};

export const Experiments: FC<{ platform?: Platform; items: Rec[]; s: Summary | null; run: Run; post: Post; update: (id: number, d: Record<string, unknown>) => void; remove: (id: number) => void }> = ({ platform, items, s, run, post, update, remove }) => {
  const [what, setWhat] = useState('');
  const [changed, setChanged] = useState(localDay());
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const [reviewResult, setReviewResult] = useState('');
  const due = new Set((s?.experiments_due ?? []).map((e) => e.id));
  const placeholder = EXPERIMENT_HINTS[platform?.id ?? ''] ?? 'What did you change? (new hook, portfolio item, rate…)';
  return (
    <Section title="Change log" hint={`Test one ${platform?.label ?? 'channel'} improvement at a time and review its impact after 30 days.`}>
      <form className="flex flex-wrap gap-2 mb-3" onSubmit={(e) => { e.preventDefault(); run(() => post('experiment', { what, changed_on: changed })).then(() => setWhat('')); }}>
        <input className={`${field} flex-1 min-w-48`} aria-label="What did you change" placeholder={placeholder} value={what} onChange={(e) => setWhat(e.target.value)} required />
        <input className={`${field} !w-auto`} type="date" aria-label="Changed on" value={changed} onChange={(e) => setChanged(e.target.value)} />
        <Button small type="submit"><Plus className="h-3.5 w-3.5" />Log change</Button>
      </form>
      {items.length === 0 ? <p className="text-xs text-slate-500">No changes logged yet.</p> : (
        <ul className="divide-y divide-slate-800">{[...items].reverse().map((x) => (
          <li key={x.id} className="py-2 space-y-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex-1 min-w-48"><div className={x.done ? 'text-slate-500 line-through' : 'text-slate-100'}>{x.what}</div>
                <div className="text-[11px] text-slate-500">changed {x.changed_on} · review {x.review_on}{x.result ? ` · ${x.result}` : ''}</div></div>
              {due.has(x.id) && <Badge tone="warn">Review now</Badge>}
              {!x.done && (
                <Button small onClick={() => { setReviewingId(reviewingId === x.id ? null : x.id); setReviewResult(''); }}>
                  {reviewingId === x.id ? 'Cancel' : 'Mark reviewed'}
                </Button>
              )}
              <button aria-label={`Delete ${x.what}`} onClick={() => remove(x.id)} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
            </div>
            {reviewingId === x.id && (
              <form className="flex flex-wrap gap-2 p-2 rounded-lg bg-slate-900/70 border border-slate-800" onSubmit={(e) => {
                e.preventDefault();
                update(x.id, { done: true, result: reviewResult.trim() || 'Reviewed' });
                setReviewingId(null);
                setReviewResult('');
              }}>
                <input className={`${field} flex-1`} aria-label="Review outcome" placeholder="What happened? (e.g. reply rate rose from 8% to 14%)" value={reviewResult} onChange={(e) => setReviewResult(e.target.value)} autoFocus />
                <Button small type="submit" variant="primary">Save review</Button>
              </form>
            )}
          </li>))}</ul>)}
    </Section>
  );
};
