import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { Bell, Check, Copy, Download, ExternalLink, PanelRight, Plus, Search, Trash2 } from 'lucide-react';
import { Badge, Button, EmptyState, SearchInput, SuggestInput, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { send } from '../../lib/hooks';
import { openSide } from './browser';
import { Section } from './shared';
import type { Post, Run } from './shared';
import { KIND_LABEL, STATUS_LABEL, localDay } from './types';
import type { Platform, Rec, Summary } from './types';

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

export const OpenInBrowser: FC<{ platform: Platform; links: Rec[]; run: Run; post: Post; remove: (id: number) => void }> = ({ platform, links, run, post, remove }) => {
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState('');
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [company, setCompany] = useState('');
  const [people, setPeople] = useState<Array<{ label: string; url: string }>>([]);

  const search = async () => {
    setMsg('');
    const res = await apiFetch(`/api/channels/${platform.id}/search_url?q=${encodeURIComponent(q)}`);
    const body = await res.json().catch(() => ({}));
    if (res.ok) openTab(body.url); else setMsg(apiErrorMessage(res.status, body));
  };
  const findPeople = async () => {
    setMsg('');
    try { setPeople((await send<{ links: Array<{ label: string; url: string }> }>('/api/channels/linkedin/search_links', 'POST', { company })).links); } catch (e) { setMsg((e as Error).message); }
  };

  return (
    <Section title="Open in my browser" hint="These links open in your normal browser tab, where you are already signed in. This app never sees your login.">
      <div className="flex flex-wrap gap-2 mb-3">
        {platform.home && <Button small onClick={() => openTab(platform.home!)}><ExternalLink className="h-3.5 w-3.5" />Open {platform.label}</Button>}
        {platform.home && <Button small onClick={() => openSide(platform.home!)}><PanelRight className="h-3.5 w-3.5" />Open beside this app</Button>}
      </div>
      {platform.has_search && (
        <form className="flex gap-2 mb-3" onSubmit={(e) => { e.preventDefault(); if (q.trim()) search(); }}>
          <SuggestInput className="flex-1" kinds={['skill', 'business']} label={`Search ${platform.label}`} placeholder={`Search ${platform.label} (opens in a new tab)`} value={q} onChange={setQ} />
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
            <li key={l.url}><a href={l.url} target="_blank" rel="noopener noreferrer" className="text-xs text-indigo-400 hover:underline inline-flex items-center gap-1">{l.label}<ExternalLink className="h-3 w-3" /></a></li>))}</ul>}
          <p className="text-[11px] text-slate-500 mt-2">Plain search links only. Nothing is fetched from LinkedIn.</p>
        </div>)}
      {msg && <p role="alert" className="text-xs text-rose-300 mb-2">{msg}</p>}
      <div className="text-xs font-medium text-slate-300 mb-1.5">Saved links</div>
      {links.length === 0 ? <p className="text-xs text-slate-500">Save the searches, saved filters and pages you use every day.</p> : (
        <ul className="space-y-1">{links.map((l) => (
          <li key={l.id} className="flex items-center gap-2 group">
            <a href={l.url} target="_blank" rel="noopener noreferrer" className="flex-1 min-w-0 truncate text-sm text-indigo-400 hover:underline">{l.title || l.url}</a>
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

export const Pipeline: FC<{ statuses: string[]; items: Rec[]; run: Run; post: Post; update: (id: number, d: Record<string, unknown>) => void; remove: (id: number) => void }> = ({ statuses, items, run, post, update, remove }) => {
  const blank = { title: '', counterparty: '', url: '', value: '', cost: '', next_followup: '', status: 'applied' };
  const [f, setF] = useState(blank);
  const [filter, setFilter] = useState('all');
  const [find, setFind] = useState('');
  const today = localDay();
  const shown = items.filter((r) => (filter === 'all' || r.status === filter) && (!find.trim() || `${r.title} ${r.counterparty ?? ''} ${r.notes ?? ''}`.toLowerCase().includes(find.trim().toLowerCase())));
  const exportCsv = () => {
    const q = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const rows = [['title', 'client', 'status', 'value', 'follow_up', 'link'], ...items.map((r) => [r.title, r.counterparty, r.status, r.value, r.next_followup, r.url])];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([rows.map((r) => r.map(q).join(',')).join('\n')], { type: 'text/csv' }));
    a.download = 'applications.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const set = (k: keyof typeof blank) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Section title="Applications and outreach" hint="Log every proposal, bid or message you send, with a follow-up date. Overdue follow-ups are surfaced on Today.">
      <form className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6 mb-4" onSubmit={(e) => { e.preventDefault(); run(() => post('pipeline', { ...f, value: f.value === '' ? null : Number(f.value), cost: f.cost === '' ? null : Number(f.cost) })).then(() => setF(blank)); }}>
        <input className={`${field} lg:col-span-2`} aria-label="Title" placeholder="Project or person" value={f.title} onChange={set('title')} required />
        <input className={field} aria-label="Client" placeholder="Client or company" value={f.counterparty} onChange={set('counterparty')} />
        <input className={field} aria-label="Value in dollars" placeholder="Value $" inputMode="decimal" value={f.value} onChange={set('value')} />
        <select className={field} aria-label="Status" value={f.status} onChange={set('status')}>{statuses.map((s) => <option key={s} value={s}>{STATUS_LABEL[s] ?? s}</option>)}</select>
        <input className={field} type="date" aria-label="Follow up on" value={f.next_followup} onChange={set('next_followup')} />
        <input className={`${field} sm:col-span-2 lg:col-span-3`} aria-label="Link" placeholder="Link to the post or thread (optional)" value={f.url} onChange={set('url')} />
        <input className={`${field} lg:col-span-2`} aria-label="Cost to apply in dollars" inputMode="decimal" placeholder="Cost to apply $ (Connects, fees)" value={f.cost} onChange={set('cost')} />
        <Button type="submit" variant="primary"><Plus className="h-3.5 w-3.5" />Log it</Button>
      </form>
      {items.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 mb-2" role="group" aria-label="Filter by status">
          {['all', ...statuses].map((st) => { const n = st === 'all' ? items.length : items.filter((r) => r.status === st).length; return (
            <button key={st} aria-pressed={filter === st} onClick={() => setFilter(st)}
              className={`px-2.5 py-1 rounded-md text-xs border ${filter === st ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-300' : 'border-slate-700 text-slate-400'}`}>{st === 'all' ? 'All' : STATUS_LABEL[st] ?? st} <span className="tabular opacity-70">{n}</span></button>); })}
          <SearchInput className="w-48 ml-auto" label="Search applications" value={find} onChange={setFind} />
          <Button small onClick={exportCsv}><Download className="h-3.5 w-3.5" />CSV</Button>
        </div>)}
      {items.length === 0 ? <EmptyState title="Nothing logged yet" hint="Add each application after you send it in your own browser." /> : shown.length === 0 ? <p className="text-xs text-slate-500 py-3">Nothing matches.</p> : (
        <ul className="divide-y divide-slate-800">
          {[...shown].reverse().map((r) => {
            const open = r.status !== 'won' && r.status !== 'lost';
            const overdue = open && r.next_followup && r.next_followup <= today;
            return (
              <li key={r.id} className="py-2.5 flex flex-wrap items-center gap-2">
                <div className="flex-1 min-w-[12rem]">
                  <div className="text-sm text-slate-100">{r.url ? <a href={r.url} target="_blank" rel="noopener noreferrer" className="hover:underline text-indigo-400">{r.title}</a> : r.title}</div>
                  <div className="text-[11px] text-slate-500">{[r.counterparty, r.value ? `$${Number(r.value).toLocaleString()}` : null].filter(Boolean).join(' · ') || 'no client or value'}</div>
                </div>
                {overdue && <Badge tone="warn">Follow up</Badge>}
                <select className={`${field} !w-auto`} aria-label={`Status of ${r.title}`} value={r.status} onChange={(e) => update(r.id, { status: e.target.value })}>{statuses.map((s) => <option key={s} value={s}>{STATUS_LABEL[s] ?? s}</option>)}</select>
                <input className={`${field} !w-auto`} type="date" aria-label={`Follow up date for ${r.title}`} value={r.next_followup ?? ''} onChange={(e) => update(r.id, { next_followup: e.target.value || null })} />
                <button aria-label={`Delete ${r.title}`} onClick={() => remove(r.id)} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
              </li>);
          })}
        </ul>)}
    </Section>
  );
};

export const Templates: FC<{ platform: Platform; items: Rec[]; run: Run; post: Post; remove: (id: number) => void }> = ({ platform, items, run, post, remove }) => {
  const [name, setName] = useState('');
  const [body, setBody] = useState('');
  const [copied, setCopied] = useState<string | null>(null);
  const limit = platform.limits.note_chars;
  const saved = new Set(items.map((i) => i.name));
  const starters = platform.templates.filter((t) => !saved.has(t.name));
  const copy = async (key: string, text: string) => { try { await navigator.clipboard.writeText(text); setCopied(key); window.setTimeout(() => setCopied(null), 1500); } catch { setCopied(null); } };
  const count = (text: string) => limit ? <span className={`text-[11px] tabular ${text.length > limit ? 'text-rose-400' : 'text-slate-500'}`}>{text.length}/{limit}</span> : null;
  return (
    <Section title="Message templates" hint="Fill the {placeholders} yourself before you send. Copy, then paste into the site.">
      <ul className="space-y-2">
        {[...items.map((t): Tpl => ({ id: t.id, name: String(t.name), body: String(t.body), saved: true })), ...starters.map((t, i): Tpl => ({ id: -1 - i, name: t.name, body: t.body, saved: false }))].map((t) => (
          <li key={`${t.saved}-${t.id}`} className="rounded-lg border border-slate-800 p-2.5">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-medium text-slate-100 flex-1">{t.name}</span>{!t.saved && <Badge tone="info">Starter</Badge>}{count(t.body)}
              <button aria-label={`Copy ${t.name}`} onClick={() => copy(`${t.id}`, t.body)} className="text-slate-400 hover:text-white">{copied === `${t.id}` ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}</button>
              {t.saved ? <button aria-label={`Delete ${t.name}`} onClick={() => remove(t.id)} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
                : <button aria-label={`Save ${t.name} to my templates`} onClick={() => run(() => post('template', { name: t.name, body: t.body }))} className="text-slate-400 hover:text-white"><Plus className="h-4 w-4" /></button>}
            </div>
            <p className="text-xs text-slate-400 whitespace-pre-wrap">{t.body}</p>
          </li>))}
      </ul>
      <form className="space-y-2 mt-3" onSubmit={(e) => { e.preventDefault(); run(() => post('template', { name, body })).then(() => { setName(''); setBody(''); }); }}>
        <input className={field} aria-label="Template name" placeholder="Template name" value={name} onChange={(e) => setName(e.target.value)} required />
        <textarea className={field} rows={3} aria-label="Template text" placeholder="Template text" value={body} onChange={(e) => setBody(e.target.value)} required />
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

export const Activity: FC<{ kinds: string[]; s: Summary | null; today: string; run: Run; post: Post }> = ({ kinds, s, today, run, post }) => {
  const [kind, setKind] = useState(kinds[0] ?? 'message_sent');
  const [qty, setQty] = useState('1');
  const week = s?.activity_this_week ?? {};
  return (
    <Section title="Activity this week" hint="Count what you did (and the numbers your dashboard shows you), so you can see what is working.">
      {Object.keys(week).length === 0 ? <p className="text-xs text-slate-500 mb-3">Nothing logged since Monday.</p> : (
        <div className="flex flex-wrap gap-2 mb-3">{Object.entries(week).map(([k, v]) => <Badge key={k} tone="accent">{KIND_LABEL[k] ?? k}: {v}</Badge>)}</div>)}
      <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); run(() => post('activity', { kind, qty: Number(qty), day: today })); }}>
        <select className={`${field} !w-auto flex-1`} aria-label="Activity" value={kind} onChange={(e) => setKind(e.target.value)}>{kinds.map((k) => <option key={k} value={k}>{KIND_LABEL[k] ?? k}</option>)}</select>
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
        <label>Remind <select className={`${field} !w-auto`} value={cfg.remind_minutes} onChange={(e) => save({ remind_minutes: Number(e.target.value) })}>
          <option value={0}>at start only</option><option value={30}>every 30 min</option><option value={60}>every hour</option><option value={120}>every 2 hours</option></select></label>
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

export const QuickPages: FC<{ platform: Platform }> = ({ platform }) => {
  if (platform.pages.length === 0) return null;
  return (
    <Section title={`${platform.label} pages`} hint="Jump straight to the page you need. Each opens beside this app, in your own signed-in browser.">
      <div className="flex flex-wrap gap-2">{platform.pages.map((p) => <Button key={p.url} small onClick={() => openSide(p.url)}><PanelRight className="h-3.5 w-3.5" />{p.label}</Button>)}</div>
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
      : [['Proposal reply rate', pct(g('reply_received'), g('proposal_sent')), 'replies per proposal sent']];
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

export const Experiments: FC<{ items: Rec[]; s: Summary | null; run: Run; post: Post; update: (id: number, d: Record<string, unknown>) => void; remove: (id: number) => void }> = ({ items, s, run, post, update, remove }) => {
  const [what, setWhat] = useState('');
  const [changed, setChanged] = useState(localDay());
  const due = new Set((s?.experiments_due ?? []).map((e) => e.id));
  return (
    <Section title="Change log" hint="Change one thing at a time and judge it after about 30 days, as Fiverr's own help advises. Log what you changed; it comes due for review automatically.">
      <form className="flex flex-wrap gap-2 mb-3" onSubmit={(e) => { e.preventDefault(); run(() => post('experiment', { what, changed_on: changed })).then(() => setWhat('')); }}>
        <input className={`${field} flex-1 min-w-48`} aria-label="What did you change" placeholder="What did you change? (new gig thumbnail, new headline…)" value={what} onChange={(e) => setWhat(e.target.value)} required />
        <input className={`${field} !w-auto`} type="date" aria-label="Changed on" value={changed} onChange={(e) => setChanged(e.target.value)} />
        <Button small type="submit"><Plus className="h-3.5 w-3.5" />Log change</Button>
      </form>
      {items.length === 0 ? <p className="text-xs text-slate-500">No changes logged yet.</p> : (
        <ul className="divide-y divide-slate-800">{[...items].reverse().map((x) => (
          <li key={x.id} className="py-2 flex flex-wrap items-center gap-2 text-sm">
            <div className="flex-1 min-w-48"><div className={x.done ? 'text-slate-500 line-through' : 'text-slate-100'}>{x.what}</div>
              <div className="text-[11px] text-slate-500">changed {x.changed_on} · review {x.review_on}{x.result ? ` · ${x.result}` : ''}</div></div>
            {due.has(x.id) && <Badge tone="warn">Review now</Badge>}
            {!x.done && <Button small onClick={() => { const result = window.prompt('What happened? (for example: click rate went from 3% to 4%)') ; if (result !== null) update(x.id, { done: true, result }); }}>Mark reviewed</Button>}
            <button aria-label={`Delete ${x.what}`} onClick={() => remove(x.id)} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
          </li>))}</ul>)}
    </Section>
  );
};
