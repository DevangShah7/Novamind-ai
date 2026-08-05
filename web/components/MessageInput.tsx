import { useState, useRef, useEffect } from 'react';
import { Upload, Mic, Send, Paperclip, X, Loader2, ImageIcon, Sparkles } from 'lucide-react';
import { speechToText } from '../lib/voice';

interface MessageInputProps {
  onSend: (content: string) => Promise<void>;
  onFileUpload?: (file: File) => Promise<string>;
  loading?: boolean;
}

// Image-generation mode lets the user pick a style and size, then submit
// a prompt that gets sent to Pollinations via the chat endpoint's image
// branch. Size options are deliberately small (the free Pollinations
// tier times out on anything over ~1024×1024).
const IMAGE_STYLES = [
  { id: 'realistic', label: 'Realistic' },
  { id: 'artistic', label: 'Artistic' },
  { id: 'cartoon', label: 'Cartoon' },
  { id: 'anime', label: 'Anime' },
] as const;

const IMAGE_SIZES = [
  { id: 512, label: '512×512' },
  { id: 768, label: '768×768' },
  { id: 1024, label: '1024×1024' },
] as const;

export default function MessageInput({
  onSend,
  onFileUpload,
  loading = false
}: MessageInputProps) {
  const [content, setContent] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<'text' | 'image'>('text');
  const [imageStyle, setImageStyle] = useState<(typeof IMAGE_STYLES)[number]['id']>('realistic');
  const [imageSize, setImageSize] = useState<(typeof IMAGE_SIZES)[number]['id']>(512);
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
  // Image generation through Pollinations is slower than chat — bump the
  // threshold so the "taking longer" banner doesn't show during normal
  // 5–30 s FLUX render times.
  const IMAGE_HANG_THRESHOLD = 30000;

  useEffect(() => {
    if (loading) {
      setHangNotice(false);
      if (hangTimerRef.current) clearTimeout(hangTimerRef.current);
      const threshold = mode === 'image' ? IMAGE_HANG_THRESHOLD : HANG_THRESHOLD;
      hangTimerRef.current = setTimeout(() => setHangNotice(true), threshold);
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
  }, [loading, mode]);

  const canSend = (content.trim().length > 0 || files.length > 0) && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
    if (content.trim()) {
      // The image-mode chip state lives in this component; we stash it on
      // window as a side-channel so the chat page (which calls sendMessage)
      // can read style/size without us having to lift state up. This keeps
      // MessageInput drop-in for the text path — the parent doesn't even
      // need to know an image mode exists.
      if (mode === 'image') {
        (window as any).__pendingImageOpts = {
          messageType: 'image' as const,
          metaData: {
            style: imageStyle,
            width: imageSize,
            height: imageSize,
          },
        };
      } else {
        // Clear any stale opts from a previous image send so a plain text
        // reply right after an image doesn't accidentally re-send with
        // message_type='image'.
        (window as any).__pendingImageOpts = null;
      }
      try {
        await onSend(content);
        setContent('');
        setFiles([]);
      } finally {
        // Don't clear opts until the parent has consumed them. They'll be
        // overwritten on the next send anyway.
      }
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

  const isImageMode = mode === 'image';

  return (
    <form
      onSubmit={handleSubmit}
      className={`relative rounded-2xl border bg-card shadow-sm transition-all ${
        isFocused ? 'border-primary ring-2 ring-ring' : 'border-border'
      }`}
    >
      {/* Image-mode option chips. Shown above the input only when the
          user has toggled image mode on; nothing is sent until they
          actually hit Send. */}
      {isImageMode && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Style
          </div>
          <div className="flex flex-wrap gap-1">
            {IMAGE_STYLES.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setImageStyle(s.id)}
                aria-pressed={imageStyle === s.id}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  imageStyle === s.id
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted text-muted-foreground hover:bg-muted/70'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            Size
          </div>
          <div className="flex flex-wrap gap-1">
            {IMAGE_SIZES.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setImageSize(s.id)}
                aria-pressed={imageSize === s.id}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  imageSize === s.id
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted text-muted-foreground hover:bg-muted/70'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Hang-detection banner — only shown if loading stays true. Threshold
          depends on mode so a normal 20 s image generation doesn't trip it. */}
      {hangNotice && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-start gap-2 border-b border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300"
        >
          <Loader2 className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 animate-spin" />
          <span>
            {isImageMode
              ? 'Still rendering your image — free image models can take 20–30 seconds. Hang tight, or refresh if it stalls.'
              : 'Taking longer than expected. The request may be stuck — try pressing Enter in this box to retry, or refresh the page if it doesn’t recover.'}
          </span>
        </div>
      )}
      {/* File attachments — only relevant in text mode (image mode
          ignores file uploads because the prompt is the only input). */}
      {files.length > 0 && !isImageMode && (
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
        {/* Attach file — hidden in image mode (the prompt is the only input). */}
        {!isImageMode && (
          <>
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
          </>
        )}

        {/* Mode toggle: text / image. Image mode changes the composer into
            a prompt box for Pollinations. */}
        <button
          type="button"
          onClick={() => setMode(isImageMode ? 'text' : 'image')}
          aria-label={isImageMode ? 'Switch to text mode' : 'Switch to image generation'}
          aria-pressed={isImageMode}
          title={isImageMode ? 'Switch to text mode' : 'Generate an image'}
          className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors ${
            isImageMode
              ? 'bg-primary/15 text-primary ring-1 ring-primary/30'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          }`}
        >
          <ImageIcon className="h-4 w-4" />
        </button>

        {/* Textarea / prompt */}
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={
            isImageMode
              ? `Describe the image you want… (${imageStyle}, ${imageSize}×${imageSize})`
              : 'Message NovaMind…  (Shift+Enter for newline)'
          }
          className="flex-1 resize-none border-0 bg-transparent px-1 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-0"
          rows={1}
          disabled={loading}
          style={{ minHeight: '36px', maxHeight: '200px' }}
        />

        {/* Voice — text mode only. */}
        {!isImageMode && (
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
        )}

        {/* Send / Generate */}
        <button
          type="submit"
          disabled={!canSend}
          aria-label={isImageMode ? 'Generate image' : 'Send message'}
          className={`flex h-9 flex-shrink-0 items-center justify-center gap-1.5 rounded-lg text-sm font-medium shadow-sm transition-all hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100 ${
            isImageMode
              ? 'gradient-bg px-3 text-white'
              : 'w-9 gradient-bg text-white'
          }`}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : isImageMode ? (
            <>
              <Sparkles className="h-3.5 w-3.5" />
              Generate
            </>
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </div>
    </form>
  );
}