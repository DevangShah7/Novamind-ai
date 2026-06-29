import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import AppShell, { SidebarChatList } from '../components/AppShell';
import { useAuth } from '../lib/auth';
import { BookOpen, ExternalLink, Code2, ShieldCheck, Zap, ArrowRight } from 'lucide-react';

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/v1$/, '') ||
  'http://localhost:8000';
const SWAGGER_URL = `${BACKEND_URL}/docs`;
const OPENAPI_URL = `${BACKEND_URL}/api/v1/openapi.json`;

export default function DocsPage() {
  const { user, loading: authLoading } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [swaggerOk, setSwaggerOk] = useState<boolean | null>(null);

  useEffect(() => {
    setMounted(true);
    // Ping /docs to see if the backend is reachable from the browser
    fetch(SWAGGER_URL, { method: 'HEAD', mode: 'no-cors' })
      .then(() => setSwaggerOk(true))
      .catch(() => setSwaggerOk(false));
  }, []);

  const endpoints = useMemo(
    () => [
      {
        group: 'Auth',
        items: [
          { method: 'POST', path: '/api/v1/auth/register', desc: 'Create a new account' },
          { method: 'POST', path: '/api/v1/auth/login', desc: 'Exchange email/password for a JWT' },
          { method: 'POST', path: '/api/v1/auth/google', desc: 'Google OAuth sign-in' },
          { method: 'GET',  path: '/api/v1/users/me', desc: 'Get the current user (JWT)' },
        ],
      },
      {
        group: 'API Keys (JWT)',
        items: [
          { method: 'GET',    path: '/api/v1/api-keys/', desc: 'List your keys' },
          { method: 'POST',   path: '/api/v1/api-keys/', desc: 'Create a new key (returns secret once)' },
          { method: 'POST',   path: '/api/v1/api-keys/{id}/rotate', desc: 'Issue a new secret, invalidating the old one' },
          { method: 'PUT',    path: '/api/v1/api-keys/{id}', desc: 'Rename, disable, set limits/allowlists' },
          { method: 'DELETE', path: '/api/v1/api-keys/{id}', desc: 'Delete a key' },
          { method: 'GET',    path: '/api/v1/api-keys/usage/summary', desc: 'Totals + per-endpoint rollup' },
        ],
      },
      {
        group: 'OpenAI-compatible /v1/*',
        items: [
          { method: 'GET',  path: '/v1/models', desc: 'List available models (API-key bearer)' },
          { method: 'POST', path: '/v1/chat/completions', desc: 'Chat completion (supports `stream=true` SSE)' },
          { method: 'POST', path: '/v1/embeddings', desc: 'Generate an embedding vector' },
          { method: 'GET',  path: '/v1/usage?days=30', desc: 'Per-day usage rollup' },
          { method: 'GET',  path: '/v1/billing', desc: 'Current billing snapshot' },
          { method: 'GET',  path: '/v1/billing/invoices', desc: 'Invoice history' },
        ],
      },
      {
        group: 'Chats (JWT)',
        items: [
          { method: 'GET',    path: '/api/v1/chats', desc: 'List your conversations' },
          { method: 'POST',   path: '/api/v1/chats', desc: 'Create a conversation' },
          { method: 'GET',    path: '/api/v1/chats/{id}', desc: 'Get a conversation with messages' },
          { method: 'DELETE', path: '/api/v1/chats/{id}', desc: 'Delete a conversation' },
          { method: 'POST',   path: '/api/v1/chats/{id}/messages', desc: 'Send a user message, get an AI reply' },
        ],
      },
    ],
    [],
  );

  if (!mounted || authLoading || !user) return null;

  return (
    <AppShell sidebar={<SidebarChatList />}>
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <BookOpen className="h-4 w-4" />
              <span>Documentation</span>
            </div>
            <h1 className="mt-1 text-3xl font-bold tracking-tight text-foreground">
              NovaMind API Reference
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Full OpenAPI schema, plus quick reference for the most-used endpoints.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/developer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              <ShieldCheck className="h-4 w-4" />
              Developer Portal
            </Link>
            <Link
              href="/developer/playground"
              className="inline-flex items-center gap-1.5 rounded-lg gradient-bg px-3 py-2 text-sm font-semibold text-white shadow-sm hover:opacity-90"
            >
              <Zap className="h-4 w-4" />
              Open Playground
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        {/* Cheat sheet */}
        <div className="mb-8 space-y-6">
          {endpoints.map((g) => (
            <section
              key={g.group}
              className="overflow-hidden rounded-xl border border-border bg-card shadow-sm"
            >
              <div className="border-b border-border bg-muted/40 px-5 py-3">
                <h2 className="text-sm font-semibold text-foreground">{g.group}</h2>
              </div>
              <ul className="divide-y divide-border">
                {g.items.map((it) => (
                  <li key={it.path} className="flex items-center gap-3 px-5 py-3">
                    <MethodBadge method={it.method} />
                    <code className="flex-1 truncate font-mono text-xs text-foreground">
                      {it.path}
                    </code>
                    <span className="hidden text-sm text-muted-foreground sm:inline">
                      {it.desc}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        {/* cURL / Python snippets */}
        <section className="mb-10 grid gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <Code2 className="h-4 w-4 text-primary" />
              <h3 className="text-base font-semibold text-foreground">cURL</h3>
            </div>
            <pre className="overflow-x-auto rounded-lg bg-zinc-950 px-4 py-3 text-xs leading-relaxed text-zinc-100">
{`# 1. Create a key (JWT in $TOKEN)
curl -X POST ${BACKEND_URL}/api/v1/api-keys/ \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "my-app"}'

# 2. Use the returned secret (nm_...) to call /v1/chat/completions
curl ${BACKEND_URL}/v1/chat/completions \\
  -H "Authorization: Bearer $NOVAMIND_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "NovaMind-local-v1",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'`}
            </pre>
          </div>
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <Code2 className="h-4 w-4 text-primary" />
              <h3 className="text-base font-semibold text-foreground">OpenAI SDK</h3>
            </div>
            <pre className="overflow-x-auto rounded-lg bg-zinc-950 px-4 py-3 text-xs leading-relaxed text-zinc-100">
{`from openai import OpenAI

client = OpenAI(
    api_key="nm_...",          # your NovaMind key
    base_url="${BACKEND_URL}/v1",
)

resp = client.chat.completions.create(
    model="NovaMind-local-v1",
    messages=[{"role": "user", "content": "Hello!"}],
)

print(resp.choices[0].message.content)
print(resp.usage.total_tokens)`}
            </pre>
          </div>
        </section>

        {/* Swagger UI iframe */}
        <section className="rounded-xl border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <h2 className="text-sm font-semibold text-foreground">
              Live OpenAPI explorer
            </h2>
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    swaggerOk === null
                      ? 'bg-muted-foreground'
                      : swaggerOk
                      ? 'bg-green-500'
                      : 'bg-destructive'
                  }`}
                />
                {swaggerOk === null
                  ? 'Checking backend…'
                  : swaggerOk
                  ? 'Backend reachable'
                  : 'Backend not reachable'}
              </span>
              <a
                href={SWAGGER_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                Open in new tab
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
          <div className="relative">
            <iframe
              src={SWAGGER_URL}
              title="NovaMind OpenAPI"
              className="h-[70vh] w-full border-0"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            />
            {swaggerOk === false && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background/80 p-6 text-center backdrop-blur-sm">
                <p className="text-sm font-medium text-foreground">
                  Can't reach the backend at {BACKEND_URL}
                </p>
                <p className="max-w-md text-xs text-muted-foreground">
                  Make sure the FastAPI server is running. If you're on a different host,
                  set <code className="rounded bg-muted px-1 font-mono">NEXT_PUBLIC_API_URL</code> in
                  your environment.
                </p>
                <a
                  href={OPENAPI_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                  View raw openapi.json
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function MethodBadge({ method }: { method: string }) {
  const palette: Record<string, string> = {
    GET: 'bg-green-500/10 text-green-700 dark:text-green-300',
    POST: 'bg-blue-500/10 text-blue-700 dark:text-blue-300',
    PUT: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
    DELETE: 'bg-destructive/10 text-destructive',
    PATCH: 'bg-purple-500/10 text-purple-700 dark:text-purple-300',
  };
  return (
    <span
      className={`inline-flex w-16 flex-shrink-0 items-center justify-center rounded-md px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wide ${palette[method] ?? 'bg-muted text-foreground'}`}
    >
      {method}
    </span>
  );
}