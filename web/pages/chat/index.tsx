import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { getChats, createChat } from '../../lib/api';
import ChatList from '../../components/ChatList';
import { useAuth } from '../../lib/auth';

// Render at request time so auth-protected chat list isn't statically prerendered.
export const getServerSideProps = async () => ({ props: {} });

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
    } catch (err) {
      setError('Failed to load chats');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setLoading(true);
    try {
      const newChat = await createChat(title);
      setChats([newChat, ...chats]);
      setTitle('');
      router.push(`/chat/${newChat.id}`);
    } catch (err) {
      setError('Failed to create chat');
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    router.replace('/login');
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="py-8">
          <div className="mb-6 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Your Chats</h1>
            <form onSubmit={handleCreateChat} className="flex space-x-2">
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="New chat title"
                className="flex-1 min-w-0 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
              <button
                type="submit"
                disabled={loading}
                className="rounded-md border border-transparent px-4 py-2 bg-indigo-600 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
              >
                {loading ? 'Creating...' : 'New Chat'}
              </button>
            </form>
          </div>
          {error && <p className="mb-4 text-sm text-red-500">{error}</p>}
          <ChatList chats={chats} onDeleteChat={loadChats} />
        </div>
      </div>
    </div>
  );
}