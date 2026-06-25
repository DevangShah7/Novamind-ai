import { useState, useRef, useEffect } from 'react';
import { Upload, Mic, Send, Paperclip, X, Loader2 } from 'lucide-react';
import { speechToText } from '../lib/voice';

interface MessageInputProps {
  onSend: (content: string) => Promise<void>;
  onFileUpload?: (file: File) => Promise<string>;
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
  const [isListening, setIsListening] = useState(false);
  const [speechRecognition, setSpeechRecognition] = useState<any>(null);
  // "Looks hung" — set when `loading` stays true for >HANG_THRESHOLD ms.
  // The mock backend replies within ~1s; the FastAPI backend replies within
  // a few seconds. If neither fires, this banner tells the user the request
  // is stuck instead of leaving them staring at a spinner.
  const [hangNotice, setHangNotice] = useState(false);
  const hangTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const HANG_THRESHOLD = 8000;

  useEffect(() => {
    if (loading) {
      setHangNotice(false);
      if (hangTimerRef.current) clearTimeout(hangTimerRef.current);
      hangTimerRef.current = setTimeout(() => setHangNotice(true), HANG_THRESHOLD);
    } else {
      setHangNotice(false);
      if (hangTimerRef.current) {
        clearTimeout(hangTimerRef.current);
        hangTimerRef.current = null;
      }
    }
    return () => {
      if (hangTimerRef.current) clearTimeout(hangTimerRef.current);
    };
  }, [loading]);

  const canSend = (content.trim().length > 0 || files.length > 0) && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    if (content.trim()) {
      await onSend(content);
      setContent('');
      setFiles([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as React.FormEvent);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length > 0) {
      setFiles(prev => [...prev, ...selectedFiles]);
      e.target.value = '';
    }
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  // Auto-resize textarea up to ~6 rows
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [content]);

  // Initialize speech recognition
  useEffect(() => {
    let rec: any = null;
    if (typeof window !== 'undefined') {
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SR) rec = new SR();
    }
    if (rec) {
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = 'en-US';
      rec.onresult = (event: any) => {
        setContent(event.results[0][0].transcript);
        setIsListening(false);
      };
      rec.onerror = () => setIsListening(false);
      rec.onend = () => setIsListening(false);
      setSpeechRecognition(rec);
    }
  }, []);

  const handleSpeechToText = async () => {
    if (!speechRecognition || isListening) return;
    try {
      setIsListening(true);
      speechRecognition.start();
    } catch (error) {
      console.error('Speech recognition error:', error);
      setIsListening(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={`relative rounded-2xl border bg-card shadow-sm transition-all ${
        isFocused ? 'border-primary ring-2 ring-ring' : 'border-border'
      }`}
    >
      {/* Hang-detection banner — only shown if loading stays true for >8s. */}
      {hangNotice && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-start gap-2 border-b border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300"
        >
          <Loader2 className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 animate-spin" />
          <span>
            Taking longer than expected. The request may be stuck — try
            pressing <kbd className="rounded border border-amber-500/40 px-1">Enter</kbd>{' '}
            in this box to retry, or refresh the page if it doesn&apos;t recover.
          </span>
        </div>
      )}
      {/* File attachments */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2 border-b border-border p-3">
          {files.map((file, index) => (
            <div
              key={index}
              className="flex items-center gap-2 rounded-lg border border-border bg-muted px-2.5 py-1.5 text-xs"
            >
              <Paperclip className="h-3 w-3 text-primary" />
              <span className="max-w-[160px] truncate text-foreground">{file.name}</span>
              <button
                type="button"
                onClick={() => removeFile(index)}
                aria-label="Remove file"
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2 p-2.5">
        {/* Attach file */}
        <label
          htmlFor="file-upload"
          className="flex h-9 w-9 flex-shrink-0 cursor-pointer items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Attach file"
        >
          <Upload className="h-4 w-4" />
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

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Message NovaMind…  (Shift+Enter for newline)"
          className="flex-1 resize-none border-0 bg-transparent px-1 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-0"
          rows={1}
          disabled={loading}
          style={{ minHeight: '36px', maxHeight: '200px' }}
        />

        {/* Voice */}
        <button
          type="button"
          onClick={handleSpeechToText}
          disabled={loading || !speechRecognition}
          aria-label={isListening ? 'Listening…' : 'Voice input'}
          title={speechRecognition ? 'Voice input' : 'Voice not supported in this browser'}
          className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors ${
            isListening
              ? 'bg-primary text-white animate-pulse'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          } disabled:opacity-40`}
        >
          <Mic className="h-4 w-4" />
        </button>

        {/* Send */}
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send message"
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg gradient-bg text-white shadow-sm transition-all hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </div>
    </form>
  );
}