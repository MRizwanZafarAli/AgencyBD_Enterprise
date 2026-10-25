// Authenticated fetch wrapper. The API key lives in sessionStorage only (cleared when the tab closes),
// never in localStorage, URLs or logs.

const STORAGE_KEY = 'agencybd.apiKey';
export const UNAUTHORIZED_EVENT = 'agencybd:unauthorized';

export interface Me {
  user_id: string;
  org_id: string;
  role: string;
  permissions: string[];
  auth_method: string;
}

export const getApiKey = (): string | null => {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
};

export const setApiKey = (key: string): void => {
  try {
    sessionStorage.setItem(STORAGE_KEY, key);
  } catch {
    /* storage unavailable (private mode): key is kept for this page load only via callers */
  }
};

export const clearApiKey = (): void => {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
};

export async function apiFetch(input: string, init: RequestInit = {}, keyOverride?: string): Promise<Response> {
  const headers = new Headers(init.headers);
  const key = keyOverride ?? getApiKey();
  if (key) headers.set('X-API-Key', key);
  const res = await fetch(input, { ...init, headers });
  if (res.status === 401 && !keyOverride) {
    clearApiKey();
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }
  return res;
}

/** Validates a key against the API and returns the identity it maps to, or null if rejected. */
export async function verifyKey(key: string): Promise<Me | null> {
  const res = await apiFetch('/api/auth/me', {}, key);
  return res.ok ? ((await res.json()) as Me) : null;
}

/** Turns an API failure into a message a person can act on. Never hides "not configured" behind a generic error. */
export function apiErrorMessage(status: number, body: any): string {
  if (body?.status === 'not_configured') return `Not configured: ${body.detail}`;
  if (body?.status === 'portfolio_empty') return `${body.detail}`;
  if (body?.status === 'unreachable') return `Site unreachable: ${body.detail}`;
  if (status === 401) return 'Your session expired. Sign in again.';
  if (status === 403) return 'You do not have permission for this action.';
  if (typeof body?.detail === 'string') return body.detail;
  return `Request failed (HTTP ${status}).`;
}

/** Opens an authenticated file (report HTML/PDF) in a new tab: plain links cannot carry the API key header. */
export async function openProtected(path: string): Promise<void> {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error(apiErrorMessage(res.status, await res.json().catch(() => ({}))));
  const url = URL.createObjectURL(await res.blob());
  window.open(url, '_blank', 'noopener');
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
