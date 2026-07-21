import { motion } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

/**
 * Three-dot typing indicator with a vertical bounce + a tiny
 * waveform beside it. Used in the assistant message slot before
 * the first streamed token arrives (i.e. while the ThinkingOrb is
 * already visible this is hidden — they don't run together).
 */
export function TypingIndicator() {
  const reduced = useReducedMotionSafe();
  const dot = (i: number) => (
    <motion.span
      key={i}
      className="inline-block w-1.5 h-1.5 rounded-full bg-foreground/60"
      animate={reduced ? undefined : { y: [0, -4, 0] }}
      transition={reduced ? undefined : { duration: 0.9, repeat: Infinity, delay: i * 0.12, ease: 'easeInOut' }}
    />
  );
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground" aria-label="Assistant is typing">
      <div className="flex items-end gap-1">
        {dot(0)}
        {dot(1)}
        {dot(2)}
      </div>
      <Waveform />
    </div>
  );
}

function Waveform() {
  const reduced = useReducedMotionSafe();
  const bars = [0, 1, 2, 3, 4];
  return (
    <div className="flex items-end gap-0.5 h-3">
      {bars.map((i) => (
        <motion.span
          key={i}
          className="w-0.5 bg-foreground/40 rounded-sm"
          style={{ height: '100%' }}
          animate={reduced ? undefined : { scaleY: [0.3, 1, 0.3] }}
          transition={reduced ? undefined : { duration: 0.8, repeat: Infinity, delay: i * 0.1, ease: 'easeInOut' }}
        />
      ))}
    </div>
  );
}
