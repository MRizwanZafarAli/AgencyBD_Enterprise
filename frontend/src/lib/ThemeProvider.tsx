import { useEffect, useState } from 'react';
import type { FC, ReactNode } from 'react';
import { ThemeContext, type Theme } from './theme-context';

export type AccentPreset = 'emerald' | 'indigo' | 'cobalt' | 'custom';

const PRESET_COLORS: Record<Exclude<AccentPreset, 'custom'>, { light: string; dark: string; rgb: string }> = {
  emerald: { light: '#0f766e', dark: '#2dd4bf', rgb: '15, 118, 110' },
  indigo: { light: '#4338ca', dark: '#818cf8', rgb: '67, 56, 202' },
  cobalt: { light: '#1d4ed8', dark: '#60a5fa', rgb: '29, 78, 216' },
};

function hexToRgb(hex: string): string {
  const clean = hex.replace('#', '');
  if (!/^[0-9a-fA-F]{6}$/.test(clean)) return '15, 118, 110';
  return `${parseInt(clean.slice(0, 2), 16)}, ${parseInt(clean.slice(2, 4), 16)}, ${parseInt(clean.slice(4, 6), 16)}`;
}

export function applyWorkspaceAccent(preset: AccentPreset, customHex: string, theme: Theme) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (preset === 'custom' && /^#[0-9a-fA-F]{6}$/.test(customHex)) {
    root.style.setProperty('--color-indigo-600', customHex);
    root.style.setProperty('--color-indigo-500', customHex);
    root.style.setProperty('--color-indigo-400', customHex);
    root.style.setProperty('--color-indigo-300', customHex);
    root.style.setProperty('--focus', customHex);
    root.style.setProperty('--link', customHex);
    root.style.setProperty('--accent-rgb', hexToRgb(customHex));
    return;
  }
  const p = PRESET_COLORS[preset === 'custom' ? 'emerald' : preset];
  const color = theme === 'light' ? p.light : p.dark;
  root.style.setProperty('--color-indigo-600', color);
  root.style.setProperty('--color-indigo-500', color);
  root.style.setProperty('--color-indigo-400', color);
  root.style.setProperty('--color-indigo-300', color);
  root.style.setProperty('--focus', color);
  root.style.setProperty('--link', color);
  root.style.setProperty('--accent-rgb', p.rgb);
}

export const ThemeProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === 'undefined') return 'dark';
    const stored = localStorage.getItem('agencybd_theme');
    if (stored === 'light' || stored === 'dark') return stored;
    return 'light';
  });

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);
    if (theme === 'light') {
      root.classList.remove('dark');
      root.classList.add('light');
    } else {
      root.classList.remove('light');
      root.classList.add('dark');
    }
    localStorage.setItem('agencybd_theme', theme);
    const preset = (localStorage.getItem('agencybd_accent_preset') as AccentPreset) || 'emerald';
    const hex = localStorage.getItem('agencybd_brand_hex') || '#0f766e';
    applyWorkspaceAccent(preset, hex, theme);
  }, [theme]);

  const setTheme = (t: Theme) => setThemeState(t);
  const toggleTheme = () => setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'));

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
