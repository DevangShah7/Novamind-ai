import { motion } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

interface StreamingCursorProps {
  /** Tail className passthrough for color/size tweaks. */
  className?: string;
}

/**
 * Blinking caret rendered at the tail of the streaming assistant
 * message. Honors `prefers-reduced-motion` — becomes a static
 * 50%-opacity caret instead of blinking.
 */
export function StreamingCursor({ className = 'bg-foreground' }: StreamingCursorProps) {
  const reduced = useReducedMotionSafe();
  if (reduced) {
    return (
      <span
        aria-hidden
        className={`inline-block w-1.5 h-4 ml-0.5 align-middle opacity-50 ${className}`}
      />
    );
  }
  return (
    <motion.span
      aria-hidden
      className={`inline-block w-1.5 h-4 ml-0.5 align-middle ${className}`}
      animate={{ opacity: [1, 0, 1] }}
      transition={{ duration: 0.9, repeat: Infinity, ease: 'easeInOut' }}
    />
  );
}
