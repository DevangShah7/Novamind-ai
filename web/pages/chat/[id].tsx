import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import { getMessages, sendMessage } from '../../lib/api';
import MessageInput from '../../components/MessageInput';
import AppShell, { SidebarChatList } from '../../components/AppShell';
import { useAuth } from '../../lib/auth';
import { Chat, Message } from '../../types';
import { Brain, Sparkles, Copy, Check, MoreVertical, Loader2 } from 'lucide-react';

export const getServerSideProps = async () => ({ props: {} });

export default function ChatPage() {
  const router = useRouter();
  const rawChatId = router.query.chatId;
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
      router.replace('/chat');
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
    if (!user) return;
    setLoading(true);
    try {
      const data = await getMessages(chatId);
      setMessages(data);
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
    setLoading(true);
    setIsTyping(true);
    try {
      await sendMessage(chatId, content);
      setLoading(false);
      await loadMessages();
      setTimeout(() => {
        setIsTyping(false);
      }, 1500 + Math.random() * 1000);
    } catch (err: any) {
      setError(err?.message || 'Failed to send message');
      console.error(err);
      setLoading(false);
      setIsTyping(false);
    }
  };

  const handleCopy = async (msg: Message) => {
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopiedId(msg.id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch (err) {
      console.error('Copy failed', err);
    }
  };

  if (!mounted) {
    // SSR + first client paint: render a loading state. We can't decide
    // whether to redirect to /login until the auth context has hydrated.
    return (
      <div className="flex h-screen items-center justify-center bg-background text-foreground">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
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
                  Online · {chat?.chat_type === 'private' ? 'Private conversation' : 'Group chat'}
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
                      <p className="whitespace-pre-wrap break-words leading-relaxed">{msg.content}</p>
                    </div>

                    <div className={`mt-1 flex items-center gap-2 text-xs text-muted-foreground ${msg.is_ai ? '' : 'flex-row-reverse'}`}>
                      <span>
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                      {msg.is_ai && msg.meta_data?.model && (
                        <>
                          <span>·</span>
                          <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                            {msg.meta_data.model}
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