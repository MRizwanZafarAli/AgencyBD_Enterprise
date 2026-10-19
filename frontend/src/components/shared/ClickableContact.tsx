import { useState } from 'react';
import type { FC, ReactNode, MouseEvent } from 'react';
import { ExternalLink as ExternalLinkIcon, Phone, Copy, Check, Mail } from 'lucide-react';
import { normalizeUrl } from '../../lib/urls';

interface ExternalLinkProps {
  href?: string | null | undefined;
  children?: ReactNode;
  className?: string;
  showIcon?: boolean;
  iconClassName?: string;
  title?: string;
}

export const ExternalLink: FC<ExternalLinkProps> = ({
  href,
  children,
  className = '',
  showIcon = true,
  iconClassName = 'h-3 w-3',
  title
}) => {
  // If no href is provided, gracefully act as the Lucide ExternalLink icon
  if (!href) {
    return <ExternalLinkIcon className={className || iconClassName} />;
  }

  const targetUrl = normalizeUrl(href);
  const displayLabel = children || href.replace(/^https?:\/\/(www\.)?/i, '').replace(/\/$/, '');

  const handleClick = (e: MouseEvent) => {
    e.stopPropagation();
  };

  return (
    <a
      href={targetUrl}
      target="_blank"
      rel="noopener noreferrer"
      onClick={handleClick}
      title={title || `Open ${displayLabel} in new tab`}
      className={`inline-flex items-center gap-1 text-indigo-400 hover:text-indigo-300 hover:underline transition-colors ${className}`}
    >
      <span className="truncate">{displayLabel}</span>
      {showIcon && <ExternalLinkIcon className={`shrink-0 opacity-80 group-hover:opacity-100 ${iconClassName}`} />}
    </a>
  );
};

interface CopyablePhoneProps {
  phone: string | null | undefined;
  className?: string;
  showCallIcon?: boolean;
}

export const CopyablePhone: FC<CopyablePhoneProps> = ({
  phone,
  className = '',
  showCallIcon = true,
}) => {
  const [copied, setCopied] = useState(false);
  if (!phone) return null;

  const cleanPhone = phone.trim();
  const telHref = `tel:${cleanPhone.replace(/[^\d+]/g, '')}`;

  const handleCopy = (e: MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    navigator.clipboard.writeText(cleanPhone);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      onClick={handleCopy}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 text-slate-300 hover:text-white cursor-pointer transition select-all font-mono text-[11px] group ${className}`}
      title="Click to copy phone number to clipboard"
    >
      <Phone className="h-3 w-3 text-slate-400 group-hover:text-emerald-400 transition-colors shrink-0" />
      <span className="truncate">{cleanPhone}</span>
      <button
        type="button"
        onClick={handleCopy}
        className="text-slate-400 group-hover:text-white shrink-0 ml-0.5"
        title="Copy phone number"
      >
        {copied ? (
          <span className="text-emerald-400 flex items-center gap-0.5 text-[10px] font-sans font-medium">
            <Check className="h-3 w-3" />
            <span>Copied!</span>
          </span>
        ) : (
          <Copy className="h-2.5 w-2.5 opacity-60 group-hover:opacity-100" />
        )}
      </button>

      {showCallIcon && (
        <a
          href={telHref}
          onClick={(e) => e.stopPropagation()}
          className="text-emerald-400 hover:text-emerald-300 p-0.5 rounded hover:bg-emerald-950/40 shrink-0 ml-0.5"
          title={`Call ${cleanPhone}`}
        >
          <Phone className="h-2.5 w-2.5" />
        </a>
      )}
    </div>
  );
};

interface CopyableEmailProps {
  email: string | null | undefined;
  className?: string;
}

export const CopyableEmail: FC<CopyableEmailProps> = ({
  email,
  className = '',
}) => {
  const [copied, setCopied] = useState(false);
  if (!email) return null;

  const cleanEmail = email.trim();

  const handleCopy = (e: MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    navigator.clipboard.writeText(cleanEmail);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      onClick={handleCopy}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 text-slate-300 hover:text-white cursor-pointer transition select-all font-mono text-[11px] group ${className}`}
      title="Click to copy email address"
    >
      <Mail className="h-3 w-3 text-indigo-400 shrink-0" />
      <span className="truncate">{cleanEmail}</span>
      <button
        type="button"
        onClick={handleCopy}
        className="text-slate-400 group-hover:text-white shrink-0"
      >
        {copied ? (
          <span className="text-emerald-400 flex items-center gap-0.5 text-[10px] font-sans font-medium">
            <Check className="h-3 w-3" />
            <span>Copied!</span>
          </span>
        ) : (
          <Copy className="h-2.5 w-2.5 opacity-60 group-hover:opacity-100" />
        )}
      </button>

      <a
        href={`mailto:${cleanEmail}`}
        onClick={(e) => e.stopPropagation()}
        className="text-indigo-400 hover:text-indigo-300 p-0.5 rounded hover:bg-indigo-950/40 shrink-0 ml-0.5"
        title={`Compose email to ${cleanEmail}`}
      >
        <Mail className="h-2.5 w-2.5" />
      </a>
    </div>
  );
};
