import { useEffect, useState } from 'react';

/**
 * SSR-safe `prefers-reduced-motion` matcher.
 *
 * On the server `window` is undefined — we return `false` (i.e. motion
 * is allowed) so the first client paint matches the markup that React
 * produced. After mount, we listen for changes so the UI can react
 * live if the user toggles the OS-level setting.
 */
export function useReducedMotionSafe(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    setReduced(mq.matches);
    // Safari < 14 used `addListener`; modern browsers use `addEventListener`.
    if (mq.addEventListener) {
      mq.addEventListener('change', handler);
      return () => mq.removeEventListener('change', handler);
    }
    mq.addListener(handler);
    return () => mq.removeListener(handler);
  }, []);

  return reduced;
}
