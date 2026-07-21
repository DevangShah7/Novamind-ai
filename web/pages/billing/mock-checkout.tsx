/**
 * `/billing/mock-checkout` — the dev-only "fake Stripe" page.
 *
 * Triggered by the mock-mode response from `POST /billing/checkout-session`.
 * Renders the plan name + price + a "Confirm subscription" button that
 * POSTs a synthetic `checkout.session.completed` event to
 * `/api/v1/billing/webhook` (with a `mock_`-prefixed event id, which
 * the webhook handler uses as a forgery guard), then redirects to
 * `/billing?checkout=success`.
 *
 * Real-mode users never see this page — Stripe redirects them straight
 * to its hosted checkout instead.
 */
import { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Check, ShieldCheck, Sparkles, ArrowLeft } from 'lucide-react';
import { Card, CardContent } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { toast } from '../../components/ui/Toaster';
import { PLANS, formatPrice } from '../../lib/plans';

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface MockSession {
  session_id: string;
  plan_slug: 'pro' | 'business';
}

/**
 * Parse `?session=mock_xxx&plan=pro` from the URL. Returns null when
 * we're not on a real mock-checkout URL (e.g. someone navigated here
 * directly), in which case we render a polite "invalid session" card.
 */
function parseSession(): MockSession | null {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.search);
  const session_id = params.get('session');
  const plan_slug = params.get('plan');
  if (!session_id || !session_id.startsWith('mock_')) return null;
  if (plan_slug !== 'pro' && plan_slug !== 'business') return null;
  return { session_id, plan_slug };
}

export default function MockCheckoutPage() {
  const router = useRouter();
  const [session, setSession] = useState<MockSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setSession(parseSession());
  }, []);

  const plan = session ? PLANS.find((p) => p.slug === session.plan_slug) : null;

  async function handleConfirm() {
    if (!session) return;
    setBusy(true);
    try {
      const token =
        typeof window !== 'undefined'
          ? window.localStorage.getItem('token')
          : null;
      if (!token) {
        toast.error('You need to sign in first.');
        router.push('/login');
        return;
      }
      // We need the user id to populate `metadata.user_id` so the
      // webhook handler can flip the right row. The /users/me endpoint
      // is the cheapest way to get it.
      const meRes = await fetch(`${API_URL}/users/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!meRes.ok) {
        toast.error('Could not load your account. Please sign in again.');
        router.push('/login');
        return;
      }
      const me = await meRes.json();

      // Synthesize a checkout.session.completed event. The id MUST start
      // with "mock_" so the webhook handler's forgery guard accepts it.
      const event = {
        id: session.session_id, // already mock_-prefixed
        type: 'checkout.session.completed',
        data: {
          object: {
            id: session.session_id,
            mode: 'subscription',
            metadata: {
              user_id: String(me.id),
              plan_slug: session.plan_slug,
            },
            client_reference_id: String(me.id),
          },
        },
      };

      // The webhook endpoint doesn't require auth (Stripe can't sign
      // with our bearer token) — but the mock handler does require the
      // `mock_` prefix in the event id, which is our auth.
      const res = await fetch(`${API_URL}/billing/webhook`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(event),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || `Webhook failed (${res.status})`);
      }
      toast.success('Subscription activated! (mock mode)');
      router.push('/billing?checkout=success');
    } catch (e) {
      toast.error((e as Error)?.message || 'Mock checkout failed');
    } finally {
      setBusy(false);
    }
  }

  if (!mounted) return null;

  // Invalid or missing session — show a polite error card with a
  // "back to pricing" CTA. This is what someone gets if they paste
  // the URL into a private window.
  if (!session || !plan) {
    return (
      <>
        <Head>
          <title>Mock checkout · NovaMind AI</title>
        </Head>
        <div className="flex min-h-screen items-center justify-center bg-background p-4 text-foreground">
          <Card className="w-full max-w-md">
            <CardContent className="p-6 text-center">
              <h1 className="text-lg font-semibold">Invalid mock session</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                This page is only reachable from the mock-mode checkout flow.
                Start at the pricing page to see it in action.
              </p>
              <Link
                href="/pricing"
                legacyBehavior
                className="mt-4 inline-block"
              >
                <a>
                  <Button>Back to pricing</Button>
                </a>
              </Link>
            </CardContent>
          </Card>
        </div>
      </>
    );
  }

  return (
    <>
      <Head>
        <title>Confirm subscription · NovaMind AI</title>
        <meta name="robots" content="noindex,nofollow" />
      </Head>
      <div className="flex min-h-screen items-center justify-center bg-background p-4 text-foreground">
        <div className="w-full max-w-md">
          {/* Mock-mode banner */}
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
            <ShieldCheck className="h-3.5 w-3.5 flex-shrink-0" />
            <span>
              <strong>Mock mode:</strong> this is a dev-only checkout
              stand-in. No real card is charged.
            </span>
          </div>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Sparkles className="h-4 w-4" />
                <span>Confirm subscription</span>
              </div>
              <h1 className="mt-2 text-2xl font-bold tracking-tight">
                Subscribe to {plan.name}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {plan.tagline}
              </p>

              <div className="mt-5 rounded-lg border border-border bg-muted/30 p-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-muted-foreground">
                    {plan.name} plan
                  </span>
                  <span className="text-2xl font-bold">
                    {formatPrice(plan.priceCents)}
                    <span className="text-xs font-normal text-muted-foreground">
                      /mo
                    </span>
                  </span>
                </div>
                <ul className="mt-3 space-y-1.5 text-sm">
                  {plan.features.map((f) => (
                    <li key={f.label} className="flex items-start gap-2">
                      <Check className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-primary" />
                      <span>{f.label}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {busy ? (
                <div className="mt-5 space-y-2">
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : (
                <div className="mt-5 space-y-2">
                  <Button
                    onClick={handleConfirm}
                    disabled={busy}
                    className="w-full"
                  >
                    <Check className="h-4 w-4" />
                    Confirm subscription
                  </Button>
                  <Link
                    href="/pricing"
                    legacyBehavior
                    className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-input bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
                  >
                    <a className="flex w-full items-center justify-center gap-1.5">
                      <ArrowLeft className="h-3.5 w-3.5" />
                      Cancel and go back
                    </a>
                  </Link>
                </div>
              )}

              <p className="mt-4 text-center text-[10px] text-muted-foreground">
                Session id:{' '}
                <code className="font-mono">{session.session_id}</code>
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
