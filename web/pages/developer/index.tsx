import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import AppShell, { SidebarChatList } from '../../components/AppShell';
import { useAuth } from '../../lib/auth';
import {
  ApiKey,
  UsageSummary,
  ModelInfo,
  listApiKeys,
  createApiKey,
  rotateApiKey,
  updateApiKey,
  deleteApiKey,
  getUsageSummary,
  listModels,
} from '../../lib/developer';
import {
  Key,
  Plus,
  Copy,
  RefreshCw,
  Trash2,
  ToggleRight,
  ToggleLeft,
  Check,
  AlertCircle,
  Activity,
  Zap,
  Box,
  Code2,
  Eye,
  EyeOff,
} from 'lucide-react';

const V1_BASE_URL =
  process.env.NEXT_PUBLIC_V1_URL || 'http://localhost:8000/v1';

export default function DeveloperPortal() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Create-key modal state
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createOrg, setCreateOrg] = useState('');
  const [createTags, setCreateTags] = useState('');
  const [createTokenLimit, setCreateTokenLimit] = useState('');
  const [createReqLimit, setCreateReqLimit] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  // Newly-issued key (shown once)
  const [newKey, setNewKey] = useState<string | null>(null);

  // Toast
  const [toast, setToast] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null);

  useEffect(() => {
    setMounted(true);
    if (authLoading) return;
    if (!user) {
      router.replace('/login');
      return;
    }
    refresh();
  }, [user, authLoading]);

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const list = await listApiKeys();
      setKeys(list);
      const u = await getUsageSummary();
      setUsage(u);
      // Try listing models with the first active key — if none, skip.
      const active = list.find((k) => k.is_active && !k.is_disabled);
      if (active && active.key) {
        try {
          const m = await listModels(active.key);
          setModels(m);
        } catch {
          setModels([]);
        }
      } else if (active) {
        // No secret stored client-side — show local model hint
        setModels([{ id: 'NovaMind-local-v1', source: 'local' }]);
      } else {
        setModels([]);
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load developer data');
    } finally {
      setLoading(false);
    }
  }

  function flash(kind: 'ok' | 'err', msg: string) {
    setToast({ kind, msg });
    setTimeout(() => setToast(null), 2400);
  }

  async function handleCreate() {
    if (!createName.trim()) {
      setCreateError('Name is required');
      return;
    }
    setCreating(true);
    setCreateError('');
    try {
      const tags = createTags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);
      const k = await createApiKey({
        name: createName.trim(),
        organization: createOrg.trim() || undefined,
        tags: tags.length ? tags : undefined,
        monthly_token_limit: createTokenLimit ? Number(createTokenLimit) : undefined,
        monthly_request_limit: createReqLimit ? Number(createReqLimit) : undefined,
      });
      if (k.key) setNewKey(k.key);
      setShowCreate(false);
      setCreateName('');
      setCreateOrg('');
      setCreateTags('');
      setCreateTokenLimit('');
      setCreateReqLimit('');
      flash('ok', `Created "${k.name}"`);
      await refresh();
    } catch (e: any) {
      setCreateError(e?.message || 'Failed to create key');
    } finally {
      setCreating(false);
    }
  }

  async function handleRotate(id: number, name: string) {
    if (!confirm(`Rotate "${name}"? The old secret will stop working immediately.`)) return;
    try {
      const k = await rotateApiKey(id);
      if (k.key) setNewKey(k.key);
      flash('ok', `Rotated "${name}"`);
      await refresh();
    } catch (e: any) {
      flash('err', e?.message || 'Rotate failed');
    }
  }

  async function handleToggleDisable(k: ApiKey) {
    try {
      if (k.is_disabled) {
        await updateApiKey(k.id, { is_disabled: false, disable_reason: null });
        flash('ok', `Re-enabled "${k.name}"`);
      } else {
        await updateApiKey(k.id, { is_disabled: true, disable_reason: 'Disabled by owner' });
        flash('ok', `Disabled "${k.name}"`);
      }
      await refresh();
    } catch (e: any) {
      flash('err', e?.message || 'Update failed');
    }
  }

  async function handleDelete(k: ApiKey) {
    if (!confirm(`Delete "${k.name}" permanently?`)) return;
    try {
      await deleteApiKey(k.id);
      flash('ok', `Deleted "${k.name}"`);
      await refresh();
    } catch (e: any) {
      flash('err', e?.message || 'Delete failed');
    }
  }

  function copy(text: string, label = 'Copied') {
    navigator.clipboard.writeText(text).then(
      () => flash('ok', label),
      () => flash('err', 'Copy failed'),
    );
  }

  if (!mounted || authLoading || !user) return null;

  const totalKeys = keys.length;
  const activeKeys = keys.filter((k) => k.is_active && !k.is_disabled).length;
  const monthlyTokens = usage?.month_tokens_used ?? 0;

  return (
    <AppShell sidebar={<SidebarChatList />}>
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Key className="h-4 w-4" />
              <span>Developer Portal</span>
            </div>
            <h1 className="mt-1 text-3xl font-bold tracking-tight text-foreground">
              API Keys &amp; Usage
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Create keys, monitor usage, and integrate NovaMind into your product.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/developer/playground"
              className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              <Zap className="h-4 w-4" />
              Playground
            </Link>
            <Link
              href="/docs"
              className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              <Code2 className="h-4 w-4" />
              API Docs
            </Link>
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              className="inline-flex items-center gap-1.5 rounded-lg gradient-bg px-3 py-2 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              New API key
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="API keys"
            value={String(totalKeys)}
            sub={`${activeKeys} active`}
            icon={Key}
          />
          <StatCard
            label="Requests this month"
            value={formatNumber(usage?.month_requests ?? 0)}
            sub={`${formatNumber(usage?.today_requests ?? 0)} today`}
            icon={Activity}
          />
          <StatCard
            label="Tokens used"
            value={formatNumber(monthlyTokens)}
            sub="this month"
            icon={Zap}
          />
          <StatCard
            label="Avg latency"
            value={`${Math.round(usage?.average_response_time_ms ?? 0)} ms`}
            sub={`${usage?.top_endpoints?.length ?? 0} endpoints`}
            icon={Box}
          />
        </div>

        {error && (
          <div className="mb-6 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Models */}
        <section className="mb-10 rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-foreground">Available models</h2>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Served by NovaMind-local engine and Ollama (when available).
              </p>
            </div>
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
              {models.length} model{models.length === 1 ? '' : 's'}
            </span>
          </div>
          {models.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No models loaded yet. Create an API key to query the model list.
            </p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {models.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{m.id}</p>
                    <p className="text-xs text-muted-foreground">via {m.source}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => copy(m.id)}
                    className="ml-2 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    aria-label="Copy model id"
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* API keys */}
        <section className="rounded-xl border border-border bg-card shadow-sm">
          <div className="border-b border-border px-6 py-4">
            <h2 className="text-lg font-semibold text-foreground">Your API keys</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Use these in the <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">Authorization: Bearer</code> header.
            </p>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : keys.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Key className="h-6 w-6" />
              </div>
              <h3 className="text-base font-semibold text-foreground">No API keys yet</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Create your first key to start calling the NovaMind API.
              </p>
              <button
                type="button"
                onClick={() => setShowCreate(true)}
                className="mt-4 inline-flex items-center gap-1.5 rounded-lg gradient-bg px-4 py-2 text-sm font-semibold text-white shadow-sm hover:opacity-90"
              >
                <Plus className="h-4 w-4" />
                New API key
              </button>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {keys.map((k) => (
                <ApiKeyRow
                  key={k.id}
                  apiKey={k}
                  onRotate={() => handleRotate(k.id, k.name)}
                  onToggle={() => handleToggleDisable(k)}
                  onDelete={() => handleDelete(k)}
                  onCopy={() => copy('placeholder')}
                />
              ))}
            </div>
          )}
        </section>

        {/* Quick start */}
        <section className="mt-10 grid gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <h3 className="text-base font-semibold text-foreground">Quick start (cURL)</h3>
            <p className="mt-1 text-sm text-muted-foreground">Hit the chat completion endpoint with any active key.</p>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-zinc-950 px-4 py-3 text-xs leading-relaxed text-zinc-100">
{`curl ${V1_BASE_URL}/chat/completions \\
  -H "Authorization: Bearer $NOVAMIND_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${models[0]?.id ?? 'NovaMind-local-v1'}",
    "messages": [
      {"role": "user", "content": "Hello, NovaMind!"}
    ]
  }'`}
            </pre>
          </div>
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <h3 className="text-base font-semibold text-foreground">Quick start (Python)</h3>
            <p className="mt-1 text-sm text-muted-foreground">Use the OpenAI SDK with a swapped base URL.</p>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-zinc-950 px-4 py-3 text-xs leading-relaxed text-zinc-100">
{`from openai import OpenAI

client = OpenAI(
    api_key="nm_...",  # your NovaMind API key
    base_url="${V1_BASE_URL}",
)

resp = client.chat.completions.create(
    model="${models[0]?.id ?? 'NovaMind-local-v1'}",
    messages=[{"role": "user", "content": "Hi!"}],
)
print(resp.choices[0].message.content)`}
            </pre>
          </div>
        </section>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => !creating && setShowCreate(false)}
          />
          <div className="relative z-10 w-full max-w-lg overflow-hidden rounded-xl border border-border bg-card shadow-2xl">
            <div className="border-b border-border px-6 py-4">
              <h3 className="text-base font-semibold text-foreground">Create API key</h3>
              <p className="mt-0.5 text-sm text-muted-foreground">
                The secret is shown once — copy it before closing this dialog.
              </p>
            </div>
            <div className="space-y-4 px-6 py-5">
              <Field label="Name" required>
                <input
                  type="text"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  placeholder="e.g. Production backend"
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  autoFocus
                />
              </Field>
              <Field label="Organization (optional)">
                <input
                  type="text"
                  value={createOrg}
                  onChange={(e) => setCreateOrg(e.target.value)}
                  placeholder="e.g. ACME Inc."
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </Field>
              <Field label="Tags (comma separated)">
                <input
                  type="text"
                  value={createTags}
                  onChange={(e) => setCreateTags(e.target.value)}
                  placeholder="production, backend, mobile"
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Monthly token limit">
                  <input
                    type="number"
                    min="0"
                    value={createTokenLimit}
                    onChange={(e) => setCreateTokenLimit(e.target.value)}
                    placeholder="unlimited"
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </Field>
                <Field label="Monthly request limit">
                  <input
                    type="number"
                    min="0"
                    value={createReqLimit}
                    onChange={(e) => setCreateReqLimit(e.target.value)}
                    placeholder="unlimited"
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </Field>
              </div>
              {createError && (
                <p className="flex items-center gap-1.5 text-xs text-destructive">
                  <AlertCircle className="h-3.5 w-3.5" />
                  {createError}
                </p>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-border bg-muted/40 px-6 py-3">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                disabled={creating}
                className="rounded-lg border border-input bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreate}
                disabled={creating}
                className="inline-flex items-center gap-1.5 rounded-lg gradient-bg px-4 py-2 text-sm font-semibold text-white shadow-sm hover:opacity-90 disabled:opacity-50"
              >
                {creating && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                Create key
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Newly-issued secret banner */}
      {newKey && (
        <NewKeyModal
          secret={newKey}
          onClose={() => setNewKey(null)}
          onCopy={() => copy(newKey, 'API key copied')}
        />
      )}

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 left-1/2 z-50 -translate-x-1/2 transform rounded-lg border px-4 py-2.5 text-sm shadow-lg ${
            toast.kind === 'ok'
              ? 'border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-300'
              : 'border-destructive/30 bg-destructive/10 text-destructive'
          }`}
        >
          {toast.msg}
        </div>
      )}
    </AppShell>
  );
}

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: any;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-2xl font-bold text-foreground">{value}</p>
          {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
        </div>
        <div className="rounded-lg bg-primary/10 p-2 text-primary">
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-foreground">
        {label}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </span>
      {children}
    </label>
  );
}

function ApiKeyRow({
  apiKey: k,
  onRotate,
  onToggle,
  onDelete,
}: {
  apiKey: ApiKey;
  onRotate: () => void;
  onToggle: () => void;
  onDelete: () => void;
  onCopy: () => void;
}) {
  const status = k.is_disabled ? 'disabled' : k.is_active ? 'active' : 'inactive';
  const statusColor =
    status === 'active'
      ? 'bg-green-500/10 text-green-700 dark:text-green-300'
      : status === 'disabled'
      ? 'bg-destructive/10 text-destructive'
      : 'bg-muted text-muted-foreground';
  const used = k.monthly_token_count ?? 0;
  const limit = k.monthly_token_limit ?? 0;
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;

  return (
    <div className="px-6 py-4 transition-colors hover:bg-muted/30">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-foreground">{k.name}</p>
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${statusColor}`}
            >
              {status}
            </span>
            {k.organization && (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                {k.organization}
              </span>
            )}
          </div>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            nm_••••••••{String(k.id).padStart(4, '0')}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>{k.usage_count ?? 0} lifetime requests</span>
            <span>{k.monthly_request_count ?? 0} this month</span>
            {limit > 0 && (
              <span>
                Tokens: {formatNumber(used)} / {formatNumber(limit)} ({pct}%)
              </span>
            )}
            {k.last_used_at && <span>Last used {timeAgo(k.last_used_at)}</span>}
          </div>
          {limit > 0 && (
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full ${
                  pct >= 90 ? 'bg-destructive' : pct >= 70 ? 'bg-amber-500' : 'bg-primary'
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
          )}
          {k.tags && k.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {k.tags.map((t) => (
                <span
                  key={t}
                  className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
                >
                  #{t}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1">
          <IconButton onClick={onToggle} title={k.is_disabled ? 'Enable key' : 'Disable key'}>
            {k.is_disabled ? (
              <ToggleRight className="h-4 w-4" />
            ) : (
              <ToggleLeft className="h-4 w-4" />
            )}
          </IconButton>
          <IconButton onClick={onRotate} title="Rotate secret">
            <RefreshCw className="h-4 w-4" />
          </IconButton>
          <IconButton
            onClick={onDelete}
            title="Delete key"
            className="hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </IconButton>
        </div>
      </div>
    </div>
  );
}

function IconButton({
  children,
  onClick,
  title,
  className = '',
}: {
  children: React.ReactNode;
  onClick: () => void;
  title?: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground ${className}`}
    >
      {children}
    </button>
  );
}

function NewKeyModal({
  secret,
  onClose,
  onCopy,
}: {
  secret: string;
  onClose: () => void;
  onCopy: () => void;
}) {
  const [revealed, setRevealed] = useState(false);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg overflow-hidden rounded-xl border border-amber-500/30 bg-card shadow-2xl">
        <div className="border-b border-amber-500/30 bg-amber-500/10 px-6 py-4">
          <div className="flex items-center gap-2">
            <Check className="h-5 w-5 text-amber-700 dark:text-amber-300" />
            <h3 className="text-base font-semibold text-foreground">API key created</h3>
          </div>
          <p className="mt-1 text-sm text-amber-900 dark:text-amber-200">
            Copy this secret now — for security we won't show it again.
          </p>
        </div>
        <div className="px-6 py-5">
          <div className="flex items-center gap-2 rounded-lg border border-input bg-background p-2">
            <code className="flex-1 truncate font-mono text-xs">
              {revealed ? secret : secret.replace(/.(?=.{8})/g, '•')}
            </code>
            <button
              type="button"
              onClick={() => setRevealed((r) => !r)}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              title={revealed ? 'Hide' : 'Reveal'}
            >
              {revealed ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
            <button
              type="button"
              onClick={onCopy}
              className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/20"
            >
              <Copy className="h-3.5 w-3.5" />
              Copy
            </button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Use it as <code className="rounded bg-muted px-1 font-mono">Authorization: Bearer {secret.slice(0, 6)}…</code>
          </p>
        </div>
        <div className="flex justify-end border-t border-border bg-muted/40 px-6 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

function formatNumber(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

function timeAgo(iso: string): string {
  const t = new Date(iso).getTime();
  const sec = Math.floor((Date.now() - t) / 1000);
  if (sec < 60) return 'just now';
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}