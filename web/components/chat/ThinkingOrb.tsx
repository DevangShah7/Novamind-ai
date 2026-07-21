import dynamic from 'next/dynamic';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

type Status = 'thinking' | 'complete' | 'idle';

interface ThinkingOrbProps {
  status?: Status;
  size?: number;
  className?: string;
  /** Show a static gradient fallback even when motion is allowed. */
  staticFallback?: boolean;
}

/**
 * Wrapper around the R3F scene. Lazy-loaded so `three` and R3F
 * don't bloat the initial chat route. The fallback is a CSS-only
 * pulsing dot — no JS bundle until the scene is ready.
 */
const Scene = dynamic(() => import('./ThinkingOrbScene'), {
  ssr: false,
  loading: () => <FallbackOrb />,
});

function FallbackOrb() {
  // CSS-only pulse: looks intentional, doesn't require JS to render.
  return (
    <div
      className="rounded-full bg-gradient-to-br from-violet-500 via-cyan-400 to-pink-500 animate-pulse-glow"
      style={{ width: 64, height: 64 }}
      aria-hidden
    />
  );
}

function StaticOrb({ status = 'thinking' }: { status?: Status }) {
  // Used when prefers-reduced-motion is set, or when the caller asks for it.
  const colors =
    status === 'complete'
      ? 'from-emerald-500 via-cyan-400 to-blue-500'
      : status === 'idle'
      ? 'from-slate-500 via-slate-400 to-slate-300'
      : 'from-violet-500 via-cyan-400 to-pink-500';
  return (
    <div
      className={`rounded-full bg-gradient-to-br ${colors}`}
      style={{ width: 64, height: 64 }}
      aria-hidden
    />
  );
}

export function ThinkingOrb({ status = 'thinking', size = 96, className, staticFallback }: ThinkingOrbProps) {
  const reduced = useReducedMotionSafe();
  if (reduced || staticFallback) {
    return <StaticOrb status={status} />;
  }
  return <Scene status={status} size={size} className={className} />;
}
