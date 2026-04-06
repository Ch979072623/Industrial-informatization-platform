/**
 * 缩略图图片组件
 * 
 * 通过 Axios 获取需要认证的缩略图，支持自动刷新和错误处理
 */
import { useEffect, useState, useRef } from 'react';
import { datasetApi } from '@/services/api';
import { Loader2, ImageOff } from 'lucide-react';
import { cn } from '@/utils/cn';

interface ThumbnailImageProps {
  /** 数据集ID */
  datasetId: string;
  /** 图像ID */
  imageId: string;
  /** 替代文本 */
  alt: string;
  /** 自定义类名 */
  className?: string;
  /** 缩略图宽度 */
  width?: number;
  /** 缩略图高度 */
  height?: number;
  /** 是否懒加载 */
  lazy?: boolean;
}

export function ThumbnailImage({
  datasetId,
  imageId,
  alt,
  className,
  width = 256,
  height = 256,
  lazy = true,
}: ThumbnailImageProps) {
  const [imageUrl, setImageUrl] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadThumbnail = async () => {
      try {
        setLoading(true);
        setError(false);

        const response = await datasetApi.getImageThumbnail(datasetId, imageId, width, height);
        
        if (!isMounted) return;

        // response.data 已经是 Blob 类型（因为设置了 responseType: 'blob'）
        const blob = response.data as unknown as Blob;
        const url = URL.createObjectURL(blob);
        
        // 保存 URL 引用以便后续清理
        objectUrlRef.current = url;
        setImageUrl(url);
      } catch (err) {
        console.error('加载缩略图失败:', err);
        if (isMounted) {
          setError(true);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadThumbnail();

    // 清理函数
    return () => {
      isMounted = false;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [datasetId, imageId, width, height]);

  // 加载中状态
  if (loading) {
    return (
      <div
        className={cn(
          'flex items-center justify-center bg-muted',
          className
        )}
      >
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/50" />
      </div>
    );
  }

  // 错误状态
  if (error || !imageUrl) {
    return (
      <div
        className={cn(
          'flex items-center justify-center bg-muted',
          className
        )}
      >
        <ImageOff className="h-6 w-6 text-muted-foreground/30" />
      </div>
    );
  }

  // 正常显示图片
  return (
    <img
      src={imageUrl}
      alt={alt}
      className={className}
      loading={lazy ? 'lazy' : 'eager'}
    />
  );
}

export default ThumbnailImage;
