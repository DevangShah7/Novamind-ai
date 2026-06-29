import { Message, asMeta } from '../types';
import { formatDistanceToNow } from 'date-fns';
import { Copy, Speaker } from 'lucide-react';
import { textToSpeech } from '../lib/voice';

interface MessageListProps {
  messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="py-12 text-center text-gray-500">
        <div className="flex items-center justify-center space-x-3 mb-4">
          <div className="h-12 w-12 flex items-center justify-center bg-indigo-100 rounded-full">
            <span className="text-indigo-600 font-medium">🤖</span>
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">Welcome to NovaMind AI</h3>
            <p className="text-sm text-gray-600">
              I'm your AI assistant. Ask me anything or start a conversation!
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 py-6">
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
              <div className="ml-3 max-w-[80%] relative">
                <div className="flex items-center space-x-2 mb-1">
                  <span className="text-xs text-indigo-600 font-medium">NovaMind AI</span>
                  <span className="text-xs text-gray-400">
                    {formatDistanceToNow(new Date(msg.created_at), { addSuffix: true }) !== 'just now'
                      ? formatDistanceToNow(new Date(msg.created_at), { addSuffix: true })
                      : 'just now'}
                  </span>
                </div>
                <div className="bg-gray-50 rounded-xl px-4 py-3 max-w-[80%] break-words">
                  <div className="prose prose-sm max-w-none">
                    {msg.content}
                  </div>
                  {msg.message_type === 'code' && (
                    <div className="mt-3 bg-gray-100 rounded p-3 text-xs font-mono overflow-auto">
                      {/* In a real app, we'd use a syntax highlighting library like Prism or Highlight.js */}
                      <code>{msg.content}</code>
                    </div>
                  )}
                  {msg.message_type === 'image' && (
                    <div className="mt-3">
                      {/* In a real app, we'd display the image */}
                      <div className="aspect-w-16 aspect-h-9 bg-gray-200 rounded flex items-center justify-center">
                        <span className="text-gray-500">[Image]</span>
                      </div>
                    </div>
                  )}
                </div>
                <div className="mt-2 flex items-center space-x-3 text-xs text-gray-400">
                  {(() => {
                    // What served this reply? Prefer backend metadata (real engine
                    // name); fall back to the local engine label so the UI is
                    // always honest about what's actually behind the answer.
                    const meta = asMeta(msg.meta_data);
                    const engineName =
                      meta?.model ||
                      (typeof window !== 'undefined' &&
                        (window as any).__NOVAMIND_ENGINE__) ||
                      'NovaMind local v1';
                    return (
                      <span
                        className="flex items-center space-x-1"
                        title="The engine that produced this reply. NovaMind local is a rule-based engine running on our own backend - not a foundation model."
                      >
                        <span className="h-2 w-2 bg-green-500 rounded-full"></span>
                        <span>engine: {engineName}</span>
                      </span>
                    );
                  })()}
                  {(() => {
                    const meta = asMeta(msg.meta_data);
                    const t = meta?.tokens ?? meta?.tokens_used;
                    return t ? <span>{t} tokens</span> : null;
                  })()}
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      try {
                        const audioBlob = await textToSpeech(msg.content);
                        const audioUrl = URL.createObjectURL(audioBlob);
                        const audio = new Audio(audioUrl);
                        audio.play();

                        // Clean up object URL after playback
                        audio.onended = () => {
                          URL.revokeObjectURL(audioUrl);
                        };
                      } catch (error) {
                        console.error('Error playing text-to-speech:', error);
                        alert('Failed to play audio');
                      }
                    }}
                    className="p-1 rounded hover:bg-gray-200 transition-colors"
                    title="Play message"
                  >
                    <Speaker className="h-4 w-4 text-gray-500 hover:text-indigo-500" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigator.clipboard.writeText(msg.content).then(() => {
                        // Show temporary success message
                        alert('Message copied to clipboard!');
                      });
                    }}
                    className="p-1 rounded hover:bg-gray-200 transition-colors"
                    title="Copy message"
                  >
                    <Copy className="h-4 w-4 text-gray-500 hover:text-indigo-500" />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="ml-auto flex-shrink-0">
                <div className="flex items-center space-x-2 mb-1">
                  <span className="text-xs text-gray-400">
                    {formatDistanceToNow(new Date(msg.created_at), { addSuffix: true }) !== 'just now'
                      ? formatDistanceToNow(new Date(msg.created_at), { addSuffix: true })
                      : 'just now'}
                  </span>
                  <div className="flex-shrink-0 h-10 w-10 flex items-center justify-center bg-gray-100 rounded-full">
                    <span className="text-gray-600 font-medium">{msg.user_id ? 'You' : 'User'}</span>
                  </div>
                </div>
                <div className="bg-indigo-600 text-white rounded-xl px-4 py-3 max-w-[80%] break-words relative">
                  <div className="prose prose-sm max-w-none text-white">
                    {msg.content}
                  </div>
                  {msg.message_type === 'code' && (
                    <div className="mt-3 bg-indigo-700 rounded p-3 text-xs font-mono text-indigo-100 overflow-auto">
                      {/* In a real app, we'd use a syntax highlighting library */}
                      <code className="text-indigo-100">{msg.content}</code>
                    </div>
                  )}
                  {msg.message_type === 'image' && (
                    <div className="mt-3">
                      {/* In a real app, we'd display the image */}
                      <div className="aspect-w-16 aspect-h-9 bg-indigo-700 rounded flex items-center justify-center text-indigo-100">
                        <span className="text-indigo-400">[Image]</span>
                      </div>
                    </div>
                  )}
                </div>
                <div className="mt-2 flex items-center space-x-3 text-xs text-gray-400">
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      try {
                        const audioBlob = await textToSpeech(msg.content);
                        const audioUrl = URL.createObjectURL(audioBlob);
                        const audio = new Audio(audioUrl);
                        audio.play();

                        // Clean up object URL after playback
                        audio.onended = () => {
                          URL.revokeObjectURL(audioUrl);
                        };
                      } catch (error) {
                        console.error('Error playing text-to-speech:', error);
                        alert('Failed to play audio');
                      }
                    }}
                    className="p-1 rounded hover:bg-gray-200 transition-colors"
                    title="Play message"
                  >
                    <Speaker className="h-4 w-4 text-gray-500 hover:text-indigo-500" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigator.clipboard.writeText(msg.content).then(() => {
                        // Show temporary success message
                        alert('Message copied to clipboard!');
                      });
                    }}
                    className="p-1 rounded hover:bg-gray-200 transition-colors"
                    title="Copy message"
                  >
                    <Copy className="h-4 w-4 text-gray-500 hover:text-indigo-500" />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}