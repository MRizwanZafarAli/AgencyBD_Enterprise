import { useState } from 'react';
import type { FC } from 'react';
import { ExternalLink, PanelRight } from 'lucide-react';
import { Button, Drawer, Skeletons, field } from '../ui';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useApi } from '../../lib/hooks';
import { openSide } from './browser';
import type { Catalog } from './types';

/** Quick launcher for every site you work in. Opens each page in a window docked beside this app. */
export const BrowserDock: FC<{ open: boolean; onClose: () => void; onChannel: (platformId: string) => void }> = ({ open, onClose, onChannel }) => {
  const catalog = useApi<Catalog>(open ? '/api/channels/platforms' : null);
  const [dock, setDock] = useState(true);
  const [url, setUrl] = useState('');
  const [msg, setMsg] = useState('');
  const go = (target: string) => { setMsg(openSide(target, dock) ? '' : 'Your browser blocked the window. Allow pop-ups for this page and try again.'); };

  return (
    <Drawer open={open} title="Browser dock" onClose={onClose}>
      <p className="text-xs text-slate-400 mb-3">Open a site beside this app. Log in there yourself, as you normally do. Sites do not allow being embedded, so each opens in its own window. This app never sees your login and never controls the page.</p>
      <label className="flex items-center gap-2 text-xs text-slate-300 mb-3"><input type="checkbox" checked={dock} onChange={(e) => setDock(e.target.checked)} />Dock to the right edge and reuse one window</label>
      {msg && <p role="alert" className="text-xs text-amber-300 mb-2">{msg}</p>}
      <form className="flex gap-2 mb-4" onSubmit={(e) => { e.preventDefault(); if (url.trim()) go(/^https?:\/\//i.test(url.trim()) ? url.trim() : `https://${url.trim()}`); }}>
        <input className={field} aria-label="Address to open" placeholder="Any address, e.g. upwork.com" value={url} onChange={(e) => setUrl(e.target.value)} />
        <Button small type="submit"><PanelRight className="h-3.5 w-3.5" />Open</Button>
      </form>
      <ErrorBanner message={catalog.error} />
      {catalog.loading && !catalog.data ? <Skeletons rows={4} /> : (
        <ul className="space-y-4">
          {catalog.data?.platforms.filter((p) => p.home).map((p) => (
            <li key={p.id}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-sm font-medium text-slate-100 flex-1">{p.label}</span>
                <button onClick={() => { onChannel(p.id); onClose(); }} className="text-xs text-indigo-400 hover:underline">Control centre</button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Button small onClick={() => go(p.home!)}><ExternalLink className="h-3 w-3" />Home</Button>
                {p.pages.map((pg) => <Button key={pg.url} small onClick={() => go(pg.url)}>{pg.label}</Button>)}
              </div>
            </li>))}
        </ul>)}
    </Drawer>
  );
};
