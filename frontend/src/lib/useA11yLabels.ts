import { useEffect } from 'react';

const NAMED = (el: Element) =>
  el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) || el.closest('label');

/** Best available human-readable name for a form control, or null. */
function guessName(el: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement): string | null {
  const direct = el.getAttribute('placeholder') || el.title;
  if (direct) return direct;
  let node: Element | null = el;
  for (let hops = 0; hops < 3 && node; hops++) {          // nearest preceding text in the same group
    let prev = node.previousElementSibling;
    while (prev) {
      const t = prev.textContent?.trim();
      if (t && t.length < 60 && !prev.querySelector('input,select,textarea')) return t;
      prev = prev.previousElementSibling;
    }
    node = node.parentElement;
  }
  return el.getAttribute('name');
}

/**
 * Safety net for older tool screens whose visible captions are not programmatically tied to their inputs: gives every unlabeled
 * control an aria-label derived from its placeholder, nearby caption or name. New screens label their controls properly.
 */
export function useA11yLabels(): void {
  useEffect(() => {
    const apply = () => {
      document.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea').forEach((el) => {
        if (el.type === 'hidden' || NAMED(el)) return;
        const name = guessName(el);
        if (name) el.setAttribute('aria-label', name);
      });
    };
    apply();
    const obs = new MutationObserver(() => apply());
    obs.observe(document.body, { childList: true, subtree: true });
    return () => obs.disconnect();
  }, []);
}
