export interface Platform {
  id: string; label: string; kind: string; home: string | null; terms: string | null; rules: string[]; profile: string[];
  limits: { note_chars?: number }; templates: Array<{ name: string; body: string }>; has_search: boolean;
  pages: Array<{ label: string; url: string }>; features: Array<{ title: string; text: string; tip: string }>;
}
export interface Catalog { platforms: Platform[]; statuses: string[]; activity_kinds: string[] }
export interface Rec { id: number; type: string; [k: string]: any }
export interface Summary {
  pipeline: { counts: Record<string, number>; open: number; followups_due: number; due_titles: string[]; win_rate_percent: number | null; value_won: number; value_open: number };
  response: { messages_30d: number; replied: number; average_minutes: number | null; within_1h_pct: number | null; within_24h_pct: number | null; unanswered: number; oldest_unanswered_hours: number };
  activity_this_week: Record<string, number>;
  routine: { total: number; done_today: number; streak_days: number };
  setting: { work_days: number[]; start: string; end: string; remind_minutes: number; notify: boolean; weekly_invite_limit?: number } | null;
  funnel: { applications: number; reply_rate_percent: number | null; interview_rate_percent: number | null; win_rate_of_applied_percent: number | null; cost_total: number; cost_per_reply: number | null; cost_per_win: number | null };
  pacing: { invites_7d: number; today: number; limit: number; remaining: number | null; over: boolean; note: string } | null;
  experiments_due: Array<{ id: number; what: string; review_on: string }>;
}
export const localDay = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const KIND_LABEL: Record<string, string> = {
  invite_sent: 'Invites sent', message_sent: 'Messages sent', reply_received: 'Replies received', profile_view: 'Profile views', proposal_sent: 'Proposals sent',
  order_received: 'Orders received', gig_impressions: 'Gig impressions', gig_clicks: 'Gig clicks', gig_orders: 'Gig orders', invite_accepted: 'Invites accepted', connects_spent: 'Connects spent',
};
export const STATUS_LABEL: Record<string, string> = { saved: 'Saved', applied: 'Applied', replied: 'Replied', interview: 'Interview', won: 'Won', lost: 'Lost' };
export const fmtMinutes = (m: number | null) => (m === null ? 'n/a' : m < 60 ? `${m} min` : m < 1440 ? `${(m / 60).toFixed(1)} h` : `${(m / 1440).toFixed(1)} d`);
