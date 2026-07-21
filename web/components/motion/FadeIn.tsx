import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { useReducedMotionSafe } from './useReducedMotionSafe';
import { fadeUp, EASE_OUT, DUR } from '../../lib/motion';

interface FadeInProps {
  children: ReactNode;
  /** Extra delay in seconds before the animation starts. */
  delay?: number;
  /** How far to slide. Defaults to 18px. */
  y?: number;
  /** Set to false to animate every time the element enters view. */
  once?: boolean;
  className?: string;
  as?: 'div' | 'section' | 'article' | 'li' | 'span';
}

/**
 * Reveal-on-scroll wrapper. Animates opacity + a small upward slide
 * the first time the element enters the viewport.
 *
 * Honors `prefers-reduced-motion: reduce` — the element appears in
 * its final state with no animation.
 */
export function FadeIn({
  children,
  delay = 0,
  y = 18,
  once = true,
  className,
  as = 'div',
}: FadeInProps) {
  const reduced = useReducedMotionSafe();
  const Comp = motion[as] as typeof motion.div;

  if (reduced) {
    return <Comp className={className}>{children}</Comp>;
  }

  return (
    <Comp
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once, margin: '-60px' }}
      transition={{ duration: DUR.reveal, delay, ease: EASE_OUT }}
    >
      {children}
    </Comp>
  );
}
