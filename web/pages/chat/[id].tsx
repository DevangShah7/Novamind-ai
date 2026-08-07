import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import { getMessages, sendMessage } from '../../lib/api';
import MessageInput from '../../components/MessageInput';
import AppShell, { SidebarChatList } from '../../components/AppShell';
import { useAuth } from '../../lib/auth';
import { Chat, Message, asMeta } from '../../types';
import { Brain, Sparkles, Copy, Check, MoreVertical, Loader2, Download, Presentation, FileText, Code2, Terminal, AlertTriangle } from 'lucide-react';
import { Skeleton } from '../../components/ui/Skeleton';
import { toast } from '../../components/ui/Toaster';

export const getServerSideProps = async () => ({ props: {} });

// Small renderer for an image-typed message bubble. Reads base64 from
// meta_data (the chat endpoint persists it there) and renders a real
// <img>. A Download link lets the user save the file to disk.
function ImageBubble({ msg }: { msg: Message }) {
  const meta = asMeta(msg.meta_data) ?? {};
  const b64 = typeof meta.image_base64 === 'string' ? meta.image_base64 : null;
  const fmt = typeof meta.image_format === 'string' ? meta.image_format : 'jpeg';
  const prompt = typeof meta.prompt === 'string' ? meta.prompt : msg.content;
  const w = typeof meta.width === 'number' ? meta.width : null;
  const h = typeof meta.height === 'number' ? meta.height : null;

  if (!b64) {
    // Defensive fallback — the row claims it's an image but the payload
    // didn't round-trip. Surface something honest rather than a broken
    // <img> icon.
    return (
      <div className="text-sm italic text-muted-foreground">
        Image unavailable.
      </div>
    );
  }

  const dataUrl = `data:image/${fmt};base64,${b64}`;
  const downloadName = `novamind-${msg.id}.${fmt === 'jpeg' ? 'jpg' : fmt}`;

  return (
    <div className="space-y-2">
      <p className="text-sm leading-relaxed">{msg.content}</p>
      <a
        href={dataUrl}
        download={downloadName}
        className="group block max-w-md overflow-hidden rounded-xl border border-border bg-background shadow-sm transition-shadow hover:shadow-md"
      >
        <img
          src={dataUrl}
          alt={prompt}
          width={w ?? undefined}
          height={h ?? undefined}
          className="block h-auto w-full"
        />
      </a>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <a
          href={dataUrl}
          download={downloadName}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 transition-colors hover:bg-muted hover:text-foreground"
        >
          <Download className="h-3 w-3" />
          Download
        </a>
        {meta.generation_model && (
          <>
            <span>·</span>
            <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
              {String(meta.generation_model)}
            </span>
          </>
        )}
        {w && h && (
          <>
            <span>·</span>
            <span>{w}×{h}</span>
          </>
        )}
      </div>
    </div>
  );
}

// PowerPoint (.pptx) bubble. Reads `file_b64` (base64-encoded
// presentation), `filename`, `size_bytes`, and a few descriptive
// metadata fields from `meta_data`. Renders a download-card with the
// theme + slide count pill, similar in spirit to ImageBubble.
function PptxBubble({ msg }: { msg: Message }) {
  const meta = asMeta(msg.meta_data) ?? {};
  const b64 = typeof meta.file_b64 === 'string' ? meta.file_b64 : null;
  const filename =
    typeof meta.filename === 'string' ? meta.filename : `slides-${msg.id}.pptx`;
  const sizeBytes = typeof meta.size_bytes === 'number' ? meta.size_bytes : null;
  const theme = typeof meta.theme === 'string' ? meta.theme : null;
  const slideCount = typeof meta.slide_count === 'number' ? meta.slide_count : null;
  const modelUsed = typeof meta.model_used === 'string' ? meta.model_used : null;

  if (!b64) {
    return (
      <div className="text-sm italic text-muted-foreground">
        Presentation unavailable.
      </div>
    );
  }

  const dataUrl = `data:application/vnd.openxmlformats-officedocument.presentationml.presentation;base64,${b64}`;

  return (
    <div className="space-y-2">
      <p className="text-sm leading-relaxed">{msg.content}</p>
      <a
        href={dataUrl}
        download={filename}
        className="group flex max-w-md items-start gap-3 rounded-xl border border-border bg-background p-3.5 shadow-sm transition-all hover:border-primary/40 hover:shadow-md"
      >
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400">
          <Presentation className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{filename}</p>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase">
              PPTX
            </span>
            {slideCount != null && <span>{slideCount} slides</span>}
            {theme && (
              <>
                <span>·</span>
                <span>{theme}</span>
              </>
            )}
            {sizeBytes != null && (
              <>
                <span>·</span>
                <span>{Math.ceil(sizeBytes / 1024)} KB</span>
              </>
            )}
          </p>
        </div>
        <Download className="h-4 w-4 flex-shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
      </a>
      {modelUsed && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
            {modelUsed}
          </span>
        </div>
      )}
    </div>
  );
}

// Word (.docx) bubble. Mirror of PptxBubble but with a different icon
// and the docx-specific metadata (style, paragraph_count).
function DocxBubble({ msg }: { msg: Message }) {
  const meta = asMeta(msg.meta_data) ?? {};
  const b64 = typeof meta.file_b64 === 'string' ? meta.file_b64 : null;
  const filename =
    typeof meta.filename === 'string' ? meta.filename : `document-${msg.id}.docx`;
  const sizeBytes = typeof meta.size_bytes === 'number' ? meta.size_bytes : null;
  const style = typeof meta.style === 'string' ? meta.style : null;
  const paragraphCount = typeof meta.paragraph_count === 'number' ? meta.paragraph_count : null;
  const modelUsed = typeof meta.model_used === 'string' ? meta.model_used : null;

  if (!b64) {
    return (
      <div className="text-sm italic text-muted-foreground">
        Document unavailable.
      </div>
    );
  }

  const dataUrl = `data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,${b64}`;

  return (
    <div className="space-y-2">
      <p className="text-sm leading-relaxed">{msg.content}</p>
      <a
        href={dataUrl}
        download={filename}
        className="group flex max-w-md items-start gap-3 rounded-xl border border-border bg-background p-3.5 shadow-sm transition-all hover:border-primary/40 hover:shadow-md"
      >
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
          <FileText className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{filename}</p>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase">
              DOCX
            </span>
            {style && (
              <>
                <span className="capitalize">{style}</span>
                <span>·</span>
              </>
            )}
            {paragraphCount != null && <span>{paragraphCount} paragraphs</span>}
            {sizeBytes != null && (
              <>
                <span>·</span>
                <span>{Math.ceil(sizeBytes / 1024)} KB</span>
              </>
            )}
          </p>
        </div>
        <Download className="h-4 w-4 flex-shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
      </a>
      {modelUsed && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
            {modelUsed}
          </span>
        </div>
      )}
    </div>
  );
}

// Code-run bubble. The backend executed the user's code in a
// sandboxed subprocess and persisted the result in meta_data. We
// render: a header chip (language, exit code, elapsed), the source
// code in a monospace block with a Copy button, and stdout/stderr in
// a collapsible panel. Failures (`runtime_missing`, `timed_out`, non-
// zero exit) get an error-state pill so the user sees at a glance.
function CodeBubble({ msg }: { msg: Message }) {
  const meta = asMeta(msg.meta_data) ?? {};
  const language = typeof meta.language === 'string' ? meta.language : 'python';
  const code = typeof meta.code === 'string' ? meta.code : '';
  const stdout = typeof meta.stdout === 'string' ? meta.stdout : '';
  const stderr = typeof meta.stderr === 'string' ? meta.stderr : '';
  const exitCode = typeof meta.exit_code === 'number' ? meta.exit_code : null;
  const timedOut = meta.timed_out === true;
  const runtimeMissing = meta.runtime_missing === true;
  const elapsedMs = typeof meta.elapsed_ms === 'number' ? meta.elapsed_ms : null;
  const [copied, setCopied] = useState(false);

  const ok = !runtimeMissing && !timedOut && exitCode === 0;
  const statusLabel = runtimeMissing
    ? 'Runtime not available'
    : timedOut
    ? 'Timed out'
    : exitCode === 0
    ? 'Success'
    : `Exit ${exitCode}`;

  const statusColor = ok
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
    : 'border-destructive/30 bg-destructive/10 text-destructive';

  const handleCopyCode = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error('Copy failed', err);
    }
  };

  return (
    <div className="space-y-2">
      <p className="text-sm leading-relaxed">{msg.content}</p>
      <div
        className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs ${statusColor}`}
      >
        {!ok && <AlertTriangle className="h-3 w-3" />}
        <Code2 className="h-3 w-3" />
        <span className="font-medium">{language.toUpperCase()}</span>
        <span>·</span>
        <span>{statusLabel}</span>
        {elapsedMs != null && (
          <>
            <span>·</span>
            <span>{elapsedMs} ms</span>
          </>
        )}
      </div>
      {code && (
        <div className="relative max-w-2xl overflow-hidden rounded-lg border border-border bg-zinc-950 text-zinc-100 shadow-sm">
          <button
            type="button"
            onClick={handleCopyCode}
            className="absolute right-2 top-2 z-10 flex h-7 items-center gap-1 rounded-md bg-zinc-800/80 px-2 text-xs text-zinc-100 backdrop-blur-sm transition-colors hover:bg-zinc-700"
            aria-label="Copy code"
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 text-emerald-400" /> Copied
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" /> Copy
              </>
            )}
          </button>
          <pre className="overflow-x-auto p-3.5 pr-20 text-xs leading-relaxed">
            <code>{code}</code>
          </pre>
        </div>
      )}
      {(stdout || stderr) && (
        <details className="max-w-2xl rounded-lg border border-border bg-muted/30">
          <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground">
            <Terminal className="mr-1.5 inline-block h-3 w-3" />
            Output{stdout && ` (${stdout.split('\n').length} lines)`}
            {stderr && ' · has errors'}
          </summary>
          <div className="space-y-2 border-t border-border px-3 py-2">
            {stdout && (
              <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-zinc-950/95 p-2.5 text-xs text-zinc-100">
                <code>{stdout}</code>
              </pre>
            )}
            {stderr && (
              <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-red-950/95 p-2.5 text-xs text-red-100">
                <code>{stderr}</code>
              </pre>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

export default function ChatPage() {
  const router = useRouter();
  // The dynamic route is [id].tsx, so the query key is `id` — not `chatId`.
  // (Earlier this read `router.query.chatId`, which is always undefined and
  // immediately bounced users back to /chat. That's why chat appeared broken.)
  const rawChatId = router.query.id;
  const chatId = Array.isArray(rawChatId) ? rawChatId[0] : rawChatId;
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chat, setChat] = useState<Chat | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [mounted, setMounted] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const { user } = useAuth();

  useEffect(() => {
    setMounted(true);
    if (!chatId || typeof chatId !== 'string') {
      return;
    }
    loadChat();
    loadMessages();
  }, [chatId]);

  // Mock backend fires 'mock:message-added' when an async assistant
  // reply lands. Real backends do this over WebSockets / SSE in the future.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ chatId: string }>).detail;
      if (detail?.chatId === chatId) {
        loadMessages();
        setIsTyping(false);
      }
    };
    window.addEventListener('mock:message-added', handler);
    return () => window.removeEventListener('mock:message-added', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId]);

  const loadChat = async () => {
    setChat({
      id: parseInt(chatId),
      title: `Chat ${chatId}`,
      user_id: typeof user?.id === 'number' ? user.id : 1,
      chat_type: 'private',
      status: 'active',
      settings: {},
      tags: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_message_at: null,
      messages: []
    });
  };

  const loadMessages = async () => {
    if (!user || !chatId) return;
    setLoading(true);
    try {
      const data = await getMessages(chatId);
      setMessages(data);
      setError(null);
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } catch (err: any) {
      setError(err?.message || 'Failed to load messages');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!user || !content.trim()) return;
    // Two side-channels from MessageInput: __pendingImageOpts (image
    // gen) and __pendingFileOpts (PPT/Word/Code). Image mode takes
    // priority because the existing UI contract for that path is
    // well-established; file opts are the new path.
    const w = typeof window !== 'undefined' ? (window as any) : null;
    const pendingImage = w?.__pendingImageOpts ?? null;
    const pendingFile = w?.__pendingFileOpts ?? null;
    const messageType = pendingImage?.messageType ?? pendingFile?.messageType;
    const metaData = pendingImage?.metaData ?? pendingFile?.metaData;
    setLoading(true);
    setIsTyping(true);
    setError(null);
    try {
      await sendMessage(chatId, content, { messageType, metaData });
      setLoading(false);
      await loadMessages();
      setIsTyping(false);
    } catch (err: any) {
      setError(err?.message || 'Failed to send message');
      toast.error(err?.message || 'Failed to send message');
      console.error(err);
      setLoading(false);
      setIsTyping(false);
    } finally {
      // Consume both side-channels so a subsequent text send isn't
      // accidentally treated as another image or file generation.
      if (w) {
        w.__pendingImageOpts = null;
        w.__pendingFileOpts = null;
      }
    }
  };

  const handleCopy = async (msg: Message) => {
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopiedId(msg.id);
      setTimeout(() => setCopiedId(null), 1500);
      toast.success('Copied to clipboard');
    } catch (err) {
      console.error('Copy failed', err);
      toast.error('Could not copy to clipboard');
    }
  };

  if (!mounted) {
    // SSR + first client paint: render a skeleton shell. We can't decide
    // whether to redirect to /login until the auth context has hydrated.
    return (
      <div className="flex h-screen flex-col bg-background text-foreground">
        <div className="flex-shrink-0 border-b border-border bg-card/80 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Skeleton className="h-10 w-10 rounded-lg" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        </div>
        <div className="mx-auto w-full max-w-3xl flex-1 space-y-6 px-4 py-8 sm:px-6">
          <div className="flex items-start gap-3">
            <Skeleton className="h-9 w-9 rounded-lg" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-72" />
              <Skeleton className="h-4 w-56" />
            </div>
          </div>
          <div className="flex items-start gap-3 flex-row-reverse">
            <Skeleton className="h-9 w-9 rounded-lg" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-40" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!user) {
    router.replace('/login');
    return null;
  }

  if (!chatId || typeof chatId !== 'string') {
    return null;
  }

  return (
    <AppShell sidebar={<SidebarChatList />}>
      <div className="flex h-full flex-col">
        {/* Chat header */}
        <div className="flex-shrink-0 border-b border-border bg-card/80 px-4 py-3 backdrop-blur-md sm:px-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg gradient-bg text-white shadow-sm">
                <Brain className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <h1 className="truncate text-base font-semibold text-foreground sm:text-lg">
                  {chat?.title || 'NovaMind AI Chat'}
                </h1>
                <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Online · {chat?.chat_type === 'private' ? 'Private conversation' : 'Group chat'} · NovaMind local engine
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                aria-label="More options"
                className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <MoreVertical className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto bg-background">
          <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
            {error && (
              <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
                {error}
              </div>
            )}

            {messages.length === 0 && !isTyping && (
              <div className="flex flex-col items-center justify-center py-20 text-center animate-fade-in">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl gradient-bg text-white shadow-lg">
                  <Sparkles className="h-8 w-8" />
                </div>
                <h2 className="text-xl font-semibold text-foreground">Start the conversation</h2>
                <p className="mt-2 max-w-md text-sm text-muted-foreground">
                  Ask a question, paste some code, or just say hi. I&apos;m here to help.
                </p>
              </div>
            )}

            {isTyping && (
              <div className="mb-4 flex items-start gap-3 animate-fade-in">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg gradient-bg text-white">
                  <Brain className="h-4 w-4" />
                </div>
                <div className="rounded-2xl rounded-tl-sm border border-border bg-card px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-1.5">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                    <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse [animation-delay:150ms]" />
                    <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-6">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`group flex items-start gap-3 animate-fade-in ${
                    msg.is_ai ? '' : 'flex-row-reverse'
                  }`}
                >
                  {msg.is_ai ? (
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg gradient-bg text-white">
                      <Brain className="h-4 w-4" />
                    </div>
                  ) : (
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-muted text-foreground">
                      <span className="text-xs font-semibold">
                        {(user.full_name || user.username || user.email || 'U').slice(0, 2).toUpperCase()}
                      </span>
                    </div>
                  )}

                  <div className={`flex max-w-[80%] flex-col ${msg.is_ai ? 'items-start' : 'items-end'}`}>
                    <div
                      className={`rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                        msg.is_ai
                          ? 'rounded-tl-sm border border-border bg-card text-foreground'
                          : 'rounded-tr-sm gradient-bg text-white'
                      }`}
                    >
                      {msg.message_type === 'image' ? (
                        msg.is_ai ? (
                          <ImageBubble msg={msg} />
                        ) : (
                          // User side: they asked for an image. Show the
                          // prompt as text and an image icon as a visual
                          // breadcrumb. We don't have their text in
                          // meta_data here (it's in `content`), so reuse it.
                          <div className="space-y-1">
                            <p className="whitespace-pre-wrap break-words leading-relaxed">
                              {msg.content}
                            </p>
                            <p className="flex items-center gap-1 text-[11px] opacity-80">
                              <Sparkles className="h-3 w-3" />
                              Generating image…
                            </p>
                          </div>
                        )
                      ) : msg.message_type === 'file' && msg.is_ai ? (
                        // File-typed AI message: pick pptx vs docx
                        // from meta_data.kind (not from message_type —
                        // the backend reuses MessageType.FILE for both
                        // to keep the enum stable).
                        asMeta(msg.meta_data)?.kind === 'docx' ? (
                          <DocxBubble msg={msg} />
                        ) : (
                          <PptxBubble msg={msg} />
                        )
                      ) : msg.message_type === 'code' ? (
                        msg.is_ai ? (
                          <CodeBubble msg={msg} />
                        ) : (
                          // User side: they asked the assistant to run
                          // code. Show prompt + a small breadcrumb.
                          <div className="space-y-1">
                            <p className="whitespace-pre-wrap break-words leading-relaxed">
                              {msg.content}
                            </p>
                            <p className="flex items-center gap-1 text-[11px] opacity-80">
                              <Code2 className="h-3 w-3" />
                              Running code…
                            </p>
                          </div>
                        )
                      ) : msg.message_type === 'file' && !msg.is_ai ? (
                        // User side: they asked for a file. Match the
                        // image-mode breadcrumb style for consistency.
                        <div className="space-y-1">
                          <p className="whitespace-pre-wrap break-words leading-relaxed">
                            {msg.content}
                          </p>
                          <p className="flex items-center gap-1 text-[11px] opacity-80">
                            <Presentation className="h-3 w-3" />
                            Building file…
                          </p>
                        </div>
                      ) : (
                        <p className="whitespace-pre-wrap break-words leading-relaxed">{msg.content}</p>
                      )}
                    </div>

                    <div className={`mt-1 flex items-center gap-2 text-xs text-muted-foreground ${msg.is_ai ? '' : 'flex-row-reverse'}`}>
                      <span>
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                      {msg.is_ai && asMeta(msg.meta_data)?.model && (
                        <>
                          <span>·</span>
                          <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                            {asMeta(msg.meta_data)!.model}
                          </span>
                        </>
                      )}
                      {msg.is_ai && (
                        <button
                          type="button"
                          onClick={() => handleCopy(msg)}
                          aria-label="Copy message"
                          className="flex h-6 w-6 items-center justify-center rounded opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100"
                        >
                          {copiedId === msg.id ? (
                            <Check className="h-3 w-3 text-emerald-500" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>

        {/* Input */}
        <div className="flex-shrink-0 border-t border-border bg-card/80 backdrop-blur-md">
          <div className="mx-auto max-w-3xl px-4 py-3 sm:px-6 sm:py-4">
            <MessageInput onSend={handleSendMessage} loading={loading} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}