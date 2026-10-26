import { useState } from 'react';
import type { FC } from 'react';
import { Check, Copy, Download } from 'lucide-react';
import { Badge, Button, Card, Skeletons, Stat } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { useApi } from '../../lib/hooks';

interface Summary { counts: Record<string, number>; exports: string[]; installation?: { database_bytes: number; backups: number; last_backup_at: string | null; backup_command: string } }

const COUNT_LABEL: Record<string, string> = { clients: 'Clients', contacts: 'Contacts', audits: 'Site audits', notes_and_tasks: 'Notes and tasks', channel_entries: 'Channel entries', emails_sent: 'Emails sent' };
const EXPORT: Record<string, { label: string; hint: string }> = {
  clients: { label: 'Clients', hint: 'Company, website, stage, source' }, notes: { label: 'Notes and follow-ups', hint: 'Everything written on client pages' },
  channels: { label: 'Channel logs', hint: 'Applications, messages, activity from LinkedIn and freelance sites' }, audits: { label: 'Audit history', hint: 'Website, score, status, date' },
};
const size = (b: number) => (b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);

export const DataPanel: FC = () => {
  const data = useApi<Summary>('/api/workspace/data/summary');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const d = data.data;

  const download = async (kind: string) => {
    setError('');
    const res = await apiFetch(`/api/workspace/data/export/${kind}`);
    if (!res.ok) { setError(apiErrorMessage(res.status, await res.json().catch(() => ({})))); return; }
    const name = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') ?? '')?.[1] ?? `agencybd-${kind}.csv`;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(await res.blob());
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const copy = async (text: string) => { try { await navigator.clipboard.writeText(text); setCopied(true); window.setTimeout(() => setCopied(false), 1500); } catch { /* the command is visible to copy by hand */ } };

  return (
    <div className="space-y-5">
      <ErrorBanner message={error || data.error} />
      {data.loading && !d ? <Skeletons rows={3} /> : d && (
        <>
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-3">{Object.entries(d.counts).map(([k, v]) => <Stat key={k} label={COUNT_LABEL[k] ?? k} value={v.toLocaleString()} />)}</div>
          <Card>
            <h2 className="text-sm font-semibold text-white">Export your records</h2>
            <p className="text-xs text-slate-400 mt-1 mb-3">CSV files of this workspace only. They open in Excel and Google Sheets, and cells that could run as formulas are neutralised first. No keys or secrets are ever included.</p>
            <ul className="divide-y divide-slate-800">{d.exports.map((k) => (
              <li key={k} className="py-2.5 flex items-center gap-3"><div className="mr-auto min-w-0"><div className="text-sm text-slate-100">{EXPORT[k]?.label ?? k}</div><div className="text-xs text-slate-500">{EXPORT[k]?.hint}</div></div>
                <Button small onClick={() => download(k)} aria-label={`Download ${EXPORT[k]?.label ?? k} as CSV`}><Download className="h-3.5 w-3.5" />CSV</Button></li>))}</ul>
          </Card>
          {d.installation && (
            <Card>
              <div className="flex flex-wrap items-center gap-2 mb-1"><h2 className="text-sm font-semibold text-white">Backups</h2>
                <Badge tone={d.installation.backups ? 'good' : 'warn'}>{d.installation.backups ? `${d.installation.backups} on disk` : 'No backup yet'}</Badge></div>
              <p className="text-xs text-slate-400">Database size {size(d.installation.database_bytes)}. {d.installation.last_backup_at ? `Last backup ${new Date(d.installation.last_backup_at).toLocaleString()}.` : 'Nothing has been backed up. Do it before an upgrade, and on a schedule.'}</p>
              <div className="mt-3 flex items-center gap-2 rounded-xl border border-slate-800 px-3 py-2"><code className="font-mono text-xs text-slate-200 mr-auto">{d.installation.backup_command}</code>
                <button aria-label="Copy backup command" onClick={() => copy(d.installation!.backup_command)} className="text-slate-400 hover:text-white">{copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}</button></div>
              <p className="text-[11px] text-slate-500 mt-2">Restore with scripts/restore_db.py. See docs/OPERATIONS.md.</p>
            </Card>)}
        </>)}
    </div>
  );
};
