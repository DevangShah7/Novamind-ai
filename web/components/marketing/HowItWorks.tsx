import { useTheme } from '../../lib/theme';
import { cn } from '../../lib/cn';

const STEPS = [
  {
    n: '01',
    title: 'Create your account',
    body: 'Sign up with email or Google. Free tier is unlocked the moment you verify.',
  },
  {
    n: '02',
    title: 'Pick a model',
    body: 'Choose from llama3, mistral, qwen, and more — switching is one click.',
  },
  {
    n: '03',
    title: 'Chat, build, ship',
    body: 'Use the web app or hit /v1/* with an API key. Same models, same billing.',
  },
] as const;

/**
 * "How it works" 3-step explainer for the landing page. The step
 * number colors adapt to the current theme (gradient in light, solid
 * indigo in dark) for legibility.
 */
export default function HowItWorks() {
  const { resolved } = useTheme();
  return (
    <section className="border-t border-border/60 bg-muted/30 py-20 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            From sign-up to first reply{' '}
            <span className="gradient-text">in three steps</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            No credit card. No waiting list. No custom config to read.
          </p>
        </div>

        <ol className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-3">
          {STEPS.map(({ n, title, body }) => (
            <li
              key={n}
              className="relative rounded-xl border border-border bg-card p-6 shadow-sm transition-shadow hover:shadow-md"
            >
              <span
                className={cn(
                  'inline-flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold text-white',
                  resolved === 'dark' ? 'bg-primary' : 'gradient-bg'
                )}
              >
                {n}
              </span>
              <h3 className="mt-4 text-lg font-semibold">{title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
