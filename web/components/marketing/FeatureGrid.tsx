import { Brain, Zap, ShieldCheck, Sparkles, Code2, Mic } from 'lucide-react';
import { Card, CardContent } from '../ui/Card';

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
    icon: Mic,
    title: 'Voice built-in',
    body: 'Speak to your models with built-in voice input and transcription.',
  },
  {
    icon: Code2,
    title: 'Production APIs',
    body: 'Issue API keys, hit /v1/chat/completions, get OpenAI-compatible JSON.',
  },
  {
    icon: Sparkles,
    title: 'Built for builders',
    body: 'File uploads, code blocks, and copy-to-clipboard ship out of the box.',
  },
] as const;

/**
 * Feature grid for the landing page. Lifted from AuthLayout so the
 * marketing site and the auth pages show the same brand voice.
 */
export default function FeatureGrid() {
  return (
    <section id="features" className="border-t border-border/60 bg-background py-20 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need,{' '}
            <span className="gradient-text">in one workspace</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Stop stitching together five different tools. NovaMind AI keeps your
            chat, voice, and API workflows under one account.
          </p>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <Card
              key={title}
              className="group relative overflow-hidden transition-all hover:-translate-y-0.5 hover:shadow-lg"
            >
              <CardContent className="p-6">
                <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg gradient-bg text-white shadow-sm">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-lg font-semibold">{title}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
