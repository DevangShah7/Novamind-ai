import { ReactNode, useCallback, useState, DragEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useReducedMotionSafe } from '../motion/useReducedMotionSafe';

interface DropZoneProps {
  children: ReactNode;
  /** Called when one or more files are dropped. */
  onFiles: (files: File[]) => void;
  /** Optional list of MIME prefixes to accept (e.g. ['image/', 'application/pdf']). */
  acceptPrefixes?: string[];
  className?: string;
}

/**
 * Magnetic drag-and-drop overlay that wraps the message composer.
 * On `dragenter`, the composer's border glows with an animated
 * gradient sweep. On `dragover`, a circular pulse follows the
 * cursor. On `drop`, the file list is forwarded to `onFiles`.
 *
 * Pure overlay: the children remain interactive for typing, sending,
 * etc. — this only steals pointer events during an active drag.
 */
export function DropZone({
  children,
  onFiles,
  acceptPrefixes,
  className,
}: DropZoneProps) {
  const reduced = useReducedMotionSafe();
  const [active, setActive] = useState(false);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);

  const filterAccept = useCallback(
    (files: FileList | File[]) => {
      const arr = Array.from(files);
      if (!acceptPrefixes || acceptPrefixes.length === 0) return arr;
      return arr.filter((f) => acceptPrefixes.some((p) => f.type.startsWith(p)));
    },
    [acceptPrefixes]
  );

  const onDragEnter = (e: DragEvent<HTMLDivElement>) => {
    if (!e.dataTransfer.types.includes('Files')) return;
    e.preventDefault();
    setActive(true);
  };
  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    if (!e.dataTransfer.types.includes('Files')) return;
    e.preventDefault();
    setPointer({ x: e.clientX, y: e.clientY });
  };
  const onDragLeave = (e: DragEvent<HTMLDivElement>) => {
    // Only deactivate when leaving the zone itself, not nested elements.
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setActive(false);
    setPointer(null);
  };
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const files = filterAccept(e.dataTransfer.files);
    if (files.length > 0) onFiles(files);
    setActive(false);
    setPointer(null);
  };

  return (
    <div
      className={`relative ${className ?? ''}`}
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {children}
      <AnimatePresence>
        {active && (
          <motion.div
            className="absolute inset-0 pointer-events-none rounded-2xl dropzone-active"
            initial={reduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            {!reduced && pointer && (
              <motion.span
                className="absolute w-16 h-16 rounded-full bg-foreground/20 -translate-x-1/2 -translate-y-1/2"
                style={{ left: pointer.x, top: pointer.y }}
                animate={{ scale: [1, 1.25, 1], opacity: [0.6, 0.25, 0.6] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
              />
            )}
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="px-3 py-1.5 rounded-full bg-foreground/10 text-xs text-foreground backdrop-blur-sm">
                Drop files to attach
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
