import Link from 'next/link';
import { useRouter } from 'next/router';
import { Brain, Github } from 'lucide-react';
import { buttonVariants } from '../ui/Button';
import { cn } from '../../lib/cn';

interface NavBarProps {
  /** Optional: a list of links overrides. Default: marketing links. */
  variant?: 'marketing' | 'app';
}

/**
 * Public-facing top nav. The `marketing` variant is for the landing
 * and pricing pages (links to docs, pricing, login/signup). The `app`
 * variant is for inside the product — but for now, both look the same
 * and the variant prop is reserved for future expansion.
 *
 * Note: the CTA links here intentionally don't use Radix's
 * ``Button asChild`` pattern. ``<Slot>`` calls ``React.Children.only``,
 * which the production-build prerender rejects when its single child
 * is a Next.js ``<Link>`` (it produces multiple child elements
 * internally). Rendering ``Link`` with ``buttonVariants`` directly
 * gives the same look without the prerender regression.
 */
export default function NavBar({ variant = 'marketing' }: NavBarProps) {
  const router = useRouter();
  const isAuthed = typeof window !== 'undefined' && !!window.localStorage.getItem('token');

  return (
    <header className="sticky top-0 z-30 w-full border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-bg text-white">
              <Brain className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold tracking-tight">NovaMind AI</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {variant === 'marketing' && (
            <>
              <Link
                href="/#features"
                className={cn(
                  'rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground'
                )}
              >
                Features
              </Link>
              <Link
                href="/pricing"
                className={cn(
                  'rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground',
                  router.pathname === '/pricing' && 'text-foreground'
                )}
              >
                Pricing
              </Link>
              <Link
                href="/docs"
                className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                Docs
              </Link>
            </>
          )}
        </nav>

        <div className="flex items-center gap-2">
          <a
            href="https://github.com/"
            target="_blank"
            rel="noreferrer"
            className="hidden h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground sm:inline-flex"
            aria-label="GitHub"
          >
            <Github className="h-4 w-4" />
          </a>
          {isAuthed ? (
            <Link
              href="/chat"
              className={buttonVariants({ size: 'sm' })}
            >
              Open app
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className={cn(
                  buttonVariants({ variant: 'ghost', size: 'sm' }),
                  'hidden sm:inline-flex'
                )}
              >
                Sign in
              </Link>
              <Link
                href="/signup"
                className={buttonVariants({ size: 'sm' })}
              >
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
