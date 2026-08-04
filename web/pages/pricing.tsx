import { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { Check, Sparkles } from 'lucide-react';
import NavBar from '../components/marketing/NavBar';
import Footer from '../components/marketing/Footer';
import { Button } from '../components/ui/Button';
import { Card, CardContent } from '../components/ui/Card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../components/ui/Dialog';
import { PLANS, formatPrice, type Plan } from '../lib/plans';
import { toast } from '../components/ui/Toaster';

// Resolve API URL at module load (mirrors lib/api.ts).
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/**
 * Marketing pricing page.
 *
 * CTAs are routed through `handleCta`:
 *   - "signup"   → push to /signup
 *   - "checkout" → try POST /api/v1/billing/checkout-session
 *                  - 200: redirect to the Stripe URL
 *                  - 501 / 503 / "not configured" payload: open a
 *                    dialog saying "Stripe is not configured" (mock mode)
 *   - "contact"  → open a "Talk to us" dialog (Phase 10 will wire email)
 */
// Skip static prerender — see comment in pages/index.tsx.
export const getServerSideProps = async () => ({ props: {} });

export default function Pricing() {
  const [busy, setBusy] = useState<Plan['slug'] | null>(null);
  const [dialog, setDialog] = useState<
    | { kind: 'not_configured'; plan: Plan }
    | { kind: 'contact'; plan: Plan }
    | null
  >(null);

  const handleCta = async (plan: Plan) => {
    if (plan.ctaKind === 'signup') {
      window.location.href = '/signup';
      return;
    }
    if (plan.ctaKind === 'contact') {
      setDialog({ kind: 'contact', plan });
      return;
    }
    // checkout
    setBusy(plan.slug);
    try {
      const token =
        typeof window !== 'undefined'
          ? window.localStorage.getItem('token')
          : null;
      const res = await fetch(`${API_BASE}/billing/checkout-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ plan: plan.slug }),
      });
      if (!res.ok) {
        // 501 / 503 / mock-mode: backend returns a JSON shape with
        // `{ error: "not_configured" }` and we surface a dialog.
        const body = await res.json().catch(() => ({}));
        if (
          res.status === 501 ||
          res.status === 503 ||
          body?.error === 'not_configured' ||
          body?.error === 'stripe_not_configured'
        ) {
          setDialog({ kind: 'not_configured', plan });
          return;
        }
        throw new Error(body?.detail || 'Checkout failed');
      }
      const { url } = await res.json();
      if (!url) {
        setDialog({ kind: 'not_configured', plan });
        return;
      }
      window.location.href = url;
    } catch (err: any) {
      toast.error(err?.message || 'Could not start checkout');
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <Head>
        <title>Pricing · NovaMind AI</title>
        <meta
          name="description"
          content="Simple, token-based pricing. Start free, upgrade when you ship."
        />
      </Head>
      <div className="min-h-screen bg-background text-foreground">
        <NavBar />

        <main>
          <section className="relative overflow-hidden">
            <div className="pointer-events-none absolute inset-0 -z-10">
              <div className="absolute left-1/2 top-0 h-72 w-[600px] -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />
            </div>
            <div className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6 sm:py-20">
              <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
                Simple, token-based{' '}
                <span className="gradient-text">pricing</span>
              </h1>
              <p className="mt-4 text-lg text-muted-foreground">
                Start free. Upgrade when you need more tokens, more keys, or
                more models. No per-seat fees.
              </p>
            </div>
          </section>

          <section className="pb-20">
            <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 sm:px-6 md:grid-cols-3">
              {PLANS.map((plan) => (
                <Card
                  key={plan.slug}
                  className={
                    plan.popular
                      ? 'relative border-primary/60 shadow-lg ring-1 ring-primary/20'
                      : ''
                  }
                >
                  {plan.popular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <span className="inline-flex items-center gap-1 rounded-full gradient-bg px-3 py-1 text-xs font-semibold text-white shadow-sm">
                        <Sparkles className="h-3 w-3" />
                        Most popular
                      </span>
                    </div>
                  )}
                  <CardContent className="p-6">
                    <div className="flex items-center gap-2">
                      <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg gradient-bg text-white">
                        <plan.icon className="h-5 w-5" />
                      </div>
                      <h2 className="text-xl font-semibold">{plan.name}</h2>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {plan.tagline}
                    </p>

                    <div className="mt-6 flex items-baseline gap-1">
                      <span className="text-4xl font-bold">
                        {formatPrice(plan.priceCents)}
                      </span>
                      {plan.priceCents > 0 && (
                        <span className="text-sm text-muted-foreground">
                          /month
                        </span>
                      )}
                    </div>

                    <ul className="mt-6 space-y-3">
                      {plan.features.map((f) => (
                        <li
                          key={f.label}
                          className="flex items-start gap-2 text-sm"
                        >
                          <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
                          <span>
                            {f.label}
                            {f.hint && (
                              <span className="ml-1 text-xs text-muted-foreground">
                                ({f.hint})
                              </span>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>

                    <Button
                      onClick={() => handleCta(plan)}
                      disabled={busy === plan.slug}
                      className="mt-6 w-full"
                      variant={plan.popular ? 'default' : 'outline'}
                    >
                      {busy === plan.slug ? 'Working…' : plan.cta}
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          <section className="border-t border-border/60 bg-muted/30 py-16">
            <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
              <h2 className="text-2xl font-semibold">All plans include</h2>
              <ul className="mt-6 grid grid-cols-1 gap-3 text-sm text-muted-foreground sm:grid-cols-2">
                {[
                  'Every model in the catalog',
                  'OpenAI-compatible API',
                  'Streaming responses',
                  'Per-key usage dashboard',
                ].map((label) => (
                  <li
                    key={label}
                    className="flex items-center justify-center gap-2 sm:justify-start"
                  >
                    <Check className="h-4 w-4 text-primary" />
                    {label}
                  </li>
                ))}
              </ul>
              <p className="mt-8 text-sm text-muted-foreground">
                Need help choosing?{' '}
                <Link
                  href="/docs"
                  className="font-medium text-foreground underline-offset-4 hover:underline"
                >
                  Read the docs
                </Link>{' '}
                or open a chat and ask the assistant.
              </p>
            </div>
          </section>
        </main>

        <Footer />

        {/* Stripe-not-configured dialog (mock mode) */}
        <Dialog
          open={!!dialog && dialog.kind === 'not_configured'}
          onOpenChange={(open) => !open && setDialog(null)}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Stripe isn&apos;t configured yet</DialogTitle>
              <DialogDescription>
                {dialog?.kind === 'not_configured'
                  ? `You're on the ${dialog.plan.name} plan. To enable real billing, set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET in backend/.env, then restart the backend. Until then, the app runs in mock mode — every user is on the Free plan.`
                  : ''}
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDialog(null)}>
                Got it
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Contact dialog (Business plan) */}
        <Dialog
          open={!!dialog && dialog.kind === 'contact'}
          onOpenChange={(open) => !open && setDialog(null)}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Talk to sales</DialogTitle>
              <DialogDescription>
                Email{' '}
                <a
                  href="mailto:sales@novamind.ai"
                  className="font-medium text-foreground underline-offset-4 hover:underline"
                >
                  sales@novamind.ai
                </a>{' '}
                with your expected monthly tokens and we&apos;ll get back to
                you within one business day.
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end">
              <Button onClick={() => setDialog(null)}>Close</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </>
  );
}
