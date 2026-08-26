import { AnimatePresence, motion } from 'framer-motion';
import { Mic, X } from 'lucide-react';

interface VoiceOrbProps {
  open: boolean;
  level: number; // 0..1 live mic volume
  transcript: string;
  interimTranscript: string;
  error: string | null;
  onClose: () => void;
}

// Bar heights derive from the live mic level plus a per-bar phase offset
// so the waveform ripples instead of moving as one flat block — this is
// the detail that makes it read as "actually listening" rather than a
// generic pulsing icon.
const BAR_COUNT = 5;

export default function VoiceOrb({ open, level, transcript, interimTranscript, error, onClose }: VoiceOrbProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center p-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {/* Backdrop */}
          <motion.div
            className="absolute inset-0 bg-background/70 backdrop-blur-xl"
            onClick={onClose}
          />

          <motion.div
            className="glass-strong relative z-10 flex w-full max-w-md flex-col items-center gap-6 rounded-3xl px-8 py-10 text-center"
            initial={{ opacity: 0, scale: 0.92, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 8 }}
            transition={{ type: 'spring', damping: 22, stiffness: 260 }}
          >
            <button
              type="button"
              onClick={onClose}
              aria-label="Close voice input"
              className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>

            {/* Orb + reactive waveform */}
            <div className="relative flex h-32 w-32 items-center justify-center">
              <span className="absolute inset-0 rounded-full animate-pulse-ring gradient-bg opacity-40" />
              <span
                className="absolute inset-0 rounded-full animate-pulse-ring gradient-bg opacity-30"
                style={{ animationDelay: '0.6s' }}
              />
              <div
                className="relative flex h-24 w-24 items-center justify-center rounded-full gradient-bg shadow-2xl shadow-primary/40 transition-transform"
                style={{ transform: `scale(${1 + level * 0.18})` }}
              >
                {error ? (
                  <Mic className="h-9 w-9 text-white/70" />
                ) : (
                  <div className="flex items-end gap-1" aria-hidden="true">
                    {Array.from({ length: BAR_COUNT }).map((_, i) => {
                      const phase = Math.sin((i / BAR_COUNT) * Math.PI + level * 6) * 0.5 + 0.5;
                      const h = 8 + level * 34 * (0.4 + phase * 0.6);
                      return (
                        <span
                          key={i}
                          className="w-1.5 rounded-full bg-white"
                          style={{ height: `${Math.max(6, h)}px`, transition: 'height 90ms ease-out' }}
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            <div className="min-h-[3.5rem] space-y-1">
              <p className="font-display text-lg font-semibold text-foreground">
                {error ? 'Something went wrong' : 'Listening…'}
              </p>
              <p className="text-sm text-muted-foreground">
                {error || 'Speak now — I’ll send it when you pause.'}
              </p>
            </div>

            {(transcript || interimTranscript) && (
              <div className="w-full rounded-2xl bg-muted/50 px-4 py-3 text-left">
                <p className="text-sm leading-relaxed text-foreground">
                  {transcript}
                  <span className="text-muted-foreground">{interimTranscript}</span>
                </p>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
