import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { Bell, PhoneCall, Send, ShieldCheck, Users } from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';

interface ProviderData {
  enabled: boolean;
  config: Record<string, string>;
}

interface ScheduleData {
  mode: 'solo' | 'agency_shifts';
  primary_rep_name: string;
  primary_whatsapp: string;
  primary_phone: string;
  primary_telegram_chat_id: string;
  backup_rep_name: string;
  backup_whatsapp: string;
  backup_phone: string;
  voice_call_delay_sec: number;
  backup_escalate_sec: number;
  quiet_hours_override: boolean;
}

export const WakeUpEnginePanel: FC = () => {
  const [providers, setProviders] = useState<Record<string, ProviderData>>({
    twilio: { enabled: false, config: {} },
    meta_whatsapp: { enabled: false, config: {} },
    telegram: { enabled: false, config: {} },
  });
  const [schedule, setSchedule] = useState<ScheduleData>({
    mode: 'solo',
    primary_rep_name: '',
    primary_whatsapp: '',
    primary_phone: '',
    primary_telegram_chat_id: '',
    backup_rep_name: '',
    backup_whatsapp: '',
    backup_phone: '',
    voice_call_delay_sec: 120,
    backup_escalate_sec: 300,
    quiet_hours_override: true,
  });
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const res = await apiFetch('/api/alerts/providers');
    if (res.ok) {
      const d = await res.json();
      if (d.providers) setProviders(d.providers);
      if (d.schedule) setSchedule(d.schedule);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const saveProvider = async (prov: 'twilio' | 'meta_whatsapp' | 'telegram') => {
    setSaving(true);
    setError('');
    setStatusMsg('');
    try {
      const res = await apiFetch('/api/alerts/providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: prov, enabled: providers[prov]?.enabled ?? false, config: providers[prov]?.config ?? {} }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, d));
      if (d.providers) setProviders(d.providers);
      setStatusMsg(`Saved ${prov.replace('_', ' ')} settings.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const saveSchedule = async () => {
    setSaving(true);
    setError('');
    setStatusMsg('');
    try {
      const res = await apiFetch('/api/alerts/providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schedule }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, d));
      setStatusMsg('Saved Solo / Agency Escalation Schedule.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const runTest = async (target: 'telegram' | 'meta_whatsapp' | 'twilio_whatsapp' | 'twilio_voice') => {
    setError('');
    setStatusMsg('');
    const res = await apiFetch('/api/alerts/wakeup-test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: target }),
    });
    const d = await res.json().catch(() => ({}));
    if (!res.ok || d.ok === false) {
      setError(d.detail || apiErrorMessage(res.status, d));
    } else {
      setStatusMsg(`Test sent via ${target.replace('_', ' ')}.`);
    }
  };

  const simulateEmail = async () => {
    setError('');
    setStatusMsg('');
    const res = await apiFetch('/api/alerts/events/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from_email: 'noreply@e.fiverr.com',
        subject: 'New message from Alex Chen about Next.js SaaS Audit',
        body: 'Hi! Looking to hire an agency this week for our SaaS landing page and speed audit. https://www.fiverr.com/inbox',
      }),
    });
    if (res.ok) setStatusMsg('Simulated Fiverr buyer inquiry ingested into Channels + Escalation Ladder.');
    else setError('Could not simulate inquiry.');
  };

  const updateCfg = (prov: string, key: string, val: string) =>
    setProviders((p) => ({
      ...p,
      [prov]: { ...p[prov], config: { ...(p[prov]?.config ?? {}), [key]: val } },
    }));

  return (
    <div className="space-y-5 mb-6">
      <Card className="!border-emerald-500/30 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <PhoneCall className="h-4 w-4 text-emerald-400" /> Zero-Ban-Risk Wake-Up &amp; Escalation Engine
            </h3>
            <p className="text-xs text-slate-400">
              Second 0: WhatsApp + Telegram · Minute 2: Twilio Voice Wake-Up Call · Minute 5: Agency Backup Rep fallback.
            </p>
          </div>
          <Button small variant="secondary" onClick={simulateEmail}>
            <Bell className="h-3.5 w-3.5" /> Simulate Fiverr Inquiry
          </Button>
        </div>

        {statusMsg && <p className="text-xs text-emerald-400">{statusMsg}</p>}
        {error && <p className="text-xs text-rose-400">{error}</p>}

        {/* Solo vs Multi-Rep Agency Escalation Schedule */}
        <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-semibold text-white flex items-center gap-1.5">
              <Users className="h-3.5 w-3.5 text-indigo-400" /> Escalation Mode
            </span>
            <div className="flex gap-1.5">
              {(['solo', 'agency_shifts'] as const).map((m) => (
                <Button key={m} small variant={schedule.mode === m ? 'primary' : 'secondary'} onClick={() => setSchedule((s) => ({ ...s, mode: m }))}>
                  {m === 'solo' ? 'Solo Freelancer' : 'Multi-Rep Agency Shifts'}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-4">
            <input className={field} placeholder="Primary Rep Name" value={schedule.primary_rep_name} onChange={(e) => setSchedule((s) => ({ ...s, primary_rep_name: e.target.value }))} />
            <input className={field} placeholder="WhatsApp (+1...)" value={schedule.primary_whatsapp} onChange={(e) => setSchedule((s) => ({ ...s, primary_whatsapp: e.target.value }))} />
            <input className={field} placeholder="Wake-Up Voice Phone (+1...)" value={schedule.primary_phone} onChange={(e) => setSchedule((s) => ({ ...s, primary_phone: e.target.value }))} />
            <input className={field} placeholder="Telegram Chat ID" value={schedule.primary_telegram_chat_id} onChange={(e) => setSchedule((s) => ({ ...s, primary_telegram_chat_id: e.target.value }))} />
          </div>

          {schedule.mode === 'agency_shifts' && (
            <div className="grid gap-2 sm:grid-cols-4 pt-2 border-t border-slate-800">
              <input className={field} placeholder="Backup Rep Name" value={schedule.backup_rep_name} onChange={(e) => setSchedule((s) => ({ ...s, backup_rep_name: e.target.value }))} />
              <input className={field} placeholder="Backup WhatsApp (+1...)" value={schedule.backup_whatsapp} onChange={(e) => setSchedule((s) => ({ ...s, backup_whatsapp: e.target.value }))} />
              <input className={field} placeholder="Backup Voice Phone (+1...)" value={schedule.backup_phone} onChange={(e) => setSchedule((s) => ({ ...s, backup_phone: e.target.value }))} />
              <input className={field} type="number" placeholder="Backup Delay (sec)" value={schedule.backup_escalate_sec} onChange={(e) => setSchedule((s) => ({ ...s, backup_escalate_sec: Number(e.target.value) || 300 }))} />
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="flex items-center gap-2 text-xs text-slate-300">
              <span>Voice Call Delay (sec):</span>
              <input type="number" className={`${field} !w-24`} value={schedule.voice_call_delay_sec} onChange={(e) => setSchedule((s) => ({ ...s, voice_call_delay_sec: Number(e.target.value) || 120 }))} />
            </label>
            <Button small variant="primary" onClick={saveSchedule} disabled={saving}>Save Escalation Schedule</Button>
          </div>
        </div>

        {/* 3 Provider Cards */}
        <div className="grid gap-4 lg:grid-cols-3">
          {/* Twilio */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">Twilio (WhatsApp + Voice)</span>
              <label className="flex items-center gap-1.5 text-[11px] text-slate-300 cursor-pointer">
                <input type="checkbox" checked={!!providers.twilio?.enabled} onChange={(e) => setProviders((p) => ({ ...p, twilio: { ...p.twilio, enabled: e.target.checked } }))} />
                Enabled
              </label>
            </div>
            <input className={field} placeholder="Account SID (AC...)" value={providers.twilio?.config?.account_sid ?? ''} onChange={(e) => updateCfg('twilio', 'account_sid', e.target.value)} />
            <input className={field} type="password" placeholder="Auth Token" value={providers.twilio?.config?.auth_token ?? ''} onChange={(e) => updateCfg('twilio', 'auth_token', e.target.value)} />
            <input className={field} placeholder="WhatsApp From (+14155238886)" value={providers.twilio?.config?.whatsapp_from ?? ''} onChange={(e) => updateCfg('twilio', 'whatsapp_from', e.target.value)} />
            <input className={field} placeholder="Voice From (+1...)" value={providers.twilio?.config?.voice_from ?? ''} onChange={(e) => updateCfg('twilio', 'voice_from', e.target.value)} />
            <div className="flex flex-wrap gap-1.5 pt-1">
              <Button small variant="primary" onClick={() => saveProvider('twilio')} disabled={saving}>Save</Button>
              <Button small variant="secondary" onClick={() => runTest('twilio_whatsapp')}><Send className="h-3 w-3" /> Test WA</Button>
              <Button small variant="secondary" onClick={() => runTest('twilio_voice')}><PhoneCall className="h-3 w-3" /> Test Call</Button>
            </div>
          </div>

          {/* Meta WhatsApp Cloud API */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">Meta WhatsApp Cloud API</span>
              <label className="flex items-center gap-1.5 text-[11px] text-slate-300 cursor-pointer">
                <input type="checkbox" checked={!!providers.meta_whatsapp?.enabled} onChange={(e) => setProviders((p) => ({ ...p, meta_whatsapp: { ...p.meta_whatsapp, enabled: e.target.checked } }))} />
                Enabled
              </label>
            </div>
            <input className={field} placeholder="Phone Number ID" value={providers.meta_whatsapp?.config?.phone_number_id ?? ''} onChange={(e) => updateCfg('meta_whatsapp', 'phone_number_id', e.target.value)} />
            <input className={field} type="password" placeholder="Permanent Access Token" value={providers.meta_whatsapp?.config?.access_token ?? ''} onChange={(e) => updateCfg('meta_whatsapp', 'access_token', e.target.value)} />
            <Badge tone="good">Official Direct API · Low Cost</Badge>
            <div className="flex flex-wrap gap-1.5 pt-1">
              <Button small variant="primary" onClick={() => saveProvider('meta_whatsapp')} disabled={saving}>Save</Button>
              <Button small variant="secondary" onClick={() => runTest('meta_whatsapp')}><Send className="h-3 w-3" /> Test Meta WA</Button>
            </div>
          </div>

          {/* Telegram Bot */}
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">Telegram Bot (1-Tap ACK)</span>
              <label className="flex items-center gap-1.5 text-[11px] text-slate-300 cursor-pointer">
                <input type="checkbox" checked={!!providers.telegram?.enabled} onChange={(e) => setProviders((p) => ({ ...p, telegram: { ...p.telegram, enabled: e.target.checked } }))} />
                Enabled
              </label>
            </div>
            <input className={field} type="password" placeholder="Bot Token (12345:ABC...)" value={providers.telegram?.config?.bot_token ?? ''} onChange={(e) => updateCfg('telegram', 'bot_token', e.target.value)} />
            <input className={field} placeholder="Default Chat ID" value={providers.telegram?.config?.chat_id ?? ''} onChange={(e) => updateCfg('telegram', 'chat_id', e.target.value)} />
            <input className={field} type="password" placeholder="Webhook Secret Token" value={providers.telegram?.config?.webhook_secret ?? ''} onChange={(e) => updateCfg('telegram', 'webhook_secret', e.target.value)} />
            <Badge tone="info"><ShieldCheck className="h-3 w-3 mr-1 inline" /> Inline I&apos;m On It Button</Badge>
            <div className="flex flex-wrap gap-1.5 pt-1">
              <Button small variant="primary" onClick={() => saveProvider('telegram')} disabled={saving}>Save</Button>
              <Button small variant="secondary" onClick={() => runTest('telegram')}><Send className="h-3 w-3" /> Test Telegram</Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};
