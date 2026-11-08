// Authenticated fetch wrapper. The session token (issued after a password sign-in) lives in sessionStorage only (cleared when the tab closes),
// never in localStorage, URLs or logs. The password itself is never stored anywhere in the browser.

const STORAGE_KEY = 'agencybd.session';
export const UNAUTHORIZED_EVENT = 'agencybd:unauthorized';

export interface Me {
  user_id: string;
  org_id: string;
  role: string;
  permissions: string[];
  auth_method: string;
}

export interface Tier { role: string; label: string; available: boolean }

export const getToken = (): string | null => {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
};

export const setToken = (token: string): void => {
  try {
    sessionStorage.setItem(STORAGE_KEY, token);
  } catch {
    /* storage unavailable (private mode): the session lasts for this page load only */
  }
};

export const clearToken = (): void => {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
};

export async function apiFetch(input: string, init: RequestInit = {}, tokenOverride?: string): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = tokenOverride ?? getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(input, { ...init, headers });
  if (res.status === 401 && !tokenOverride && token) {
    clearToken();
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }
  return res;
}

/** Checks a stored session against the API and returns who it belongs to, or null if it ended. */
export async function verifySession(token: string): Promise<Me | null> {
  const res = await apiFetch('/api/auth/me', {}, token);
  return res.ok ? ((await res.json()) as Me) : null;
}

/** Which tiers can sign in here (names only). */
export async function loadTiers(): Promise<{ tiers: Tier[]; any_set: boolean } | null> {
  try {
    const res = await fetch('/api/auth/tiers');
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/** Signs in with a tier and its password. Resolves to the identity, or throws a message a person can act on. */
export async function login(role: string, password: string): Promise<Me> {
  let res: Response;
  try {
    res = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role, password }) });
  } catch {
    throw new Error('Could not reach the server. Is the backend running?');
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : `Sign-in failed (HTTP ${res.status}).`);
  setToken(body.token);
  return body.me as Me;
}

/** Turns an API failure into a message a person can act on. Never hides "not configured" behind a generic error. */
export function apiErrorMessage(status: number, body: any): string {
  if (body?.status === 'not_configured') return `Not configured: ${body.detail}`;
  if (body?.status === 'portfolio_empty') return `${body.detail}`;
  if (body?.status === 'unreachable') return `Site unreachable: ${body.detail}`;
  if (body?.status === 'llm_error') return `${body.detail}`;
  if (status === 401) return 'Your session expired. Sign in again.';
  if (status === 403) return 'You do not have permission for this action.';
  if (typeof body?.detail === 'string') return body.detail;
  return `Request failed (HTTP ${status}).`;
}

/** Opens an authenticated file (report HTML/PDF) in a new tab: plain links cannot carry the session header. */
export async function openProtected(path: string): Promise<void> {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error(apiErrorMessage(res.status, await res.json().catch(() => ({}))));
  const url = URL.createObjectURL(await res.blob());
  window.open(url, '_blank', 'noopener');
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
