import { ReactNode, useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useAuth } from '../lib/auth';
import { logout } from '../lib/api';
import { getMyPlan, type PlanInfo } from '../lib/billing';
import { Brain, LogOut, MessageSquarePlus, ChevronDown, User as UserIcon, Sparkles, Key, CreditCard } from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import { Badge } from './ui/Badge';

interface AppShellProps {
  children: ReactNode;
  /** Optional left rail content (chat list, new chat button, etc.). */
  sidebar?: ReactNode;
  /** Hides the floating ThemeToggle because the header has one too. */
  embeddedThemeToggle?: boolean;
}

function getInitials(name: string | null | undefined, email: string | null | undefined): string {
  const src = (name || email || '?').trim();
  const parts = src.split(/\s+|@/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

/**
 * Plan chip shown next to the user avatar. Pulls the plan from
 * `/api/v1/billing/plan` and updates when the user upgrades. In
 * mock mode this is always "Free".
 */
function PlanBadge() {
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  useEffect(() => {
    let cancelled = false;
    getMyPlan()
      .then((p) => {
        if (!cancelled) setPlan(p);
      })
      .catch(() => {
        if (!cancelled) setPlan(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  if (!plan) return null;
  const variant =
    plan.slug === 'pro'
      ? 'default'
      : plan.slug === 'business'
      ? 'success'
      : 'secondary';
  return (
    <Badge variant={variant as any} className="hidden sm:inline-flex">
      {plan.name}
    </Badge>
  );
}

export default function AppShell({ children, sidebar }: AppShellProps) {
  const { user } = useAuth();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      {/* Top bar */}
      <header className="glass relative z-20 flex-shrink-0 border-x-0 border-t-0">
        <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6">
          {/* Next.js 12 <Link> requires exactly one child. */}
          <Link href="/chat" className="group">
            <div className="flex items-center gap-2.5">
              <div className="relative flex h-9 w-9 items-center justify-center rounded-xl gradient-bg text-white shadow-lg shadow-primary/30 transition-transform group-hover:scale-105 group-hover:rotate-3">
                <Brain className="h-5 w-5" />
              </div>
              <span className="font-display text-lg font-bold tracking-tight">NovaMind AI</span>
              <span className="hidden rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent sm:inline-flex">
                <Sparkles className="mr-1 inline h-3 w-3" /> Beta
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-2">
            <PlanBadge />
            <button
              type="button"
              onClick={() => router.push('/chat')}
              className="hidden items-center gap-1.5 rounded-xl glass-card px-3 py-2 text-sm font-medium text-foreground transition-all hover:border-primary/40 hover:-translate-y-0.5 sm:flex"
            >
              <MessageSquarePlus className="h-4 w-4" />
              New chat
            </button>
            <button
              type="button"
              onClick={() => router.push('/developer')}
              title="Developer Portal"
              className="hidden items-center gap-1.5 rounded-xl glass-card px-3 py-2 text-sm font-medium text-foreground transition-all hover:border-primary/40 hover:-translate-y-0.5 sm:flex"
            >
              <Key className="h-4 w-4" />
              API
            </button>
            <ThemeToggle />

            {/* User menu */}
            {user && (
              <div ref={menuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setMenuOpen((o) => !o)}
                  className="flex items-center gap-2 rounded-xl glass-card px-2 py-1.5 text-sm font-medium transition-all hover:border-primary/40"
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-full gradient-bg text-xs font-bold text-white">
                    {getInitials(user.full_name, user.email)}
                  </div>
                  <span className="hidden sm:inline max-w-[120px] truncate text-foreground">
                    {user.full_name || user.username || user.email}
                  </span>
                  <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
                </button>
                {menuOpen && (
                  <div className="glass-strong absolute right-0 mt-2 w-56 overflow-hidden rounded-2xl animate-rise-in z-50">
                    <div className="border-b border-border/60 px-4 py-3">
                      <p className="text-sm font-semibold text-foreground truncate">
                        {user.full_name || user.username || 'User'}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => { setMenuOpen(false); router.push('/developer'); }}
                      className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-primary/10"
                    >
                      <Key className="h-4 w-4" />
                      Developer Portal
                    </button>
                    <button
                      type="button"
                      onClick={() => { setMenuOpen(false); router.push('/billing'); }}
                      className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-primary/10"
                    >
                      <CreditCard className="h-4 w-4" />
                      Billing &amp; plan
                    </button>
                    <button
                      type="button"
                      onClick={() => { setMenuOpen(false); router.push('/docs'); }}
                      className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-primary/10"
                    >
                      <Brain className="h-4 w-4" />
                      API Documentation
                    </button>
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="flex w-full items-center gap-2 border-t border-border/60 px-4 py-2.5 text-sm text-destructive transition-colors hover:bg-destructive/10"
                    >
                      <LogOut className="h-4 w-4" />
                      Log out
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {sidebar && (
          <aside className="hidden w-72 flex-shrink-0 border-r border-border/60 bg-card/40 backdrop-blur-md md:block overflow-y-auto">
            {sidebar}
          </aside>
        )}
        <main className="relative flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

// Re-export for use in pages that want to embed the chat list rail.
export { default as SidebarChatList } from './SidebarChatList';
export { Brain, UserIcon };