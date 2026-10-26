import type { Surface } from '../../types';

export interface Command { id: string; label: string; hint: string; surface: Surface; section?: string }

export const COMMANDS: Command[] = [
  { id: 'today', label: 'Today', hint: 'inbox, approvals, run a search', surface: 'today' },
  { id: 'find-local', label: 'Find local businesses', hint: 'by type and city', surface: 'find' },
  { id: 'find-jobs', label: 'Find jobs and projects', hint: 'feeds and tenders', surface: 'find' },
  { id: 'clients', label: 'Clients', hint: 'pipeline and client pages', surface: 'clients' },
  { id: 'channels', label: 'Channels', hint: 'LinkedIn, Fiverr, Upwork: pipeline, routine, templates', surface: 'channels' },
  { id: 'tools', label: 'Tools', hint: 'website doctor, compare, report, email tools', surface: 'tools' },
  { id: 'settings-setup', label: 'Setup checklist', hint: 'what is missing', surface: 'settings', section: 'setup' },
  { id: 'settings-keys', label: 'Integrations and API keys', hint: 'Anthropic, Google Places, verifiers', surface: 'settings', section: 'keys' },
  { id: 'settings-services', label: 'Services and proof', hint: 'case studies, price bands', surface: 'settings', section: 'services' },
  { id: 'settings-sending', label: 'Sending and policy', hint: 'mailboxes, approvals, caps', surface: 'settings', section: 'sending' },
  { id: 'settings-dns', label: 'Domain DNS', hint: 'SPF, DKIM, DMARC', surface: 'settings', section: 'dns' },
  { id: 'settings-unsub', label: 'Unsubscribe list', hint: 'suppression', surface: 'settings', section: 'unsub' },
  { id: 'settings-team', label: 'Team and keys', hint: 'roles, API keys', surface: 'settings', section: 'team' },
  { id: 'settings-profile', label: 'Agency profile', hint: 'name, sender, legal footer, quoted result', surface: 'settings', section: 'profile' },
  { id: 'settings-security', label: 'Security and session', hint: 'role, sign out, key hygiene', surface: 'settings', section: 'security' },
  { id: 'settings-data', label: 'Data and export', hint: 'CSV export, backups', surface: 'settings', section: 'data' },
  { id: 'settings-prefs', label: 'Appearance and shortcuts', hint: 'light or dark, keyboard', surface: 'settings', section: 'prefs' },
  { id: 'settings-tour', label: 'How it works', hint: 'short tour', surface: 'settings', section: 'tour' },
];

