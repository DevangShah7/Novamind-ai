import '../styles/globals.css';
import type { AppProps } from 'next/app';
import { SessionProvider } from '../lib/auth';
import { ThemeProvider } from '../lib/theme';
import AdminLayout from '../components/layout/AdminLayout';
import ThemeToggle from '../components/ThemeToggle';

export default function MyApp({ Component, pageProps }: AppProps) {
  // Use admin layout for admin routes
  const ComponentToUse = pageProps.pathname?.startsWith('/admin')
    ? (props: any) => <AdminLayout><Component {...props} /></AdminLayout>
    : Component;

  return (
    <ThemeProvider>
      <SessionProvider>
        <ComponentToUse {...pageProps} />
        {/* Floating theme toggle — every page, never overlaps content
            (bottom-right with 16px margin). Hidden on tiny mobile
            widths under the auth hero by CSS, but kept mounted so the
            choice is always reachable. */}
        <div className="fixed bottom-4 right-4 z-50">
          <ThemeToggle />
        </div>
        <footer className="text-center py-4 text-sm text-muted-foreground w-full">
          Developed By Devang Shah
        </footer>
      </SessionProvider>
    </ThemeProvider>
  );
}
