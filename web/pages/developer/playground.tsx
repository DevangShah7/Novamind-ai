import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import AppShell, { SidebarChatList } from '../../components/AppShell';
import { useAuth } from '../../lib/auth';
import { ApiKey, ModelInfo, listApiKeys, listModels, sendChat } from '../../lib/developer';
import { ArrowLeft, Play, Loader2, Key, Zap, AlertCircle, Copy } from 'lucide-react';

type Msg = { role: 'user' | 'assistant' | 'system'; content: string };

export default function PlaygroundPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedKeyId, setSelectedKeyId] = useState<string>('');
  const [model, setModel] = useState<string>('');
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(256);
  const [prompt, setPrompt] = useState('Write a haiku about a neural network.');
  const [messages, setMessages] = useState<Msg[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [lastRaw, setLastRaw] = useState<string>('');
  const [secret, setSecret] = useState<string>('');

  useEffect(() => {
    setMounted(true);
    if (authLoading) return;
    if (!user) {
      router.replace('/login');
      return;
    }
    (async () => {
      try {
        const list = await listApiKeys();
        setKeys(list);
        if (list.length > 0) setSelectedKeyId(String(list[0].id));
        // Try to load models with first key
        const firstActive = list.find((k) => k.is_active && !k.is_disabled);
        if (firstActive && firstActive.key) {
          try {
            const m = await listModels(firstActive.key);
            setModels(m);
            if (m.length > 0) setModel(m[0].id);
          } catch {
            setModels([{ id: 'NovaMind-local-v1', source: 'local' }]);
            setModel('NovaMind-local-v1');
          }
        }
      } catch (e: any) {
        setError(e?.message || 'Failed to load keys');
      }
    })();
  }, [user, authLoading]);

  // When user picks a different key, refresh model list with that key.
  async function loadModelsFor(keyId: string) {
    const k = keys.find((x) => String(x.id) === keyId);
    if (!k || !k.key) return;
    try {
      const m = await listModels(k.key);
      setModels(m);
      if (m.length > 0 && !m.find((mm) => mm.id === model)) setModel(m[0].id);
    } catch (e: any) {
      setError(e?.message || 'Model list failed');
    }
  }

  const selectedKey = useMemo(
    () => keys.find((k) => String(k.id) === selectedKeyId),
    [keys, selectedKeyId],
  );

  async function handleRun() {
    setError('');
    if (!selectedKey || !selectedKey.key) {
      setError('Please pick an API key first (and rotate it to receive a secret).');
      return;
    }
    if (!prompt.trim()) return;
    setRunning(true);
    const next: Msg[] = [...messages, { role: 'user', content: prompt.trim() }];
    setMessages(next);
    setPrompt('');
    try {
      const resp = await sendChat(selectedKey.key, {
        model,
        messages: next.map((m) => ({ role: m.role, content: m.content })),
        temperature,
        max_tokens: maxTokens,
      });
      const reply = resp?.choices?.[0]?.message?.content ?? '(empty response)';
      setLastRaw(JSON.stringify(resp, null, 2));
      setMessages([...next, { role: 'assistant', content: reply }]);
    } catch (e: any) {
      setError(e?.message || 'Request failed');
      setMessages(next);
    } finally {
      setRunning(false);
    }
  }

  function reset() {
    setMessages([]);
    setLastRaw('');
    setError('');
  }

  if (!mounted || authLoading || !user) return null;

  return (
    <AppShell sidebar={<SidebarChatList />}>
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="mb-6">
          <Link
            href="/developer"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to developer portal
          </Link>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground">
            API Playground
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Send a chat completion to <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">/v1/chat/completions</code> using one of your keys.
          </p>
        </div>

        {/* Controls */}
        <section className="mb-6 rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">API key</label>
              <select
                value={selectedKeyId}
                onChange={(e) => {
                  setSelectedKeyId(e.target.value);
                  if (e.target.value) loadModelsFor(e.target.value);
                }}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">— pick a key —</option>
                {keys.map((k) => (
                  <option key={k.id} value={String(k.id)}>
                    {k.name} ({k.is_disabled ? 'disabled' : k.is_active ? 'active' : 'inactive'})
                  </option>
                ))}
              </select>
              {!selectedKey?.key && (
                <p className="mt-1 text-xs text-muted-foreground">
                  No secret on file — rotate the key on the portal page to receive a new secret once.
                </p>
              )}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {models.length === 0 && <option value="">(no models available)</option>}
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.id} ({m.source})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 flex items-center justify-between text-xs font-medium text-foreground">
                <span>Temperature</span>
                <span className="font-mono text-muted-foreground">{temperature.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.05"
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                className="w-full"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">Max tokens</label>
              <input
                type="number"
                min={1}
                max={4096}
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value) || 256)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <div className="mt-4">
            <label className="mb-1 block text-xs font-medium text-foreground">Prompt</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  handleRun();
                }
              }}
              className="w-full resize-y rounded-lg border border-input bg-background px-3 py-2 font-mono text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              <kbd className="rounded border border-border bg-muted px-1 font-mono">⌘/Ctrl</kbd>+
              <kbd className="rounded border border-border bg-muted px-1 font-mono">Enter</kbd> to send.
            </p>
          </div>

          {error && (
            <p className="mt-3 flex items-start gap-1.5 text-xs text-destructive">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
              <span className="break-all">{error}</span>
            </p>
          )}

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              onClick={reset}
              className="text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              Clear conversation
            </button>
            <button
              type="button"
              onClick={handleRun}
              disabled={running || !selectedKey?.key}
              className="inline-flex items-center gap-1.5 rounded-lg gradient-bg px-4 py-2 text-sm font-semibold text-white shadow-sm hover:opacity-90 disabled:opacity-50"
            >
              {running ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Send
            </button>
          </div>
        </section>

        {/* Conversation */}
        <section className="rounded-xl border border-border bg-card shadow-sm">
          <div className="border-b border-border px-5 py-3">
            <h2 className="text-sm font-semibold text-foreground">Conversation</h2>
          </div>
          {messages.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-muted-foreground">
              Send a prompt to see the response.
            </div>
          ) : (
            <div className="divide-y divide-border">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`px-5 py-3 ${
                    m.role === 'user' ? 'bg-primary/5' : 'bg-background'
                  }`}
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                        m.role === 'user'
                          ? 'bg-primary/20 text-primary'
                          : 'bg-muted text-foreground'
                      }`}
                    >
                      {m.role}
                    </span>
                  </div>
                  <pre className="whitespace-pre-wrap break-words font-sans text-sm text-foreground">
                    {m.content}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Raw response */}
        {lastRaw && (
          <section className="mt-6 rounded-xl border border-border bg-card shadow-sm">
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold text-foreground">Raw response</h2>
              <button
                type="button"
                onClick={() => navigator.clipboard.writeText(lastRaw)}
                className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                <Copy className="h-3 w-3" />
                Copy
              </button>
            </div>
            <pre className="max-h-80 overflow-auto bg-zinc-950 px-5 py-3 text-xs leading-relaxed text-zinc-100">
              {lastRaw}
            </pre>
          </section>
        )}
      </div>
    </AppShell>
  );
}