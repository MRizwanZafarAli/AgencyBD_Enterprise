import { useState } from 'react';
import type { FC } from 'react';
import {
  Award,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  Link2,
  Plus,
  Search,
  ShieldAlert,
  Sparkles,
  Star,
  Trash2,
  TrendingUp,
} from 'lucide-react';
import { Badge, Button, Card, Stat } from '../ui';
import { send } from '../../lib/hooks';
import { apiFetch } from '../../lib/api';
import type { ChannelBid, ChannelGig, ChannelReview, Platform, Summary } from './types';
import { STATUS_LABEL, localDay } from './types';
import type { ScraperMode } from '../browser/InteractiveBrowserSidepanel';

type Run = (fn: () => Promise<unknown>) => void;

export interface ArchetypeViewProps {
  platform: Platform;
  s: Summary | null;
  run: Run;
  onOpenScraper?: (url: string, mode?: ScraperMode, title?: string) => void;
}

/* 1. Social & Outbound (LinkedIn) */
export const SocialOutboundView: FC<ArchetypeViewProps> = ({ platform, s, run, onOpenScraper }) => {
  const [company, setCompany] = useState('');
  const [titles, setTitles] = useState('CEO, Founder, CTO, Head of Growth');
  const [location, setLocation] = useState('');
  const [xrayLinks, setXrayLinks] = useState<Array<{ label: string; url: string }>>([]);
  const [pacingForm, setPacingForm] = useState({ invites_sent: '10', inmails_sent: '2', comments_left: '3', ssi_score: '72' });

  const buildXray = async () => {
    if (!company.trim()) return;
    const res = await send<{ links: Array<{ label: string; url: string }> }>('/api/channels/linkedin/search_links', 'POST', {
      company: company.trim(),
      titles: titles.split(',').map((t) => t.trim()).filter(Boolean),
      location: location.trim() || undefined,
    });
    setXrayLinks(res.links ?? []);
  };

  const savePacing = () => {
    run(() =>
      send(`/api/channels/${platform.id}/pacing`, 'POST', {
        day: localDay(),
        invites_sent: Number(pacingForm.invites_sent) || 0,
        inmails_sent: Number(pacingForm.inmails_sent) || 0,
        comments_left: Number(pacingForm.comments_left) || 0,
        ssi_score: Number(pacingForm.ssi_score) || 0,
      }),
    );
  };

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Built-in LinkedIn X-Ray Builder</h3>
            <p className="text-xs text-slate-400">Generate decision-maker searches and launch in your browser or Side Panel.</p>
          </div>
          <Badge tone="accent">Account-Safe</Badge>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          <input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Target company"
            className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white"
          />
          <input
            value={titles}
            onChange={(e) => setTitles(e.target.value)}
            placeholder="Titles (CEO, CTO)"
            className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white"
          />
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Location (optional)"
            className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white"
          />
        </div>
        <Button small variant="primary" onClick={buildXray} disabled={!company.trim()}>
          <Search className="h-3.5 w-3.5" /> Build X-Ray Links
        </Button>
        {xrayLinks.length > 0 && (
          <div className="space-y-1.5 pt-2 border-t border-slate-800">
            {xrayLinks.map((lnk) => (
              <div key={lnk.url} className="flex items-center justify-between gap-2 text-xs bg-slate-900/70 px-3 py-2 rounded-lg">
                <span className="text-slate-200 truncate">{lnk.label}</span>
                <div className="flex items-center gap-2 shrink-0">
                  {onOpenScraper && (
                    <Button small variant="ghost" onClick={() => onOpenScraper(lnk.url, 'job_spec', lnk.label)}>
                      Side Panel
                    </Button>
                  )}
                  <a href={lnk.url} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:underline inline-flex items-center gap-1">
                    Open <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Daily Pacing & Warm-Up Log</h3>
            <p className="text-xs text-slate-400">Track invites, InMails, warm-up comments, and SSI score safely.</p>
          </div>
          {s?.pacing && (
            <Badge tone={s.pacing.over ? 'bad' : 'good'}>
              {s.pacing.invites_7d}/{s.pacing.limit} weekly
            </Badge>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Invites today</label>
            <input type="number" value={pacingForm.invites_sent} onChange={(e) => setPacingForm((f) => ({ ...f, invites_sent: e.target.value }))} className="w-full rounded-lg bg-slate-900 border border-slate-800 px-2.5 py-1.5 text-xs text-white" />
          </div>
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">InMails / DMs</label>
            <input type="number" value={pacingForm.inmails_sent} onChange={(e) => setPacingForm((f) => ({ ...f, inmails_sent: e.target.value }))} className="w-full rounded-lg bg-slate-900 border border-slate-800 px-2.5 py-1.5 text-xs text-white" />
          </div>
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Warm-Up Comments</label>
            <input type="number" value={pacingForm.comments_left} onChange={(e) => setPacingForm((f) => ({ ...f, comments_left: e.target.value }))} className="w-full rounded-lg bg-slate-900 border border-slate-800 px-2.5 py-1.5 text-xs text-white" />
          </div>
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">SSI Score</label>
            <input type="number" value={pacingForm.ssi_score} onChange={(e) => setPacingForm((f) => ({ ...f, ssi_score: e.target.value }))} className="w-full rounded-lg bg-slate-900 border border-slate-800 px-2.5 py-1.5 text-xs text-white" />
          </div>
        </div>
        <Button small variant="secondary" onClick={savePacing}>Save Today&apos;s Pacing</Button>
      </Card>
    </div>
  );
};

/* 2. Bidding Marketplaces (Upwork, Freelancer, PeoplePerHour, Guru) */
export const BiddingMarketplaceView: FC<ArchetypeViewProps> = ({ platform, s, run }) => {
  const currName = platform.native_currency?.name ?? 'Credits';
  const unitCost = platform.native_currency?.unit_cost_usd ?? 0.5;
  const bids: ChannelBid[] = s?.native?.bids ?? [];
  const hooks = s?.native?.hooks_leaderboard ?? [];

  const [form, setForm] = useState({
    title: '',
    client_name: '',
    url: '',
    budget: '',
    currency_spent: '12',
    boosted: false,
    hook_template_id: '',
    client_payment_verified: true,
    client_hire_rate: '65',
  });

  const captureBid = () => {
    if (!form.title.trim()) return;
    run(async () => {
      await send(`/api/channels/${platform.id}/capture`, 'POST', {
        title: form.title.trim(),
        client_name: form.client_name.trim() || undefined,
        url: form.url.trim() || undefined,
        budget: Number(form.budget) || 0,
        currency_spent: Number(form.currency_spent) || 0,
        boosted: form.boosted,
        hook_template_id: form.hook_template_id.trim() || undefined,
        client_payment_verified: form.client_payment_verified,
        client_hire_rate: Number(form.client_hire_rate) || 0,
        status: 'applied',
      });
      setForm((f) => ({ ...f, title: '', client_name: '', url: '', budget: '' }));
    });
  };

  const organicBids = bids.filter((b) => !b.boosted);
  const boostedBids = bids.filter((b) => !!b.boosted);
  const orgWins = organicBids.filter((b) => b.status === 'won').length;
  const boostWins = boostedBids.filter((b) => b.status === 'won').length;

  return (
    <div className="space-y-5">
      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">1-Click Job Capture & Client Quality Pre-Check</h3>
            <p className="text-xs text-slate-400">
              Logs into {platform.label} Bids + syncs directly to your Clients CRM. Currency: <strong>{currName}</strong> (${unitCost.toFixed(2)}/unit).
            </p>
          </div>
          <Badge tone="info">{bids.length} logged</Badge>
        </div>

        <div className="grid gap-2 sm:grid-cols-4">
          <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="Job title" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white sm:col-span-2" />
          <input value={form.client_name} onChange={(e) => setForm((f) => ({ ...f, client_name: e.target.value }))} placeholder="Client / Company" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          <input value={form.url} onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} placeholder="Job URL" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          <input type="number" value={form.budget} onChange={(e) => setForm((f) => ({ ...f, budget: e.target.value }))} placeholder="Budget ($)" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          <input type="number" value={form.currency_spent} onChange={(e) => setForm((f) => ({ ...f, currency_spent: e.target.value }))} placeholder={`${currName} spent`} className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          <input value={form.hook_template_id} onChange={(e) => setForm((f) => ({ ...f, hook_template_id: e.target.value }))} placeholder="Hook ID (e.g. Audit-L1)" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          <div className="flex items-center gap-3 text-xs text-slate-300">
            <label className="flex items-center gap-1 cursor-pointer">
              <input type="checkbox" checked={form.boosted} onChange={(e) => setForm((f) => ({ ...f, boosted: e.target.checked }))} />
              Boosted
            </label>
            <label className="flex items-center gap-1 cursor-pointer">
              <input type="checkbox" checked={form.client_payment_verified} onChange={(e) => setForm((f) => ({ ...f, client_payment_verified: e.target.checked }))} />
              Verified
            </label>
          </div>
        </div>
        <Button small variant="primary" onClick={captureBid} disabled={!form.title.trim()}>
          <Sparkles className="h-3.5 w-3.5" /> Capture Bid + Sync to CRM
        </Button>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="space-y-2">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-emerald-400" /> {currName} & Boost ROI
          </h3>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
              <span className="text-slate-400 block">Organic Proposals</span>
              <span className="text-base font-bold text-white">{organicBids.length}</span>
              <span className="text-[11px] text-emerald-400 block">{orgWins} won</span>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800">
              <span className="text-slate-400 block">Boosted Proposals</span>
              <span className="text-base font-bold text-white">{boostedBids.length}</span>
              <span className="text-[11px] text-amber-400 block">{boostWins} won</span>
            </div>
          </div>
        </Card>

        <Card className="space-y-2">
          <h3 className="text-sm font-semibold text-white">First-2-Lines Hook Leaderboard</h3>
          {hooks.length === 0 ? (
            <p className="text-xs text-slate-400">Tag bids with a Hook ID (e.g. `Audit-L1`) to compare View & Reply rates.</p>
          ) : (
            <div className="space-y-1.5 text-xs">
              {hooks.slice(0, 5).map((h) => (
                <div key={h.hook} className="flex items-center justify-between bg-slate-900/70 px-3 py-1.5 rounded-lg">
                  <span className="font-medium text-white">{h.hook}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400">{h.sent} sent</span>
                    <Badge tone={h.reply_rate_pct >= 20 ? 'good' : 'neutral'}>{h.reply_rate_pct}% reply</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {bids.length > 0 && (
        <Card className="space-y-2">
          <h3 className="text-sm font-semibold text-white">Tracked {platform.label} Bids</h3>
          <div className="space-y-2">
            {bids.slice(0, 12).map((b) => (
              <div key={b.id} className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-xl border border-slate-800 bg-slate-900/50 text-xs">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white truncate">{b.title}</span>
                    {b.boosted ? <Badge tone="warn">Boosted</Badge> : null}
                    {b.client_payment_verified ? <Badge tone="good">Payment Verified</Badge> : null}
                    {b.hook_template_id && <Badge tone="ai">{b.hook_template_id}</Badge>}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {b.client_name || 'Client'} · ${b.bid_amount.toLocaleString()} · {b.currency_spent} {b.currency_name || currName}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={b.status}
                    onChange={(e) => {
                      const val = e.target.value;
                      run(() => apiFetch(`/api/channels/${platform.id}/bids/${b.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: val }) }));
                    }}
                    className="rounded-lg bg-slate-950 border border-slate-800 px-2 py-1 text-xs text-white"
                  >
                    {['saved', 'applied', 'viewed', 'replied', 'interview', 'won', 'lost'].map((st) => (
                      <option key={st} value={st}>{STATUS_LABEL[st] ?? st}</option>
                    ))}
                  </select>
                  <button type="button" onClick={() => run(() => send(`/api/channels/${platform.id}/bids/${b.id}`, 'DELETE'))} aria-label="Delete bid">
                    <Trash2 className="h-3.5 w-3.5 text-rose-400" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

/* 3. Inbound Storefronts (Fiverr, Contra) */
export const InboundStorefrontView: FC<ArchetypeViewProps> = ({ platform, s, run }) => {
  const gigs: ChannelGig[] = s?.native?.gigs ?? [];
  const [form, setForm] = useState({ title: '', impressions: '0', clicks: '0', orders: '0', revenue: '0', keywords: '' });

  const createGig = () => {
    if (!form.title.trim()) return;
    run(async () => {
      await send(`/api/channels/${platform.id}/gigs`, 'POST', {
        title: form.title.trim(),
        impressions: Number(form.impressions) || 0,
        clicks: Number(form.clicks) || 0,
        orders: Number(form.orders) || 0,
        revenue: Number(form.revenue) || 0,
        keywords: form.keywords.trim(),
      });
      setForm({ title: '', impressions: '0', clicks: '0', orders: '0', revenue: '0', keywords: '' });
    });
  };

  const unanswered = s?.response.unanswered ?? 0;
  return (
    <div className="space-y-5">
      <Card className={`!border-${unanswered > 0 ? 'rose' : 'emerald'}-500/30 flex flex-wrap items-center justify-between gap-3`}>
        <div className="flex items-center gap-2.5 text-xs">
          {unanswered > 0 ? <ShieldAlert className="h-4 w-4 text-rose-400" /> : <Clock className="h-4 w-4 text-emerald-400" />}
          <div>
            <span className="font-semibold text-white block">1-Hour Response SLA Guard</span>
            <span className="text-slate-400">
              {unanswered > 0
                ? `${unanswered} buyer message(s) waiting — reply within ${platform.sla_target_mins}m to protect Seller Level.`
                : `Inbox clear. Target response SLA: <= ${platform.sla_target_mins} min.`}
            </span>
          </div>
        </div>
        <Badge tone={unanswered > 0 ? 'bad' : 'good'}>{unanswered > 0 ? 'SLA At Risk' : 'SLA Healthy'}</Badge>
      </Card>

      <Card className="space-y-3">
        <h3 className="text-sm font-semibold text-white">Gig / Service SKU Performance Matrix</h3>
        <div className="grid gap-2 sm:grid-cols-6">
          <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="Gig / Service title" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white sm:col-span-2" />
          <input type="number" value={form.impressions} onChange={(e) => setForm((f) => ({ ...f, impressions: e.target.value }))} placeholder="Impressions" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          <input type="number" value={form.clicks} onChange={(e) => setForm((f) => ({ ...f, clicks: e.target.value }))} placeholder="Clicks" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          <input type="number" value={form.orders} onChange={(e) => setForm((f) => ({ ...f, orders: e.target.value }))} placeholder="Orders" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          <input type="number" value={form.revenue} onChange={(e) => setForm((f) => ({ ...f, revenue: e.target.value }))} placeholder="Revenue ($)" className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
        </div>
        <Button small variant="primary" onClick={createGig} disabled={!form.title.trim()}>
          <Plus className="h-3.5 w-3.5" /> Add Gig / Service SKU
        </Button>

        {gigs.length > 0 && (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 pr-2">SKU</th>
                  <th className="py-2 px-2">Impr</th>
                  <th className="py-2 px-2">Clicks</th>
                  <th className="py-2 px-2">CTR</th>
                  <th className="py-2 px-2">Orders</th>
                  <th className="py-2 px-2">CVR</th>
                  <th className="py-2 px-2">Revenue</th>
                  <th className="py-2 pl-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {gigs.map((g) => {
                  const ctr = g.impressions > 0 ? `${((g.clicks / g.impressions) * 100).toFixed(1)}%` : '—';
                  const cvr = g.clicks > 0 ? `${((g.orders / g.clicks) * 100).toFixed(1)}%` : '—';
                  return (
                    <tr key={g.id}>
                      <td className="py-2 pr-2 font-medium text-white">{g.title}</td>
                      <td className="py-2 px-2 text-slate-300">{g.impressions.toLocaleString()}</td>
                      <td className="py-2 px-2 text-slate-300">{g.clicks.toLocaleString()}</td>
                      <td className="py-2 px-2 text-indigo-300">{ctr}</td>
                      <td className="py-2 px-2 text-slate-300">{g.orders}</td>
                      <td className="py-2 px-2 text-emerald-400">{cvr}</td>
                      <td className="py-2 px-2 font-semibold text-emerald-300">${g.revenue.toLocaleString()}</td>
                      <td className="py-2 pl-2 text-right">
                        <button type="button" onClick={() => run(() => send(`/api/channels/${platform.id}/gigs/${g.id}`, 'DELETE'))}>
                          <Trash2 className="h-3.5 w-3.5 text-rose-400" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};

/* 4. Vetted Networks (Toptal) */
export const VettedNetworkView: FC<ArchetypeViewProps> = ({ platform, s, run }) => {
  const [avail, setAvail] = useState<'Full-Time' | 'Part-Time' | 'Booked'>(s?.setting?.notify ? 'Full-Time' : 'Part-Time');
  const [rate, setRate] = useState('125');
  const [hours, setHours] = useState('40');
  const weeklyGross = (Number(rate) || 0) * (Number(hours) || 0);

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="space-y-3">
        <h3 className="text-sm font-semibold text-white">Bench & Availability Toggle</h3>
        <p className="text-xs text-slate-400">Keep talent matchers updated so you receive qualified trial matches.</p>
        <div className="flex flex-wrap gap-2">
          {(['Full-Time', 'Part-Time', 'Booked'] as const).map((st) => (
            <Button
              key={st}
              small
              variant={avail === st ? 'primary' : 'secondary'}
              onClick={() => {
                setAvail(st);
                run(() => send(`/api/channels/${platform.id}/records`, 'POST', { type: 'setting', data: { work_days: [0, 1, 2, 3, 4], start: '09:00', end: '17:00', remind_minutes: 60, notify: st !== 'Booked' } }));
              }}
            >
              {st}
            </Button>
          ))}
        </div>
      </Card>
      <Card className="space-y-3">
        <h3 className="text-sm font-semibold text-white">Rate Card & Weekly Margin Calculator</h3>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Net Hourly Rate ($)</label>
            <input type="number" value={rate} onChange={(e) => setRate(e.target.value)} className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          </div>
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Weekly Hours</label>
            <input type="number" value={hours} onChange={(e) => setHours(e.target.value)} className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white" />
          </div>
        </div>
        <Stat label="Projected Weekly Net" value={`$${weeklyGross.toLocaleString()}`} hint={`$${(weeklyGross * 4).toLocaleString()}/mo at 0% fee`} />
      </Card>
    </div>
  );
};

/* 5. B2B Review Directory (Clutch) */
export const ReviewDirectoryView: FC<ArchetypeViewProps> = ({ platform, s, run }) => {
  const reviews: ChannelReview[] = s?.native?.reviews ?? [];
  const wonClients = s?.native?.won_clients ?? [];
  const [utmBase, setUtmBase] = useState('https://youragency.com');
  const [copied, setCopied] = useState(false);

  const utmUrl = `${utmBase.replace(/\/$/, '')}/?utm_source=clutch&utm_medium=directory&utm_campaign=leader_matrix`;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
                <Award className="h-4 w-4 text-amber-400" /> Automated Review Request Engine
              </h3>
              <p className="text-xs text-slate-400">Pulls Won deals from Clients CRM so you can invite happy clients in 1 click.</p>
            </div>
            <Badge tone="good">{reviews.filter((r) => r.status === 'published').length} published</Badge>
          </div>
          {wonClients.length === 0 ? (
            <p className="text-xs text-slate-400">Mark deals as Won in Clients CRM to surface them here for Clutch review requests.</p>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {wonClients.map((wc) => {
                const existing = reviews.find((r) => r.client_id === wc.id || r.client_name === wc.company_name);
                return (
                  <div key={wc.id} className="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
                    <div className="min-w-0">
                      <span className="font-semibold text-white block truncate">{wc.company_name}</span>
                      <span className="text-[11px] text-slate-400">{wc.domain}</span>
                    </div>
                    {existing ? (
                      <Badge tone={existing.status === 'published' ? 'good' : 'warn'}>{existing.status}</Badge>
                    ) : (
                      <Button
                        small
                        variant="primary"
                        onClick={() => run(() => send(`/api/channels/${platform.id}/reviews`, 'POST', { client_id: wc.id, client_name: wc.company_name, status: 'invited' }))}
                      >
                        Invite Review
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        <Card className="space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
            <Link2 className="h-4 w-4 text-indigo-400" /> UTM Referral Link Builder
          </h3>
          <p className="text-xs text-slate-400">Add this tagged URL to your Clutch profile so Visitor Radar attributes inbound traffic.</p>
          <input
            value={utmBase}
            onChange={(e) => setUtmBase(e.target.value)}
            placeholder="https://youragency.com"
            className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-white"
          />
          <div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-indigo-300">
            <span className="truncate">{utmUrl}</span>
            <Button
              small
              variant="secondary"
              onClick={() => {
                navigator.clipboard?.writeText(utmUrl);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
            >
              {copied ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
        </Card>
      </div>

      {reviews.length > 0 && (
        <Card className="space-y-2">
          <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
            <Star className="h-4 w-4 text-amber-400" /> Tracked Clutch Reviews
          </h3>
          <div className="space-y-2">
            {reviews.map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-slate-900/50 border border-slate-800 text-xs">
                <span className="font-medium text-white">{r.client_name}</span>
                <div className="flex items-center gap-2">
                  <select
                    value={r.status}
                    onChange={(e) => {
                      const val = e.target.value;
                      run(() => apiFetch(`/api/channels/${platform.id}/reviews/${r.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: val }) }));
                    }}
                    className="rounded-lg bg-slate-950 border border-slate-800 px-2 py-1 text-xs text-white"
                  >
                    <option value="invited">Invited</option>
                    <option value="submitted">Submitted</option>
                    <option value="published">Published</option>
                  </select>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};
