import { useMemo, useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

interface SparklineProps {
  /** Series of values. The path is normalized to fit the viewBox. */
  data: number[];
  width?: number;
  height?: number;
  /** Stroke color. Defaults to a primary-ish hue that reads on dark + light. */
  stroke?: string;
  /** Optional fill below the line. */
  fill?: string;
  className?: string;
  /** Stroke width in px. */
  strokeWidth?: number;
  /** When true, also draws a dot at the final value. */
  showEndDot?: boolean;
}

/**
 * Tiny inline-SVG sparkline. Animates the path being "drawn" with
 * `stroke-dashoffset` when the element first scrolls into view.
 * Path is a smooth bezier through the data points.
 */
export function Sparkline({
  data,
  width = 120,
  height = 36,
  stroke = 'currentColor',
  fill,
  className,
  strokeWidth = 1.5,
  showEndDot = true,
}: SparklineProps) {
  const reduced = useReducedMotionSafe();
  const ref = useRef<SVGPathElement>(null);
  const inView = useInView(ref, { once: true, margin: '-40px' });

  const { line, area, length, last } = useMemo(() => {
    if (data.length === 0) return { line: '', area: '', length: 0, last: null as null | { x: number; y: number } };
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const padX = 2;
    const padY = 3;
    const w = width - padX * 2;
    const h = height - padY * 2;
    const stepX = data.length > 1 ? w / (data.length - 1) : 0;

    const points = data.map((v, i) => {
      const x = padX + i * stepX;
      const y = padY + h - ((v - min) / range) * h;
      return { x, y };
    });

    // Smooth Catmull-Rom → bezier.
    let path = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i - 1] || points[i];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[i + 2] || p2;
      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;
      path += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)} ${cp2x.toFixed(2)} ${cp2y.toFixed(2)} ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
    }

    const areaPath = fill
      ? `${path} L ${points[points.length - 1].x.toFixed(2)} ${height} L ${points[0].x.toFixed(2)} ${height} Z`
      : '';

    // Approximate path length by counting segments × distance. Good enough for the
    // dash-offset trick; the visual fill is unaffected.
    let len = 0;
    for (let i = 1; i < points.length; i++) {
      const dx = points[i].x - points[i - 1].x;
      const dy = points[i].y - points[i - 1].y;
      len += Math.hypot(dx, dy);
    }
    return { line: path, area: areaPath, length: len * 1.2, last: points[points.length - 1] };
  }, [data, width, height, fill]);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      role="img"
      aria-label="Trend"
    >
      {fill && (
        <motion.path
          d={area}
          fill={fill}
          initial={reduced ? false : { opacity: 0 }}
          animate={inView || reduced ? { opacity: 0.4 } : {}}
          transition={{ duration: 0.8, delay: 0.4 }}
        />
      )}
      <motion.path
        ref={ref}
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={reduced ? false : { strokeDasharray: length, strokeDashoffset: length }}
        animate={inView || reduced ? { strokeDashoffset: 0 } : {}}
        transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
      />
      {showEndDot && last && (
        <motion.circle
          cx={last.x}
          cy={last.y}
          r={2.5}
          fill={stroke}
          initial={reduced ? false : { scale: 0, opacity: 0 }}
          animate={inView || reduced ? { scale: 1, opacity: 1 } : {}}
          transition={{ duration: 0.3, delay: 1.0 }}
          style={{ transformOrigin: `${last.x}px ${last.y}px` }}
        />
      )}
    </svg>
  );
}
