import { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  Sparkles,
  ArrowLeft,
  Play,
  Loader2,
  RefreshCw,
  Code2,
  TerminalSquare,
  Trash2,
} from 'lucide-react';
import AppShell, { SidebarChatList } from '../../components/AppShell';
import { useAuth } from '../../lib/auth';
import {
  deleteApp,
  getApp,
  previewAppUrl,
  runAppCode,
  type AppManifest,
  type AppRunResult,
} from '../../lib/api';
import { toast } from '../../components/ui/Toaster';

const DEFAULT_PY_SNIPPET = `# Runs in the NovaMind sandbox.\n# No env, no network, hard 10s timeout.\nprint("hello from the sandbox")\nfor i in range(3):\n    print(i, i ** 2)\n`;

const DEFAULT_JS_SNIPPET = `// Node.js snippet, sandboxed.\nconsole.log("hello from the sandbox");\nfor (let i = 0; i < 3; i++) {\n  console.log(i, i * i);\n}\n`;

type Lang = 'python' | 'javascript';

export default function AppDetailPage() {
  const router = useRouter();
  const { user } = useAuth();
  const appId = typeof router.query.id === 'string' ? router.query.id : '';

  const [manifest, setManifest] = useState<AppManifest | null>(null);
  const [previewKey, setPreviewKey] = useState(0); // bump to force iframe reload
  const [activeFile, setActiveFile] = useState<string>('index.html');
  const [codeLang, setCodeLang] = useState<Lang>('python');
  const [code, setCode] = useState<string>(DEFAULT_PY_SNIPPET);
  const [result, setResult] = useState<AppRunResult | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!user || !appId) return;
    let cancelled = false;
    getApp(appId)
      .then((m) => {
        if (!cancelled) setManifest(m);
      })
      .catch((e: Error) => {
        if (!cancelled) toast.error(e.message || 'App not found');
      });
    return () => {
      cancelled = true;
    };
  }, [user, appId]);

  useEffect(() => {
    setCode(codeLang === 'python' ? DEFAULT_PY_SNIPPET : DEFAULT_JS_SNIPPET);
    setResult(null);
  }, [codeLang]);

  const previewSrc = useMemo(
    () => (manifest ? previewAppUrl(manifest.id, activeFile) + `?v=${previewKey}` : ''),
    [manifest, activeFile, previewKey],
  );

  if (!user) return null;

  if (!manifest) {
    return (
      <>
        <Head>
          <title>App · NovaMind AI</title>
        </Head>
        <AppShell sidebar={<SidebarChatList />}>
          <div className="mx-auto max-w-5xl px-4 py-12 text-sm text-muted-foreground">
            <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
            Loading app…
          </div>
        </AppShell>
      </>
    );
  }

  const run = async () => {
    setRunning(true);
    try {
      const r = await runAppCode(manifest.id, { language: codeLang, code });
      setResult(r);
      if (r.stderr) {
        toast.error('Run finished with errors — see output');
      } else {
        toast.success('Code executed');
      }
    } catch (e: any) {
      toast.error(e?.message || 'Run failed');
    } finally {
      setRunning(false);
    }
  };

  const onDelete = async () => {
    if (!confirm(`Delete "${manifest.name}"? This cannot be undone.`)) return;
    try {
      await deleteApp(manifest.id);
      toast.success('App deleted');
      router.push('/apps');
    } catch (e: any) {
      toast.error(e?.message || 'Delete failed');
    }
  };

  return (
    <>
      <Head>
        <title>{manifest.name} · NovaMind AI</title>
      </Head>
      <AppShell sidebar={<SidebarChatList />}>
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Link
                href="/apps"
                className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
                legacyBehavior={false}
              >
                <ArrowLeft className="h-4 w-4" /> Apps
              </Link>
              <span className="text-muted-foreground">/</span>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-bg text-white">
                  <Sparkles className="h-4 w-4" />
                </div>
                <h1 className="text-lg font-semibold">{manifest.name}</h1>
              </div>
            </div>
            <button
              onClick={onDelete}
              className="inline-flex items-center gap-1 rounded p-1.5 text-sm text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              aria-label="Delete app"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>

          {manifest.description && (
            <p className="mb-4 text-sm text-muted-foreground">{manifest.description}</p>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            {/* Preview pane */}
            <div className="overflow-hidden rounded-lg border border-border bg-card">
              <div className="flex items-center justify-between border-b border-border px-3 py-2 text-xs">
                <div className="flex items-center gap-1">
                  {manifest.files.map((f) => (
                    <button
                      key={f}
                      onClick={() => setActiveFile(f)}
                      className={`rounded px-2 py-1 ${
                        activeFile === f ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setPreviewKey((k) => k + 1)}
                  className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
                  aria-label="Reload preview"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                </button>
              </div>
              <iframe
                title="App preview"
                src={previewSrc}
                className="h-[28rem] w-full bg-white"
              />
            </div>

            {/* Code + output pane */}
            <div className="flex flex-col rounded-lg border border-border bg-card">
              <div className="flex items-center justify-between border-b border-border px-3 py-2">
                <div className="flex items-center gap-1 text-sm">
                  <button
                    onClick={() => setCodeLang('python')}
                    className={`rounded px-2 py-1 ${
                      codeLang === 'python' ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <Code2 className="mr-1 inline h-3.5 w-3.5" /> Python
                  </button>
                  <button
                    onClick={() => setCodeLang('javascript')}
                    className={`rounded px-2 py-1 ${
                      codeLang === 'javascript' ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <Code2 className="mr-1 inline h-3.5 w-3.5" /> JavaScript
                  </button>
                </div>
                <button
                  onClick={run}
                  disabled={running}
                  className="inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                >
                  {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  Run
                </button>
              </div>
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                spellCheck={false}
                className="h-56 w-full resize-none border-b border-border bg-background px-3 py-2 font-mono text-xs leading-relaxed focus:outline-none"
              />
              <div className="flex-1 overflow-auto px-3 py-2">
                <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                  <TerminalSquare className="h-3.5 w-3.5" /> Output
                </div>
                {result ? (
                  <div className="space-y-1 font-mono text-xs">
                    {result.unavailable && (
                      <div className="rounded bg-amber-100 px-2 py-1 text-amber-900">
                        {codeLang === 'javascript'
                          ? 'Node.js is not installed on this host.'
                          : 'Backend runtime unavailable.'}
                      </div>
                    )}
                    {result.stdout && (
                      <pre className="whitespace-pre-wrap text-foreground">{result.stdout}</pre>
                    )}
                    {result.stderr && (
                      <pre className="whitespace-pre-wrap text-destructive">{result.stderr}</pre>
                    )}
                    {!result.stdout && !result.stderr && !result.unavailable && (
                      <pre className="text-muted-foreground">(no output)</pre>
                    )}
                    <div className="pt-2 text-[10px] text-muted-foreground">
                      exit {result.return_code} · {result.execution_time.toFixed(3)}s
                      {result.timed_out ? ' · timed out' : ''}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Press <kbd className="rounded border px-1">Run</kbd> to execute the snippet in the sandbox.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </AppShell>
    </>
  );
}