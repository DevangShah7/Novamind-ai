import '../styles/globals.css';
import type { AppProps } from 'next/app';
import { SessionProvider } from '../lib/auth';
import AdminLayout from '../components/layout/AdminLayout';

export default function MyApp({ Component, pageProps }: AppProps) {
  // Use admin layout for admin routes
  const ComponentToUse = pageProps.pathname?.startsWith('/admin')
    ? (props: any) => <AdminLayout><Component {...props} /></AdminLayout>
    : Component;

  return (
    <SessionProvider>
      <ComponentToUse {...pageProps} />
      <footer className="text-center py-4 text-sm text-gray-500 w-full">
        Developed By Devang Shah
      </footer>
    </SessionProvider>
  );
}