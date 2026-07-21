import { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

interface StreamingMarkdownProps {
  children: ReactNode;
  /** When true, animates block entrance (use for first paint of a new message). */
  animateEnter?: boolean;
}

/**
 * Wraps the existing markdown renderer with a per-block fade-in.
 * The actual markdown rendering is left to the consumer — this just
 * provides a presentational wrapper that fades children as they
 * appear. For per-element animation, the consumer should split the
 * markdown into discrete children (one per block).
 *
 * Light-weight: we don't parse markdown here, we trust the consumer.
 */
export function StreamingMarkdown({ children, animateEnter = true }: StreamingMarkdownProps) {
  const reduced = useReducedMotionSafe();
  if (reduced || !animateEnter) {
    return <div className="prose prose-invert dark:prose-invert max-w-none">{children}</div>;
  }
  return (
    <motion.div
      className="prose prose-invert dark:prose-invert max-w-none"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
