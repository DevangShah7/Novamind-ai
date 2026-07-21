import { useEffect, useRef, useState } from 'react';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

export interface RequestEvent {
  /** Time of the request in ms since the epoch. */
  t: number;
  /** HTTP-style status code. 2xx → success color, 4xx/5xx → error. */
  status: number;
}

interface RequestDotsProps {
  /** Stream of recent requests. Newest at the end. */
  events: RequestEvent[];
  /** Window in seconds shown on the timeline. */
  windowSec?: number;
  /** Height of the canvas in px. */
  height?: number;
  className?: string;
}

/**
 * Canvas2D request timeline. Renders the last `windowSec` seconds of
 * API requests as colored dots on a scrolling line (1 dot per
 * request, 2px wide). Animation pauses when off-screen via
 * IntersectionObserver.
 */
export function RequestDots({
  events,
  windowSec = 60,
  height = 48,
  className,
}: RequestDotsProps) {
  const reduced = useReducedMotionSafe();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [visible, setVisible] = useState(true);

  // Pause animation when off-screen. Saves a few ms in admin tabs the
  // user can't see.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(
      (entries) => setVisible(entries[0]?.isIntersecting ?? true),
      { threshold: 0 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = canvas.clientWidth;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    function draw() {
      if (!ctx || !canvas) return;
      const w = canvas.clientWidth;
      ctx.clearRect(0, 0, w, height);

      // Baseline.
      ctx.strokeStyle = 'rgba(127,127,127,0.2)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(w, height / 2);
      ctx.stroke();

      const now = Date.now();
      const windowMs = windowSec * 1000;
      for (const e of events) {
        const age = now - e.t;
        if (age > windowMs) continue;
        const x = w - (age / windowMs) * w;
        const y = height / 2;
        const ok = e.status >= 200 && e.status < 400;
        ctx.fillStyle = ok ? 'rgba(16,185,129,0.85)' : 'rgba(239,68,68,0.85)';
        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    draw();
    if (reduced || !visible) return;
    const id = setInterval(draw, 1000);
    return () => clearInterval(id);
  }, [events, windowSec, height, reduced, visible]);

  return (
    <div ref={containerRef} className={className}>
      <canvas ref={canvasRef} style={{ width: '100%', height }} />
    </div>
  );
}
