import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { getApiKeys, getSystemStats } from '../../lib/admin';
import { useAuth } from '../../lib/auth';
import StatsCard from '../../components/admin/StatsCard';
import ApiKeyList from '../../components/admin/ApiKeyList';
import AppShell from '../../components/AppShell';
import { Skeleton } from '../../components/ui/Skeleton';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card';
import { toast } from '../../components/ui/Toaster';
import { Shield } from 'lucide-react';

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
  const router = useRouter();

  useEffect(() => {
    setMounted(true);
    loadData();
  }, []);

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
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatsCard title="Total Users" value={stats.total_users || 0} />
            <StatsCard title="Admin Users" value={stats.admin_users || 0} />
            <StatsCard title="Active Users" value={stats.active_users || 0} />
            <StatsCard title="API Keys" value={stats.api_keys || 0} />
          </div>
        )}

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
