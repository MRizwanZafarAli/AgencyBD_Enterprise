export interface Finding {
  category: string; check_id: string; severity: string; finding: string; fix: string | null; estimated_impact: string | null; service_id: string | null;
  evidence_value: string | null; confidence: number | null; evidence_id: number | null;
}
export interface Audit {
  audit_id: number; domain: string; overall_score: number | null; status: string; response_time_ms?: number; findings_count: number; findings: Finding[];
  blocked?: { reason: string; server: string; status_code: number } | null; checks_run?: string[]; checks_skipped?: string[];
}
export interface Resolve { company_id: number; name: string; domain: string | null; status: string; confidence: number; note: string | null; access?: 'open' | 'blocked' | null; candidates?: Array<{ domain: string; score: number; title?: string }> }
export interface Brief {
  status: string; unknown?: string[]; next_steps?: string[];
  digital_health?: { findings_by_category: Record<string, number> } | null;
  pitch_kit?: { angle: { text: string | null } | null; price_band: string | null; price_band_note?: string; talking_points: Array<{ text: string; evidence_ids: number[] }>; objections_to_prepare_for: { items: string[] } } | null;
  evidence?: Array<{ id: number; claim: string; value: string; source_url: string; observed_at: string }>;
}
export interface Rec { service_key: string; service: string; priority: string; price_band: string | null; summary: string; findings: Array<{ finding: string; severity: string; fix: string; evidence_id: number }> }
export interface Change {
  score_before: number | null; score_after: number | null; score_delta: number; previous_at: string; latest_at: string; still_open: number;
  fixed: Array<{ check_id: string; severity: string; finding: string }>; new: Array<{ check_id: string; severity: string; finding: string }>;
}
export interface History { audits: Array<{ audit_id: number; score: number | null; at: string; status: string; by_severity: Record<string, number> }>; change: Change | null }
export interface Presence { verified: boolean; confidence: number; classification: string; checks_performed: Array<{ check: string; outcome: string }>; limitations?: string[] }

export interface Chart { resolve: Resolve; audit: Audit | null; brief: Brief | null; advice: Rec[]; history: History | null; presence: Presence | null; target: Target }

export type Target = { kind: 'site'; domain: string } | { kind: 'business'; name: string; city: string };

const DOMAIN = /^(?:https?:\/\/)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)(?::\d+)?(?:[/?#].*)?$/i;

/** One box for everything: a pasted link or domain, or a business and its place ("Acme Plumbing, Austin" / "Acme Plumbing in Austin"). */
export function parseTarget(text: string): Target | null {
  const t = text.trim();
  if (t.length < 2) return null;
  const site = !/\s/.test(t) && DOMAIN.exec(t);
  if (site) return { kind: 'site', domain: site[1].toLowerCase() };
  const m = /^(.+?)\s*(?:,|\s+in\s+|\s+near\s+|\s+at\s+)\s*(.+)$/i.exec(t);
  if (m && m[1].trim().length >= 2 && m[2].trim().length >= 2) return { kind: 'business', name: m[1].trim(), city: m[2].trim() };
  return null;
}

export const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'];
export const SEVERITY_TONE: Record<string, 'bad' | 'warn' | 'info' | 'neutral' | 'accent'> = { critical: 'bad', high: 'bad', medium: 'warn', low: 'info', info: 'neutral' };
export const CATEGORY_LABEL: Record<string, string> = { security: 'Security', seo: 'SEO', performance: 'Speed', a11y: 'Accessibility', ux: 'Experience', geo: 'AI readiness', dns: 'Email and DNS', vuln: 'Known vulnerabilities', exposure: 'Exposure' };
export const PHASES: Array<{ id: string; label: string; hint: string; severities: string[] }> = [
  { id: 'now', label: 'Immediate', hint: 'Critical and high severity: fix first', severities: ['critical', 'high'] },
  { id: 'next', label: 'Next', hint: 'Medium severity', severities: ['medium'] },
  { id: 'later', label: 'Later', hint: 'Low severity and polish', severities: ['low'] },
];
