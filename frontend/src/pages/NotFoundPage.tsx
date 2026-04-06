import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { AlertCircle, Home } from 'lucide-react';

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/50 px-4">
      <div className="text-center space-y-6">
        <div className="flex justify-center">
          <div className="flex h-24 w-24 items-center justify-center rounded-full bg-muted">
            <AlertCircle className="h-12 w-12 text-muted-foreground" />
          </div>
        </div>

        <div className="space-y-2">
          <h1 className="text-6xl font-bold">404</h1>
          <h2 className="text-2xl font-semibold">页面未找到</h2>
          <p className="text-muted-foreground max-w-sm mx-auto">
            抱歉，您访问的页面不存在或已被移除。
          </p>
        </div>

        <div className="flex justify-center gap-4">
          <Button asChild>
            <Link to="/dashboard">
              <Home className="mr-2 h-4 w-4" />
              返回首页
            </Link>
          </Button>
          <Button variant="outline" onClick={() => window.history.back()}>
            返回上一页
          </Button>
        </div>
      </div>
    </div>
  );
}

export default NotFoundPage;
