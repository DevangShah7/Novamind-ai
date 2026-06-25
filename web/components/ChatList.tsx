import { useState } from 'react';
import Link from 'next/link';
import { Chat } from '../types';
import { MessageSquare, Trash2, MoreHorizontal, Sparkles } from 'lucide-react';
import { deleteChat } from '../lib/api';

interface ChatListProps {
  chats: Chat[];
  onDeleteChat: () => void;
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const sec = Math.floor((now - then) / 1000);
  if (sec < 60) return 'just now';
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 604800) return `${Math.floor(sec / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function ChatList({ chats, onDeleteChat }: ChatListProps) {
  const [busyId, setBusyId] = useState<number | null>(null);

  const handleDelete = async (e: React.MouseEvent, chatId: number) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Delete this conversation? This cannot be undone.')) return;
    setBusyId(chatId);
    try {
      await deleteChat(String(chatId));
      onDeleteChat();
    } catch (err) {
      console.error('Failed to delete chat', err);
    } finally {
      setBusyId(null);
    }
  };

  if (chats.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border bg-card/50 px-6 py-16 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl gradient-bg text-white">
          <MessageSquare className="h-8 w-8" />
        </div>
        <h3 className="text-lg font-semibold text-foreground">No conversations yet</h3>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          Start a new chat to see it here. Your conversations are saved in this browser.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {chats.map((chat) => (
        <Link
          key={chat.id}
          href={`/chat/${chat.id}`}
          className="group block"
        >
          <div className="relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-sm transition-all hover:scale-[1.02] hover:border-primary/40 hover:shadow-md">
            {/* Decorative gradient corner */}
            <div className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full gradient-bg opacity-10 blur-2xl transition-opacity group-hover:opacity-20" />

            <div className="relative flex items-start justify-between gap-2">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <MessageSquare className="h-5 w-5" />
              </div>
              <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <button
                  type="button"
                  onClick={(e) => handleDelete(e, chat.id)}
                  disabled={busyId === chat.id}
                  aria-label="Delete chat"
                  className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            <h3 className="relative mt-4 line-clamp-2 text-base font-semibold text-foreground group-hover:text-primary">
              {chat.title || 'Untitled chat'}
            </h3>
            <p className="relative mt-2 flex items-center gap-1 text-xs text-muted-foreground">
              <Sparkles className="h-3 w-3" />
              {timeAgo(chat.updated_at || chat.created_at)}
            </p>

            {/* Animated bottom border on hover */}
            <div className="absolute bottom-0 left-0 h-0.5 w-0 gradient-bg transition-all duration-300 group-hover:w-full" />
          </div>
        </Link>
      ))}
    </div>
  );
}