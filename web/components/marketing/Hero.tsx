import Link from 'next/link';
import { ArrowRight, Sparkles } from 'lucide-react';
import { buttonVariants } from '../ui/Button';

/**
 * Hero section for the marketing landing page.
 *
 * Composition (top to bottom):
 *   1. Eyebrow chip ("AI operating system")
 *   2. Headline (gradient text on the accent word)
 *   3. Subhead (one-sentence value prop)
 *   4. CTA pair (Get started → /signup, View pricing → /pricing)
 *   5. Trust strip ("No credit card · Free tier · Cancel anytime")
 *
 * Note: the CTA links here intentionally don't use Radix's
 * ``Button asChild`` pattern. ``<Slot>`` calls ``React.Children.only``,
 * which the production-build prerender rejects when its single child
 * is a Next.js ``<Link>`` (it produces multiple child elements
 * internally). Rendering ``Link`` with ``buttonVariants`` directly
 * gives the same look without the prerender regression.
 */
export default function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* Decorative animated blobs (reuse the AuthLayout keyframes) */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div
          className="absolute -left-20 top-20 h-72 w-72 rounded-full bg-primary/20 blur-3xl animate-blob"
          style={{ animationDelay: '0s' }}
        />
        <div
          className="absolute right-0 top-40 h-80 w-80 rounded-full bg-accent/20 blur-3xl animate-blob"
          style={{ animationDelay: '4s' }}
        />
        <div
          className="absolute bottom-10 left-1/3 h-64 w-64 rounded-full bg-pink-400/10 blur-3xl animate-blob"
          style={{ animationDelay: '8s' }}
        />
      </div>

      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28 lg:py-32">
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/50 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur-sm">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            <span>Your AI operating system</span>
          </div>

          <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
            Think faster.{' '}
            <span className="gradient-text">Build smarter.</span>
            <br />
            Ship without limits.
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            NovaMind AI is the unified workspace for chat, voice, code, and
            production-ready APIs. One account, every model, one bill.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/signup" className={buttonVariants({ size: 'lg' })}>
              <span className="inline-flex items-center gap-2">
                Get started free
                <ArrowRight className="h-4 w-4" />
              </span>
            </Link>
            <Link href="/pricing" className={buttonVariants({ size: 'lg', variant: 'outline' })}>
              <span className="inline-flex items-center">View pricing</span>
            </Link>
          </div>

          <p className="mt-6 text-xs text-muted-foreground">
            No credit card · Free tier · Cancel anytime
          </p>
        </div>
      </div>
    </section>
  );
}
