import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

interface SidebarRailProps {
  children: ReactNode;
  className?: string;
}

/**
 * Slide-in rail that wraps the chat list / dev navigation. Adds:
 *  - entrance animation (x: -260 → 0 with a spring)
 *  - respect for `prefers-reduced-motion`
 *
 * Visual treatment (active row glow, hover lift, click ripple) is
 * handled by the children — SidebarRail is just a motion wrapper.
 */
export function SidebarRail({ children, className }: SidebarRailProps) {
  const reduced = useReducedMotionSafe();
  if (reduced) {
    return <aside className={className}>{children}</aside>;
  }
  return (
    <motion.aside
      className={className}
      initial={{ x: -260, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 260, damping: 30 }}
    >
      {children}
    </motion.aside>
  );
}
