import { ReactNode } from 'react';
import { Brain, Zap, ShieldCheck, Sparkles } from 'lucide-react';
import Aurora from './ui/Aurora';

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  children: ReactNode;
}

const FEATURES = [
  {
    icon: Brain,
    title: 'Multi-model intelligence',
    body: 'Switch between reasoning, code, and chat-tuned models in one place.',
  },
  {
    icon: Zap,
    title: 'Realtime streaming',
    body: 'Tokens arrive as they are generated — no waiting for full replies.',
  },
  {
    icon: ShieldCheck,
    title: 'Your data stays yours',
    body: 'Chats and keys are scoped per account. No training on your prompts.',
  },
  {
    icon: Sparkles,
    title: 'Built for builders',
    body: 'Voice input, file uploads, and API keys ship out of the box.',
  },
] as const;

export default function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="grid min-h-screen md:grid-cols-2">
        {/* Marketing panel — ambient aurora, glass feature cards. */}
        <aside className="relative hidden overflow-hidden md:flex md:flex-col md:justify-between bg-background p-10 lg:p-16">
          <Aurora />

          <div className="relative z-10">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl gradient-bg text-white shadow-xl shadow-primary/30">
                <Brain className="h-7 w-7" />
              </div>
              <span className="font-display text-2xl font-bold tracking-tight text-foreground">NovaMind AI</span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">Your AI operating system.</p>
          </div>

          <div className="relative z-10 space-y-6">
            <h2 className="font-display text-3xl font-bold leading-tight text-foreground lg:text-4xl">
              Think faster. Build smarter.<br />
              <span className="gradient-text">Ship without limits.</span>
            </h2>
            <ul className="space-y-3">
              {FEATURES.map(({ icon: Icon, title, body }) => (
                <li key={title} className="glass-card flex items-start gap-3 rounded-2xl p-3.5">
                  <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg gradient-bg text-white">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">{title}</p>
                    <p className="text-sm text-muted-foreground">{body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="relative z-10 text-sm text-muted-foreground">
            © {new Date().getFullYear()} NovaMind AI
          </div>
        </aside>

        {/* Form panel */}
        <main className="relative flex items-center justify-center overflow-hidden p-6 sm:p-10">
          <Aurora variant="subtle" />
          <div className="glass-strong relative z-10 w-full max-w-md rounded-3xl p-8 sm:p-10">
            {/* Mobile-only logo strip */}
            <div className="mb-8 flex items-center gap-3 md:hidden">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl gradient-bg text-white shadow-lg shadow-primary/30">
                <Brain className="h-6 w-6" />
              </div>
              <span className="font-display text-xl font-bold tracking-tight">NovaMind AI</span>
            </div>

            <div className="animate-rise-in">
              <h1 className="font-display text-3xl font-bold tracking-tight">{title}</h1>
              <p className="mt-2 text-muted-foreground">{subtitle}</p>
            </div>

            <div className="mt-8">{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
