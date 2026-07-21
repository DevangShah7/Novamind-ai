import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { getApiKeys, getSystemStats } from '../../lib/admin';
import { useAuth } from '../../lib/auth';
import AppShell from '../../components/AppShell';
import { Skeleton } from '../../components/ui/Skeleton';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card';
import { toast } from '../../components/ui/Toaster';
import { Shield, Users as UsersIcon, ArrowRight } from 'lucide-react';
import { GlassCard } from '../../components/dashboard/GlassCard';
import { AnimatedCounter } from '../../components/dashboard/AnimatedCounter';
import { RequestDots, RequestEvent } from '../../components/dashboard/RequestDots';
import { StaggerChildren, StaggerItem } from '../../components/motion';
import ApiKeyList from '../../components/admin/ApiKeyList';

export default function AdminDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<{
    total_users?: number;
    admin_users?: number;
    active_users?: number;
    api_keys?: number;
  }>({});
  const [apiKeys, setApiKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mounted, setMounted] = useState(false);
  // Synthetic live-traffic stream for the request timeline. Newest at the end.
  const [events, setEvents] = useState<RequestEvent[]>(() => seedEvents());
  const router = useRouter();

  useEffect(() => {
    setMounted(true);
    loadData();
  }, []);

  // Live-traffic generator: append a synthetic event every ~700 ms so the
  // canvas shows dots scrolling left in real time. 90% success / 10% error
  // to keep the colour mix visually interesting.
  useEffect(() => {
    if (!mounted) return;
    const id = setInterval(() => {
      setEvents((prev) => {
        const next: RequestEvent = {
          t: Date.now(),
          status: Math.random() < 0.9 ? 200 : 500,
        };
        // Keep the last 90s so the timeline has a small history buffer.
        const cutoff = Date.now() - 90 * 1000;
        return [...prev, next].filter((e) => e.t >= cutoff);
      });
    }, 700);
    return () => clearInterval(id);
  }, [mounted]);

  const loadData = async () => {
    if (!user) {
      router.replace('/login');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const [statsData, apiKeysData] = await Promise.all([
        getSystemStats(),
        getApiKeys()
      ]);
      setStats(statsData);
      setApiKeys(apiKeysData);
    } catch (err: any) {
      const msg = 'Failed to load admin dashboard data';
      setError(msg);
      toast.error(msg);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (!mounted) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <Skeleton className="mb-6 h-10 w-64" />
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (!user) {
    return null; // Redirect handled in useEffect
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <div className="mb-6 flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Admin Dashboard</h1>
        </div>
        <p className="mb-6 text-sm text-muted-foreground">
          Welcome back, {user.full_name || user.email}
        </p>

        {error && (
          <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Stats Cards */}
        {loading ? (
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-28 w-full rounded-xl" />
            ))}
          </div>
        ) : (
          <StaggerChildren
            className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
            gap={0.06}
          >
            <StaggerItem>
              <GlassCard className="p-5" noShimmer>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Total Users
                </p>
                <AnimatedCounter
                  value={stats.total_users || 0}
                  numberClassName="mt-2 text-2xl font-bold tabular-nums text-foreground"
                />
              </GlassCard>
            </StaggerItem>
            <StaggerItem>
              <GlassCard className="p-5" noShimmer>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Admin Users
                </p>
                <AnimatedCounter
                  value={stats.admin_users || 0}
                  numberClassName="mt-2 text-2xl font-bold tabular-nums text-foreground"
                />
              </GlassCard>
            </StaggerItem>
            <StaggerItem>
              <GlassCard className="p-5" noShimmer>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Active Users
                </p>
                <AnimatedCounter
                  value={stats.active_users || 0}
                  numberClassName="mt-2 text-2xl font-bold tabular-nums text-foreground"
                />
              </GlassCard>
            </StaggerItem>
            <StaggerItem>
              <GlassCard className="p-5" noShimmer>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  API Keys
                </p>
                <AnimatedCounter
                  value={stats.api_keys || 0}
                  numberClassName="mt-2 text-2xl font-bold tabular-nums text-foreground"
                />
              </GlassCard>
            </StaggerItem>
          </StaggerChildren>
        )}

        {/* Live request timeline */}
        <GlassCard className="mb-6 p-6" noShimmer>
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">
                Live request timeline
              </h2>
              <p className="text-xs text-muted-foreground">
                Last 60 seconds of API traffic — synthesised for the demo.
              </p>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              online
            </span>
          </div>
          <RequestDots
            events={events}
            height={56}
            className="h-14 w-full"
          />
        </GlassCard>

        {/* Admin shortcut tiles — links to the pages an admin actually
            uses. The stats grid above is read-only; these tiles are the
            action surface. */}
        <StaggerChildren
          className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
          gap={0.06}
        >
          <StaggerItem>
            <Link
              href="/admin/users"
              className="group block transition-transform hover:scale-[1.01]"
            >
              <GlassCard className="p-5" noShimmer>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="mb-2 flex items-center gap-2">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <UsersIcon className="h-5 w-5" />
                      </div>
                      <h2 className="text-base font-semibold text-foreground">
                        Manage users
                      </h2>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {stats.total_users ?? 0} registered · {stats.admin_users ?? 0} admins
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                </div>
              </GlassCard>
            </Link>
          </StaggerItem>
        </StaggerChildren>

        {/* API Keys Section */}
        <Card>
          <CardHeader>
            <CardTitle>API Keys</CardTitle>
            <CardDescription>Manage API keys for programmatic access</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="space-y-2 p-6">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : (
              <ApiKeyList apiKeys={apiKeys} onRefresh={loadData} />
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

/** Seed the timeline with ~25 dots spread across the last 30 seconds. */
function seedEvents(): RequestEvent[] {
  const out: RequestEvent[] = [];
  const now = Date.now();
  for (let i = 0; i < 25; i++) {
    out.push({
      t: now - Math.floor(Math.random() * 30 * 1000),
      status: Math.random() < 0.9 ? 200 : 500,
    });
  }
  return out.sort((a, b) => a.t - b.t);
}
