import { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { LogIn, Sparkles, Mail, Lock, ArrowRight } from 'lucide-react';
import { login, googleLogin, isMockMode } from '../lib/api';
import AuthLayout from '../components/AuthLayout';
import TextField from '../components/TextField';
import GoogleButton from '../components/GoogleButton';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const router = useRouter();

  const emailErr = email && !EMAIL_RE.test(email) ? 'Enter a valid email' : '';
  const pwdErr = password && password.length < 6 ? 'At least 6 characters' : '';
  const canSubmit = EMAIL_RE.test(email) && password.length >= 6 && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError('');
    try {
      const data = await login(email, password);
      localStorage.setItem('token', data.access_token);
      router.push('/chat');
    } catch (err: any) {
      // Mock backend throws plain `new Error('Invalid email or password')`
      // — fall back to a generic message for anything we don't recognise.
      setError(err?.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setGoogleLoading(true);
    setError('');
    try {
      // In mock mode this signs you in as the seeded demo Google user.
      // With a real backend + NEXT_PUBLIC_USE_MOCK=false it would route
      // through Google OAuth (see plan, Phase 1 Option B).
      const data = await googleLogin('demo-token');
      localStorage.setItem('token', data.access_token);
      router.push('/chat');
    } catch (err: any) {
      setError(err?.message || 'Google sign-in failed');
    } finally {
      setGoogleLoading(false);
    }
  };

  const fillDemo = () => {
    setEmail('admin@novamind.ai');
    setPassword('admin123');
  };

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue chatting with NovaMind AI."
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
        <TextField
          id="password"
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          error={pwdErr}
          autoComplete="current-password"
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
              Signing in…
            </>
          ) : (
            <>
              <LogIn className="h-4 w-4" />
              Sign in
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </>
          )}
        </button>
      </form>

      {/* Divider with "or" */}
      <div className="my-6 flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs uppercase tracking-wider text-muted-foreground">or</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <GoogleButton onClick={handleGoogleLogin} loading={googleLoading} />

      {/* Demo mode helper — only visible when running on the mock backend. */}
      {isMockMode && (
        <button
          type="button"
          onClick={fillDemo}
          className="mt-4 flex w-full items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-left transition-colors hover:bg-primary/10"
        >
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground">Try the demo account</p>
            <p className="text-xs text-muted-foreground truncate">
              admin@novamind.ai / admin123
            </p>
          </div>
          <ArrowRight className="h-4 w-4 text-muted-foreground" />
        </button>
      )}

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{' '}
        <Link href="/signup" className="font-semibold text-primary hover:underline">
          Create one
        </Link>
      </p>

      <p className="mt-3 text-center text-xs text-muted-foreground">
        By continuing, you agree to NovaMind AI&apos;s Terms of Service and Privacy Policy.
      </p>
    </AuthLayout>
  );
}