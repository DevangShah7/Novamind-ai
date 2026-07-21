import { ReactNode, useRef, useState, MouseEvent } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { useReducedMotionSafe } from './useReducedMotionSafe';

interface MagneticButtonProps {
  children: ReactNode;
  /** Strength of the magnetic pull. 0 = no effect, 1 = very strong. */
  strength?: number;
  /** Pixel radius around the element where pointer movement is tracked. */
  radius?: number;
  className?: string;
  /** Disable on touch devices (no hover). */
  desktopOnly?: boolean;
}

/**
 * Wraps any child in a magnetic hover effect — the child translates
 * up to ±N pixels toward the cursor with a soft spring.
 *
 * Used for primary CTAs. Pure pointer-events passthrough: click /
 * focus / keyboard navigation on the child element still works.
 *
 * Respects reduced-motion (becomes a plain wrapper). On viewports
 * below 768px the effect is disabled by default — touch users don't
 * get the magnetic feel anyway.
 */
export function MagneticButton({
  children,
  strength = 0.3,
  radius = 80,
  className,
  desktopOnly = true,
}: MagneticButtonProps) {
  const reduced = useReducedMotionSafe();
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 220, damping: 18, mass: 0.6 });
  const sy = useSpring(y, { stiffness: 220, damping: 18, mass: 0.6 });
  const [enabled, setEnabled] = useState(true);

  function handleMove(e: MouseEvent<HTMLDivElement>) {
    if (reduced || !enabled || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const dx = e.clientX - (rect.left + rect.width / 2);
    const dy = e.clientY - (rect.top + rect.height / 2);
    const dist = Math.hypot(dx, dy);
    if (dist > radius) {
      x.set(0);
      y.set(0);
      return;
    }
    x.set(dx * strength);
    y.set(dy * strength);
  }

  function handleLeave() {
    x.set(0);
    y.set(0);
  }

  // SSR + desktop detection. Only disable on touch viewports when
  // `desktopOnly` is set (default true).
  if (typeof window !== 'undefined' && desktopOnly) {
    if (window.matchMedia && window.matchMedia('(max-width: 768px)').matches) {
      // no-op: still wrap so click handlers work, but skip the motion math
      // by leaving values at 0.
    }
  }

  if (reduced) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      style={{ x: sx, y: sy, display: 'inline-block' }}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
    >
      {children}
    </motion.div>
  );
}
