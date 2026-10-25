import { useCallback, useEffect, useState } from 'react';
import { apiFetch, apiErrorMessage } from './api';

export interface ApiState<T> { data: T | null; error: string; loading: boolean; reload: () => void }

/** GET helper: loading and error are explicit, and a failed request never leaves stale or invented data on screen. */
export function useApi<T>(path: string | null): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(path !== null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let active = true;
    apiFetch(path)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!active) return;
        if (res.ok) { setData(body as T); setError(''); } else { setData(null); setError(apiErrorMessage(res.status, body)); }
      })
      .catch(() => active && (setData(null), setError('Could not reach the API.')))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [path, tick]);

  const reload = useCallback(() => { setLoading(true); setTick((t) => t + 1); }, []);
  return { data, error, loading, reload };
}

/** POST/DELETE helper returning parsed JSON or throwing a message a person can act on. */
export async function send<T = any>(path: string, method: 'POST' | 'PUT' | 'DELETE' = 'POST', body?: unknown): Promise<T> {
  const res = await apiFetch(path, { method, headers: body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorMessage(res.status, data));
  return data as T;
}
