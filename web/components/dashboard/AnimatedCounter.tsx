import { CountUp } from '../motion/CountUp';

interface AnimatedCounterProps {
  value: number;
  label?: string;
  /** Locale for the count-up. */
  locale?: string;
  /** Min / max fraction digits for the number formatter. */
  minFractionDigits?: number;
  maxFractionDigits?: number;
  /** Prefix / suffix (e.g. "$" / "%"). */
  prefix?: string;
  suffix?: string;
  /** Optional class for the number itself. */
  numberClassName?: string;
  className?: string;
}

/**
 * Big stat number with a subtle scale-in entrance and a tween
 * from 0 → value. Use for hero stats on the dashboard cards.
 */
export function AnimatedCounter({
  value,
  label,
  locale = 'en-US',
  minFractionDigits = 0,
  maxFractionDigits = 0,
  prefix = '',
  suffix = '',
  numberClassName = 'text-3xl font-bold tabular-nums text-foreground',
  className,
}: AnimatedCounterProps) {
  return (
    <div className={className}>
      <div className={numberClassName}>
        <CountUp
          to={value}
          locale={locale}
          minFractionDigits={minFractionDigits}
          maxFractionDigits={maxFractionDigits}
          prefix={prefix}
          suffix={suffix}
          duration={1.4}
        />
      </div>
      {label && <p className="mt-1 text-xs text-muted-foreground">{label}</p>}
    </div>
  );
}
