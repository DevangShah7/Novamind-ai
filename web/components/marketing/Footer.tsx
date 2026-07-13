import Link from 'next/link';
import { Brain, Github, Twitter } from 'lucide-react';

/**
 * Public-facing site footer. Used by the landing and pricing pages.
 */
export default function Footer() {
  return (
    <footer className="border-t border-border/60 bg-background">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-bg text-white">
                <Brain className="h-5 w-5" />
              </div>
              <span className="text-lg font-bold tracking-tight">NovaMind AI</span>
            </Link>
            <p className="mt-3 text-sm text-muted-foreground">
              Your AI operating system. Chat, build, ship.
            </p>
          </div>

          <div>
            <h4 className="text-sm font-semibold">Product</h4>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>
                <Link href="/#features" className="hover:text-foreground">Features</Link>
              </li>
              <li>
                <Link href="/pricing" className="hover:text-foreground">Pricing</Link>
              </li>
              <li>
                <Link href="/docs" className="hover:text-foreground">Docs</Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold">Account</h4>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>
                <Link href="/login" className="hover:text-foreground">Sign in</Link>
              </li>
              <li>
                <Link href="/signup" className="hover:text-foreground">Create account</Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold">Connect</h4>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>
                <a
                  href="https://github.com/"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 hover:text-foreground"
                >
                  <Github className="h-3.5 w-3.5" />
                  GitHub
                </a>
              </li>
              <li>
                <a
                  href="https://twitter.com/"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 hover:text-foreground"
                >
                  <Twitter className="h-3.5 w-3.5" />
                  Twitter
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-border/60 pt-6 sm:flex-row">
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} NovaMind AI. All rights reserved.
          </p>
          <p className="text-xs text-muted-foreground">Developed By Devang Shah</p>
        </div>
      </div>
    </footer>
  );
}
