/**
 * Single source of truth for plan tiers.
 *
 * Backend seeding is owned by `app/models/billing.py` — keep slugs in
 * sync with the database. CTAs are wired client-side: they call
 * `POST /api/v1/billing/checkout-session` when Stripe is configured
 * or open a "not configured" dialog in mock mode (see
 * `web/pages/pricing.tsx`).
 */
import { Check, Sparkles, Rocket, Building2 } from 'lucide-react';

export interface PlanFeature {
  /** Bullet text shown in the card. */
  label: string;
  /** Optional: a small superscript hint, e.g. "soon" or "beta". */
  hint?: string;
}

export interface Plan {
  /** Stable id, also the DB slug. */
  slug: 'free' | 'pro' | 'business';
  /** Display name. */
  name: string;
  /** One-line tagline. */
  tagline: string;
  /** Monthly price in cents (USD). 0 = free. */
  priceCents: number;
  /** Bulleted feature list. */
  features: PlanFeature[];
  /** CTA button label. */
  cta: string;
  /** CTA destination: "signup" | "checkout" | "contact". */
  ctaKind: 'signup' | 'checkout' | 'contact';
  /** Highlight card with a "Most popular" ribbon. */
  popular?: boolean;
  /** Lucide icon to render at the top of the card. */
  icon: typeof Sparkles;
}

export const PLANS: Plan[] = [
  {
    slug: 'free',
    name: 'Free',
    tagline: 'Try every model with enough credits to evaluate.',
    priceCents: 0,
    icon: Sparkles,
    features: [
      { label: '50,000 tokens / month' },
      { label: '500 requests / month' },
      { label: '1 API key' },
      { label: 'Community support' },
    ],
    cta: 'Start free',
    ctaKind: 'signup',
  },
  {
    slug: 'pro',
    name: 'Pro',
    tagline: 'For builders shipping with AI in their projects.',
    priceCents: 1900,
    icon: Rocket,
    popular: true,
    features: [
      { label: '1,000,000 tokens / month' },
      { label: '10,000 requests / month' },
      { label: '5 API keys' },
      { label: 'IP allowlist per key' },
      { label: 'Email support' },
    ],
    cta: 'Subscribe to Pro',
    ctaKind: 'checkout',
  },
  {
    slug: 'business',
    name: 'Business',
    tagline: 'For teams that need quotas, SSO, and a real SLA.',
    priceCents: 9900,
    icon: Building2,
    features: [
      { label: '10,000,000 tokens / month' },
      { label: '100,000 requests / month' },
      { label: 'Unlimited API keys' },
      { label: 'Per-key usage analytics' },
      { label: 'Priority support + 99.9% SLA' },
    ],
    cta: 'Talk to sales',
    ctaKind: 'contact',
  },
];

export function formatPrice(priceCents: number): string {
  if (priceCents === 0) return '$0';
  return `$${(priceCents / 100).toFixed(0)}`;
}
