import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { getChats, createChat, isMockMode } from '../../lib/api';
import ChatList from '../../components/ChatList';
import AppShell, { SidebarChatList } from '../../components/AppShell';
import { useAuth } from '../../lib/auth';
import { Sparkles, MessageSquarePlus, Wand2, Code2, BookOpen, Lightbulb, ArrowRight } from 'lucide-react';

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
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    loadChats();
  }, []);

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
      setError(err?.message || 'Failed to create chat');
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    router.replace('/login');
    return null;
  }

  return (
    <AppShell sidebar={<SidebarChatList />}>
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8 sm:py-12">
        {isMockMode && (
          <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-300 animate-fade-in">
            <strong>Demo mode.</strong> Running with an in-browser mock backend (localStorage). Data stays on this device.
            Try the default admin: <code className="rounded bg-amber-500/20 px-1.5 py-0.5">admin@novamind.ai</code> / <code className="rounded bg-amber-500/20 px-1.5 py-0.5">admin123</code>.
          </div>
        )}

        {/* Hero "new chat" panel */}
        <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-10">
          <div className="pointer-events-none absolute -right-20 -top-20 h-60 w-60 rounded-full gradient-bg opacity-10 blur-3xl" />
          <div className="relative">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-primary">
              <Sparkles className="h-4 w-4" />
              Start a new conversation
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              What can I help you with today?
            </h1>
            <p className="mt-2 text-muted-foreground">
              Ask anything, paste code, or pick one of the starters below.
            </p>

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

            {/* Example prompt chips */}
            <div className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {EXAMPLE_PROMPTS.map(({ icon: Icon, label, text }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => handleCreateChat(text)}
                  disabled={loading}
                  className="group flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-2.5 text-left text-sm transition-colors hover:border-primary/40 hover:bg-muted"
                >
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary group-hover:bg-primary/20">
                    <Icon className="h-4 w-4" />
                  </div>
                  <span className="flex-1 text-foreground">{label}</span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                </button>
              ))}
            </div>
          </div>
        </div>

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