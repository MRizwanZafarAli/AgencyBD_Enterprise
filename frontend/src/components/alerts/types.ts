export type ChannelId = 'telegram' | 'ntfy' | 'whatsapp' | 'call';
export interface Step { after_minutes: number; channel: ChannelId }
export interface AlertSettings {
  enabled: boolean; timezone: string; ai_summary: boolean; paused_until: string | null;
  schedule: { days: number[]; start: string; end: string; off_hours: 'hold' | 'first_only' };
  quiet_hours: { enabled: boolean; start: string; end: string };
  steps: Step[];
  channels: { telegram: { chat_id: string }; ntfy: { topic: string; server: string }; whatsapp: { to: string }; call: { to: string } };
  watch: { platforms: string[]; extra_senders: string[]; poll_seconds: number };
}
export interface DeskStatus {
  enabled: boolean; paused: boolean; paused_until: string | null; working_now: boolean; waiting: number; last_cycle_at: string | null; last_mail_poll: string | null;
  last_mail_error: string | null; channels_ready: Record<ChannelId, boolean>; mailbox_ready: boolean;
}
export interface SettingsResponse { settings: AlertSettings; status: DeskStatus; can_edit: boolean; platforms: Record<string, string>; channels: ChannelId[] }
export interface Attempt { step_index: number; channel: ChannelId; status: 'sent' | 'failed' | 'skipped'; detail: string; at: string }
export interface ClientMessage {
  id: number; platform: string; kind: string; sender: string; subject: string; preview: string; url: string | null; origin: string; received_at: string;
  status: 'new' | 'acknowledged' | 'dismissed'; acknowledged_via: string | null; attempts: Attempt[];
}
export const CHANNEL_LABEL: Record<ChannelId, string> = { telegram: 'Telegram', ntfy: 'ntfy push', whatsapp: 'WhatsApp', call: 'Phone call' };
export const DAY_LABEL = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export const PRESETS: Array<{ id: string; label: string; hint: string; steps: Step[] }> = [
  { id: 'gentle', label: 'Gentle', hint: 'A message now, a reminder after 10 minutes. No calls.', steps: [{ after_minutes: 0, channel: 'telegram' }, { after_minutes: 10, channel: 'whatsapp' }] },
  { id: 'standard', label: 'Standard', hint: 'Telegram now, WhatsApp after 5 minutes, a phone call after 15.', steps: [{ after_minutes: 0, channel: 'telegram' }, { after_minutes: 5, channel: 'whatsapp' }, { after_minutes: 15, channel: 'call' }] },
  { id: 'persistent', label: 'Persistent', hint: 'Calls after 15, 30 and 60 minutes until you answer.', steps: [{ after_minutes: 0, channel: 'whatsapp' }, { after_minutes: 15, channel: 'call' }, { after_minutes: 30, channel: 'call' }, { after_minutes: 60, channel: 'call' }] },
];
export function describeSteps(steps: Step[]): string {
  return [...steps].sort((a, b) => a.after_minutes - b.after_minutes).map((s) => `${CHANNEL_LABEL[s.channel]} ${s.after_minutes === 0 ? 'right away' : `after ${s.after_minutes >= 60 && s.after_minutes % 60 === 0 ? `${s.after_minutes / 60} h` : `${s.after_minutes} min`}`}`).join(' → ');
}
