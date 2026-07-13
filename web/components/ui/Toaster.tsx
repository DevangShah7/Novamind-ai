import { Toaster as SonnerToaster, toast } from 'sonner';
import { useTheme } from '../../lib/theme';

interface ToasterProps {
  /** Override the default position. */
  position?:
    | 'top-left'
    | 'top-right'
    | 'top-center'
    | 'bottom-left'
    | 'bottom-right'
    | 'bottom-center';
}

/**
 * Mount a single <Toaster /> near the root of the app. Wraps Sonner
 * so the active theme (light/dark) is picked up automatically from
 * our hand-rolled `useTheme` context.
 */
export function Toaster({ position = 'top-right' }: ToasterProps) {
  const { resolved } = useTheme();
  return (
    <SonnerToaster
      theme={resolved}
      position={position}
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast: 'rounded-xl border border-border shadow-lg',
          title: 'font-semibold',
          description: 'text-muted-foreground',
        },
      }}
    />
  );
}

/** Convenience re-exports so consumers can `import { toast } from '...'`. */
export { toast };
