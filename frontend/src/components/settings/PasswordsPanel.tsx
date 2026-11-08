import { useState } from 'react';
import type { FC, FormEvent } from 'react';
import { Check, Copy, Wand2 } from 'lucide-react';
import { Badge, Button, Card, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { apiFetch, apiErrorMessage, setToken } from '../../lib/api';
import { useApi } from '../../lib/hooks';

interface TierRow { role: string; label: string; is_set: boolean; updated_at: number | null; updated_by: string | null }
interface Data { tiers: TierRow[]; min_length: number; can_set_all: boolean }

const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789-_';
const strong = () => Array.from(crypto.getRandomValues(new Uint32Array(20)), (n) => ALPHABET[n % ALPHABET.length]).join('');
const when = (t: number | null) => (t ? new Date(t * 1000).toLocaleString() : 'never');

/** Each tier has its own secret password. Only a hash is stored, so a password can be replaced but never shown again. */
export const PasswordsPanel: FC<{ myRole: string }> = ({ myRole }) => {
  const data = useApi<Data>('/api/auth/passwords');
  const [open, setOpen] = useState<string | null>(null);
  const [f, setF] = useState({ current: '', next: '', again: '' });
  const [error, setError] = useState('');
  const [done, setDone] = useState('');
  const [shown, setShown] = useState('');
  const [copied, setCopied] = useState(false);

  const start = (role: string) => { setOpen(open === role ? null : role); setF({ current: '', next: '', again: '' }); setError(''); setDone(''); setShown(''); };
  const make = () => { const pw = strong(); setF({ ...f, next: pw, again: pw }); setShown(pw); setCopied(false); };
  const copy = async () => { try { await navigator.clipboard.writeText(shown); setCopied(true); window.setTimeout(() => setCopied(false), 1800); } catch { setError('Copy was blocked. Select the password and copy it by hand.'); } };

  const submit = async (e: FormEvent, role: string) => {
    e.preventDefault();
    setError('');
    if (f.next !== f.again) { setError('The two new passwords do not match.'); return; }
    const own = role === myRole;
    const res = await apiFetch('/api/auth/password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role, new_password: f.next, ...(own ? { current_password: f.current } : {}) }) });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) { setError(apiErrorMessage(res.status, body)); return; }
    if (body.token) setToken(body.token);                       // keeps this person signed in after changing their own password
    setDone(`Password for ${data.data?.tiers.find((t) => t.role === role)?.label} changed. ${body.note}`);
    setOpen(null); setF({ current: '', next: '', again: '' }); setShown(''); data.reload();
  };

  const d = data.data;
  return (
    <Card>
      <h2 className="text-sm font-semibold text-white">Tier passwords</h2>
      <p className="text-xs text-slate-400 mt-1 mb-4">
        Each tier signs in with its own secret password, and no two tiers may share one. Passwords are stored only as a salted hash, so they can be replaced but never shown.
        Changing a password signs out everyone in that tier. Use at least {d?.min_length ?? 12} characters.
      </p>
      <ErrorBanner message={error || data.error} />
      {done && <p role="status" className="text-xs text-emerald-300 mb-3">{done}</p>}
      <ul className="divide-y divide-slate-800">
        {(d?.tiers ?? []).map((t) => (
          <li key={t.role} className="py-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-white">{t.label}</span>
              <Badge tone={t.is_set ? 'good' : 'warn'}>{t.is_set ? 'Password set' : 'No password yet'}</Badge>
              {t.role === myRole && <Badge tone="accent">You</Badge>}
              <span className="text-xs text-slate-500">Changed {when(t.updated_at)}</span>
              <Button small className="ml-auto" onClick={() => start(t.role)} aria-label={`${t.is_set ? 'Change' : 'Set'} password for ${t.label}`}>{t.is_set ? 'Change password' : 'Set password'}</Button>
            </div>
            {open === t.role && (
              <form className="mt-3 grid gap-2 sm:grid-cols-2 p-3 rounded-2xl border border-slate-800" onSubmit={(e) => submit(e, t.role)} autoComplete="off">
                {t.role === myRole && <label className="text-xs text-slate-400 sm:col-span-2">Current password<input className={`${field} mt-1`} type="password" autoComplete="current-password" required value={f.current} onChange={(e) => setF({ ...f, current: e.target.value })} /></label>}
                <label className="text-xs text-slate-400">New password<input className={`${field} mt-1`} type={shown ? 'text' : 'password'} autoComplete="new-password" required minLength={d?.min_length} value={f.next} onChange={(e) => { setF({ ...f, next: e.target.value }); setShown(''); }} /></label>
                <label className="text-xs text-slate-400">Type it again<input className={`${field} mt-1`} type={shown ? 'text' : 'password'} autoComplete="new-password" required value={f.again} onChange={(e) => setF({ ...f, again: e.target.value })} /></label>
                <div className="sm:col-span-2 flex flex-wrap items-center gap-2">
                  <Button small type="button" onClick={make}><Wand2 className="h-3.5 w-3.5" />Make a strong one</Button>
                  {shown && <><code className="font-mono text-xs text-white bg-slate-950 rounded-xl px-3 py-1.5 select-all">{shown}</code>
                    <Button small type="button" variant="ghost" onClick={copy} aria-label="Copy the new password">{copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}</Button>
                    <span className="text-xs text-amber-300">Store it in a password manager before you save. It cannot be shown again.</span></>}
                  <Button small variant="primary" type="submit" className="ml-auto">Save password</Button>
                </div>
              </form>)}
          </li>))}
      </ul>
      {d && !d.can_set_all && <p className="text-xs text-slate-500 mt-3">Only the super admin can change the other tiers.</p>}
    </Card>
  );
};
