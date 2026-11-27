import { useState } from 'react';
import type { FC } from 'react';
import { Calculator, CheckCircle2, Copy, Globe, Shield, Sparkles } from 'lucide-react';
import { Badge, Button, Card, Stat, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';

export const AgencyRoiCalculator: FC = () => {
  const [visitors, setVisitors] = useState('15000');
  const [crPct, setCrPct] = useState('1.4');
  const [dealVal, setDealVal] = useState('450');
  const [liftPct, setLiftPct] = useState('30');
  const [copied, setCopied] = useState(false);

  const v = Math.max(0, Number(visitors) || 0);
  const cr = Math.max(0, Number(crPct) || 0) / 100;
  const dv = Math.max(0, Number(dealVal) || 0);
  const lift = Math.max(0, Number(liftPct) || 0) / 100;

  const currentRev = v * cr * dv;
  const recoveredMonthly = Math.round(currentRev * lift);
  const recoveredAnnual = recoveredMonthly * 12;
  const hook = `Fixing your mobile checkout & page speed (lifting conversion by ${liftPct}%) recovers ~$${recoveredMonthly.toLocaleString()}/mo ($${recoveredAnnual.toLocaleString()}/yr) on your existing ${v.toLocaleString()} monthly visitors.`;

  return (
    <div className="space-y-5">
      <Card className="space-y-4">
        <div className="flex items-center gap-2">
          <Calculator className="h-5 w-5 text-emerald-400" />
          <div>
            <h3 className="text-sm font-semibold text-white">Agency Pricing &amp; Client ROI Calculator</h3>
            <p className="text-xs text-slate-400">Turn a prospect&apos;s traffic and conversion gap into a concrete revenue hook for your pitch.</p>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-4">
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Monthly Visitors</label>
            <input type="number" className={field} value={visitors} onChange={(e) => setVisitors(e.target.value)} />
          </div>
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Current Conv. Rate (%)</label>
            <input type="number" step="0.1" className={field} value={crPct} onChange={(e) => setCrPct(e.target.value)} />
          </div>
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Avg Order / Lead Value ($)</label>
            <input type="number" className={field} value={dealVal} onChange={(e) => setDealVal(e.target.value)} />
          </div>
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Expected Lift (%)</label>
            <input type="number" className={field} value={liftPct} onChange={(e) => setLiftPct(e.target.value)} />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Current Monthly Revenue" value={`$${Math.round(currentRev).toLocaleString()}`} hint="baseline estimate" />
          <Stat label="Monthly Recovered Upside" value={`+$${recoveredMonthly.toLocaleString()}/mo`} hint={`${liftPct}% conversion lift`} />
          <Stat label="Annualized Impact" value={`+$${recoveredAnnual.toLocaleString()}/yr`} hint={`Suggested fee: $${Math.max(1500, Math.round(recoveredMonthly * 0.25)).toLocaleString()}/mo`} />
        </div>
        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs">
          <span className="text-slate-200">{hook}</span>
          <Button
            small
            variant="primary"
            onClick={() => {
              navigator.clipboard?.writeText(hook);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
          >
            {copied ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied Hook' : 'Copy Client Hook'}
          </Button>
        </div>
      </Card>
    </div>
  );
};

export const DomainDnsStudio: FC<{ initialDomain?: string }> = ({ initialDomain = '' }) => {
  const [domain, setDomain] = useState(initialDomain);
  const [esp, setEsp] = useState<'google' | 'ms365' | 'smtp'>('google');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [audit, setAudit] = useState<any>(null);
  const [records, setRecords] = useState<any>(null);

  const runLookup = async () => {
    const clean = domain.trim().replace(/^https?:\/\//i, '').split('/')[0];
    if (!clean) return;
    setLoading(true);
    setError('');
    try {
      const [aRes, rRes] = await Promise.all([
        apiFetch('/api/outbound/dns/audit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ domain: clean }),
        }),
        apiFetch('/api/outbound/dns/records', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ domain: clean, esp_provider: esp, dmarc_policy: 'quarantine' }),
        }),
      ]);
      const aData = await aRes.json().catch(() => ({}));
      const rData = await rRes.json().catch(() => ({}));
      if (!aRes.ok) throw new Error(apiErrorMessage(aRes.status, aData));
      setAudit(aData);
      if (rRes.ok) setRecords(rData);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <Card className="space-y-4">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-indigo-400" />
          <div>
            <h3 className="text-sm font-semibold text-white">Domain &amp; Deliverability DNS Studio</h3>
            <p className="text-xs text-slate-400">1-click SPF, DKIM, DMARC, and MX audit for your sending domains or prospect domains.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="relative flex-1 min-w-60">
            <Globe className="h-4 w-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              className={`${field} pl-9`}
              placeholder="e.g. acme.com"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
            />
          </div>
          <select
            value={esp}
            onChange={(e) => setEsp(e.target.value as typeof esp)}
            className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-xs text-white"
          >
            <option value="google">Google Workspace</option>
            <option value="ms365">Microsoft 365</option>
            <option value="smtp">Custom SMTP</option>
          </select>
          <Button variant="primary" onClick={runLookup} disabled={loading || !domain.trim()}>
            <Sparkles className="h-3.5 w-3.5" /> {loading ? 'Checking DNS…' : 'Run DNS Audit'}
          </Button>
        </div>
        {error && <p className="text-xs text-rose-400">{error}</p>}
      </Card>

      {audit && (
        <div className="grid gap-4 md:grid-cols-3">
          {['spf', 'dkim', 'dmarc'].map((k) => {
            const item = audit[k] ?? audit?.checks?.[k] ?? {};
            const ok = item.valid ?? item.present ?? item.status === 'pass';
            return (
              <Card key={k} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase text-white">{k}</span>
                  <Badge tone={ok ? 'good' : 'bad'}>{ok ? 'Pass' : 'Missing / Weak'}</Badge>
                </div>
                <p className="text-[11px] font-mono text-slate-400 break-all">{item.record || item.detail || 'No record detected'}</p>
              </Card>
            );
          })}
        </div>
      )}

      {records && (
        <Card className="space-y-2">
          <h4 className="text-xs font-semibold text-white">Recommended DNS Records ({esp.toUpperCase()})</h4>
          <pre className="text-[11px] font-mono text-slate-300 bg-slate-950 p-3 rounded-xl border border-slate-800 overflow-x-auto">
            {JSON.stringify(records, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
};
