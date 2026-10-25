import type { FC, ReactNode } from 'react';
import { Card } from '../ui';

export type Run = (fn: () => Promise<unknown>) => Promise<void>;
export type Post = (type: string, data: Record<string, unknown>) => Promise<unknown>;

export const Section: FC<{ title: string; hint?: string; children: ReactNode; aside?: ReactNode }> = ({ title, hint, children, aside }) => (
  <Card>
    <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
      <div><h2 className="text-sm font-semibold text-white">{title}</h2>{hint && <p className="text-xs text-slate-400 mt-0.5 max-w-xl">{hint}</p>}</div>{aside}
    </div>
    {children}
  </Card>
);

