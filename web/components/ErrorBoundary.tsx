import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Optional fallback UI. Defaults to a small inline panel. */
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Top-level ErrorBoundary — keeps a render-time exception in the React tree
 * from blanking the whole app. Logs to the console (the browser dev-tools
 * console is enough; we don't want to leak crash details to end users in prod).
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error('[NovaMind] UI error boundary caught:', error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.fallback) return this.props.fallback;

    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <div className="max-w-md rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center shadow-sm">
          <h1 className="text-lg font-semibold text-destructive">Something went wrong</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            The page hit an unexpected error. Reload to try again — your work in other tabs is safe.
          </p>
          {error.message && (
            <p className="mt-3 break-words rounded bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
              {error.message}
            </p>
          )}
          <button
            type="button"
            onClick={this.reset}
            className="mt-4 inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }
}
