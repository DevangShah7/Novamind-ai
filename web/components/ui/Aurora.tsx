import { motion } from 'framer-motion';

/**
 * Ambient animated backdrop used behind glass surfaces (auth, landing,
 * empty chat states). Three soft, slow-drifting color fields plus a
 * fixed grain overlay — deliberately restrained (low opacity, long
 * durations) so it reads as ambient lighting, not a moving wallpaper.
 */
export default function Aurora({ variant = 'default' }: { variant?: 'default' | 'subtle' }) {
  const opacity = variant === 'subtle' ? 0.35 : 1;
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" style={{ opacity }}>
      <motion.div
        className="absolute -left-1/4 -top-1/4 h-[60%] w-[60%] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, hsl(var(--primary) / 0.35), transparent 70%)' }}
        animate={{ x: [0, 40, -20, 0], y: [0, -30, 20, 0] }}
        transition={{ duration: 22, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute -right-1/4 top-0 h-[55%] w-[55%] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, hsl(var(--accent) / 0.28), transparent 70%)' }}
        animate={{ x: [0, -30, 20, 0], y: [0, 40, -10, 0] }}
        transition={{ duration: 26, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute bottom-0 left-1/3 h-[50%] w-[50%] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(circle, hsl(268 78% 62% / 0.22), transparent 70%)' }}
        animate={{ x: [0, 25, -25, 0], y: [0, -20, 15, 0] }}
        transition={{ duration: 30, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  );
}
