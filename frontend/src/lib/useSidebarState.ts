import { useCallback, useState } from 'react';

const KEY = 'agencybd.sidebarCollapsed';

/** Sidebar collapsed/expanded, remembered in this browser (storage can be blocked, so every access is guarded). */
export function useSidebarState(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(KEY) === '1'; } catch { return false; }
  });
  const toggle = useCallback(() => {
    setCollapsed((c) => {
      try { localStorage.setItem(KEY, c ? '0' : '1'); } catch { /* ignore */ }
      return !c;
    });
  }, []);
  return [collapsed, toggle];
}
