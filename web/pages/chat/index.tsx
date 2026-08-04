import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { getChats, createChat, isMockMode } from '../../lib/api';
import ChatList from '../../components/ChatList';
import AppShell, { SidebarChatList } from '../../components/AppShell';
import { useAuth } from '../../lib/auth';
import { Sparkles, MessageSquarePlus, Wand2, Code2, BookOpen, Lightbulb, ArrowRight, Loader2, FileText, Presentation, Image as ImageIcon } from 'lucide-react';
import { Skeleton } from '../../components/ui/Skeleton';
import { toast } from '../../components/ui/Toaster';
import { ThinkingOrb } from '../../components/chat/ThinkingOrb';
import { GlassCard } from '../../components/dashboard/GlassCard';
import { StaggerChildren, StaggerItem } from '../../components/motion';

export const getServerSideProps = async () => ({ props: {} });

const EXAMPLE_PROMPTS = [
  { icon: Wand2, label: 'Write a creative story', text: 'Write a short story about a sentient AI learning to paint' },
  { icon: Code2, label: 'Help me code', text: 'Explain how async/await works in JavaScript with examples' },
  { icon: BookOpen, label: 'Summarize a topic', text: 'Give me a beginner-friendly summary of quantum computing' },
  { icon: Lightbulb, label: 'Brainstorm ideas', text: 'Help me brainstorm 5 product names for a meditation app' },
] as const;

export default function ChatListPage() {
  const [chats, setChats] = useState([]);
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mounted, setMounted] = useState(false);
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    setMounted(true);
    if (user) loadChats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const loadChats = async () => {
    setLoading(true);
    try {
      const data = await getChats();
      setChats(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load chats');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateChat = async (text?: string) => {
    const t = (text ?? title).trim();
    if (!t) return;
    setLoading(true);
    try {
      const newChat = await createChat(t);
      setChats([newChat, ...chats]);
      setTitle('');
      router.push(`/chat/${newChat.id}`);
    } catch (err: any) {
      const msg = err?.message || 'Failed to create chat';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  if (!mounted) {
    // SSR + first client paint: render a skeleton shell while the auth
    // context hydrates — same shape as the real page so the transition
    // is seamless.
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <Skeleton className="h-48 w-full rounded-2xl" />
        <div className="mt-10 space-y-3">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      </div>
    );
  }

  if (!user) {
    // Redirect with the dev-error marker so /login can show the actual
    // fetch error (silent redirects have been the #1 source of confusion
    // when the dev tunnel rotates underneath the SPA).
    router.replace('/login?dev_error=1');
    return null;
  }

  return (
    <AppShell sidebar={<SidebarChatList />}>
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8 sm:py-12">
        {isMockMode ? (
          <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-300 animate-fade-in">
            <strong>Demo mode.</strong> Running with an in-browser mock backend (localStorage).
            Data stays on this device. Replies come from <em>NovaMind</em>, our private AI assistant.
            Try the default admin: <code className="rounded bg-amber-500/20 px-1.5 py-0.5">admin@novamind.ai</code> / <code className="rounded bg-amber-500/20 px-1.5 py-0.5">admin123</code>.
          </div>
        ) : (
          <div className="mb-6 rounded-lg border border-indigo-500/30 bg-indigo-500/5 px-4 py-2 text-xs text-indigo-700 dark:text-indigo-300 animate-fade-in flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-indigo-500" />
            Powered by NovaMind.
          </div>
        )}

        {/* Hero "new chat" panel */}
        <GlassCard className="p-6 sm:p-10" noHover noShimmer>
          <div className="pointer-events-none absolute -right-20 -top-20 h-60 w-60 rounded-full gradient-bg opacity-10 blur-3xl" />
          <div className="relative">
            <div className="mb-4 flex items-center gap-4">
              <ThinkingOrb status="idle" size={64} />
              <div>
                <div className="mb-1 flex items-center gap-2 text-sm font-medium text-primary">
                  <Sparkles className="h-4 w-4" />
                  Start a new conversation
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                  What can I help you with today?
                </h1>
                <p className="mt-1 text-muted-foreground">
                  Ask anything, paste code, or pick one of the starters below.
                </p>
              </div>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleCreateChat();
              }}
              className="mt-6 flex flex-col gap-2 sm:flex-row"
            >
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ask NovaMind anything…"
                className="flex-1 rounded-lg border border-input bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button
                type="submit"
                disabled={loading || !title.trim()}
                className="group inline-flex items-center justify-center gap-2 rounded-lg gradient-bg px-5 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:shadow-lg hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
              >
                <MessageSquarePlus className="h-4 w-4" />
                {loading ? 'Starting…' : 'Start chat'}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </button>
            </form>

            {/* Quick links to the document / image generators */}
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="font-medium">Quick tools:</span>
              <Link
                href={`/tools?kind=pdf&prompt=${encodeURIComponent(title)}`}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2.5 py-1 hover:border-primary/40 hover:text-primary"
                legacyBehavior={false}
              >
                <FileText className="h-3 w-3" /> PDF
              </Link>
              <Link
                href={`/tools?kind=pptx&prompt=${encodeURIComponent(title)}`}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2.5 py-1 hover:border-primary/40 hover:text-primary"
                legacyBehavior={false}
              >
                <Presentation className="h-3 w-3" /> Slides
              </Link>
              <Link
                href={`/tools?kind=image&prompt=${encodeURIComponent(title)}`}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2.5 py-1 hover:border-primary/40 hover:text-primary"
                legacyBehavior={false}
              >
                <ImageIcon className="h-3 w-3" /> Image
              </Link>
            </div>

            {/* Example prompt chips */}
            <StaggerChildren className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2" delay={0.1} gap={0.06}>
              {EXAMPLE_PROMPTS.map(({ icon: Icon, label, text }) => (
                <StaggerItem key={label}>
                  <button
                    type="button"
                    onClick={() => handleCreateChat(text)}
                    disabled={loading}
                    className="group flex w-full items-center gap-3 rounded-lg border border-border bg-background px-3 py-2.5 text-left text-sm transition-colors hover:border-primary/40 hover:bg-muted"
                  >
                    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary group-hover:bg-primary/20">
                      <Icon className="h-4 w-4" />
                    </div>
                    <span className="flex-1 text-foreground">{label}</span>
                    <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </button>
                </StaggerItem>
              ))}
            </StaggerChildren>
          </div>
        </GlassCard>

        {/* Recent chats */}
        <div className="mt-10">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            <span>Recent conversations</span>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-foreground">
              {chats.length}
            </span>
          </h2>
          {error && (
            <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
              {error}
            </div>
          )}
          <ChatList chats={chats} onDeleteChat={loadChats} />
        </div>
      </div>
    </AppShell>
  );
}