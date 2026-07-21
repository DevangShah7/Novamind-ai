import { ReactNode, forwardRef } from 'react';
import { motion, MotionProps } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';
import { hoverLift } from '../../lib/motion';

interface GlassCardProps extends Omit<MotionProps, 'children'> {
  children: ReactNode;
  className?: string;
  /** Disable the hover lift. */
  noHover?: boolean;
  /** Disable the animated border shimmer on hover. */
  noShimmer?: boolean;
  /** Render as a different element (e.g. `article`, `li`). */
  as?: 'div' | 'article' | 'li' | 'section';
}

/**
 * Glassmorphism card. Backdrop blur + slight transparency + a
 * subtle border. Hover lifts the card (-3px) and sweeps a soft
 * shimmer across the top edge.
 *
 * Reduced motion → no lift, no shimmer. The card stays static and
 * the border is plain.
 */
export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(function GlassCard(
  { children, className = '', noHover, noShimmer, as = 'div', ...rest },
  ref
) {
  const reduced = useReducedMotionSafe();
  const Comp = motion[as] as typeof motion.div;
  const liftProps: MotionProps = !reduced && !noHover ? { whileHover: hoverLift } : {};

  return (
    <Comp
      ref={ref as any}
      className={`relative overflow-hidden rounded-xl border border-white/10 bg-card/60 backdrop-blur-md ${className}`}
      {...liftProps}
      {...rest}
    >
      {!reduced && !noShimmer && <span className="card-shimmer pointer-events-none absolute inset-0" aria-hidden />}
      <div className="relative z-10">{children}</div>
    </Comp>
  );
});
