import { ReactNode, useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useAuth } from '../lib/auth';
import { logout } from '../lib/api';
import { getMyPlan, type PlanInfo } from '../lib/billing';
import { Brain, LogOut, MessageSquarePlus, ChevronDown, User as UserIcon, Sparkles, Key, CreditCard } from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import { Badge } from './ui/Badge';
import { ShellHeader } from './shell/ShellHeader';
import { SidebarRail } from './sidebar/SidebarRail';

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

function UserMenu() {
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

  if (!user) return null;

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        onClick={() => setMenuOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg border border-input bg-card px-2 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-full gradient-bg text-xs font-bold text-white">
          {getInitials(user.full_name, user.email)}
        </div>
        <span className="hidden sm:inline max-w-[120px] truncate text-foreground">
          {user.full_name || user.username || user.email}
        </span>
        <ChevronDown className="h-4 w-4 text-muted-foreground" />
      </button>
      {menuOpen && (
        <div className="absolute right-0 mt-2 w-56 overflow-hidden rounded-lg border border-border bg-card shadow-lg animate-fade-in z-50">
          <div className="border-b border-border px-4 py-3">
            <p className="text-sm font-semibold text-foreground truncate">
              {user.full_name || user.username || 'User'}
            </p>
            <p className="text-xs text-muted-foreground truncate">{user.email}</p>
          </div>
          <button
            type="button"
            onClick={() => { setMenuOpen(false); router.push('/developer'); }}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-muted"
          >
            <Key className="h-4 w-4" />
            Developer Portal
          </button>
          <button
            type="button"
            onClick={() => { setMenuOpen(false); router.push('/billing'); }}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-muted"
          >
            <CreditCard className="h-4 w-4" />
            Billing &amp; plan
          </button>
          <button
            type="button"
            onClick={() => { setMenuOpen(false); router.push('/docs'); }}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-muted"
          >
            <Brain className="h-4 w-4" />
            API Documentation
          </button>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 border-t border-border px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-muted"
          >
            <LogOut className="h-4 w-4" />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}

function Logo() {
  return (
    <Link href="/chat" className="group">
      <div className="flex items-center gap-2.5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg gradient-bg text-white shadow-sm transition-transform group-hover:scale-105">
          <Brain className="h-5 w-5" />
        </div>
        <span className="text-lg font-bold tracking-tight">NovaMind AI</span>
        <span className="hidden rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary sm:inline-flex">
          <Sparkles className="mr-1 inline h-3 w-3" /> Beta
        </span>
      </div>
    </Link>
  );
}

function TopBarActions() {
  const router = useRouter();
  return (
    <div className="flex items-center gap-2">
      <PlanBadge />
      <button
        type="button"
        onClick={() => router.push('/chat')}
        className="hidden items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted sm:flex"
      >
        <MessageSquarePlus className="h-4 w-4" />
        New chat
      </button>
      <button
        type="button"
        onClick={() => router.push('/developer')}
        title="Developer Portal"
        className="hidden items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted sm:flex"
      >
        <Key className="h-4 w-4" />
        API
      </button>
      <ThemeToggle />
      <UserMenu />
    </div>
  );
}

export default function AppShell({ children, sidebar }: AppShellProps) {
  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <ShellHeader>
        <Logo />
        <TopBarActions />
      </ShellHeader>

      <div className="flex flex-1 overflow-hidden">
        {sidebar && (
          <SidebarRail className="hidden w-72 flex-shrink-0 border-r border-border bg-card/50 md:block overflow-y-auto">
            {sidebar}
          </SidebarRail>
        )}
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

// Re-export for use in pages that want to embed the chat list rail.
export { default as SidebarChatList } from './SidebarChatList';
export { Brain, UserIcon };
