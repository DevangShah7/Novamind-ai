/**
 * Static list of actions the command palette (Ctrl+K) can run.
 * Each action: {id, label, group, hint, run()}. The palette renders
 * them and calls `run()` on enter.
 */
import { useRouter } from 'next/router';
import { useTheme } from './theme';
import type { ComponentType } from 'react';

export interface CommandAction {
  id: string;
  label: string;
  /** Group label for the palette ("Navigation", "Theme", "Account"). */
  group: string;
  /** Optional sub-label / shortcut hint shown on the right. */
  hint?: string;
  /** Lucide icon component. */
  icon?: ComponentType<{ className?: string }>;
  run: (helpers: CommandHelpers) => void | Promise<void> | Promise<unknown> | unknown;
}

export interface CommandHelpers {
  router: ReturnType<typeof useRouter>;
  setTheme: (t: 'light' | 'dark' | 'system') => void;
}

export function useCommandActions(): CommandAction[] {
  const router = useRouter();
  const { setTheme } = useTheme();
  const helpers: CommandHelpers = { router, setTheme };

  return [
    {
      id: 'nav.new-chat',
      label: 'New chat',
      group: 'Navigation',
      hint: 'Go to /chat',
      run: ({ router }) => router.push('/chat'),
    },
    {
      id: 'nav.developer',
      label: 'Developer Portal',
      group: 'Navigation',
      hint: 'API keys, playground, usage',
      run: ({ router }) => router.push('/developer'),
    },
    {
      id: 'nav.billing',
      label: 'Billing & plan',
      group: 'Navigation',
      run: ({ router }) => router.push('/billing'),
    },
    {
      id: 'nav.docs',
      label: 'API documentation',
      group: 'Navigation',
      run: ({ router }) => router.push('/docs'),
    },
    {
      id: 'theme.light',
      label: 'Theme: light',
      group: 'Theme',
      run: ({ setTheme }) => setTheme('light'),
    },
    {
      id: 'theme.dark',
      label: 'Theme: dark',
      group: 'Theme',
      run: ({ setTheme }) => setTheme('dark'),
    },
    {
      id: 'theme.system',
      label: 'Theme: system',
      group: 'Theme',
      run: ({ setTheme }) => setTheme('system'),
    },
  ];
}
