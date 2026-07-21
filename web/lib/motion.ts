/**
 * Shared animation variants + easings for the NovaMind motion system.
 *
 * Everything in `web/components/motion/*` and most of the in-page
 * framer-motion transitions in product pages should import from here
 * so we have one source of truth for timing / easing curves. If you
 * need a new motion primitive, add it here first.
 */
import type { Variants, Transition } from 'framer-motion';

/* Easings — the "feel" of NovaMind is "soft spring with a hint of snap". */
export const EASE_OUT: Transition['ease'] = [0.22, 1, 0.36, 1];
export const EASE_OUT_BACK: Transition['ease'] = [0.34, 1.56, 0.64, 1];
export const EASE_IN_OUT: Transition['ease'] = [0.65, 0, 0.35, 1];

/* Common durations. */
export const DUR = {
  fast: 0.18,
  base: 0.32,
  slow: 0.55,
  reveal: 0.7,
} as const;

/* ----- Variants ----- */

/** Fade + slight upward slide. Use for sections, cards, anything appearing. */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.reveal, ease: EASE_OUT },
  },
};

/** Fade + slide from the left. Use for sidebar/rail items. */
export const fadeLeft: Variants = {
  hidden: { opacity: 0, x: -16 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: DUR.base, ease: EASE_OUT },
  },
};

/** Slight scale-in. Use for cards in a grid. */
export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { duration: DUR.base, ease: EASE_OUT_BACK },
  },
};

/** Container variant for staggerChildren. Pair with fadeUp on children. */
export const staggerParent = (delay = 0, gap = 0.07): Variants => ({
  hidden: {},
  visible: {
    transition: {
      delayChildren: delay,
      staggerChildren: gap,
    },
  },
});

/** Slide-in from the left for sidebar/panel entrance. */
export const slideInLeft: Variants = {
  hidden: { x: -260, opacity: 0 },
  visible: {
    x: 0,
    opacity: 1,
    transition: { type: 'spring', stiffness: 260, damping: 30 },
  },
};

/** Zoom-in for modal-style components (command palette, dialogs). */
export const zoomIn: Variants = {
  hidden: { scale: 0.95, opacity: 0 },
  visible: {
    scale: 1,
    opacity: 1,
    transition: { duration: DUR.base, ease: EASE_OUT_BACK },
  },
  exit: {
    scale: 0.97,
    opacity: 0,
    transition: { duration: 0.15, ease: EASE_IN_OUT },
  },
};

/** Hover lift preset for cards. Pass to `whileHover`. */
export const hoverLift = { y: -3, transition: { type: 'spring', stiffness: 300, damping: 22 } } as const;

/** Hover for icon-only buttons — subtle scale. */
export const hoverScale = { scale: 1.06, transition: { duration: 0.18, ease: EASE_OUT } } as const;
