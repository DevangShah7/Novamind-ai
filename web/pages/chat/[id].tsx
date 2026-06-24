import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import { getMessages, sendMessage } from '../../lib/api';
import MessageList from '../../components/MessageList';
import MessageInput from '../../components/MessageInput';
import { useAuth } from '../../lib/auth';
import { Chat, Message } from '../../types';

export default function ChatPage() {
  const router = useRouter();
  const rawChatId = router.query.chatId;
  const chatId = Array.isArray(rawChatId) ? rawChatId[0] : rawChatId;
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chat, setChat] = useState<Chat | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { user } = useAuth();

  useEffect(() => {
    if (!chatId || typeof chatId !== 'string') {
      router.replace('/chat');
      return;
    }
    loadChat();
    loadMessages();
  }, [chatId]);

  const loadChat = async () => {
    // In a real app, we'd fetch chat details
    // For now, we'll create a placeholder
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

      // Scroll to bottom after messages load
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } catch (err) {
      setError('Failed to load messages');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!user || !content.trim()) return;

    setLoading(true);
    setIsTyping(true); // Show typing indicator
    try {
      await sendMessage(chatId, content);
      // Clear input (handled by MessageInput component)
      setLoading(false);

      // Reload messages to include the new one
      await loadMessages();

      // Simulate AI thinking time (hide typing indicator after delay)
      setTimeout(() => {
        setIsTyping(false);
      }, 1500 + Math.random() * 1000); // Random delay between 1.5-2.5 seconds
    } catch (err) {
      setError('Failed to send message');
      console.error(err);
      setLoading(false);
      setIsTyping(false); // Hide typing indicator on error
    }
  };

  if (!user) {
    router.replace('/login');
    return null;
  }

  if (!chatId || typeof chatId !== 'string') {
    return <div>Loading...</div>;
  }

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* Chat Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="h-10 w-10 flex items-center justify-center bg-indigo-100 rounded-full">
                <span className="text-indigo-600 font-medium">AI</span>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  {chat?.title || 'NovaMind AI Chat'}
                </h1>
                <p className="text-sm text-gray-500">
                  {chat?.chat_type === 'private' ? 'Private conversation' : 'Group chat'}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <button
                className="p-2 rounded hover:bg-gray-100"
                title="Chat settings"
              >
                {/* Settings icon would go here */}
                <span className="text-gray-500">⋯</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {isTyping && (
          <div className="mb-4 flex items-center space-x-3">
            <div className="h-10 w-10 flex items-center justify-center bg-indigo-100 rounded-full">
              <span className="text-indigo-600 font-medium">AI</span>
            </div>
            <div className="flex space-x-2">
              <div className="h-2 w-2 bg-indigo-500 rounded-full animate-pulse"></div>
              <div className="h-2 w-2 bg-indigo-500 rounded-full animate-pulse delay-100"></div>
              <div className="h-2 w-2 bg-indigo-500 rounded-full animate-pulse delay-200"></div>
              <span className="text-sm text-gray-500">NovaMind AI is typing...</span>
            </div>
          </div>
        )}

        <div className="space-y-6">
          {messages.map((msg, index) => (
            <div
              key={msg.id}
              className="flex w-full"
            >
              {msg.is_ai ? (
                <>
                  <div className="flex-shrink-0 h-10 w-10 flex items-center justify-center bg-indigo-100 rounded-full">
                    <span className="text-indigo-600 font-medium">AI</span>
                  </div>
                  <div className="ml-3 max-w-[80%]">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-xs text-indigo-600 font-medium">NovaMind AI</span>
                      <span className="text-xs text-gray-400">
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className="bg-gray-50 rounded-xl px-4 py-3 max-w-[80%] break-words">
                      <div className="prose prose-sm max-w-none">
                        {msg.content}
                      </div>
                    </div>
                    {msg.meta_data && (
                      <div className="mt-2 flex items-center space-x-3 text-xs text-gray-400">
                        {msg.meta_data.model && (
                          <span className="flex items-center space-x-1">
                            <span className="h-2 w-2 bg-green-500 rounded-full"></span>
                            <span>{msg.meta_data.model}</span>
                          </span>
                        )}
                        {msg.meta_data.tokens && (
                          <span>{msg.meta_data.tokens} tokens</span>
                        )}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <div className="ml-auto flex-shrink-0">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-xs text-gray-400">
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                      <div className="flex-shrink-0 h-10 w-10 flex items-center justify-center bg-gray-100 rounded-full">
                        <span className="text-gray-600 font-medium">{msg.user_id ? 'You' : 'User'}</span>
                      </div>
                    </div>
                    <div className="bg-indigo-600 text-white rounded-xl px-4 py-3 max-w-[80%] break-words">
                      <div className="prose prose-sm max-w-none text-white">
                        {msg.content}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          ))}

          {/* Scroll spacer */}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Container */}
      <div className="border-t border-gray-200">
        <div className="px-4 sm:px-6 lg:px-8 py-4">
          <MessageInput
            onSend={handleSendMessage}
            loading={loading}
          />
        </div>
      </div>
    </div>
  );
}