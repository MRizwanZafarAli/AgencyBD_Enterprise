import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { Send, RefreshCw } from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from './ErrorBanner';

interface Digest { opportunity_count: number; lead_count: number; text: string }

/** Today's best matches as they would be posted to Slack. Preview first, then send. */
export const DigestPanel: FC = () => {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const res = await apiFetch('/api/digest?limit=10');
    if (res.ok) setDigest(await res.json());
  };

  useEffect(() => {
    let active = true;
    apiFetch('/api/digest?limit=10').then(async (r) => {
      if (active && r.ok) setDigest(await r.json());
    });
    return () => {
      active = false;
    };
  }, []);

  const send = async () => {
    setBusy(true);
    setError('');
    setNote('');
    const res = await apiFetch('/api/digest/send', { method: 'POST' });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) setError(apiErrorMessage(res.status, body));
    else setNote(body.delivered ? 'Posted to Slack.' : 'Slack did not accept the post. Check the webhook URL.');
    setBusy(false);
  };

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-white">Daily digest</h2>
        <div className="flex gap-2">
          <button onClick={load} className="flex items-center gap-1 text-xs text-slate-300 border border-slate-700 hover:border-slate-500 rounded-lg px-2.5 py-1.5">
            <RefreshCw className="h-3 w-3" />Refresh
          </button>
          <button onClick={send} disabled={busy} className="flex items-center gap-1 text-xs text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg px-2.5 py-1.5">
            <Send className="h-3 w-3" />Send to Slack
          </button>
        </div>
      </div>
      <ErrorBanner message={error} />
      {note && <div className="text-xs text-emerald-300">{note}</div>}
      {digest ? (
        <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">{digest.text}</pre>
      ) : (
        <div className="skeleton h-20" />
      )}
    </section>
  );
};
