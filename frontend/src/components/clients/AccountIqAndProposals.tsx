import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { Check, Copy, Eye, FileSignature, Sparkles } from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { apiFetch, apiErrorMessage } from '../../lib/api';

interface AccountIQ {
  lead_id: number;
  audit_score: number | null;
  critical_findings_count: number;
  verified_contacts_count: number;
  decision_makers_count: number;
  recommended_angle: string;
  smart_link_engagement: Array<{ report_type: string; views: number; last_viewed_at: string }>;
}

interface Proposal {
  id: number;
  token: string;
  title: string;
  price_amount: number | null;
  currency: string;
  status: string;
  signed_by?: string | null;
}

export const AccountIqAndProposals: FC<{ leadId: number; companyName: string }> = ({ leadId, companyName }) => {
  const [iq, setIq] = useState<AccountIQ | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState(`Technical Growth & Web Modernization — ${companyName}`);
  const [summary, setSummary] = useState('Scoped deliverables based on our technical audit findings.');
  const [price, setPrice] = useState('3500');
  const [busy, setBusy] = useState(false);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);
  const [err, setErr] = useState('');

  const load = async () => {
    try {
      const [iqRes, propRes] = await Promise.all([
        apiFetch(`/api/clients/${leadId}/account-iq`),
        apiFetch(`/api/proposals/lead/${leadId}`),
      ]);
      if (iqRes.ok) setIq(await iqRes.json());
      if (propRes.ok) {
        const pb = await propRes.json();
        setProposals(pb.proposals || []);
      }
    } catch {
      /* optional enrichment */
    }
  };

  useEffect(() => {
    load();
  }, [leadId]); // eslint-disable-line react-hooks/exhaustive-deps

  const createProposal = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const res = await apiFetch('/api/proposals/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_id: leadId,
          title: title.trim(),
          summary: summary.trim(),
          scope_items: ['Core Web Vitals & Security Hardening', 'SEO & Conversion Architecture Fix', 'QA & Production Rollout'],
          price_amount: price ? Number(price) : null,
          currency: 'USD',
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiErrorMessage(res.status, body));
      setShowCreate(false);
      await load();
    } catch (ex) {
      setErr((ex as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-indigo-400" />
          Account IQ &amp; Interactive Proposals
        </h3>
        <Button small variant="secondary" onClick={() => setShowCreate((v) => !v)}>
          <FileSignature className="h-3.5 w-3.5 text-indigo-400" />
          {showCreate ? 'Cancel' : 'New E-Sign Proposal'}
        </Button>
      </div>

      {iq && (
        <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2 mb-3 text-xs">
          <div className="flex flex-wrap gap-2">
            <Badge tone={iq.critical_findings_count > 0 ? 'warn' : 'good'}>
              {iq.critical_findings_count} critical/high findings
            </Badge>
            <Badge tone={iq.verified_contacts_count > 0 ? 'good' : 'neutral'}>
              {iq.verified_contacts_count}/{iq.decision_makers_count} verified contacts
            </Badge>
            {iq.smart_link_engagement.map((v) => (
              <Badge key={v.report_type} tone="accent">
                <Eye className="h-3 w-3 mr-1" /> {v.report_type}: {v.views} view(s)
              </Badge>
            ))}
          </div>
          <p className="text-slate-300 leading-relaxed">
            <strong className="text-white">Recommended Angle:</strong> {iq.recommended_angle}
          </p>
        </div>
      )}

      {showCreate && (
        <form onSubmit={createProposal} className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 mb-3">
          <input className={field} required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Proposal title" />
          <input className={field} value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Executive summary" />
          <div className="flex gap-2">
            <input className={field} type="number" min={0} value={price} onChange={(e) => setPrice(e.target.value)} placeholder="Price (USD)" />
            <Button type="submit" variant="primary" disabled={busy}>{busy ? 'Creating…' : 'Publish Smart Link'}</Button>
          </div>
          {err && <p className="text-xs text-rose-400">{err}</p>}
        </form>
      )}

      {proposals.length > 0 && (
        <ul className="divide-y divide-slate-800 text-xs">
          {proposals.map((p) => {
            const url = `${window.location.origin}/p/${p.token}`;
            return (
              <li key={p.id} className="py-2 flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-slate-200 truncate">{p.title}</div>
                  <div className="text-[11px] text-slate-400">
                    {p.price_amount != null ? `$${p.price_amount.toLocaleString()} ${p.currency} · ` : ''}
                    Status: <span className="text-indigo-300">{p.status}</span>
                    {p.signed_by ? ` (Signed by ${p.signed_by})` : ''}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <a href={`/p/${p.token}`} target="_blank" rel="noopener noreferrer" className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-300 text-[11px]">
                    Open
                  </a>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(url);
                      setCopiedToken(p.token);
                      setTimeout(() => setCopiedToken(null), 2000);
                    }}
                    className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] inline-flex items-center gap-1"
                  >
                    {copiedToken === p.token ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                    {copiedToken === p.token ? 'Copied' : 'Copy Link'}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
};
