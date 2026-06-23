import { useState, useRef, useEffect } from 'react';
import { Upload, Copy, Mic, Speaker } from 'lucide-react';
import { speechToText } from '../lib/voice';

interface MessageInputProps {
  onSend: (content: string) => Promise<void>;
  onFileUpload?: (file: File) => Promise<string>; // Returns URL or placeholder
  loading?: boolean;
}

export default function MessageInput({
  onSend,
  onFileUpload,
  loading = false
}: MessageInputProps) {
  const [content, setContent] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [charCount, setCharCount] = useState(0);
  const [isListening, setIsListening] = useState(false);
  const [speechRecognition, setSpeechRecognition] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() && files.length === 0) return;

    // For now, just send text - file upload would need backend implementation
    if (content.trim()) {
      await onSend(content);
      setContent('');
      setFiles([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Send on Ctrl+Enter or Meta+Enter (Cmd+Enter on Mac)
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit(e as React.FormEvent);
    }
    // Send on Enter alone if not shift (for newline)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as React.FormEvent);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length > 0) {
      setFiles(prev => [...prev, ...selectedFiles]);
      // Reset file input
      e.target.value = '';
    }
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  // Auto-resize textarea and update character count
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
    setCharCount(content.length);
  }, [content]);

  // Initialize speech recognition
  useEffect(() => {
    if ('SpeechRecognition' in window) {
      setSpeechRecognition(new (window as any).SpeechRecognition());
    } else if ('webkitSpeechRecognition' in window) {
      setSpeechRecognition(new (window as any).webkitSpeechRecognition());
    }

    if (speechRecognition) {
      speechRecognition.continuous = false;
      speechRecognition.interimResults = false;
      speechRecognition.lang = 'en-US';

      speechRecognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setContent(transcript);
        setIsListening(false);
      };

      speechRecognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
      };

      speechRecognition.onend = () => {
        setIsListening(false);
      };
    }
  }, [speechRecognition]);

  // Handle speech to text button click
  const handleSpeechToText = async () => {
    if (!speechRecognition || isListening) return;

    try {
      setIsListening(true);
      speechRecognition.start();
    } catch (error) {
      console.error('Error starting speech recognition:', error);
      setIsListening(false);
    }
  };

  return (
    <div className={`border-t border-gray-200 bg-white ${isFocused ? 'border-indigo-500' : ''} transition-border`}
      onFocus={() => setIsFocused(true)}
      onBlur={() => setIsFocused(false)}
    >
      <div className="flex flex-col px-4 py-3">
        {/* File attachments preview */}
        {files.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {files.map((file, index) => (
              <div key={index} className="flex items-center space-x-2 bg-gray-50 rounded px-3 py-1 text-sm">
                <span className="text-indigo-500">📎</span>
                <span className="truncate max-w-xs">{file.name}</span>
                <button
                  onClick={() => removeFile(index)}
                  className="text-gray-400 hover:text-gray-600 p-1 rounded"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Character counter */}
        <div className="mb-2 flex justify-between text-xs text-gray-500">
          <span>{charCount}/1000</span>
          <span>{files.length} file{files.length !== 1 ? 's' : ''} attached</span>
        </div>

        {/* Textarea and controls */}
        <div className="flex items-start">
          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            className={`flex-1 min-w-0 border border-gray-300 rounded-xl px-4 py-3 text-base
                      focus:outline-none focus:ring-2 focus:ring-indigo-500
                      resize-none
                      ${loading ? 'opacity-75' : ''}`}
            rows={1}
            disabled={loading}
            style={{ minHeight: '48px' }}
          />
          <div className="ml-3 flex-shrink-0 flex items-center space-x-2">
            <label
              htmlFor="file-upload"
              className={`flex items-center justify-center w-10 h-10 rounded-lg
                        ${loading ? 'opacity-50' : 'hover:bg-gray-100'}
                        transition-colors`}
              onClick={() => !loading && document.getElementById('file-upload')?.click()}
            >
              <Upload className="h-4 w-4 text-indigo-500" />
            </label>
            <input
              id="file-upload"
              type="file"
              multiple
              accept="image/*,.pdf,.txt,.doc,.docx"
              onChange={handleFileChange}
              className="hidden"
              disabled={loading}
            />
            <button
              type="button"
              onClick={handleSpeechToText}
              disabled={loading || !('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)}
              className={`flex items-center justify-center w-10 h-10 rounded-lg
                        ${loading ? 'opacity-50' : 'hover:bg-gray-100'}
                        transition-colors
                        ${isListening ? 'bg-indigo-500' : ''}`}
              title="Speech to text"
            >
              {isListening ? (
                <Mic className="h-4 w-4 text-white animate-pulse" />
              ) : (
                <Mic className="h-4 w-4 text-indigo-500" />
              )}
            </button>
            <button
              type="submit"
              disabled={loading || (!content.trim() && files.length === 0)}
              className={`ml-2 rounded-xl border border-transparent px-4 py-2
                        font-medium
                        ${loading
                          ? 'bg-gray-400 opacity-75'
                          : 'bg-indigo-600 text-white hover:bg-indigo-700'}
                        transition-all
                        disabled:opacity-50`}
            >
              {loading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}