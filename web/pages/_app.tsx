import '../styles/globals.css';
import type { AppProps } from 'next/app';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { SessionProvider } from '../lib/auth';
import { ThemeProvider } from '../lib/theme';
import AdminLayout from '../components/layout/AdminLayout';
import ThemeToggle from '../components/ThemeToggle';
import ErrorBoundary from '../components/ErrorBoundary';
import { Toaster } from '../components/ui/Toaster';
import { ThemeReveal } from '../components/theme/ThemeReveal';
import { CommandPalette } from '../components/ui/CommandPalette';

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

export default function MyApp({ Component, pageProps }: AppProps) {
  // Wrap with GoogleOAuthProvider ONLY when the env var is set. When
  // unset, the GoogleButton component falls back to a disabled
  // placeholder so the app still boots without a configured OAuth
  // client. Mounting the provider with an empty string would force
  // the GIS script to load and fail at runtime.
  const content = (
    <ThemeProvider>
      <SessionProvider>
        <AppRoot Component={Component} pageProps={pageProps} />
        <Toaster />
        <ThemeReveal />
        <CommandPalette />
      </SessionProvider>
    </ThemeProvider>
  );

  return GOOGLE_CLIENT_ID ? (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>{content}</GoogleOAuthProvider>
  ) : (
    content
  );
}

// Inner root — split out so MyApp's return is always a single element tree
// and the providers each have a single child (no fragments, no arrays).
function AppRoot(props: any) {
  const { Component, pageProps } = props;
  const isAdmin = pageProps?.pathname?.startsWith('/admin');
  const content = isAdmin ? (
    <AdminLayout>
      <Component {...pageProps} />
    </AdminLayout>
  ) : (
    <Component {...pageProps} />
  );

  return (
    <ErrorBoundary>
      <div className="flex min-h-screen flex-col">
        <div className="flex-1">{content}</div>
        <div className="fixed bottom-4 right-4 z-50">
          <ThemeToggle />
        </div>
        <footer className="text-center py-4 text-sm text-muted-foreground w-full">
          Developed By Devang Shah
        </footer>
      </div>
    </ErrorBoundary>
  );
}
