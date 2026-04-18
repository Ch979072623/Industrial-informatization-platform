/**
 * React Error Boundary
 *
 * 捕获子组件渲染异常，避免整个应用白屏。
 * 用于 ModelBuilder 等复杂交互场景，方便定位渲染错误。
 */
import { Component, type ReactNode, type ErrorInfo } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] 渲染异常:', error);
    console.error('[ErrorBoundary] 组件栈:', info.componentStack);
    this.props.onError?.(error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="flex flex-col items-center justify-center min-h-[300px] p-6 border rounded-lg bg-destructive/5">
          <AlertTriangle className="h-10 w-10 text-destructive mb-4" />
          <h3 className="text-lg font-semibold text-destructive mb-2">
            组件渲染错误
          </h3>
          <p className="text-sm text-muted-foreground mb-4 text-center max-w-md">
            {this.state.error?.message || '未知错误'}
          </p>
          <pre className="text-xs bg-card p-3 rounded border overflow-auto max-w-full max-h-[200px] mb-4">
            {this.state.error?.stack}
          </pre>
          <Button onClick={this.handleReset} variant="outline">
            重试
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
