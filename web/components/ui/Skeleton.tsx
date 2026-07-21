import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  /** Use the slow CSS shimmer instead of the default pulse. Default: false. */
  shimmer?: boolean;
}

function Skeleton({ className, shimmer = false, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        shimmer ? 'skeleton-shimmer' : 'animate-pulse',
        'rounded-md bg-muted',
        className
      )}
      {...props}
    />
  );
}

export { Skeleton };
