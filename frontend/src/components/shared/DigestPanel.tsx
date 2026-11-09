import { useEffect, useState } from 'react';
import type { FC } from 'react';
import { Send, RefreshCw, Sparkles, Inbox } from 'lucide-react';
import { apiFetch, apiErrorMessage } from '../../lib/api';
import { ErrorBanner } from './ErrorBanner';

interface Digest { opportunity_count: number; lead_count: number; text: string }

interface DigestPanelProps {
  onRefresh?: () => void;
}

/** Today's best matches as they would be posted to Slack. Preview first, then send. */
export const DigestPanel: FC<DigestPanelProps> = ({ onRefresh }) => {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/digest?limit=10');
      if (res.ok) {
        const data = await res.json();
        setDigest(data);
      } else {
        setDigest(null);
      }
      if (onRefresh) onRefresh();
    } catch {
      setDigest(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    apiFetch('/api/digest?limit=10')
      .then(async (r) => {
        if (!active) return;
        if (r.ok) setDigest(await r.json());
        else setDigest(null);
      })
      .catch(() => active && setDigest(null))
      .finally(() => active && setLoading(false));
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
    else setNote(body.delivered ? 'Posted to Slack successfully.' : 'Slack webhook not configured in .env or rejected.');
    setBusy(false);
  };

  return (
    <section className="bento-tile p-5 sm:p-6 space-y-3.5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-indigo-400" />
          <h2 className="text-sm font-semibold text-white">Daily Opportunity & Sourcing Digest</h2>
        </div>
        <div className="flex gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1 text-xs text-slate-300 border border-slate-700 hover:border-slate-500 rounded-lg px-2.5 py-1.5 transition"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={send}
            disabled={busy || !digest?.text}
            className="flex items-center gap-1 text-xs text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg px-2.5 py-1.5 transition shadow-sm"
          >
            <Send className="h-3 w-3" />
            <span>Post to Slack</span>
          </button>
        </div>
      </div>
      <ErrorBanner message={error} />
      {note && (
        <div className="text-xs text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-2.5">
          {note}
        </div>
      )}

      {loading ? (
        <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 text-xs text-slate-400 flex items-center justify-center gap-2">
          <RefreshCw className="h-3.5 w-3.5 animate-spin text-indigo-400" />
          <span>Synthesizing today's top opportunities...</span>
        </div>
      ) : digest && digest.text && digest.text.trim().length > 0 ? (
        <pre tabIndex={0} aria-label="Digest text (scrollable)" className="text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed bg-slate-900/50 p-3.5 rounded-xl border border-slate-800/60 overflow-x-auto max-h-60">
          {digest.text}
        </pre>
      ) : (
        <div className="p-6 rounded-xl bg-slate-900/30 border border-slate-800/60 text-center space-y-2">
          <div className="flex justify-center">
            <Inbox className="h-7 w-7 text-slate-500" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-200">No Outreach Digests Queued</h4>
            <p className="text-[11px] text-slate-400 mt-0.5 max-w-md mx-auto">
              Your radar currently has no unreviewed opportunities. Connect Upwork, GitHub, or RSS feeds in Opportunity Radar to prioritize live tenders.
            </p>
          </div>
        </div>
      )}
    </section>
  );
};
