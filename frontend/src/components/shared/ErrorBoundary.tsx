import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button } from '../ui';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 my-4 rounded-2xl border border-rose-500/30 bg-rose-950/20 text-slate-100 max-w-2xl mx-auto shadow-2xl space-y-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center shrink-0">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">
                {this.props.fallbackTitle || 'Component Encountered an Unexpected Issue'}
              </h2>
              <p className="text-xs text-rose-300/80">
                A rendering guard intercepted a runtime error to prevent application crash.
              </p>
            </div>
          </div>

          {this.state.error && (
            <div className="p-3 bg-slate-950/80 rounded-xl border border-rose-500/20 font-mono text-xs text-rose-300 break-words">
              {this.state.error.message}
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <Button variant="primary" onClick={this.handleReset}>
              <RefreshCw className="h-3.5 w-3.5" /> Reload View
            </Button>
            <Button onClick={() => window.location.reload()}>
              <Home className="h-3.5 w-3.5" /> Hard Refresh
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
