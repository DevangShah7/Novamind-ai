import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, KeyRound, CheckCircle2 } from 'lucide-react';
import { forgotPassword } from '../lib/api';
import AuthLayout from '../components/AuthLayout';
import TextField from '../components/TextField';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * "Forgot password" entry point.
 *
 * The backend always returns 200 (even when the email is unknown) to
 * avoid leaking which addresses are registered. So this page shows
 * the same neutral "we sent a link if the account exists" message
 * for every submission — there's no success/failure branch to show.
 *
 * In dev (SMTP_HOST empty), the link lands in backend/logs/dev-mail.log
 * — see the local-dev banner below the form.
 */
export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const emailErr = email && !EMAIL_RE.test(email) ? 'Enter a valid email' : '';
  const canSubmit = EMAIL_RE.test(email) && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError('');
    try {
      await forgotPassword(email);
      setSubmitted(true);
    } catch (err: any) {
      // Network errors do surface here, but the backend will never
      // 404 on an unknown email.
      setError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <AuthLayout
        title="Check your inbox"
        subtitle="If that account exists, we just sent a reset link."
      >
        <div className="space-y-5">
          <div className="flex items-center gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <p className="text-sm text-foreground">
              If an account exists for{' '}
              <span className="font-medium">{email}</span>, a reset link is on
              its way. The link expires in 1 hour.
            </p>
          </div>

          <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">Local dev tip</p>
            <p className="mt-1">
              When <code className="rounded bg-background px-1 py-0.5">SMTP_HOST</code> is
              empty, the email is written to{' '}
              <code className="rounded bg-background px-1 py-0.5">backend/logs/dev-mail.log</code>{' '}
              instead of being sent. Open that file to grab the reset link.
            </p>
          </div>

          <Link
            href="/login"
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 py-2.5 text-sm font-semibold text-foreground transition-all hover:bg-muted"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to sign in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Forgot your password?"
      subtitle="Enter the email you used to sign up. We'll send a link to set a new password."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <TextField
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          error={emailErr}
          autoComplete="email"
          required
        />

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive animate-fade-in">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          className="group flex w-full items-center justify-center gap-2 rounded-lg gradient-bg px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:shadow-lg hover:scale-[1.01] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
        >
          {loading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              Sending link…
            </>
          ) : (
            <>
              <KeyRound className="h-4 w-4" />
              Send reset link
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </>
          )}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Remembered it?{' '}
        <Link href="/login" className="font-semibold text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
