import '../styles/globals.css';
import type { AppProps } from 'next/app';
import { SessionProvider } from '../lib/auth';
import { ThemeProvider } from '../lib/theme';
import AdminLayout from '../components/layout/AdminLayout';
import ThemeToggle from '../components/ThemeToggle';

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <ThemeProvider>
      <SessionProvider>
        <AppRoot Component={Component} pageProps={pageProps} />
      </SessionProvider>
    </ThemeProvider>
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
    <div className="flex min-h-screen flex-col">
      <div className="flex-1">{content}</div>
      <div className="fixed bottom-4 right-4 z-50">
        <ThemeToggle />
      </div>
      <footer className="text-center py-4 text-sm text-muted-foreground w-full">
        Developed By Devang Shah
      </footer>
    </div>
  );
}