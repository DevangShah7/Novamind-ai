import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Brain, Github } from 'lucide-react';
import { Button } from '../ui/Button';
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
 */
export default function NavBar({ variant = 'marketing' }: NavBarProps) {
  const router = useRouter();
  // Read auth state from localStorage AFTER mount. Reading it during the
  // initial render causes a React #418 hydration mismatch: the server
  // prerender doesn't have window, so it always renders the
  // "Sign in / Get started" pair; if a returning visitor has a token in
  // localStorage, the client first-render shows "Open app" instead.
  // Deferring to useEffect keeps the initial server+client HTML identical
  // and flips the buttons after hydration. The brief flash is invisible
  // because the route is cached on the prerendered page.
  const [isAuthed, setIsAuthed] = useState(false);
  useEffect(() => {
    setIsAuthed(!!window.localStorage.getItem('token'));
  }, []);

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
            <Button asChild size="sm">
              <Link href="/chat">Open app</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
                <Link href="/login">Sign in</Link>
              </Button>
              <Button asChild size="sm">
                <Link href="/signup">Get started</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
