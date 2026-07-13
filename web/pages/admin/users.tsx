import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { getUsers } from '../../lib/admin';
import { useAuth } from '../../lib/auth';
import { User } from '../../types';
import AppShell from '../../components/AppShell';
import { Skeleton } from '../../components/ui/Skeleton';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { toast } from '../../components/ui/Toaster';
import { Users as UsersIcon } from 'lucide-react';

export default function UsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [mounted, setMounted] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setMounted(true);
    loadUsers();
  }, []);

  const loadUsers = async () => {
    if (!user) {
      router.replace('/login');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const usersData = await getUsers();
      setUsers(usersData);
    } catch (err) {
      const msg =
        'Failed to fetch users: ' + (err instanceof Error ? err.message : String(err));
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  if (!mounted) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <Skeleton className="mb-6 h-10 w-64" />
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <UsersIcon className="h-5 w-5 text-primary" />
              <h1 className="text-2xl font-bold tracking-tight text-foreground">Users Management</h1>
            </div>
            <p className="text-sm text-muted-foreground">
              {users.length} {users.length === 1 ? 'user' : 'users'} in the system
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => toast.info('Create user coming soon')}
          >
            New user
          </Button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
            {error}
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>User list ({users.length})</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="space-y-2 p-6">
                {[0, 1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="h-10 w-10 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-40" />
                      <Skeleton className="h-3 w-56" />
                    </div>
                  </div>
                ))}
              </div>
            ) : users.length === 0 ? (
              <div className="px-6 py-12 text-center text-sm text-muted-foreground">
                No users found.
              </div>
            ) : (
              <div className="divide-y divide-border">
                {users.map((u) => (
                  <div key={u.id} className="flex items-center justify-between px-6 py-4">
                    <div className="flex items-center gap-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-sm font-semibold text-foreground">
                        {u.full_name ? u.full_name.charAt(0).toUpperCase() : 'U'}
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-foreground">
                          {u.full_name || u.username || 'Unnamed user'}
                        </h3>
                        <p className="text-xs text-muted-foreground">{u.email || 'No email'}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span
                        className={
                          u.is_active
                            ? 'rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-600 dark:text-emerald-400'
                            : 'rounded-full bg-muted px-2 py-0.5 text-muted-foreground'
                        }
                      >
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                      <span
                        className={
                          u.is_verified
                            ? 'rounded-full bg-blue-500/10 px-2 py-0.5 text-blue-600 dark:text-blue-400'
                            : 'rounded-full bg-muted px-2 py-0.5 text-muted-foreground'
                        }
                      >
                        {u.is_verified ? 'Verified' : 'Unverified'}
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => toast.info(`Edit user ${u.id} coming soon`)}
                      >
                        Edit
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
