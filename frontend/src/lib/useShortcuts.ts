import { useEffect } from 'react';
import type { Surface } from '../types';

const CHORDS: Record<string, Surface> = { t: 'today', f: 'find', c: 'clients', h: 'channels', o: 'tools', s: 'settings' };
export const SHORTCUTS: Array<{ keys: string; label: string }> = [
  { keys: '⌘K / Ctrl K', label: 'Open the command palette' }, { keys: 'G then T', label: 'Go to Today' }, { keys: 'G then F', label: 'Go to Find' },
  { keys: 'G then C', label: 'Go to Clients' }, { keys: 'G then H', label: 'Go to Channels' }, { keys: 'G then O', label: 'Go to Tools' }, { keys: 'G then S', label: 'Go to Settings' },
  { keys: '[', label: 'Collapse or expand the sidebar' }, { keys: '?', label: 'Show this help' }, { keys: 'Esc', label: 'Close a drawer, palette or dialog' },
];

const typing = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable);
};

/** Linear-style keyboard navigation. Ignored while typing and when a modifier key is held. */
export function useShortcuts(opts: { onNavigate: (s: Surface) => void; onToggleSidebar: () => void; onHelp: () => void; enabled: boolean }): void {
  const { onNavigate, onToggleSidebar, onHelp, enabled } = opts;
  useEffect(() => {
    if (!enabled) return;
    let pending = false;
    let timer: number | undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || typing(e.target)) return;
      const k = e.key.toLowerCase();
      if (pending) {
        pending = false;
        window.clearTimeout(timer);
        if (CHORDS[k]) { e.preventDefault(); onNavigate(CHORDS[k]); }
        return;
      }
      if (k === 'g') { pending = true; timer = window.setTimeout(() => { pending = false; }, 1200); }
      else if (k === '[') { e.preventDefault(); onToggleSidebar(); }
      else if (e.key === '?') { e.preventDefault(); onHelp(); }
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); window.clearTimeout(timer); };
  }, [enabled, onNavigate, onToggleSidebar, onHelp]);
}
