import { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  Sparkles,
  Trash2,
  Plus,
  LayoutTemplate,
  Loader2,
} from 'lucide-react';
import AppShell, { SidebarChatList } from '../../components/AppShell';
import { useAuth } from '../../lib/auth';
import { listApps, deleteApp, type AppManifest } from '../../lib/api';
import { toast } from '../../components/ui/Toaster';

export default function AppsIndexPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [apps, setApps] = useState<AppManifest[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    listApps()
      .then((items) => {
        if (!cancelled) setApps(items);
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setApps([]);
          toast.error(e.message || 'Could not load apps');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) return null;

  const onDelete = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    setBusyId(id);
    try {
      await deleteApp(id);
      setApps((prev) => (prev || []).filter((a) => a.id !== id));
      toast.success('App deleted');
    } catch (e: any) {
      toast.error(e?.message || 'Delete failed');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <Head>
        <title>Apps · NovaMind AI</title>
      </Head>
      <AppShell sidebar={<SidebarChatList />}>
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
          <div className="mb-6 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg gradient-bg text-white">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Apps</h1>
                <p className="text-sm text-muted-foreground">
                  Tiny web projects scaffolded from a prompt. Edit, preview, and run code in a sandbox.
                </p>
              </div>
            </div>
            <button
              onClick={() => router.push('/apps/new')}
              className="inline-flex items-center gap-2 rounded-lg gradient-bg px-4 py-2 text-sm font-semibold text-white shadow-sm hover:shadow-md"
            >
              <Plus className="h-4 w-4" /> New app
            </button>
          </div>

          {apps === null ? (
            <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading apps…
            </div>
          ) : apps.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-card p-10 text-center">
              <LayoutTemplate className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
              <h2 className="text-lg font-semibold">No apps yet</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Pick a starter template, describe what you want, and NovaMind will scaffold it for you.
              </p>
              <Link
                href="/apps/new"
                className="mt-4 inline-flex items-center gap-2 rounded-lg gradient-bg px-4 py-2 text-sm font-semibold text-white"
                legacyBehavior={false}
              >
                <Plus className="h-4 w-4" /> Create your first app
              </Link>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {apps.map((a) => (
                <div
                  key={a.id}
                  className="group flex flex-col rounded-lg border border-border bg-card p-4 transition hover:border-primary/40"
                >
                  <Link href={`/apps/${a.id}`} className="flex-1" legacyBehavior={false}>
                    <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                      <LayoutTemplate className="h-3.5 w-3.5" />
                      <span>{a.template || a.kind}</span>
                    </div>
                    <h3 className="line-clamp-1 text-base font-semibold">{a.name}</h3>
                    <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                      {a.description || a.prompt || `${a.files.length} file${a.files.length === 1 ? '' : 's'}`}
                    </p>
                  </Link>
                  <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
                    <span>{a.files.length} file{a.files.length === 1 ? '' : 's'}</span>
                    <button
                      disabled={busyId === a.id}
                      onClick={() => onDelete(a.id, a.name)}
                      className="inline-flex items-center gap-1 rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
                      aria-label={`Delete ${a.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </AppShell>
    </>
  );
}