export interface KpiDef {
  id: string;
  label: string;
}

export interface KpiCard {
  id: string;
  label: string;
  value: string | number;
  hint: string;
}

export interface NativeCurrency {
  name: string;
  unit_cost_usd: number;
  action_kind: string;
}

export interface QuickAction {
  kind: string;
  label: string;
}

export interface Platform {
  id: string;
  label: string;
  kind: string;
  archetype: 'social_outbound' | 'bidding_marketplace' | 'inbound_storefront' | 'vetted_network' | 'review_directory' | 'custom';
  archetype_label: string;
  category: string;
  native_currency: NativeCurrency | null;
  sla_target_mins: number;
  kpi_definitions: KpiDef[];
  quick_actions: QuickAction[];
  is_custom?: boolean;
  home: string | null;
  terms: string | null;
  rules: string[];
  profile: string[];
  limits: { note_chars?: number };
  templates: Array<{ name: string; body: string }>;
  has_search: boolean;
  pages: Array<{ label: string; url: string }>;
  features: Array<{ title: string; text: string; tip: string }>;
}

export interface Catalog {
  platforms: Platform[];
  hidden_platforms: string[];
  statuses: string[];
  activity_kinds: string[];
  activity_labels: Record<string, string>;
  archetypes: Array<{ id: string; label: string }>;
}

export interface Rec {
  id: number;
  type: string;
  [k: string]: any;
}

export interface ChannelBid {
  id: number;
  platform: string;
  job_url: string;
  title: string;
  client_name: string;
  bid_amount: number;
  currency_name: string;
  currency_spent: number;
  boosted: number;
  hook_template_id: string;
  client_payment_verified: number;
  client_hire_rate: number;
  client_avg_hourly: number;
  status: string;
  notes: string;
  crm_lead_id: number | null;
  created_at: string;
}

export interface ChannelGig {
  id: number;
  platform: string;
  title: string;
  url: string;
  impressions: number;
  clicks: number;
  inquiries: number;
  orders: number;
  revenue: number;
  avg_response_mins: number;
  keywords: string;
  status: string;
}

export interface ChannelReview {
  id: number;
  platform: string;
  client_id: number | null;
  client_name: string;
  status: 'invited' | 'submitted' | 'published';
  rating: number | null;
  review_url: string;
  invited_at: string;
}

export interface Summary {
  platform: string;
  spec?: {
    archetype: Platform['archetype'];
    archetype_label: string;
    category: string;
    native_currency: NativeCurrency | null;
    sla_target_mins: number;
    kpi_definitions: KpiDef[];
    quick_actions: QuickAction[];
  };
  kpis?: KpiCard[];
  pipeline: {
    counts: Record<string, number>;
    open: number;
    followups_due: number;
    due_titles: string[];
    win_rate_percent: number | null;
    value_won: number;
    value_open: number;
  };
  native?: {
    bids: ChannelBid[];
    gigs: ChannelGig[];
    reviews: ChannelReview[];
    won_clients: Array<{ id: number; company_name: string; domain: string; updated_at: string }>;
    pacing_rows: Array<{ day: string; invites_sent: number; inmails_sent: number; profile_views: number; comments_left: number; weekly_limit: number; ssi_score: number }>;
    hooks_leaderboard: Array<{ hook: string; sent: number; viewed: number; replied: number; won: number; reply_rate_pct: number }>;
    spend_usd: number;
    total_currency_spent: number;
  };
  response: {
    messages_30d: number;
    replied: number;
    average_minutes: number | null;
    within_1h_pct: number | null;
    within_24h_pct: number | null;
    unanswered: number;
    oldest_unanswered_hours: number;
  };
  activity_this_week: Record<string, number>;
  routine: { total: number; done_today: number; streak_days: number };
  setting: { work_days: number[]; start: string; end: string; remind_minutes: number; notify: boolean; weekly_invite_limit?: number } | null;
  funnel: { applications: number; reply_rate_percent: number | null; interview_rate_percent: number | null; win_rate_of_applied_percent: number | null; cost_total: number; cost_per_reply: number | null; cost_per_win: number | null };
  pacing: { invites_7d: number; today: number; limit: number; remaining: number | null; over: boolean; note: string } | null;
  experiments_due: Array<{ id: number; what: string; review_on: string }>;
}

export const localDay = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export const KIND_LABEL: Record<string, string> = {
  invite_sent: 'Invites Sent',
  invite_accepted: 'Invites Accepted',
  comment_left: 'Warm-Up Comments',
  message_sent: 'Messages Sent',
  reply_received: 'Replies Received',
  profile_view: 'Profile Views',
  proposal_sent: 'Proposals Sent',
  proposal_viewed: 'Proposals Viewed',
  order_received: 'Orders Received',
  gig_impressions: 'Gig Impressions',
  gig_impression: 'Gig Impressions',
  gig_clicks: 'Gig Clicks',
  gig_click: 'Gig Clicks',
  gig_orders: 'Gig Orders',
  gig_order: 'Gig Orders',
  inquiry_received: 'Inbound Inquiries',
  call_booked: 'Calls Booked',
  connects_spent: 'Connects Spent',
  bids_spent: 'Bids Spent',
  credits_spent: 'Proposal Credits Spent',
  quotes_spent: 'Quotes Spent',
  match_received: 'Matches Received',
  trial_started: 'Trials Started',
  hire_confirmed: 'Hires Confirmed',
  review_invited: 'Reviews Invited',
  review_published: 'Reviews Published',
};

export const STATUS_LABEL: Record<string, string> = {
  saved: 'Saved',
  applied: 'Applied',
  viewed: 'Viewed',
  replied: 'Replied',
  interview: 'Interview',
  won: 'Won',
  lost: 'Lost',
};

export const fmtMinutes = (m: number | null) => (m === null ? 'n/a' : m < 60 ? `${m} min` : m < 1440 ? `${(m / 60).toFixed(1)} h` : `${(m / 1440).toFixed(1)} d`);
