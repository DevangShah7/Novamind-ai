import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme } from '../lib/theme';
import { useState, useRef, useEffect } from 'react';

export default function ThemeToggle() {
  const { theme, setTheme, resolved } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const Icon = resolved === 'dark' ? Moon : Sun;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="Toggle theme"
        className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-card text-foreground transition-colors hover:bg-muted"
      >
        <Icon className="h-5 w-5" />
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-40 overflow-hidden rounded-lg border border-border bg-card shadow-lg animate-fade-in z-50">
          {([
            { value: 'light', label: 'Light', Icon: Sun },
            { value: 'dark', label: 'Dark', Icon: Moon },
            { value: 'system', label: 'System', Icon: Monitor },
          ] as const).map(({ value, label, Icon: I }) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setTheme(value);
                setOpen(false);
              }}
              className={`flex w-full items-center gap-3 px-3 py-2 text-sm transition-colors hover:bg-muted ${
                theme === value ? 'text-primary font-medium' : 'text-foreground'
              }`}
            >
              <I className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
