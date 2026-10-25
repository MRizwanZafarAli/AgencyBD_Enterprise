/** Opens a site in a separate window docked to the right edge, like a side panel. Sites do not allow being embedded, and your normal
 *  browser session (already signed in) is reused. This app never sees credentials and never drives the page. */
export const SIDE_WINDOW = 'agencybd-side-browser';

export function openSide(url: string, dock: boolean = true): boolean {
  let u: URL;
  try { u = new URL(url); } catch { return false; }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') return false;
  const s = window.screen as Screen & { availLeft?: number; availTop?: number };
  const width = Math.max(420, Math.min(760, Math.round(s.availWidth * 0.42)));
  const height = s.availHeight;
  const left = (s.availLeft ?? 0) + s.availWidth - width;
  const features = dock ? `popup=yes,width=${width},height=${height},left=${left},top=${s.availTop ?? 0},noopener,noreferrer` : 'noopener,noreferrer';
  return window.open(u.toString(), dock ? SIDE_WINDOW : '_blank', features) !== null;
}
