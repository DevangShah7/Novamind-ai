import { useState, useRef, useEffect } from 'react';
import { Upload, Mic, Send, Paperclip, X, Loader2, ImageIcon, Sparkles, Presentation, FileText, Code2 } from 'lucide-react';
import { speechToText } from '../lib/voice';

interface MessageInputProps {
  onSend: (content: string) => Promise<void>;
  onFileUpload?: (file: File) => Promise<string>;
  loading?: boolean;
}

// Five composer modes. Each mode is a distinct way the user can ask
// the LLM to reply; the chat dispatcher in `backend/app/api/endpoints/
// chats.py` reads `message_type` and (for `file`) `meta_data.kind` to
// decide which generator to run. The text/image split was already there;
// PPT/Word/Code were added recently.
type ComposerMode = 'text' | 'image' | 'ppt' | 'docx' | 'code';

interface FileOpts {
  messageType: 'file' | 'code';
  metaData: Record<string, unknown>;
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

// PPT (slide deck) themes — selected chips mirror the python-pptx
// masters the backend uses. The backend tolerates unknown themes by
// falling back to "modern".
const PPT_THEMES = [
  { id: 'modern', label: 'Modern' },
  { id: 'minimal', label: 'Minimal' },
  { id: 'academic', label: 'Academic' },
  { id: 'pitch-deck', label: 'Pitch deck' },
] as const;

const PPT_SLIDE_COUNTS = [3, 6, 10, 15] as const;

// Word styles — the backend keeps the body rigid for memo/letter and
// looser for report/outline. Frontend mirrors that contract so users
// don't pick "memo" expecting the model to freeform.
const DOCX_STYLES = [
  { id: 'report', label: 'Report' },
  { id: 'memo', label: 'Memo' },
  { id: 'letter', label: 'Letter' },
  { id: 'outline', label: 'Outline' },
] as const;

// Code-execution languages. The dispatcher routes each language to
// its matching interpreter in `app/core/code_runner.py`; missing
// runtimes surface as `runtime_missing=true` in the AI message meta.
const CODE_LANGUAGES = [
  { id: 'python', label: 'Python' },
  { id: 'javascript', label: 'JavaScript' },
  { id: 'bash', label: 'Bash' },
  { id: 'sql', label: 'SQL' },
] as const;

export default function MessageInput({
  onSend,
  onFileUpload,
  loading = false
}: MessageInputProps) {
  const [content, setContent] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<ComposerMode>('text');
  const [imageStyle, setImageStyle] = useState<(typeof IMAGE_STYLES)[number]['id']>('realistic');
  const [imageSize, setImageSize] = useState<(typeof IMAGE_SIZES)[number]['id']>(512);
  const [pptTheme, setPptTheme] = useState<(typeof PPT_THEMES)[number]['id']>('modern');
  const [pptSlideCount, setPptSlideCount] = useState<(typeof PPT_SLIDE_COUNTS)[number]>(6);
  const [docxStyle, setDocxStyle] = useState<(typeof DOCX_STYLES)[number]['id']>('report');
  const [codeLanguage, setCodeLanguage] = useState<(typeof CODE_LANGUAGES)[number]['id']>('python');
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
  // 5–30 s FLUX render times. PPT/DOCX generation calls the LLM once
  // and then runs python-pptx/python-docx locally, so it's similar
  // to chat (8 s) plus a little headroom. Code runs the user's script
  // in a sandboxed subprocess with a hard kill at 8 s.
  const IMAGE_HANG_THRESHOLD = 30000;
  const FILE_HANG_THRESHOLD = 25000;
  const DOCX_HANG_THRESHOLD = 20000;
  const CODE_HANG_THRESHOLD = 12000;

  useEffect(() => {
    if (loading) {
      setHangNotice(false);
      if (hangTimerRef.current) clearTimeout(hangTimerRef.current);
      // Per-mode hang threshold. The banner copy below switches on
      // `mode` too, so any new mode needs both the threshold and a
      // matching banner string.
      const threshold =
        mode === 'image'
          ? IMAGE_HANG_THRESHOLD
          : mode === 'ppt'
          ? FILE_HANG_THRESHOLD
          : mode === 'docx'
          ? DOCX_HANG_THRESHOLD
          : mode === 'code'
          ? CODE_HANG_THRESHOLD
          : HANG_THRESHOLD;
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
      // Each non-text mode stashes its options on `window` as a
      // side-channel so the chat page can read them when it calls
      // `sendMessage` without us having to lift the chip state up.
      // The text path leaves both unset; the chat page treats that
      // as "default text message".
      const w = window as any;
      w.__pendingImageOpts = null;
      w.__pendingFileOpts = null;

      if (mode === 'image') {
        w.__pendingImageOpts = {
          messageType: 'image' as const,
          metaData: {
            style: imageStyle,
            width: imageSize,
            height: imageSize,
          },
        };
      } else if (mode === 'ppt') {
        const opts: FileOpts = {
          messageType: 'file',
          metaData: { kind: 'pptx', theme: pptTheme, slide_count: pptSlideCount },
        };
        w.__pendingFileOpts = opts;
      } else if (mode === 'docx') {
        const opts: FileOpts = {
          messageType: 'file',
          metaData: { kind: 'docx', style: docxStyle },
        };
        w.__pendingFileOpts = opts;
      } else if (mode === 'code') {
        const opts: FileOpts = {
          messageType: 'code',
          metaData: { language: codeLanguage },
        };
        w.__pendingFileOpts = opts;
      }

      try {
        await onSend(content);
        setContent('');
        setFiles([]);
      } finally {
        // Don't clear opts until the parent has consumed them. They'll
        // be overwritten on the next send anyway.
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
  const isPptMode = mode === 'ppt';
  const isDocxMode = mode === 'docx';
  const isCodeMode = mode === 'code';
  const isFileMode = isPptMode || isDocxMode || isCodeMode;

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

      {/* PPT-mode chips: theme + slide count. Backend's MAX_PPTX_SLIDES
          cap (25) is enforced server-side; we only expose a few sane
          choices here so the user doesn't ask for 100 slides by accident. */}
      {isPptMode && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Presentation className="h-3.5 w-3.5 text-primary" />
            Theme
          </div>
          <div className="flex flex-wrap gap-1">
            {PPT_THEMES.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setPptTheme(t.id)}
                aria-pressed={pptTheme === t.id}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  pptTheme === t.id
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted text-muted-foreground hover:bg-muted/70'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            Slides
          </div>
          <div className="flex flex-wrap gap-1">
            {PPT_SLIDE_COUNTS.map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setPptSlideCount(n)}
                aria-pressed={pptSlideCount === n}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  pptSlideCount === n
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted text-muted-foreground hover:bg-muted/70'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* DOCX-mode chips: just a style picker. Backend uses the same
          fixed templates for memo/letter and looser generation for
          report/outline. */}
      {isDocxMode && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <FileText className="h-3.5 w-3.5 text-primary" />
            Style
          </div>
          <div className="flex flex-wrap gap-1">
            {DOCX_STYLES.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setDocxStyle(s.id)}
                aria-pressed={docxStyle === s.id}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  docxStyle === s.id
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

      {/* Code-mode chips: language picker. Each language maps to a
          different interpreter in app/core/code_runner.py; missing
          runtimes surface as runtime_missing=true on the AI bubble. */}
      {isCodeMode && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Code2 className="h-3.5 w-3.5 text-primary" />
            Language
          </div>
          <div className="flex flex-wrap gap-1">
            {CODE_LANGUAGES.map((l) => (
              <button
                key={l.id}
                type="button"
                onClick={() => setCodeLanguage(l.id)}
                aria-pressed={codeLanguage === l.id}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  codeLanguage === l.id
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted text-muted-foreground hover:bg-muted/70'
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Hang-detection banner — only shown if loading stays true.
          Threshold AND copy depend on mode so a normal 20 s image
          generation doesn't trip the banner with chat-flavoured text. */}
      {hangNotice && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-start gap-2 border-b border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300"
        >
          <Loader2 className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 animate-spin" />
          <span>
            {mode === 'image'
              ? 'Still rendering your image — free image models can take 20–30 seconds. Hang tight, or refresh if it stalls.'
              : mode === 'ppt'
              ? 'Building your slides — usually takes ~10s. Hang tight, or refresh if it stalls.'
              : mode === 'docx'
              ? 'Drafting your document — usually takes ~8s. Hang tight, or refresh if it stalls.'
              : mode === 'code'
              ? 'Running your code — sandboxed with an 8s timeout. Refresh if it stalls.'
              : 'Taking longer than expected. The request may be stuck — try pressing Enter in this box to retry, or refresh the page if it doesn’t recover.'}
          </span>
        </div>
      )}
      {/* File attachments — only relevant in text mode. Image / PPT /
          Docx / Code modes treat the prompt as the only input. */}
      {files.length > 0 && !isImageMode && !isFileMode && (
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
        {/* Attach file — hidden in every non-text mode (the prompt is
            the only input for image/ppt/docx/code). */}
        {!(isImageMode || isFileMode) && (
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

        {/* Mode toggle: a 5-position segmented control. Each button
            sets `mode` and (for non-text modes) renders the matching
            chip row above the input. The currently active mode has
            the primary-tinted background. */}
        <div
          role="radiogroup"
          aria-label="Composer mode"
          className="flex flex-shrink-0 items-center rounded-lg border border-border bg-muted/50 p-0.5"
        >
          {(
            [
              { id: 'text' as const, icon: Send, label: 'Chat' },
              { id: 'image' as const, icon: ImageIcon, label: 'Image' },
              { id: 'ppt' as const, icon: Presentation, label: 'Slides' },
              { id: 'docx' as const, icon: FileText, label: 'Word' },
              { id: 'code' as const, icon: Code2, label: 'Run' },
            ]
          ).map(({ id, icon: Icon, label }) => {
            const active = mode === id;
            return (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={active}
                aria-label={`Switch to ${label.toLowerCase()} mode`}
                title={label}
                onClick={() => setMode(id)}
                className={`flex h-8 w-8 items-center justify-center rounded-md transition-colors ${
                  active
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:bg-background hover:text-foreground'
                }`}
              >
                <Icon className="h-4 w-4" />
              </button>
            );
          })}
        </div>

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
              : isPptMode
              ? `Describe the deck you want (${pptTheme}, ${pptSlideCount} slides)…`
              : isDocxMode
              ? `Describe the document you want (${docxStyle} style)…`
              : isCodeMode
              ? `Describe what you want the ${codeLanguage} code to do…`
              : 'Message NovaMind…  (Shift+Enter for newline)'
          }
          className="flex-1 resize-none border-0 bg-transparent px-1 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-0"
          rows={1}
          disabled={loading}
          style={{ minHeight: '36px', maxHeight: '200px' }}
        />

        {/* Voice — text mode only. */}
        {!(isImageMode || isFileMode) && (
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

        {/* Send / Generate / Run. Label flips per mode so the user
            sees the action they're about to take. */}
        <button
          type="submit"
          disabled={!canSend}
          aria-label={
            isImageMode
              ? 'Generate image'
              : isPptMode
              ? 'Generate slides'
              : isDocxMode
              ? 'Generate document'
              : isCodeMode
              ? 'Run code'
              : 'Send message'
          }
          className={`flex h-9 flex-shrink-0 items-center justify-center gap-1.5 rounded-lg text-sm font-medium shadow-sm transition-all hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100 ${
            isImageMode || isPptMode || isDocxMode || isCodeMode
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
          ) : isPptMode ? (
            <>
              <Presentation className="h-3.5 w-3.5" />
              Build deck
            </>
          ) : isDocxMode ? (
            <>
              <FileText className="h-3.5 w-3.5" />
              Draft doc
            </>
          ) : isCodeMode ? (
            <>
              <Code2 className="h-3.5 w-3.5" />
              Run code
            </>
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </div>
    </form>
  );
}