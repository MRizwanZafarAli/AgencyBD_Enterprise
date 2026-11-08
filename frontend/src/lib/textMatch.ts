const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Does `text` contain every word of `query`, as a word? A short term ("ai", "go", "seo", "ios") must be a whole word, otherwise "ai" matches
 *  "email" and "maintain". A longer term matches the start of a word, so "react" still finds "reactjs" but not "proactive". */
export function matchesQuery(text: string, query: string): boolean {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return true;
  const hay = text.toLowerCase();
  return terms.every((t) => new RegExp(`(?<![a-z0-9])${escape(t)}${t.length <= 3 ? '(?![a-z0-9])' : ''}`).test(hay));
}
