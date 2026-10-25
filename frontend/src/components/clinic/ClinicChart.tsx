import { useState } from 'react';
import type { FC } from 'react';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import { Badge, Card, Tabs } from '../ui';
import { CATEGORY_LABEL, PHASES, SEVERITY_ORDER, SEVERITY_TONE } from './types';
import type { Chart, Finding } from './types';

const worst = (list: Finding[]) => SEVERITY_ORDER.find((s) => list.some((f) => f.severity === s)) ?? 'info';
const scoreTone = (n: number | null) => (n === null ? 'text-slate-400' : n >= 80 ? 'text-emerald-400' : n >= 50 ? 'text-amber-400' : 'text-rose-400');

export const Vitals: FC<{ chart: Chart }> = ({ chart }) => {
  const a = chart.audit;
  if (!a) return null;
  const groups = Object.entries(a.findings.reduce<Record<string, Finding[]>>((m, f) => { (m[f.category] ??= []).push(f); return m; }, {}));
  const ch = chart.history?.change;
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-6">
        <div><div className="text-xs text-slate-400">Health score</div>{a.status === 'blocked' ? <div className="text-2xl font-semibold text-slate-300">Not graded</div> : <div className={`text-5xl font-semibold tabular ${scoreTone(a.overall_score)}`}>{a.overall_score ?? 'n/a'}<span className="text-lg text-slate-500">/100</span></div>}
          {ch && <div className="text-xs mt-1"><Badge tone={ch.score_delta > 0 ? 'good' : ch.score_delta < 0 ? 'bad' : 'neutral'}>{ch.score_delta > 0 ? '+' : ''}{ch.score_delta} since last check</Badge></div>}</div>
        <div className="flex-1 min-w-64">
          <div className="text-xs text-slate-400 mb-2">Findings by area (worst first)</div>
          <div className="flex flex-wrap gap-2">
            {groups.sort((x, y) => SEVERITY_ORDER.indexOf(worst(x[1])) - SEVERITY_ORDER.indexOf(worst(y[1]))).map(([cat, list]) => (
              <Badge key={cat} tone={SEVERITY_TONE[worst(list)]} title={`Worst severity: ${worst(list)}`}>{CATEGORY_LABEL[cat] ?? cat}: {list.length}</Badge>))}
            {groups.length === 0 && <span className="text-sm text-slate-300">No findings.</span>}
          </div>
          <p className="text-[11px] text-slate-500 mt-2">{a.response_time_ms !== undefined ? `Homepage answered in ${a.response_time_ms} ms from our servers. ` : ''}Passive checks only: nothing was attacked, tested hard or logged into.</p>
        </div>
      </div>
      {ch && (ch.fixed.length > 0 || ch.new.length > 0) && (
        <div className="mt-4 pt-3 border-t border-slate-800 grid gap-3 sm:grid-cols-3 text-xs">
          <div><div className="font-medium text-emerald-300">Fixed since {ch.previous_at.slice(0, 10)} ({ch.fixed.length})</div><ul className="text-slate-400 mt-1 space-y-0.5">{ch.fixed.slice(0, 4).map((f) => <li key={f.check_id}>{f.finding}</li>)}</ul></div>
          <div><div className="font-medium text-rose-300">New ({ch.new.length})</div><ul className="text-slate-400 mt-1 space-y-0.5">{ch.new.slice(0, 4).map((f) => <li key={f.check_id}>{f.finding}</li>)}</ul></div>
          <div><div className="font-medium text-slate-300">Still open</div><div className="text-slate-400 mt-1">{ch.still_open}</div></div>
        </div>)}
    </Card>
  );
};

export const Diagnosis: FC<{ chart: Chart }> = ({ chart }) => {
  const all = chart.audit?.findings ?? [];
  const [sev, setSev] = useState('all');
  const [open, setOpen] = useState<string | null>(null);
  if (!chart.audit) return null;
  const shown = [...all].filter((f) => sev === 'all' || f.severity === sev).sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));
  const count = (s: string) => all.filter((f) => f.severity === s).length;
  return (
    <Card>
      <h2 className="text-sm font-semibold text-white mb-3">Diagnosis</h2>
      <Tabs tabs={[{ id: 'all', label: 'All', count: all.length }, ...SEVERITY_ORDER.filter(count).map((s) => ({ id: s, label: s[0].toUpperCase() + s.slice(1), count: count(s) }))]} active={sev} onChange={setSev} />
      {shown.length === 0 ? <p className="text-sm text-slate-300">Nothing here.</p> : (
        <ul className="divide-y divide-slate-800">{shown.map((f) => {
          const isOpen = open === f.check_id;
          return (
            <li key={f.check_id} className="py-2.5">
              <button className="w-full flex items-start gap-2 text-left" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : f.check_id)}>
                {isOpen ? <ChevronDown className="h-4 w-4 mt-0.5 text-slate-500 shrink-0" /> : <ChevronRight className="h-4 w-4 mt-0.5 text-slate-500 shrink-0" />}
                <span className="flex-1 min-w-0 text-sm text-slate-100">{f.finding}</span>
                <Badge tone={SEVERITY_TONE[f.severity] ?? 'neutral'}>{f.severity}</Badge><Badge>{CATEGORY_LABEL[f.category] ?? f.category}</Badge>
              </button>
              {isOpen && (
                <dl className="mt-2 ml-6 space-y-1.5 text-xs">
                  <div><dt className="text-slate-500">Measured</dt><dd className="text-slate-200 font-mono">{f.evidence_value ?? 'n/a'}</dd></div>
                  <div><dt className="text-slate-500">Why it matters</dt><dd className="text-slate-300">{f.estimated_impact ?? 'n/a'}</dd></div>
                  <div><dt className="text-slate-500">The fix</dt><dd className="text-slate-300">{f.fix ?? 'n/a'}</dd></div>
                  <div className="text-slate-500">Evidence #{f.evidence_id ?? 'n/a'}{f.confidence !== null ? ` · confidence ${Math.round((f.confidence ?? 0) * 100)}%` : ''}</div>
                </dl>)}
            </li>);
        })}</ul>)}
    </Card>
  );
};

/** The operation, in order. Ticks are kept in this browser so you can work through it across a session. */
export const Surgery: FC<{ chart: Chart }> = ({ chart }) => {
  const key = `agencybd.clinic.plan.${chart.audit?.domain ?? ''}`;
  const [done, setDone] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem(key) ?? '[]'); } catch { return []; } });
  if (!chart.audit) return null;
  const toggle = (id: string) => { const next = done.includes(id) ? done.filter((d) => d !== id) : [...done, id]; setDone(next); try { localStorage.setItem(key, JSON.stringify(next)); } catch { /* ticks just do not persist */ } };
  const serviceOf = (f: Finding) => chart.advice.find((r) => r.findings.some((x) => x.evidence_id === f.evidence_id));
  const steps = chart.audit.findings.filter((f) => f.severity !== 'info');
  const total = steps.length;
  const finished = steps.filter((f) => done.includes(f.check_id)).length;
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <h2 className="text-sm font-semibold text-white">Surgery plan</h2>
        <Badge tone={finished === total && total > 0 ? 'good' : 'neutral'}>{finished}/{total} done</Badge>
      </div>
      <p className="text-xs text-slate-400 mb-3">Fixes in the order to do them, from the audit&apos;s own severity. Tick each as it is done, then re-examine to confirm the score moved.</p>
      {total === 0 ? <p className="text-sm text-slate-300">No operation needed. Nothing above informational level was found.</p> : PHASES.map((p) => {
        const list = steps.filter((f) => p.severities.includes(f.severity));
        if (list.length === 0) return null;
        return (
          <div key={p.id} className="mb-4 last:mb-0">
            <div className="text-xs font-semibold text-slate-200">{p.label} <span className="font-normal text-slate-500">· {p.hint}</span></div>
            <ul className="mt-1.5 space-y-1.5">{list.map((f) => {
              const rec = serviceOf(f);
              return (
                <li key={f.check_id} className="flex items-start gap-2">
                  <button role="checkbox" aria-checked={done.includes(f.check_id)} aria-label={`${f.finding}: ${done.includes(f.check_id) ? 'done' : 'not done'}`} onClick={() => toggle(f.check_id)}
                    className={`mt-0.5 h-5 w-5 rounded border flex items-center justify-center shrink-0 ${done.includes(f.check_id) ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-slate-600'}`}>{done.includes(f.check_id) && <Check className="h-3.5 w-3.5" />}</button>
                  <div className="min-w-0"><div className={`text-sm ${done.includes(f.check_id) ? 'text-slate-500 line-through' : 'text-slate-100'}`}>{f.fix ?? f.finding}</div>
                    <div className="text-[11px] text-slate-500">{f.finding}{rec ? ` · ${rec.service}` : ''}</div></div>
                </li>);
            })}</ul>
          </div>);
      })}
      {chart.advice.length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-800">
          <div className="text-xs font-semibold text-slate-200 mb-1.5">Services that cover this</div>
          <ul className="space-y-1 text-xs text-slate-300">{chart.advice.map((r) => <li key={r.service_key}><strong className="text-slate-100">{r.service}</strong> ({r.priority}): {r.summary}. {r.price_band ? `Your price band: ${r.price_band}.` : 'No price band set for this service.'}</li>)}</ul>
        </div>)}
    </Card>
  );
};

export const PitchAndPresence: FC<{ chart: Chart }> = ({ chart }) => {
  const k = chart.brief?.pitch_kit;
  const p = chart.presence;
  if (!k && !p && !(chart.brief?.unknown?.length)) return null;
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {k ? (
        <Card>
          <h2 className="text-sm font-semibold text-white mb-1">Pitch notes</h2>
          <p className="text-sm text-slate-200">{k.angle?.text ?? 'Nothing serious enough to lead with. Look for another angle.'}</p>
          <ul className="mt-2 space-y-1 text-xs text-slate-300 list-disc pl-4">{k.talking_points.map((t, i) => <li key={i}>{t.text}</li>)}</ul>
          <p className="text-[11px] text-slate-500 mt-2">Each point is backed by a measurement. {k.price_band ? `Price band: ${k.price_band}.` : k.price_band_note}</p>
          <details className="mt-2"><summary className="text-xs text-slate-400 cursor-pointer">Objections to prepare for (a generic list, not facts about this company)</summary>
            <ul className="mt-1 text-xs text-slate-400 list-disc pl-4">{k.objections_to_prepare_for.items.map((o) => <li key={o}>{o}</li>)}</ul></details>
        </Card>) : null}
      {p ? (
        <Card>
          <h2 className="text-sm font-semibold text-white mb-1">Web presence</h2>
          <div className="flex flex-wrap gap-2 mb-2"><Badge tone={p.verified ? 'good' : 'warn'}>{p.verified ? 'Verified' : 'Not verified'}</Badge><Badge>{p.classification.replace(/_/g, ' ')}</Badge><Badge>confidence {Math.round(p.confidence * 100)}%</Badge></div>
          <ul className="space-y-1 text-xs text-slate-300">{p.checks_performed.map((c, i) => <li key={i}><span className="text-slate-500">{c.check}:</span> {c.outcome}</li>)}</ul>
          {p.limitations?.map((l) => <p key={l} className="text-[11px] text-amber-300 mt-1">{l}</p>)}
        </Card>) : null}
      {chart.brief?.unknown && chart.brief.unknown.length > 0 && <Card><h2 className="text-sm font-semibold text-white mb-1">Not established</h2><p className="text-xs text-slate-300">{chart.brief.unknown.join(', ')}. Left blank rather than estimated.</p></Card>}
    </div>
  );
};

/** A site that answered but refuses automated reads. We say exactly what happened, what was still checked, and what a person can do. */
export const BlockedNotice: FC<{ chart: Chart }> = ({ chart }) => {
  const a = chart.audit;
  if (!a || a.status !== 'blocked') return null;
  const domain = chart.resolve.domain ?? a.domain;
  const b = a.blocked;
  return (
    <Card className="!border-amber-500/40">
      <h2 className="text-sm font-semibold text-white">{domain} refuses automated access</h2>
      <p className="text-sm text-slate-200 mt-1">It answered{b ? ` with ${b.reason}${b.server ? ` (${b.server})` : ''}` : ''}, so it is online. Many large sites use bot protection that turns away every automated reader, so its pages were <strong>not graded</strong>:
        grading the block page would report problems the real site does not have. We do not try to get around the protection.</p>
      <div className="grid gap-3 sm:grid-cols-2 mt-3 text-xs">
        <div><div className="font-medium text-emerald-300">Still checked</div><p className="text-slate-300 mt-1">{(a.checks_run ?? []).map((c) => c.replace(/_/g, ' ')).join(', ') || 'nothing'}: the certificate and the email DNS records, which do not need the site&apos;s pages.</p></div>
        <div><div className="font-medium text-amber-300">Not checked</div><p className="text-slate-300 mt-1">Speed, security headers, SEO, accessibility, AI readiness and exposure.</p></div>
      </div>
      <div className="flex flex-wrap gap-2 mt-3">
        <a className="text-xs text-indigo-300 hover:underline" href={`https://${domain}`} target="_blank" rel="noopener noreferrer">Open it in your own browser</a>
        <span className="text-slate-600">·</span>
        <a className="text-xs text-indigo-300 hover:underline" href={`https://pagespeed.web.dev/analysis?url=${encodeURIComponent(`https://${domain}`)}`} target="_blank" rel="noopener noreferrer">Run Google PageSpeed Insights on it</a>
      </div>
    </Card>
  );
};
