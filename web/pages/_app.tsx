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
        {/* Wrap in a single fragment-like container so SessionProvider
            always receives exactly one child — avoids React.Children.only
            errors if a child provider introspects children. */}
        <div className="flex min-h-screen flex-col">
          <div className="flex-1">
            <ComponentToUse {...pageProps} />
          </div>
          {/* Floating theme toggle — every page, never overlaps content. */}
          <div className="fixed bottom-4 right-4 z-50">
            <ThemeToggle />
          </div>
          <footer className="text-center py-4 text-sm text-muted-foreground w-full">
            Developed By Devang Shah
          </footer>
        </div>
      </SessionProvider>
    </ThemeProvider>
  );
}