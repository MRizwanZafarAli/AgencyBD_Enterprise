import type { FC } from 'react';

/** Real errors, shown plainly. The UI never substitutes made-up results when a request fails. */
export const ErrorBanner: FC<{ message: string }> = ({ message }) =>
  message ? (
    <div role="alert" className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 text-xs text-amber-200">
      {message}
    </div>
  ) : null;
