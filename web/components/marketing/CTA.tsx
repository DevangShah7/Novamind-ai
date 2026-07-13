import Link from 'next/link';
import { Button } from '../ui/Button';

/**
 * Closing CTA strip for the landing page. Pure marketing — pushes the
 * reader to /signup with a single button.
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
              <Button
                asChild
                size="lg"
                className="bg-white text-primary hover:bg-white/95"
              >
                <Link href="/signup">Create your free account</Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
