/**
 * `/billing` — user's billing dashboard.
 *
 * Shows:
 *   - Current plan + price + tagline
 *   - Monthly usage bars (tokens / requests) with overage warnings
 *   - Pay-as-you-go credits balance
 *   - Recent invoices table (empty in mock mode)
 *   - "Manage subscription" / "Upgrade" CTAs
 *
 * Mock-mode aware: when Stripe is not configured on the backend the
 * `Manage subscription` button shows a friendly "not configured" dialog
 * instead of trying to open a portal session.
 */
import { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useAuth } from '../../lib/auth';
import {
  CreditCard,
  Sparkles,
  ExternalLink,
  Receipt,
  AlertCircle,
  ArrowUpRight,
  Wallet,
  Zap,
  Activity,
} from 'lucide-react';
import AppShell, { SidebarChatList } from '../../components/AppShell';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Skeleton } from '../../components/ui/Skeleton';
import { Button } from '../../components/ui/Button';
import { GlassCard } from '../../components/dashboard/GlassCard';
import { AnimatedCounter } from '../../components/dashboard/AnimatedCounter';
import { TokenUsageBar } from '../../components/dashboard/TokenUsageBar';
import { StaggerChildren, StaggerItem } from '../../components/motion';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog';
import { Badge } from '../../components/ui/Badge';
import { toast } from '../../components/ui/Toaster';
import {
  getMyPlan,
  listInvoices,
  openBillingPortal,
  BillingNotConfigured,
  type PlanInfo,
  type Invoice,
} from '../../lib/billing';
import { PLANS, formatPrice } from '../../lib/plans';

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function formatNumber(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

function formatCents(cents: number, currency = 'USD'): string {
  const sign = cents < 0 ? '-' : '';
  const abs = Math.abs(cents);
  return `${sign}$${(abs / 100).toFixed(2)} ${currency.toUpperCase()}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

export default function BillingPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showNotConfigured, setShowNotConfigured] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (authLoading) return;
    if (!user) {
      router.replace('/login');
      return;
    }
    refresh();
    // Reload when ?checkout=success lands here after a Stripe redirect.
    if (router.query.checkout === 'success') {
      toast.success('Subscription updated! Welcome aboard.');
      // Strip the query param so a refresh doesn't re-toast.
      const { checkout, ...rest } = router.query;
      void checkout;
      router.replace({ pathname: '/billing', query: rest }, undefined, {
        shallow: true,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, authLoading]);

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const [p, inv] = await Promise.all([getMyPlan(), listInvoices()]);
      setPlan(p);
      setInvoices(inv);
    } catch (e: any) {
      setError(e?.message || 'Failed to load billing data');
    } finally {
      setLoading(false);
    }
  }

  async function handleManage() {
    setBusy(true);
    try {
      const url = await openBillingPortal();
      window.location.href = url;
    } catch (e) {
      if (e instanceof BillingNotConfigured) {
        setShowNotConfigured(true);
      } else {
        toast.error((e as Error)?.message || 'Could not open billing portal');
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleUpgrade(slug: 'pro' | 'business') {
    setBusy(true);
    try {
      const token =
        typeof window !== 'undefined'
          ? window.localStorage.getItem('token')
          : null;
      const res = await fetch(`${API_URL}/billing/checkout-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ plan: slug }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        if (
          res.status === 501 ||
          res.status === 503 ||
          body?.error === 'not_configured' ||
          body?.error === 'stripe_not_configured'
        ) {
          setShowNotConfigured(true);
          return;
        }
        throw new Error(body?.detail || 'Checkout failed');
      }
      const { url } = await res.json();
      if (!url) {
        setShowNotConfigured(true);
        return;
      }
      window.location.href = url;
    } catch (e) {
      if (!(e instanceof BillingNotConfigured)) {
        toast.error((e as Error)?.message || 'Could not start checkout');
      }
    } finally {
      setBusy(false);
    }
  }

  if (!mounted || authLoading || !user) return null;

  const planSlug = plan?.slug ?? 'free';
  const isPaid = planSlug === 'pro' || planSlug === 'business';
  const tokensUsed = plan?.monthly_token_count ?? 0;
  const tokensLimit = plan?.monthly_token_limit ?? 0;
  const reqsUsed = plan?.monthly_request_count ?? 0;
  const reqsLimit = plan?.monthly_request_limit ?? 0;
  const tokenPct =
    tokensLimit > 0 ? Math.min(100, Math.round((tokensUsed / tokensLimit) * 100)) : 0;
  const reqPct =
    reqsLimit > 0 ? Math.min(100, Math.round((reqsUsed / reqsLimit) * 100)) : 0;
  const tokenOver = tokensLimit > 0 && tokensUsed >= tokensLimit;
  const reqOver = reqsLimit > 0 && reqsUsed >= reqsLimit;
  const planMeta = PLANS.find((p) => p.slug === planSlug);

  return (
    <>
      <Head>
        <title>Billing · NovaMind AI</title>
        <meta
          name="description"
          content="Your plan, usage, and invoices for NovaMind AI."
        />
      </Head>
      <AppShell sidebar={<SidebarChatList />}>
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CreditCard className="h-4 w-4" />
              <span>Billing</span>
            </div>
            <h1 className="mt-1 text-3xl font-bold tracking-tight text-foreground">
              Plan &amp; Usage
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Your current plan, this month&apos;s usage, and your invoice history.
            </p>
          </div>

          {error && (
            <div className="mb-6 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-3">
            {/* Plan card */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>Current plan</CardTitle>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {planMeta?.tagline ?? 'Try every model with enough credits to evaluate.'}
                    </p>
                  </div>
                  {loading ? (
                    <Skeleton className="h-6 w-16" />
                  ) : (
                    <Badge
                      variant={
                        planSlug === 'pro'
                          ? 'default'
                          : planSlug === 'business'
                          ? 'success'
                          : 'secondary'
                      }
                    >
                      {plan?.name ?? 'Free'}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-8 w-32" />
                    <Skeleton className="h-4 w-64" />
                    <div className="grid gap-3 pt-2 sm:grid-cols-2">
                      <Skeleton className="h-24 w-full" />
                      <Skeleton className="h-24 w-full" />
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-bold text-foreground">
                        {formatPrice(planMeta?.priceCents ?? 0)}
                      </span>
                      {(planMeta?.priceCents ?? 0) > 0 && (
                        <span className="text-sm text-muted-foreground">/month</span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {isPaid ? 'Billed monthly' : 'Free forever — upgrade any time'}
                    </p>

                    {/* Usage bars */}
                    <div className="mt-6 grid gap-4 sm:grid-cols-2">
                      {tokensLimit > 0 ? (
                        <div className="rounded-lg border border-border bg-background p-3">
                          <TokenUsageBar
                            used={tokensUsed}
                            total={tokensLimit}
                            label="Tokens"
                            unit="tokens"
                          />
                        </div>
                      ) : (
                        <UsageMeter
                          label="Tokens"
                          icon={Zap}
                          used={tokensUsed}
                          limit={tokensLimit}
                          pct={tokenPct}
                          over={tokenOver}
                        />
                      )}
                      <UsageMeter
                        label="Requests"
                        icon={Activity}
                        used={reqsUsed}
                        limit={reqsLimit}
                        pct={reqPct}
                        over={reqOver}
                      />
                    </div>

                    <div className="mt-6 flex flex-wrap gap-2">
                      {isPaid ? (
                        <Button
                          onClick={handleManage}
                          disabled={busy}
                          variant="outline"
                        >
                          <ExternalLink className="h-4 w-4" />
                          Manage subscription
                        </Button>
                      ) : (
                        <>
                          <Button
                            onClick={() => handleUpgrade('pro')}
                            disabled={busy}
                          >
                            <Sparkles className="h-4 w-4" />
                            {busy ? 'Working…' : 'Upgrade to Pro'}
                          </Button>
                          <Button
                            onClick={() => handleUpgrade('business')}
                            disabled={busy}
                            variant="outline"
                          >
                            <ArrowUpRight className="h-4 w-4" />
                            Talk to sales
                          </Button>
                        </>
                      )}
                      <Link
                        href="/pricing"
                        className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
                      >
                        Compare plans
                      </Link>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Credits + upgrade */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Wallet className="h-4 w-4 text-primary" />
                    <CardTitle>Pay-as-you-go credits</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <Skeleton className="h-8 w-32" />
                  ) : (
                    <>
                      <p className="text-2xl font-bold text-foreground">
                        <AnimatedCounter
                          value={(plan?.credits_balance_cents ?? 0) / 100}
                          numberClassName="text-2xl font-bold tabular-nums text-foreground"
                          minFractionDigits={2}
                          maxFractionDigits={2}
                          prefix="$"
                        />
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Used when you exceed plan limits. Add credits via the
                        customer portal.
                      </p>
                    </>
                  )}
                </CardContent>
              </Card>

              {!isPaid && (
                <Card className="overflow-hidden">
                  <div className="gradient-bg p-6 text-white">
                    <Sparkles className="h-5 w-5" />
                    <h3 className="mt-3 text-lg font-semibold">
                      Need more headroom?
                    </h3>
                    <p className="mt-1 text-sm text-white/90">
                      Pro gives you 1M tokens, 10K requests, and 5 API keys.
                    </p>
                    <Button
                      onClick={() => handleUpgrade('pro')}
                      disabled={busy}
                      className="mt-4 bg-white text-primary hover:bg-white/90 hover:text-primary"
                    >
                      Upgrade now
                    </Button>
                  </div>
                </Card>
              )}
            </div>
          </div>

          {/* Invoices */}
          <Card className="mt-8">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Receipt className="h-4 w-4 text-primary" />
                <CardTitle>Recent invoices</CardTitle>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Stripe-issued invoices for the past 12 months.
              </p>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-3">
                  {[0, 1, 2].map((i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : invoices.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border bg-muted/30 px-6 py-10 text-center">
                  <Receipt className="mx-auto h-6 w-6 text-muted-foreground" />
                  <p className="mt-2 text-sm font-medium text-foreground">
                    No invoices yet
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Invoices appear here once you upgrade to a paid plan.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="py-2 pr-4 font-medium">Date</th>
                        <th className="py-2 pr-4 font-medium">Invoice</th>
                        <th className="py-2 pr-4 font-medium">Amount</th>
                        <th className="py-2 pr-4 font-medium">Status</th>
                        <th className="py-2 pr-4 font-medium text-right">PDF</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoices.map((inv) => (
                        <tr key={inv.id} className="border-b border-border/60">
                          <td className="py-2 pr-4 text-foreground">
                            {formatDate(inv.created_at)}
                          </td>
                          <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                            {inv.id}
                          </td>
                          <td className="py-2 pr-4 text-foreground">
                            {formatCents(inv.amount_cents, inv.currency)}
                          </td>
                          <td className="py-2 pr-4">
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                                inv.status === 'paid'
                                  ? 'bg-green-500/10 text-green-700 dark:text-green-300'
                                  : inv.status === 'void'
                                  ? 'bg-muted text-muted-foreground'
                                  : 'bg-amber-500/10 text-amber-700 dark:text-amber-300'
                              }`}
                            >
                              {inv.status}
                            </span>
                          </td>
                          <td className="py-2 pr-4 text-right">
                            {inv.hosted_invoice_url ? (
                              <a
                                href={inv.hosted_invoice_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                              >
                                View <ExternalLink className="h-3 w-3" />
                              </a>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Stripe-not-configured dialog (mock mode) */}
        <Dialog
          open={showNotConfigured}
          onOpenChange={setShowNotConfigured}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Billing isn&apos;t configured yet</DialogTitle>
              <DialogDescription>
                You&apos;re on the {plan?.name ?? 'Free'} plan. To enable real
                billing, set <code>STRIPE_SECRET_KEY</code> and{' '}
                <code>STRIPE_WEBHOOK_SECRET</code> in <code>backend/.env</code>,
                then restart the backend. Until then, the app runs in mock
                mode — every user is on the Free plan and the customer
                portal is unavailable.
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setShowNotConfigured(false)}
              >
                Got it
              </Button>
              <Link href="/docs">
                <Button>Read the docs</Button>
              </Link>
            </div>
          </DialogContent>
        </Dialog>
      </AppShell>
    </>
  );
}

function UsageMeter({
  label,
  icon: Icon,
  used,
  limit,
  pct,
  over,
}: {
  label: string;
  icon: typeof Zap;
  used: number;
  limit: number;
  pct: number;
  over: boolean;
}) {
  const unlimited = limit <= 0;
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex items-center justify-between text-xs">
        <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
          {label}
        </span>
        {unlimited ? (
          <span className="text-muted-foreground">Unlimited</span>
        ) : (
          <span className={over ? 'font-semibold text-destructive' : 'text-muted-foreground'}>
            {formatNumber(used)} / {formatNumber(limit)}
          </span>
        )}
      </div>
      {!unlimited && (
        <>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full ${
                pct >= 90 ? 'bg-destructive' : pct >= 70 ? 'bg-amber-500' : 'bg-primary'
              }`}
              style={{ width: `${pct}%` }}
            />
          </div>
          {over && (
            <p className="mt-1.5 text-[10px] font-medium text-destructive">
              Limit reached — upgrade to keep going
            </p>
          )}
        </>
      )}
    </div>
  );
}
