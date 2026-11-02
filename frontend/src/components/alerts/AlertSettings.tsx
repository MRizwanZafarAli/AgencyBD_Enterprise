import { useState } from 'react';
import type { FC } from 'react';
import { Bell, CheckCircle2, Mail, Phone, Plus, Send, Trash2 } from 'lucide-react';
import { Badge, Button, Card, Skeletons, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { send, useApi } from '../../lib/hooks';
import { CHANNEL_LABEL, DAY_LABEL, PRESETS, describeSteps } from './types';
import type { AlertSettings as Settings, ChannelId, SettingsResponse } from './types';

const ZONES = ['Asia/Karachi', 'Asia/Dubai', 'Asia/Riyadh', 'Asia/Kolkata', 'Asia/Singapore', 'Europe/London', 'Europe/Dublin', 'Europe/Berlin', 'America/New_York', 'America/Chicago', 'America/Los_Angeles', 'Australia/Sydney', 'UTC'];
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
interface MailRow { from: string; subject: string; platform: string; kind: string; would_alert: boolean; sender: string; preview: string }

const Test: FC<{ channel: ChannelId; ready: boolean; confirm?: string }> = ({ channel, ready, confirm }) => {
  const [res, setRes] = useState<{ ok: boolean; detail: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (confirm && !window.confirm(confirm)) return;
    setBusy(true); setRes(null);
    try { setRes(await send(`/api/alerts/test/${channel}`)); } catch (e) { setRes({ ok: false, detail: (e as Error).message }); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button small type="button" onClick={run} disabled={busy || !ready}><Send className="h-3.5 w-3.5" />{busy ? 'Sending…' : `Test ${CHANNEL_LABEL[channel]}`}</Button>
      {!ready && <span className="text-xs text-slate-500">Finish the details first, then save.</span>}
      {res && <span role="status" className={`text-xs ${res.ok ? 'text-emerald-300' : 'text-amber-300'}`}>{res.detail}</span>}
    </div>
  );
};

const Channel: FC<{ title: string; ready: boolean; children: React.ReactNode; note: string }> = ({ title, ready, children, note }) => (
  <div className="rounded-xl border border-slate-800 p-3.5 space-y-2.5">
    <div className="flex items-center gap-2"><h3 className="text-sm font-medium text-white mr-auto">{title}</h3><Badge tone={ready ? 'good' : 'neutral'}>{ready ? 'Ready' : 'Not set up'}</Badge></div>
    {children}
    <p className="text-[11px] text-slate-500">{note}</p>
  </div>
);

/** The whole Alert Desk in one place: where messages come from, where you are alerted, when, and how hard it nudges. */
export const AlertSettings: FC<{ onGo: (section: string) => void }> = ({ onGo }) => {
  const data = useApi<SettingsResponse>('/api/alerts/settings');
  const [draft, setDraft] = useState<Settings | null>(null);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [mailRows, setMailRows] = useState<{ ok: boolean; error: string | null; emails: MailRow[] } | null>(null);
  const [busy, setBusy] = useState('');
  const d = data.data;
  if (d && !draft) setDraft(clone(d.settings));
  const dirty = !!d && !!draft && JSON.stringify(d.settings) !== JSON.stringify(draft);
  const can = !!d?.can_edit;
  const ready = d?.status.channels_ready;

  const set = (fn: (s: Settings) => void) => setDraft((cur) => { if (!cur) return cur; const n = clone(cur); fn(n); return n; });
  const save = async () => {
    setError(''); setSaved(''); setBusy('save');
    try { await send('/api/alerts/settings', 'PUT', draft); setSaved('Saved. The desk uses these settings from now on.'); setDraft(null); data.reload(); } catch (e) { setError((e as Error).message); } finally { setBusy(''); }
  };
  const pause = async (minutes: number | null) => { setError(''); try { await send('/api/alerts/pause', 'POST', { minutes }); setDraft(null); data.reload(); } catch (e) { setError((e as Error).message); } };
  const checkMail = async () => { setBusy('mail'); setMailRows(null); try { setMailRows(await send('/api/alerts/mail/test')); } catch (e) { setError((e as Error).message); } finally { setBusy(''); } };
  const tryLadder = async () => {
    setError(''); setBusy('try');
    try { await send('/api/alerts/messages', 'POST', { platform: 'other', sender: 'Test client', text: 'This is a test message. It is escalated exactly like a real one, so acknowledge it in Channels to stop the reminders.' }); setSaved('A test message was added. Open Channels to see it and acknowledge it.'); } catch (e) { setError((e as Error).message); } finally { setBusy(''); }
  };
  const randomTopic = () => { const a = new Uint8Array(10); crypto.getRandomValues(a); set((s) => { s.channels.ntfy.topic = `agencybd-${Array.from(a, (b) => b.toString(36).padStart(2, '0')).join('').slice(0, 14)}`; }); };

  if (data.loading && !d) return <Skeletons rows={4} />;
  if (!d || !draft) return <ErrorBanner message={data.error} />;
  const st = d.status;
  const dis = !can;

  return (
    <div className="space-y-5">
      <ErrorBanner message={error || data.error} />
      {!can && <Card><p className="text-sm text-slate-300">Where alerts go is shared by this whole installation, so only an administrator can change it. You can see how it is set.</p></Card>}

      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <button role="switch" aria-checked={draft.enabled} aria-label="Alert Desk on or off" disabled={dis} onClick={() => set((s) => { s.enabled = !s.enabled; })}
            className={`relative h-7 w-12 rounded-full transition-colors disabled:opacity-50 ${draft.enabled ? 'bg-indigo-500' : 'bg-slate-700'}`}><span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-all ${draft.enabled ? 'left-6' : 'left-1'}`} /></button>
          <div className="mr-auto min-w-0"><div className="text-sm font-semibold text-white">{draft.enabled ? 'The Alert Desk is on' : 'The Alert Desk is off'}</div>
            <div className="text-xs text-slate-400">When a client writes on Fiverr, Upwork, LinkedIn and others, it reaches you here, and keeps nudging until you answer.</div></div>
          <Badge tone={st.working_now ? 'good' : 'neutral'}>{st.working_now ? 'Working hours now' : 'Outside working hours'}</Badge>
          <Badge tone={st.waiting ? 'warn' : 'neutral'}>{st.waiting} waiting</Badge>
          {st.paused && <Badge tone="warn">Paused</Badge>}
        </div>
        {can && <div className="flex flex-wrap items-center gap-2 mt-3"><span className="text-xs text-slate-400">Pause alerts:</span>
          <Button small type="button" onClick={() => pause(60)}>1 hour</Button><Button small type="button" onClick={() => pause(240)}>4 hours</Button><Button small type="button" onClick={() => pause(720)}>12 hours</Button>
          {st.paused && <Button small variant="primary" type="button" onClick={() => pause(null)}>Resume now</Button>}</div>}
      </Card>

      <Card>
        <div className="flex items-center gap-2 mb-1"><Mail className="h-4 w-4 text-indigo-400" aria-hidden="true" /><h2 className="text-sm font-semibold text-white">Where the messages come from</h2><Badge tone={st.mailbox_ready ? 'good' : 'warn'}>{st.mailbox_ready ? 'Mailbox connected' : 'Mailbox not set up'}</Badge></div>
        <p className="text-xs text-slate-400 max-w-3xl">The desk never logs in to Fiverr, Upwork or LinkedIn. Those sites already email you when a client writes. The desk reads those emails from your own mailbox (read-only, nothing is changed or deleted) and forwards them. Turn email notifications on in each platform, and on Upwork choose &quot;immediately&quot; instead of every 15 minutes.</p>
        {!st.mailbox_ready && <p className="text-xs text-amber-300 mt-2">Add the mailbox server, address and an app password under <button type="button" onClick={() => onGo('keys')} className="underline">Integrations and keys</button> (group &quot;Message alerts&quot;).</p>}
        {st.last_mail_error && <p role="alert" className="text-xs text-amber-300 mt-2">{st.last_mail_error}</p>}
        <div className="flex flex-wrap gap-2 mt-3" role="group" aria-label="Platforms to watch">{Object.entries(d.platforms).map(([id, label]) => { const on = draft.watch.platforms.includes(id); return (
          <button key={id} type="button" aria-pressed={on} disabled={dis} onClick={() => set((s) => { s.watch.platforms = on ? s.watch.platforms.filter((p) => p !== id) : [...s.watch.platforms, id]; })}
            className={`px-2.5 py-1 rounded-md text-xs border ${on ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-300' : 'border-slate-700 text-slate-400'}`}>{label}</button>); })}</div>
        <label className="block text-xs text-slate-400 mt-3">Also watch these senders (emails or domains, comma separated)
          <input className={`${field} mt-1`} disabled={dis} value={draft.watch.extra_senders.join(', ')} placeholder="client@company.com, company.com"
            onChange={(e) => set((s) => { s.watch.extra_senders = e.target.value.split(',').map((x) => x.trim()).filter(Boolean); })} /></label>
        {can && <div className="mt-3"><Button small type="button" onClick={checkMail} disabled={busy === 'mail' || !st.mailbox_ready}>{busy === 'mail' ? 'Reading…' : 'Show how my recent emails are read'}</Button></div>}
        {mailRows && (
          <div className="mt-3 rounded-xl border border-slate-800 p-3">
            {mailRows.error && <p role="alert" className="text-xs text-amber-300">{mailRows.error}</p>}
            {mailRows.ok && mailRows.emails.length === 0 && <p className="text-xs text-slate-400">No emails from the watched platforms were found in your latest mail.</p>}
            <ul className="divide-y divide-slate-800">{mailRows.emails.map((m, i) => (
              <li key={i} className="py-2 flex items-start gap-2 text-xs"><Badge tone={m.would_alert ? 'good' : 'neutral'}>{m.would_alert ? 'Would alert' : 'Ignored'}</Badge>
                <span className="min-w-0"><span className="text-slate-100">{m.subject}</span><span className="text-slate-500"> · {m.platform}, {m.kind}</span>{m.would_alert && <span className="block text-slate-400 truncate">{m.sender}: {m.preview}</span>}</span></li>))}</ul>
            <p className="text-[11px] text-slate-500 mt-2">If a real client message shows as Ignored, add its sender above or tell me the subject line and I will teach the desk.</p>
          </div>)}
      </Card>

      <Card>
        <div className="flex items-center gap-2 mb-1"><Bell className="h-4 w-4 text-indigo-400" aria-hidden="true" /><h2 className="text-sm font-semibold text-white">Where to alert you</h2></div>
        <p className="text-xs text-slate-400 mb-3">Each alert contains what the client wrote, so it passes through the service you pick. Secrets (bot tokens, call account) are stored encrypted under <button type="button" onClick={() => onGo('keys')} className="underline">Integrations and keys</button>.</p>
        <div className="grid gap-3 lg:grid-cols-2">
          <Channel title="Telegram" ready={!!ready?.telegram} note="Free and official. Create a bot with @BotFather, send it any message, then find your chat ID with @userinfobot. A tap on I'm on it, or any reply, stops reminders.">
            <label className="block text-xs text-slate-400">Your Telegram chat ID<input className={`${field} mt-1`} inputMode="numeric" disabled={dis} value={draft.channels.telegram.chat_id} placeholder="123456789" onChange={(e) => set((s) => { s.channels.telegram.chat_id = e.target.value.trim(); })} /></label>
            {can && <Test channel="telegram" ready={!!ready?.telegram} />}
          </Channel>
          <Channel title="ntfy push" ready={!!ready?.ntfy} note="Free, no account. Install the ntfy app and subscribe to your topic. The topic is the only password, so keep it secret.">
            <label className="block text-xs text-slate-400">Your private topic<span className="flex gap-2 mt-1"><input className={field} disabled={dis} value={draft.channels.ntfy.topic} placeholder="agencybd-x7k2m9q4" onChange={(e) => set((s) => { s.channels.ntfy.topic = e.target.value.trim(); })} />
              {can && <Button small type="button" onClick={randomTopic}>Make one</Button>}</span></label>
            {can && <Test channel="ntfy" ready={!!ready?.ntfy} />}
          </Channel>
          <Channel title="WhatsApp" ready={!!ready?.whatsapp} note="Uses Meta's official WhatsApp Cloud API. Meta changed its pricing in October 2026, so check the current free allowance. Free-form messages only work within 24 hours of you writing to the business number.">
            <label className="block text-xs text-slate-400">Your WhatsApp number<input className={`${field} mt-1`} inputMode="tel" disabled={dis} value={draft.channels.whatsapp.to} placeholder="+923001234567" onChange={(e) => set((s) => { s.channels.whatsapp.to = e.target.value; })} /></label>
            {can && <Test channel="whatsapp" ready={!!ready?.whatsapp} />}
          </Channel>
          <Channel title="Phone call" ready={!!ready?.call} note="A real call that reads the message aloud. Needs a Twilio account. A trial can only call a number you verified there, with a small total allowance, and a trial call opens with Twilio's own notice.">
            <label className="block text-xs text-slate-400">Your phone number<input className={`${field} mt-1`} inputMode="tel" disabled={dis} value={draft.channels.call.to} placeholder="+923001234567" onChange={(e) => set((s) => { s.channels.call.to = e.target.value; })} /></label>
            <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" disabled={dis} checked={draft.ai_summary} onChange={(e) => set((s) => { s.ai_summary = e.target.checked; })} />Have the AI shorten the message for the call (uses your AI key; the text goes to that provider)</label>
            {can && <Test channel="call" ready={!!ready?.call} confirm="This places a real phone call to your number and can use trial minutes or cost money. Continue?" />}
          </Channel>
        </div>
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-1">When the desk works</h2>
        <div className="flex flex-wrap gap-1.5 mb-3" role="group" aria-label="Working days">{DAY_LABEL.map((l, i) => { const on = draft.schedule.days.includes(i); return (
          <button key={l} type="button" aria-pressed={on} disabled={dis} onClick={() => set((s) => { s.schedule.days = on ? s.schedule.days.filter((x) => x !== i) : [...s.schedule.days, i]; })}
            className={`px-2.5 py-1 rounded-md text-xs border ${on ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-300' : 'border-slate-700 text-slate-400'}`}>{l}</button>); })}</div>
        <div className="flex flex-wrap items-end gap-3 text-xs text-slate-400">
          <label>From<input className={`${field} !w-auto mt-1 block`} type="time" disabled={dis} value={draft.schedule.start} onChange={(e) => e.target.value && set((s) => { s.schedule.start = e.target.value; })} /></label>
          <label>To<input className={`${field} !w-auto mt-1 block`} type="time" disabled={dis} value={draft.schedule.end} onChange={(e) => e.target.value && set((s) => { s.schedule.end = e.target.value; })} /></label>
          <label>Time zone<input className={`${field} !w-48 mt-1 block`} list="alert-zones" disabled={dis} value={draft.timezone} onChange={(e) => set((s) => { s.timezone = e.target.value; })} /></label>
          <datalist id="alert-zones">{ZONES.map((z) => <option key={z} value={z} />)}</datalist>
        </div>
        <fieldset className="mt-3 text-xs text-slate-300 space-y-1"><legend className="text-xs text-slate-400 mb-1">A client writes outside those hours</legend>
          <label className="flex items-center gap-2"><input type="radio" name="off" disabled={dis} checked={draft.schedule.off_hours === 'hold'} onChange={() => set((s) => { s.schedule.off_hours = 'hold'; })} />Wait. Alert me when my day starts.</label>
          <label className="flex items-center gap-2"><input type="radio" name="off" disabled={dis} checked={draft.schedule.off_hours === 'first_only'} onChange={() => set((s) => { s.schedule.off_hours = 'first_only'; })} />Send the first alert now, and the reminders when my day starts.</label></fieldset>
        <label className="flex items-center gap-2 mt-3 text-xs text-slate-300"><input type="checkbox" disabled={dis} checked={draft.quiet_hours.enabled} onChange={(e) => set((s) => { s.quiet_hours.enabled = e.target.checked; })} />No phone calls between
          <input className={`${field} !w-auto`} type="time" aria-label="Quiet hours start" disabled={dis} value={draft.quiet_hours.start} onChange={(e) => e.target.value && set((s) => { s.quiet_hours.start = e.target.value; })} />and
          <input className={`${field} !w-auto`} type="time" aria-label="Quiet hours end" disabled={dis} value={draft.quiet_hours.end} onChange={(e) => e.target.value && set((s) => { s.quiet_hours.end = e.target.value; })} /> (a call waits until they end)</label>
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-white mb-1">If you do not answer</h2>
        <p className="text-xs text-slate-400 mb-3">Each step fires once, in order, until you acknowledge the message. Use as many calls as you like, at any times.</p>
        <div className="flex flex-wrap gap-2 mb-3" role="group" aria-label="Presets">{PRESETS.map((p) => <Button key={p.id} small type="button" disabled={dis} title={p.hint} onClick={() => set((s) => { s.steps = clone(p.steps); })}>{p.label}</Button>)}</div>
        <ul className="space-y-2">{draft.steps.map((s, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2 text-sm text-slate-300">
            <span className="text-xs text-slate-500 w-12">Step {i + 1}</span>After
            <input className={`${field} !w-20`} type="number" min={0} max={1440} aria-label={`Minutes for step ${i + 1}`} disabled={dis} value={s.after_minutes} onChange={(e) => set((x) => { x.steps[i].after_minutes = Number(e.target.value); })} />min →
            <select className={`${field} !w-auto`} aria-label={`Channel for step ${i + 1}`} disabled={dis} value={s.channel} onChange={(e) => set((x) => { x.steps[i].channel = e.target.value as ChannelId; })}>
              {d.channels.map((c) => <option key={c} value={c}>{CHANNEL_LABEL[c]}</option>)}</select>
            {!ready?.[s.channel] && <Badge tone="warn" title="This channel is not set up yet, so this step will be skipped">not set up</Badge>}
            {can && draft.steps.length > 1 && <button type="button" aria-label={`Remove step ${i + 1}`} onClick={() => set((x) => { x.steps.splice(i, 1); })} className="text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>}
          </li>))}</ul>
        {can && draft.steps.length < 10 && <Button small type="button" className="mt-3" onClick={() => set((s) => { s.steps.push({ after_minutes: (s.steps[s.steps.length - 1]?.after_minutes ?? 0) + 15, channel: 'call' }); })}><Plus className="h-3.5 w-3.5" />Add a step</Button>}
        <p className="text-xs text-slate-300 mt-3" aria-label="Plan summary"><Phone className="inline h-3.5 w-3.5 mr-1 text-indigo-400" aria-hidden="true" />{describeSteps(draft.steps)}</p>
      </Card>

      {can && (
        <div className="sticky bottom-20 lg:bottom-4 z-20 flex flex-wrap items-center gap-3 rounded-2xl bento-tile px-4 py-3">
          <Button variant="primary" onClick={save} disabled={!dirty || busy === 'save'}>{busy === 'save' ? 'Saving…' : 'Save alert settings'}</Button>
          <Button type="button" onClick={tryLadder} disabled={busy === 'try' || dirty} title={dirty ? 'Save first' : 'Adds a test client message and runs the real plan on it'}>Try it with a test message</Button>
          {dirty && <span className="text-xs text-amber-300">Unsaved changes</span>}
          {saved && <span role="status" className="text-xs text-emerald-300 inline-flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" />{saved}</span>}
        </div>)}
    </div>
  );
};
