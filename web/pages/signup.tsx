import { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { UserPlus, ArrowRight, Check, X } from 'lucide-react';
import { register } from '../lib/api';
import AuthLayout from '../components/AuthLayout';
import TextField from '../components/TextField';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getPasswordStrength(pwd: string): { score: number; label: string; color: string } {
  let score = 0;
  if (pwd.length >= 6) score++;
  if (pwd.length >= 10) score++;
  if (/[A-Z]/.test(pwd)) score++;
  if (/[0-9]/.test(pwd)) score++;
  if (/[^A-Za-z0-9]/.test(pwd)) score++;
  const labels = ['Too short', 'Weak', 'Fair', 'Good', 'Strong', 'Excellent'];
  const colors = ['bg-muted', 'bg-destructive', 'bg-orange-500', 'bg-amber-500', 'bg-emerald-500', 'bg-emerald-600'];
  return { score, label: labels[score], color: colors[score] };
}

export default function Signup() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const emailErr = email && !EMAIL_RE.test(email) ? 'Enter a valid email' : '';
  const pwdErr = password && password.length < 6 ? 'At least 6 characters' : '';
  const confirmErr = confirm && confirm !== password ? "Passwords don't match" : '';
  const strength = getPasswordStrength(password);

  const canSubmit =
    EMAIL_RE.test(email) &&
    password.length >= 6 &&
    confirm === password &&
    !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError('');
    try {
      const data = await register(email, password);
      localStorage.setItem('token', data.access_token);
      router.push('/chat');
    } catch (err: any) {
      // Mock backend throws `new Error('Email already registered')` etc.
      // Old code expected `err.response.data.detail` (axios shape) — that
      // was always undefined, so users always saw the generic fallback.
      setError(err?.message || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Free forever. No credit card. Two minutes to set up."
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

        <div>
          <TextField
            id="password"
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            error={pwdErr}
            autoComplete="new-password"
            required
          />
          {password.length > 0 && (
            <div className="mt-2 flex items-center gap-2">
              <div className="flex flex-1 gap-1">
                {[0, 1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className={`h-1 flex-1 rounded-full transition-colors ${
                      i < strength.score ? strength.color : 'bg-muted'
                    }`}
                  />
                ))}
              </div>
              <span className="text-xs font-medium text-muted-foreground">
                {strength.label}
              </span>
            </div>
          )}
        </div>

        <TextField
          id="confirm"
          label="Confirm password"
          type="password"
          value={confirm}
          onChange={setConfirm}
          error={confirmErr}
          autoComplete="new-password"
          required
        />

        {/* Password checklist — visible once the user starts typing. */}
        {password.length > 0 && (
          <ul className="space-y-1 text-xs text-muted-foreground">
            <li className="flex items-center gap-1.5">
              {password.length >= 6 ? (
                <Check className="h-3.5 w-3.5 text-emerald-500" />
              ) : (
                <X className="h-3.5 w-3.5 text-muted-foreground" />
              )}
              At least 6 characters
            </li>
            <li className="flex items-center gap-1.5">
              {confirm && confirm === password ? (
                <Check className="h-3.5 w-3.5 text-emerald-500" />
              ) : (
                <X className="h-3.5 w-3.5 text-muted-foreground" />
              )}
              Passwords match
            </li>
          </ul>
        )}

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
              Creating account…
            </>
          ) : (
            <>
              <UserPlus className="h-4 w-4" />
              Create account
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </>
          )}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link href="/login" className="font-semibold text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
