/**
 * Typed client for the `/api/v1/billing/*` endpoints.
 *
 * Used by:
 *   - `web/pages/pricing.tsx` to start a Stripe Checkout session
 *   - `web/pages/billing/*` to show the user's current plan + invoices
 *   - `web/components/AppShell.tsx` to display a plan badge in the
 *     user menu
 *
 * The backend runs in **mock mode** by default — Stripe endpoints
 * return 501 / "not_configured" and every user is implicitly on the
 * Free plan. Callers should treat those errors as "show a friendly
 * 'Stripe not configured' dialog" rather than a hard failure.
 */

import { isMockMode } from './api';

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface PlanInfo {
  /** 'free' | 'pro' | 'business' — matches the slug in `web/lib/plans.ts`. */
  slug: 'free' | 'pro' | 'business';
  name: string;
  /** Monthly token allowance, -1 = unlimited. */
  monthly_token_limit: number;
  /** Monthly request allowance, -1 = unlimited. */
  monthly_request_limit: number;
  /** Current month-to-date usage. */
  monthly_token_count: number;
  monthly_request_count: number;
  /** Pay-as-you-go credits balance in cents. */
  credits_balance_cents: number;
}

export interface Invoice {
  id: string;
  amount_cents: number;
  currency: string;
  status: 'paid' | 'open' | 'void';
  created_at: string;
  hosted_invoice_url?: string;
}

/**
 * True when the backend told us Stripe isn't configured. Callers can
 * branch on this to render a "mock mode" banner or a different CTA.
 */
export class BillingNotConfigured extends Error {
  constructor() {
    super('Stripe is not configured on the backend.');
    this.name = 'BillingNotConfigured';
  }
}

async function getToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('token');
}

async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getToken();
  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });
}

/**
 * Resolve the error shape from a Billing response. The backend may
 * return:
 *   - 401: not signed in
 *   - 501 / 503: Stripe is not configured
 *   - 4xx: validation error
 *   - 5xx: upstream failure
 */
async function explain(res: Response): Promise<string> {
  if (res.status === 401) return 'You need to sign in to manage billing.';
  if (res.status === 501 || res.status === 503) {
    throw new BillingNotConfigured();
  }
  const body = await res.json().catch(() => ({}));
  return body?.detail || `Request failed (${res.status})`;
}

/**
 * Fetch the current user's plan + remaining quota + credits balance.
 * Returns null when the user is not signed in.
 */
export async function getMyPlan(): Promise<PlanInfo | null> {
  if (isMockMode) {
    // Mock backend: every user is on Free. No backend roundtrip.
    return {
      slug: 'free',
      name: 'Free',
      monthly_token_limit: 50_000,
      monthly_request_limit: 500,
      monthly_token_count: 0,
      monthly_request_count: 0,
      credits_balance_cents: 0,
    };
  }
  const token = await getToken();
  if (!token) return null;
  const res = await authedFetch('/billing/plan');
  if (!res.ok) {
    await explain(res);
    return null;
  }
  return res.json();
}

export async function listInvoices(): Promise<Invoice[]> {
  if (isMockMode) return [];
  const res = await authedFetch('/billing/invoices');
  if (!res.ok) {
    await explain(res);
    return [];
  }
  return res.json();
}

/**
 * Start a Stripe Checkout session for the given plan slug. Returns
 * the hosted URL. Throws `BillingNotConfigured` when the backend is
 * running in mock mode — callers should render a friendly dialog.
 */
export async function createCheckoutSession(
  plan: 'pro' | 'business'
): Promise<string> {
  const res = await authedFetch('/billing/checkout-session', {
    method: 'POST',
    body: JSON.stringify({ plan }),
  });
  if (!res.ok) {
    await explain(res);
    throw new Error('Checkout failed');
  }
  const data = await res.json();
  if (!data?.url) throw new BillingNotConfigured();
  return data.url as string;
}

/**
 * Open the Stripe customer portal for self-serve plan changes and
 * invoice history. Throws `BillingNotConfigured` in mock mode.
 */
export async function openBillingPortal(): Promise<string> {
  const res = await authedFetch('/billing/portal', { method: 'POST' });
  if (!res.ok) {
    await explain(res);
    throw new Error('Could not open billing portal');
  }
  const data = await res.json();
  if (!data?.url) throw new BillingNotConfigured();
  return data.url as string;
}
