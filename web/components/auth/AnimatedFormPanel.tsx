import { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';
import { staggerParent, fadeUp, EASE_OUT, DUR } from '../../lib/motion';

interface AnimatedFormPanelProps {
  children: ReactNode;
  /** Stagger delay for the first child (e.g. title, subtitle, form). */
  delay?: number;
  className?: string;
}

/**
 * Motion wrapper for the form side of the auth pages. Staggers
 * title → subtitle → form fields → footer into a soft entrance.
 * Pair with `<AuthLayout>` (the marketing panel stays the same).
 *
 * Reduced motion → renders as a plain wrapper.
 */
export function AnimatedFormPanel({ children, delay = 0.05, className }: AnimatedFormPanelProps) {
  const reduced = useReducedMotionSafe();
  if (reduced) {
    return <div className={className}>{children}</div>;
  }
  return (
    <motion.div
      className={className}
      variants={staggerParent(delay, 0.06)}
      initial="hidden"
      animate="visible"
      transition={{ duration: DUR.base, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  );
}

/**
 * Single stagger item used inside `<AnimatedFormPanel>`. Renders as
 * `motion.div` with the `fadeUp` variant.
 */
export function AnimatedFormItem({ children, className }: { children: ReactNode; className?: string }) {
  const reduced = useReducedMotionSafe();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div className={className} variants={fadeUp}>
      {children}
    </motion.div>
  );
}
