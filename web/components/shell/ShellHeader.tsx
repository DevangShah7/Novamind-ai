import { ReactNode, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

interface ShellHeaderProps {
  children: ReactNode;
  /** Pixels of scroll before the header shrinks. */
  shrinkAfter?: number;
}

/**
 * Top bar with a subtle scroll-shrink: the header height eases from
 * 64px → 56px once the user scrolls past `shrinkAfter`. Children
 * stay the same — they just sit in a slightly tighter band.
 *
 * Implemented with an absolutely-positioned spacer so layout doesn't
 * jump when the height changes. The header itself animates its
 * padding.
 */
export function ShellHeader({ children, shrinkAfter = 40 }: ShellHeaderProps) {
  const reduced = useReducedMotionSafe();
  const [shrunk, setShrunk] = useState(false);

  useEffect(() => {
    if (reduced || typeof window === 'undefined') return;
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => setShrunk(window.scrollY > shrinkAfter));
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(raf);
    };
  }, [reduced, shrinkAfter]);

  return (
    <div className="flex-shrink-0 border-b border-border bg-card/80 backdrop-blur-md">
      <AnimatePresence initial={false}>
        <motion.div
          className="flex items-center justify-between gap-3 px-4 sm:px-6"
          animate={{ height: shrunk && !reduced ? 56 : 64 }}
          transition={{ type: 'spring', stiffness: 240, damping: 28 }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
