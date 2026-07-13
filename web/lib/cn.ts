import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Compose Tailwind classes. The `clsx` step handles conditional class
 * arrays; `twMerge` deduplicates and resolves conflicts so that, e.g.,
 * `cn('p-2', 'p-4')` returns `'p-4'`.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
