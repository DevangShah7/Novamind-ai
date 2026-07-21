import { useEffect, useRef } from 'react';
import { motion, useInView, useMotionValue, useTransform, animate } from 'framer-motion';
import { useReducedMotionSafe } from './useReducedMotionSafe';

interface CountUpProps {
  /** The final value to count to. */
  to: number;
  /** Optional starting value. Defaults to 0. */
  from?: number;
  /** Animation duration in seconds. */
  duration?: number;
  /** Locale-aware formatting. */
  locale?: string;
  /** Minimum number of fraction digits. */
  minFractionDigits?: number;
  /** Maximum number of fraction digits. */
  maxFractionDigits?: number;
  /** Optional prefix (e.g. "$"). */
  prefix?: string;
  /** Optional suffix (e.g. "%"). */
  suffix?: string;
  className?: string;
  /** When true, restart the animation every time the element re-enters view. */
  triggerEveryTime?: boolean;
}

/**
 * Animated number that tweens from `from` to `to` when the element
 * first scrolls into view. Uses `Intl.NumberFormat` for locale-aware
 * formatting (e.g. 12,431 in en-US).
 *
 * Honors `prefers-reduced-motion: reduce` — renders the final value
 * with no animation.
 */
export function CountUp({
  to,
  from = 0,
  duration = 1.4,
  locale = 'en-US',
  minFractionDigits = 0,
  maxFractionDigits = 0,
  prefix = '',
  suffix = '',
  className,
  triggerEveryTime = false,
}: CountUpProps) {
  const reduced = useReducedMotionSafe();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: !triggerEveryTime, margin: '-40px' });
  const value = useMotionValue(reduced ? to : from);
  const formatter = new Intl.NumberFormat(locale, {
    minimumFractionDigits: minFractionDigits,
    maximumFractionDigits: maxFractionDigits,
  });

  const display = useTransform(value, (v) => `${prefix}${formatter.format(v)}${suffix}`);

  useEffect(() => {
    if (reduced) {
      value.set(to);
      return;
    }
    if (!inView) return;
    const controls = animate(value, to, {
      duration,
      ease: [0.22, 1, 0.36, 1],
    });
    return () => controls.stop();
  }, [inView, to, duration, reduced, value]);

  return <motion.span ref={ref} className={className}>{display}</motion.span>;
}
