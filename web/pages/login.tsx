import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { LogIn, Sparkles, Mail, Lock, ArrowRight, CheckCircle2 } from 'lucide-react';
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
  // Transient banner shown when the user lands here from
  // /verify-email?token=... (registered=1) or /reset-password success.
  // Auto-dismisses after 6 s.
  const [banner, setBanner] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!router.isReady) return;
    if (router.query.registered === '1') {
      setBanner('Email verified — you can sign in now.');
      // Clean the URL so a refresh doesn't re-show the banner.
      router.replace('/login', undefined, { shallow: true });
    } else if (router.query.reset === '1') {
      setBanner('Password updated — sign in with your new password.');
      router.replace('/login', undefined, { shallow: true });
    }
  }, [router.isReady, router.query.registered, router.query.reset, router]);

  useEffect(() => {
    if (!banner) return;
    const t = setTimeout(() => setBanner(null), 6000);
    return () => clearTimeout(t);
  }, [banner]);

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

  const handleGoogleCredential = async (idToken: string) => {
    setGoogleLoading(true);
    setError('');
    try {
      const data = await googleLogin(idToken);
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

  // Auto-fill (and submit, if ?go=1 is set) on ?demo=demo creds so a
  // shared link `https://...vercel.app/login?demo=demo` Just Works.
  useEffect(() => {
    if (!router.isReady) return;
    const which = router.query.demo;
    if (which === 'demo') {
      setEmail('demo@novamind.ai');
      setPassword('demo123');
      if (router.query.go === '1') {
        // small delay so state propagates
        setTimeout(() => {
          const f = document.getElementById('login-submit-btn') as HTMLButtonElement | null;
          f?.click();
        }, 100);
      }
    } else if (which === 'devang') {
      setEmail('devang@novamind.ai');
      setPassword('NovaMind2026!');
      if (router.query.go === '1') {
        setTimeout(() => {
          const f = document.getElementById('login-submit-btn') as HTMLButtonElement | null;
          f?.click();
        }, 100);
      }
    }
  }, [router.isReady, router.query.demo, router.query.go]);

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue chatting with NovaMind AI."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {banner && (
          <div className="flex items-start gap-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-2.5 text-sm text-emerald-700 dark:text-emerald-300 animate-fade-in">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{banner}</span>
          </div>
        )}
        {/* Production demo helper — pinned so anyone landing on the page
            can sign in without hunting for credentials. Hidden in real
            local dev because mock mode already has its own helper. */}
        <button
          type="button"
          onClick={() => {
            setEmail('demo@novamind.ai');
            setPassword('demo123');
            // Submit on the next tick so React state has propagated.
            setTimeout(() => {
              const f = document.getElementById('login-submit-btn') as HTMLButtonElement | null;
              f?.click();
            }, 50);
          }}
          className="flex w-full items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-left transition-colors hover:bg-primary/10"
        >
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground">Use demo credentials</p>
            <p className="text-xs text-muted-foreground truncate">
              demo@novamind.ai / demo123
            </p>
          </div>
          <ArrowRight className="h-4 w-4 text-muted-foreground" />
        </button>
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
            autoComplete="current-password"
            required
          />
          <div className="mt-1.5 flex justify-end">
            <Link
              href="/forgot-password"
              className="text-xs font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              Forgot password?
            </Link>
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive animate-fade-in">
            {error}
          </div>
        )}

        <button
          id="login-submit-btn"
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

      <GoogleButton onCredential={handleGoogleCredential} loading={googleLoading} />

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