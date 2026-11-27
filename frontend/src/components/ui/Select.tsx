import { useEffect, useId, useRef, useState } from 'react';
import type { FC, KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown } from 'lucide-react';

export interface SelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

export const Select: FC<{
  value: string | number;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  small?: boolean;
  'aria-label'?: string;
  title?: string;
}> = ({
  value,
  onChange,
  options,
  placeholder = 'Choose…',
  disabled = false,
  className = '',
  small = false,
  'aria-label': ariaLabel,
  title,
}) => {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; width: number; up: boolean }>({ top: 0, left: 0, width: 180, up: false });
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const current = options.find((o) => String(o.value) === String(value));

  const updatePos = () => {
    const el = btnRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const spaceBelow = window.innerHeight - r.bottom;
    const estHeight = Math.min(260, options.length * 36 + 16);
    const up = spaceBelow < estHeight && r.top > estHeight;
    setPos({
      top: up ? r.top - 6 : r.bottom + 6,
      left: Math.min(r.left, window.innerWidth - Math.max(r.width, 180) - 12),
      width: Math.max(r.width, 150),
      up,
    });
  };

  useEffect(() => {
    if (!open) return;
    updatePos();
    const onDocDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (btnRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onScrollOrResize = () => updatePos();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        btnRef.current?.focus();
      }
    };
    document.addEventListener('mousedown', onDocDown);
    window.addEventListener('scroll', onScrollOrResize, true);
    window.addEventListener('resize', onScrollOrResize);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocDown);
      window.removeEventListener('scroll', onScrollOrResize, true);
      window.removeEventListener('resize', onScrollOrResize);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, options.length]);

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (!open) {
        updatePos();
        setOpen(true);
      } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const enabled = options.filter((o) => !o.disabled);
        if (enabled.length === 0) return;
        const idx = enabled.findIndex((o) => String(o.value) === String(value));
        const nextIdx = e.key === 'ArrowDown' ? (idx + 1) % enabled.length : (idx - 1 + enabled.length) % enabled.length;
        onChange(String(enabled[nextIdx].value));
      }
    }
  };

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={ariaLabel}
        title={title}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        onClick={() => {
          if (disabled) return;
          if (!open) updatePos();
          setOpen((v) => !v);
        }}
        className={`inline-flex items-center justify-between gap-2 text-left bg-slate-900 border border-slate-800 text-slate-100 hover:border-indigo-500/50 focus:outline-none focus:border-indigo-500 transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
          small ? 'rounded-lg px-2.5 py-1.5 text-xs min-h-[30px]' : 'w-full rounded-xl px-3.5 py-2 text-sm min-h-[38px]'
        } ${className}`}
      >
        <span className={`truncate ${current ? 'text-slate-100' : 'text-slate-500'}`}>
          {current ? current.label : placeholder}
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-indigo-400 transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {open &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            ref={menuRef}
            id={listId}
            role="listbox"
            style={{
              position: 'fixed',
              top: pos.top,
              left: Math.max(8, pos.left),
              minWidth: pos.width,
              maxWidth: 'calc(100vw - 16px)',
              transform: pos.up ? 'translateY(-100%)' : undefined,
              zIndex: 140,
            }}
            className="max-h-64 overflow-y-auto rounded-2xl border border-slate-700 bg-slate-900/95 backdrop-blur-xl shadow-2xl p-1.5 space-y-0.5 animate-scale-in"
          >
            {options.map((o) => {
              const selected = String(o.value) === String(value);
              return (
                <button
                  key={String(o.value)}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  disabled={o.disabled}
                  onClick={() => {
                    if (o.disabled) return;
                    onChange(String(o.value));
                    setOpen(false);
                    btnRef.current?.focus();
                  }}
                  className={`w-full flex items-center justify-between gap-2 text-left rounded-xl px-3 py-1.5 text-xs transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
                    selected
                      ? 'bg-indigo-500/15 text-indigo-400 font-medium'
                      : 'text-slate-200 hover:bg-slate-800/80 hover:text-white'
                  }`}
                >
                  <span className="truncate">{o.label}</span>
                  {selected && <Check className="h-3.5 w-3.5 shrink-0 text-indigo-400" aria-hidden="true" />}
                </button>
              );
            })}
          </div>,
          document.body,
        )}
    </>
  );
};
