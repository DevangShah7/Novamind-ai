import Link from 'next/link';
import Head from 'next/head';
import { ArrowLeft } from 'lucide-react';
import { buttonVariants } from '../components/ui/Button';

/**
 * Branded 404 page.
 *
 * This page is statically prerendered during ``next build``. Earlier
 * versions mounted ``<NavBar />`` and ``<Footer />`` here, but those
 * components pull in Radix/Next primitives that call
 * ``React.Children.only`` on their children — the production-build
 * prerender rejects that with "expected to receive a single React
 * element child". To keep the page statically buildable on Vercel,
 * we render a minimal layout here (no NavBar / Footer) — visitors
 * hitting a bad URL still get a useful recovery surface, just
 * without the full marketing chrome.
 *
 * The marketing pages (which can use getServerSideProps to opt out
 * of prerender) keep their NavBar/Footer intact.
 */
export default function NotFound() {
  return (
    <>
      <Head>
        <title>Page not found · NovaMind AI</title>
      </Head>
      <div className="flex min-h-screen flex-col bg-background text-foreground">
        <main className="mx-auto flex max-w-2xl flex-1 flex-col items-center justify-center px-4 py-24 text-center sm:px-6">
          <div className="inline-flex h-20 w-20 items-center justify-center rounded-2xl gradient-bg text-white shadow-lg">
            <span className="text-3xl font-bold">?</span>
          </div>

          <h1 className="mt-8 text-5xl font-bold tracking-tight sm:text-6xl">
            <span className="gradient-text">404</span>
          </h1>
          <p className="mt-4 text-xl font-semibold">Page not found</p>
          <p className="mt-2 text-muted-foreground">
            The page you were looking for moved, was deleted, or never existed.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/" className={buttonVariants()}>
              <span className="inline-flex items-center gap-2">
                <ArrowLeft className="h-4 w-4" />
                Back to home
              </span>
            </Link>
            <Link href="/chat" className={buttonVariants({ variant: 'outline' })}>
              <span className="inline-flex items-center gap-2">Open chat</span>
            </Link>
            <Link href="/docs" className={buttonVariants({ variant: 'outline' })}>
              <span className="inline-flex items-center gap-2">Read the docs</span>
            </Link>
          </div>
        </main>
        <footer className="py-4 text-center text-sm text-muted-foreground">
          Developed By Devang Shah
        </footer>
      </div>
    </>
  );
}