/**
 * Normalizes any website or domain string into a valid https:// URL
 * and ensures it always opens securely in a new browser tab.
 */
export const normalizeUrl = (url: string | null | undefined): string => {
  if (!url) return '';
  const trimmed = url.trim();
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `https://${trimmed}`;
};
