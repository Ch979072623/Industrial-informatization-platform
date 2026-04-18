/**
 * Toast 提示 Hook
 * 
 * 简单的 toast 提示功能
 */
import { useState, useCallback } from 'react';

interface ToastOptions {
  title?: string;
  description?: string;
  variant?: 'default' | 'destructive';
  duration?: number;
}

interface Toast extends ToastOptions {
  id: string;
}

/**
 * 使用 Toast
 * 
 * 返回 toast 控制器
 */
export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((options: ToastOptions) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast: Toast = {
      ...options,
      id,
      duration: options.duration || 3000,
    };

    setToasts((prev) => [...prev, newToast]);

    // 自动移除
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, newToast.duration);

    // 控制台输出（调试用）
    if (options.variant === 'destructive') {
      console.error(`[Toast] ${options.title}: ${options.description}`);
    } else {
      console.log(`[Toast] ${options.title}: ${options.description}`);
    }
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toast, toasts, dismiss };
}

export default useToast;
