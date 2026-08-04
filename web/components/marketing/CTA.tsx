import Link from 'next/link';
import { buttonVariants } from '../ui/Button';

/**
 * Closing CTA strip for the landing page. Pure marketing — pushes the
 * reader to /signup with a single button.
 *
 * Note: the CTA link here intentionally doesn't use Radix's
 * ``Button asChild`` pattern. ``<Slot>`` calls ``React.Children.only``,
 * which the production-build prerender rejects when its single child
 * is a Next.js ``<Link>`` (it produces multiple child elements
 * internally). Rendering ``Link`` with ``buttonVariants`` directly
 * gives the same look without the prerender regression.
 */
export default function CTA() {
  return (
    <section className="border-t border-border/60 bg-background py-20 sm:py-24">
      <div className="mx-auto max-w-5xl px-4 sm:px-6">
        <div className="relative overflow-hidden rounded-2xl gradient-bg p-10 text-center text-white shadow-xl sm:p-14">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -left-20 -top-20 h-72 w-72 rounded-full bg-white/20 blur-3xl" />
            <div className="absolute -bottom-20 -right-20 h-72 w-72 rounded-full bg-pink-300/20 blur-3xl" />
          </div>
          <div className="relative">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Ready to build with AI?
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-white/90">
              Free tier gets you started in 30 seconds. Upgrade when you need
              more tokens, more keys, or more models.
            </p>
            <div className="mt-8">
              <Link
                href="/signup"
                className={buttonVariants({
                  size: 'lg',
                  className: 'bg-white text-primary hover:bg-white/95',
                })}
              >
                Create your free account
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
