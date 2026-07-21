import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { CheckCircle2, XCircle, ArrowRight, Lock, ArrowLeft } from 'lucide-react';
import { resetPassword } from '../lib/api';
import AuthLayout from '../components/AuthLayout';
import TextField from '../components/TextField';

type Status = 'form' | 'submitting' | 'success' | 'error';

/**
 * Handles the link from the password-reset email.
 *
 *   /reset-password?token=...
 *
 * On submit, calls POST /auth/reset-password with the new password.
 * On success, bounces the user to /login?reset=1 so the login page
 * can show a "password updated" banner.
 *
 * If the token is missing (user navigated here directly) or the link
 * has been used/expired, we land on a friendly recovery panel.
 */
export default function ResetPassword() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [status, setStatus] = useState<Status>('form');
  const [error, setError] = useState('');
  const [token, setToken] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);
  // Auto-submit guard for React StrictMode's double-invoke in dev.
  const submitted = useRef(false);

  useEffect(() => {
    if (!router.isReady) return;
    const t = typeof router.query.token === 'string' ? router.query.token : '';
    if (!t) {
      setTokenError(
        'This page needs the reset link from your email. Use the most recent reset email we sent.'
      );
      return;
    }
    setToken(t);
  }, [router.isReady, router.query.token]);

  const pwdErr = password && password.length < 8 ? 'At least 8 characters' : '';
  const confirmErr = confirm && confirm !== password ? "Passwords don't match" : '';
  const canSubmit =
    !!token && password.length >= 8 && confirm === password && status === 'form';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || !token) return;
    if (submitted.current) return;
    submitted.current = true;
    setStatus('submitting');
    setError('');
    try {
      await resetPassword(token, password);
      setStatus('success');
      setTimeout(() => {
        router.replace('/login?reset=1');
      }, 1200);
    } catch (err: any) {
      setStatus('form');
      submitted.current = false;
      setError(err?.message || 'Could not reset password. The link may be expired.');
    }
  };

  if (tokenError) {
    return (
      <AuthLayout
        title="Reset link missing"
        subtitle="Open the link from the email we sent you."
      >
        <div className="space-y-5">
          <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3">
            <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <p className="text-sm text-destructive">{tokenError}</p>
          </div>
          <Link
            href="/forgot-password"
            className="flex w-full items-center justify-center gap-2 rounded-lg gradient-bg px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:shadow-lg hover:scale-[1.01] active:scale-[0.99]"
          >
            <span className="inline-flex items-center gap-2">
              Request a new reset link
              <ArrowRight className="h-4 w-4" />
            </span>
          </Link>
          <Link
            href="/login"
            className="text-center text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Back to sign in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  if (status === 'success') {
    return (
      <AuthLayout
        title="Password updated"
        subtitle="Taking you to sign in…"
      >
        <div className="flex flex-col items-center gap-4 py-6">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600">
            <CheckCircle2 className="h-7 w-7" />
          </div>
          <p className="text-sm text-muted-foreground">
            Your password has been changed. Sign in with the new one.
          </p>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Set a new password"
      subtitle="Choose something memorable — at least 8 characters."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <TextField
          id="password"
          label="New password"
          type="password"
          value={password}
          onChange={setPassword}
          error={pwdErr}
          autoComplete="new-password"
          required
        />
        <TextField
          id="confirm"
          label="Confirm new password"
          type="password"
          value={confirm}
          onChange={setConfirm}
          error={confirmErr}
          autoComplete="new-password"
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
          {status === 'submitting' ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              Updating password…
            </>
          ) : (
            <>
              <Lock className="h-4 w-4" />
              Update password
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </>
          )}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        <Link
          href="/login"
          legacyBehavior
          className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
        >
          <a className="inline-flex items-center gap-1">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to sign in
          </a>
        </Link>
      </p>
    </AuthLayout>
  );
}
