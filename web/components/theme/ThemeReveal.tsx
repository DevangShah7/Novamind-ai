import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

interface Reveal {
  /** Pixel x of the toggle button center. */
  x: number;
  /** Pixel y of the toggle button center. */
  y: number;
  /** Circle color used to fill the viewport. */
  color: string;
  /** Unique key to retrigger AnimatePresence. */
  k: number;
}

/**
 * Mounted once near the root. Watches `<html>` for `class="dark"`
 * changes (the only signal our theme system emits) and plays a
 * circular reveal that grows from the theme toggle button's center.
 *
 * Implementation notes:
 *  - We use a MutationObserver instead of subscribing to the
 *    ThemeProvider so this works even if a theme change is made
 *    by a script (e.g. _document.tsx inline pre-hydration apply).
 *  - The reveal circle's `color` is the *new* theme's background.
 *  - 380ms total. Theme class is swapped immediately (no flash);
 *    the circle just masks the swap visually.
 */
export function ThemeReveal() {
  const reduced = useReducedMotionSafe();
  const [reveal, setReveal] = useState<Reveal | null>(null);

  useEffect(() => {
    if (reduced || typeof document === 'undefined') return;
    const root = document.documentElement;
    let lastDark = root.classList.contains('dark');

    const observer = new MutationObserver(() => {
      const isDark = root.classList.contains('dark');
      if (isDark === lastDark) return;
      lastDark = isDark;
      const btn = document.querySelector<HTMLElement>('[data-theme-toggle]');
      const rect = btn?.getBoundingClientRect();
      const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
      const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;
      const color = isDark ? 'rgb(15, 17, 21)' : 'rgb(255, 255, 255)';
      setReveal({ x, y, color, k: Date.now() });
    });

    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, [reduced]);

  return (
    <AnimatePresence>
      {reveal && (
        <motion.span
          key={reveal.k}
          aria-hidden
          className="pointer-events-none fixed z-[100]"
          style={{
            left: reveal.x,
            top: reveal.y,
            width: 0,
            height: 0,
            borderRadius: '9999px',
            background: reveal.color,
            // Use a 1.5× viewport radius to make sure we cover on huge monitors.
            boxShadow: `0 0 0 max(150vmax, 150vmax) ${reveal.color}`,
            transform: 'translate(-50%, -50%)',
          }}
          initial={{ scale: 0, opacity: 0.95 }}
          animate={{ scale: 14, opacity: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
        />
      )}
    </AnimatePresence>
  );
}
