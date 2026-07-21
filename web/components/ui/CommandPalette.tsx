import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Search } from 'lucide-react';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';
import { useCommandActions, type CommandAction } from '../../lib/commandActions';

interface CommandPaletteProps {
  /** Override the open state. By default the palette listens for Ctrl+K itself. */
  open?: boolean;
  onClose?: () => void;
}

/**
 * Ctrl+K (Cmd+K on Mac) command palette. Renders a small modal with
 * a search input + filtered list of actions. Each row slides in
 * from the left with a 30ms stagger on open.
 *
 * Arrow keys + enter to navigate. Esc closes. Click outside closes.
 */
export function CommandPalette({ open: openProp, onClose }: CommandPaletteProps) {
  const reduced = useReducedMotionSafe();
  const actions = useCommandActions();
  const [internalOpen, setInternalOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const open = openProp ?? internalOpen;
  const close = useCallback(() => {
    if (onClose) onClose();
    else setInternalOpen(false);
  }, [onClose]);

  // Keyboard shortcut: Ctrl+K / Cmd+K.
  useEffect(() => {
    if (openProp !== undefined) return; // controlled mode
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setInternalOpen((o) => !o);
      } else if (e.key === 'Escape') {
        setInternalOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openProp]);

  // Focus the input when we open.
  useEffect(() => {
    if (open) {
      setQuery('');
      setHighlight(0);
      const t = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return actions;
    return actions.filter(
      (a) => a.label.toLowerCase().includes(q) || a.group.toLowerCase().includes(q)
    );
  }, [actions, query]);

  // Reset highlight if the filtered list shrinks below the current index.
  useEffect(() => {
    setHighlight((h) => (h >= filtered.length ? Math.max(0, filtered.length - 1) : h));
  }, [filtered.length]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => Math.min(filtered.length - 1, h + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const a = filtered[highlight];
      if (a) run(a);
    }
  };

  function run(a: CommandAction) {
    // Use the action's own hook-bound `run`, but we need helpers here.
    // We approximate by re-deriving helpers from current router/theme.
    a.run({
      router: { push: (url: string) => window.location.assign(url) } as any,
      setTheme: (t) => document.documentElement.classList.toggle('dark', t === 'dark'),
    });
    close();
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[90] flex items-start justify-center pt-[10vh] px-4"
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          <button
            type="button"
            aria-label="Close command palette"
            onClick={close}
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
          />
          <motion.div
            role="dialog"
            aria-label="Command palette"
            initial={reduced ? false : { scale: 0.95, opacity: 0, y: -8 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={reduced ? undefined : { scale: 0.97, opacity: 0, y: -4 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-lg overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
          >
            <div className="flex items-center gap-2 border-b border-border px-3">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Type a command or search…"
                className="flex-1 bg-transparent py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
              />
              <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">Esc</kbd>
            </div>
            <ul className="max-h-80 overflow-y-auto p-1">
              {filtered.length === 0 ? (
                <li className="px-3 py-6 text-center text-sm text-muted-foreground">No matches</li>
              ) : (
                filtered.map((a, i) => (
                  <motion.li
                    key={a.id}
                    initial={reduced ? false : { opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.18, delay: i * 0.03 }}
                  >
                    <button
                      type="button"
                      onClick={() => run(a)}
                      onMouseEnter={() => setHighlight(i)}
                      className={`flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors ${
                        i === highlight ? 'bg-primary/10 text-primary' : 'text-foreground hover:bg-muted'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{a.group}</span>
                        <span>{a.label}</span>
                      </span>
                      {a.hint && <span className="text-xs text-muted-foreground">{a.hint}</span>}
                    </button>
                  </motion.li>
                ))
              )}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
