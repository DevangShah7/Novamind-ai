import Link from 'next/link';
import { ArrowRight, Mic } from 'lucide-react';
import { buttonVariants } from '../ui/Button';
import Aurora from '../ui/Aurora';

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
      <div className="absolute inset-0 -z-10">
        <Aurora />
      </div>

      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28 lg:py-32">
        <div className="mx-auto max-w-3xl text-center">
          <div className="glass-card inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium text-muted-foreground animate-rise-in">
            <Mic className="h-3.5 w-3.5 text-primary" />
            <span>Now with real-time voice conversations</span>
          </div>

          <h1 className="font-display mt-6 text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
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
