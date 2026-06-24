import { ReactNode } from 'react';
import { Brain, Zap, ShieldCheck, Sparkles } from 'lucide-react';

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
        {/* Marketing panel — gradient bg, brand, feature bullets. */}
        <aside className="relative hidden overflow-hidden md:flex md:flex-col md:justify-between gradient-bg p-10 lg:p-16 text-white">
          {/* Decorative animated blobs */}
          <div className="pointer-events-none absolute inset-0">
            <div
              className="absolute -left-20 top-20 h-72 w-72 rounded-full bg-white/20 blur-3xl animate-blob"
              style={{ animationDelay: '0s' }}
            />
            <div
              className="absolute right-0 top-1/2 h-80 w-80 rounded-full bg-pink-300/20 blur-3xl animate-blob"
              style={{ animationDelay: '4s' }}
            />
            <div
              className="absolute bottom-10 left-1/3 h-64 w-64 rounded-full bg-indigo-300/20 blur-3xl animate-blob"
              style={{ animationDelay: '8s' }}
            />
          </div>

          <div className="relative z-10">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/20 backdrop-blur-md">
                <Brain className="h-7 w-7" />
              </div>
              <span className="text-2xl font-bold tracking-tight">NovaMind AI</span>
            </div>
            <p className="mt-2 text-sm text-white/80">Your AI operating system.</p>
          </div>

          <div className="relative z-10 space-y-6">
            <h2 className="text-3xl font-bold leading-tight lg:text-4xl">
              Think faster. Build smarter.<br />
              <span className="text-white/90">Ship without limits.</span>
            </h2>
            <ul className="space-y-4">
              {FEATURES.map(({ icon: Icon, title, body }) => (
                <li key={title} className="flex items-start gap-3">
                  <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-white/20 backdrop-blur-md">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-semibold">{title}</p>
                    <p className="text-sm text-white/85">{body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="relative z-10 text-sm text-white/70">
            © {new Date().getFullYear()} NovaMind AI
          </div>
        </aside>

        {/* Form panel */}
        <main className="flex items-center justify-center p-6 sm:p-10">
          <div className="w-full max-w-md">
            {/* Mobile-only logo strip */}
            <div className="mb-8 flex items-center gap-3 md:hidden">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl gradient-bg text-white">
                <Brain className="h-6 w-6" />
              </div>
              <span className="text-xl font-bold tracking-tight">NovaMind AI</span>
            </div>

            <div className="animate-fade-in">
              <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
              <p className="mt-2 text-muted-foreground">{subtitle}</p>
            </div>

            <div className="mt-8">{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
