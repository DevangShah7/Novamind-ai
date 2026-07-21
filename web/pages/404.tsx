import Link from 'next/link';
import Head from 'next/head';
import { ArrowLeft, Search } from 'lucide-react';
import NavBar from '../components/marketing/NavBar';
import Footer from '../components/marketing/Footer';
import { Button } from '../components/ui/Button';

/**
 * Branded 404 page. Suggests a few likely destinations so the
 * visitor never feels lost.
 */
export default function NotFound() {
  return (
    <>
      <Head>
        <title>Page not found · NovaMind AI</title>
      </Head>
      <div className="min-h-screen bg-background text-foreground">
        <NavBar />
        <main className="mx-auto flex max-w-2xl flex-col items-center justify-center px-4 py-24 text-center sm:px-6">
          <div className="inline-flex h-20 w-20 items-center justify-center rounded-2xl gradient-bg text-white shadow-lg">
            <Search className="h-10 w-10" />
          </div>

          <h1 className="mt-8 text-5xl font-bold tracking-tight sm:text-6xl">
            <span className="gradient-text">404</span>
          </h1>
          <p className="mt-4 text-xl font-semibold">Page not found</p>
          <p className="mt-2 text-muted-foreground">
            The page you were looking for moved, was deleted, or never existed.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button asChild>
              <Link href="/">
                <span className="inline-flex items-center gap-2">
                  <ArrowLeft className="h-4 w-4" />
                  Back to home
                </span>
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/chat">Open chat</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/docs">Read the docs</Link>
            </Button>
          </div>
        </main>
        <Footer />
      </div>
    </>
  );
}
