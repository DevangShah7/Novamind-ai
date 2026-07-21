import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { CheckCircle2, XCircle, ArrowRight, MailQuestion } from 'lucide-react';
import { verifyEmail } from '../lib/api';
import AuthLayout from '../components/AuthLayout';

type Status = 'verifying' | 'success' | 'error';

/**
 * Handles the link from the verification email.
 *
 *   /verify-email?token=...
 *
 * Calls POST /auth/verify-email, then on success redirects to
 * /login?registered=1 so the login page can show a "you're verified!"
 * toast and let the user sign in.
 *
 * The token can be missing (user navigated here directly) or
 * expired/used (we land here from an old link). Both paths show a
 * friendly message with a "resend" affordance.
 */
export default function VerifyEmail() {
  const router = useRouter();
  const [status, setStatus] = useState<Status>('verifying');
  const [message, setMessage] = useState('Verifying your email…');
  // Track whether we've kicked off the verify call yet, so React
  // StrictMode's double-invoke in dev doesn't burn the token twice.
  const started = useRef(false);

  useEffect(() => {
    if (!router.isReady) return;
    const token = typeof router.query.token === 'string' ? router.query.token : '';
    if (!token) {
      setStatus('error');
      setMessage('This link is missing a verification token. Use the most recent email we sent.');
      return;
    }
    if (started.current) return;
    started.current = true;

    (async () => {
      try {
        await verifyEmail(token);
        setStatus('success');
        // Brief pause so the user reads the success state, then
        // bounce to /login with a query param that triggers the
        // "verified!" toast.
        setTimeout(() => {
          router.replace('/login?registered=1');
        }, 1200);
      } catch (err: any) {
        setStatus('error');
        setMessage(err?.message || 'This link is invalid or has expired.');
      }
    })();
  }, [router.isReady, router.query.token, router]);

  if (status === 'verifying') {
    return (
      <AuthLayout
        title="Verifying your email"
        subtitle="One moment while we confirm your token."
      >
        <div className="flex flex-col items-center gap-4 py-6">
          <span className="h-10 w-10 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
      </AuthLayout>
    );
  }

  if (status === 'success') {
    return (
      <AuthLayout
        title="Email verified"
        subtitle="You're all set. Taking you to sign in…"
      >
        <div className="flex flex-col items-center gap-4 py-6">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600">
            <CheckCircle2 className="h-7 w-7" />
          </div>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
      </AuthLayout>
    );
  }

  // status === 'error'
  return (
    <AuthLayout
      title="We couldn't verify that link"
      subtitle="The token may be invalid, expired, or already used."
    >
      <div className="space-y-5">
        <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3">
          <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
          <p className="text-sm text-destructive">{message}</p>
        </div>

        <p className="text-sm text-muted-foreground">
          You can request a fresh verification email from the signup page.
        </p>

        <div className="flex flex-col gap-2">
          <Link
            href="/signup"
            legacyBehavior
            className="flex w-full items-center justify-center gap-2 rounded-lg gradient-bg px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:shadow-lg hover:scale-[1.01] active:scale-[0.99]"
          >
            <a className="flex w-full items-center justify-center gap-2">
              <MailQuestion className="h-4 w-4" />
              Send a new verification email
              <ArrowRight className="h-4 w-4" />
            </a>
          </Link>
          <Link
            href="/login"
            className="text-center text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
