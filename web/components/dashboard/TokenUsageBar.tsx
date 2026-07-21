import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';
import { CountUp } from '../motion/CountUp';

interface TokenUsageBarProps {
  /** Used (numerator). */
  used: number;
  /** Cap (denominator). */
  total: number;
  /** Label above the bar. */
  label?: string;
  /** Optional unit suffix (e.g. "tokens"). */
  unit?: string;
  className?: string;
}

/**
 * Horizontal usage bar. `width` animates from 0 to its target % on
 * inView, and the number above the bar counts up. Bar color shifts
 * to a warning hue past 75% and a destructive hue past 95%.
 */
export function TokenUsageBar({ used, total, label, unit, className }: TokenUsageBarProps) {
  const reduced = useReducedMotionSafe();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-40px' });
  const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0;
  const hue = pct >= 95 ? 'bg-destructive' : pct >= 75 ? 'bg-amber-500' : 'bg-primary';
  const labelText = label ?? 'Token usage';

  return (
    <div ref={ref} className={className}>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted-foreground">{labelText}</span>
        <span className="font-mono tabular-nums text-foreground">
          <CountUp to={used} duration={1.2} triggerEveryTime={false} />
          <span className="text-muted-foreground"> / {total.toLocaleString()}</span>
          {unit && <span className="text-muted-foreground"> {unit}</span>}
        </span>
      </div>
      <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted">
        <motion.div
          className={`h-full ${hue}`}
          initial={reduced ? false : { width: 0 }}
          animate={inView || reduced ? { width: `${pct}%` } : {}}
          transition={{ duration: 1.0, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
    </div>
  );
}
