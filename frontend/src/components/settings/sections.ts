import type { LucideIcon } from 'lucide-react';
import { BookOpen, Building2, Code2, Database, Globe, KeyRound, ListChecks, Mail, Palette, ShieldCheck, Users, BadgeCheck, MailX, Zap } from 'lucide-react';

export interface SettingsSection { id: string; label: string; group: string; hint: string; keywords: string; icon: LucideIcon }

/** Order is the order on the page. Ids are stable: the command palette, the Today focus list and the tests link to them. */
export const SETTINGS_SECTIONS: SettingsSection[] = [
  { id: 'setup', label: 'Setup', group: 'Workspace', hint: 'What is left to do', keywords: 'checklist progress start onboarding missing required', icon: ListChecks },
  { id: 'profile', label: 'Agency profile', group: 'Workspace', hint: 'Name, sender, legal footer, proof', keywords: 'identity sender name address footer legal can-spam unsubscribe booking link tagline case study result proof website', icon: Building2 },
  { id: 'services', label: 'Services and proof', group: 'Workspace', hint: 'What you sell, at what price', keywords: 'price bands portfolio case studies offers services', icon: BadgeCheck },
  { id: 'keys', label: 'Integrations and keys', group: 'Connections', hint: 'API keys of the products you use', keywords: 'api key anthropic google places pagespeed zerobounce hunter slack token openai', icon: KeyRound },
  { id: 'webhooks', label: 'Webhooks & CRM', group: 'Connections', hint: 'Outbound real-time events for HubSpot, Zapier, Make', keywords: 'webhook webhooks crm sync hubspot zapier make n8n rest api signature hmac deal won audit completed', icon: Zap },
  { id: 'sending', label: 'Sending and policy', group: 'Connections', hint: 'Mailboxes, approvals, daily caps', keywords: 'mailbox smtp email approval autonomy policy cap warmup send stop', icon: Mail },
  { id: 'dns', label: 'Domain DNS', group: 'Connections', hint: 'SPF, DKIM, DMARC', keywords: 'spf dkim dmarc domain deliverability records', icon: Globe },
  { id: 'unsub', label: 'Unsubscribe list', group: 'Connections', hint: 'People you must not email', keywords: 'suppression opt out gdpr compliance can-spam block list', icon: MailX },
  { id: 'team', label: 'Team and keys', group: 'Access and data', hint: 'Roles and sign-in keys', keywords: 'users roles permissions rbac invite revoke admin api keys team members', icon: Users },
  { id: 'security', label: 'Security and session', group: 'Access and data', hint: 'Who you are signed in as', keywords: 'session sign out permissions role password key hygiene kill switch stop sending', icon: ShieldCheck },
  { id: 'data', label: 'Data and export', group: 'Access and data', hint: 'Your records, CSV, backups', keywords: 'export csv download backup restore gdpr data portability records database', icon: Database },
  { id: 'prefs', label: 'Appearance and shortcuts', group: 'Preferences', hint: 'Light or dark, keyboard', keywords: 'theme dark light mode gold glass keyboard shortcuts motion transparency', icon: Palette },
  { id: 'api', label: 'Developer', group: 'Help', hint: 'API console', keywords: 'api endpoints openapi swagger developer console rest', icon: Code2 },
  { id: 'tour', label: 'How it works', group: 'Help', hint: 'A short tour', keywords: 'help guide tour tutorial learn honesty', icon: BookOpen },
];

export const SECTION_LABEL: Record<string, string> = Object.fromEntries(SETTINGS_SECTIONS.map((s) => [s.id, s.label]));
