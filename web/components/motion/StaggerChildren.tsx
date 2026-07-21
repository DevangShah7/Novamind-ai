import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { useReducedMotionSafe } from './useReducedMotionSafe';
import { fadeUp, staggerParent, EASE_OUT, DUR } from '../../lib/motion';

interface StaggerChildrenProps {
  children: ReactNode;
  /** Delay before the first child starts animating. */
  delay?: number;
  /** Time between each child's animation start. */
  gap?: number;
  className?: string;
  /** Whether to animate only the first time the element enters view. */
  once?: boolean;
  as?: 'div' | 'ul' | 'ol' | 'section';
}

/**
 * Container that staggers its children's fade+slide entrance.
 *
 * Pair with `<StaggerItem>` on each child for the visual effect, or
 * use any child wrapped in `motion.*` with the `hidden` / `visible`
 * variants from `lib/motion`.
 */
export function StaggerChildren({
  children,
  delay = 0,
  gap = 0.07,
  className,
  once = true,
  as = 'div',
}: StaggerChildrenProps) {
  const reduced = useReducedMotionSafe();
  const Comp = motion[as] as typeof motion.div;
  const parent = staggerParent(delay, gap);

  if (reduced) {
    return <Comp className={className}>{children}</Comp>;
  }

  return (
    <Comp
      className={className}
      variants={parent}
      initial="hidden"
      whileInView="visible"
      viewport={{ once, margin: '-40px' }}
      transition={{ duration: DUR.base, ease: EASE_OUT }}
    >
      {children}
    </Comp>
  );
}

interface StaggerItemProps {
  children: ReactNode;
  className?: string;
  as?: 'div' | 'li' | 'article' | 'section';
  /** When true, uses a slightly stronger scale-in instead of fadeUp. */
  scaleIn?: boolean;
}

/**
 * Single child of `<StaggerChildren>`. Renders as `motion.div` with
 * the `hidden` / `visible` variants the parent expects.
 */
export function StaggerItem({ children, className, as = 'div', scaleIn: useScale = false }: StaggerItemProps) {
  const Comp = motion[as] as typeof motion.div;
  // Scale-in variant reuses the same transition shape.
  const variants = useScale
    ? {
        hidden: { opacity: 0, scale: 0.96 },
        visible: { opacity: 1, scale: 1, transition: { duration: DUR.base, ease: [0.34, 1.56, 0.64, 1] } },
      }
    : fadeUp;
  return (
    <Comp className={className} variants={variants}>
      {children}
    </Comp>
  );
}
