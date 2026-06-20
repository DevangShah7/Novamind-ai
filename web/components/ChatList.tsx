import Link from 'next/link';
import { Chat } from '../../types';

interface ChatListProps {
  chats: Chat[];
  onDeleteChat: () => void;
}

export default function ChatList({ chats, onDeleteChat }: ChatListProps) {
  if (chats.length === 0) {
    return (
      <div className="py-8 text-center text-gray-500">
        No chats yet. Create a new chat to get started.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {chats.map((chat) => (
        <Link
          key={chat.id}
          href={`/chat/${chat.id}`}
          passHref
          className="block"
        >
          <div className="flex items-center justify-between px-4 py-3 bg-white rounded-lg shadow-sm hover:bg-gray-50">
            <div className="flex-1">
              <h3 className="font-medium text-gray-900">{chat.title}</h3>
              <p className="text-sm text-gray-500">
                {new Date(chat.updated_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}