/**
 * 预览服务
 * 
 * 提供图片处理、缓存管理和 API 调用的封装
 */
import { augmentationApi } from './api';
import { datasetApi } from './api';
import type {
  PreviewResult,
  PreviewError,
  PreviewRequestParams,
} from '@/types/preview';
import { PREVIEW_CONFIG } from '@/types/preview';

// 消息 ID 生成器
let messageId = 0;

/**
 * Web Worker 管理器
 */
class WorkerManager {
  private worker: Worker | null = null;
  private pendingMessages: Map<string, { resolve: (value: unknown) => void; reject: (reason: Error) => void }> = new Map();

  constructor() {
    this.initWorker();
  }

  private initWorker() {
    try {
      // 使用 Vite 的 worker 导入语法
      this.worker = new Worker(new URL('@/workers/imageProcessor.worker.ts', import.meta.url), {
        type: 'module',
      });

      this.worker.onmessage = (event) => {
        const { id, success, result, error } = event.data;
        const pending = this.pendingMessages.get(id);
        
        if (pending) {
          if (success) {
            pending.resolve(result);
          } else {
            pending.reject(new Error(error));
          }
          this.pendingMessages.delete(id);
        }
      };

      this.worker.onerror = (error) => {
        console.error('Worker error:', error);
      };
    } catch (error) {
      console.warn('Web Worker initialization failed, falling back to main thread:', error);
    }
  }

  async sendMessage<T>(type: string, payload: unknown): Promise<T> {
    // 如果 Worker 不可用，使用主线程处理
    if (!this.worker) {
      return this.fallbackProcess<T>(type, payload);
    }

    return new Promise((resolve, reject) => {
      const id = `${Date.now()}_${++messageId}`;
      this.pendingMessages.set(id, { resolve: resolve as (value: unknown) => void, reject });
      
      // 设置超时
      setTimeout(() => {
        if (this.pendingMessages.has(id)) {
          this.pendingMessages.delete(id);
          reject(new Error('Worker message timeout'));
        }
      }, 5000);

      this.worker!.postMessage({ id, type, payload });
    });
  }

  private async fallbackProcess<T>(type: string, payload: unknown): Promise<T> {
    // 主线程降级处理
    switch (type) {
      case 'extractMetadata': {
        const arrayBuffer = payload as ArrayBuffer;
        const bytes = new Uint8Array(arrayBuffer);
        const result: { width?: number; height?: number; format?: string } = {};
        
        if (bytes[0] === 0xFF && bytes[1] === 0xD8) {
          result.format = 'JPEG';
        } else if (bytes[0] === 0x89 && bytes[1] === 0x50) {
          result.format = 'PNG';
        }
        
        return result as T;
      }
      default:
        throw new Error(`Fallback not implemented for type: ${type}`);
    }
  }

  terminate() {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
    }
  }
}

// 全局 Worker 实例
const workerManager = new WorkerManager();

/**
 * 预览缓存管理器
 */
class PreviewCache {
  private cache: Map<string, { result: PreviewResult; timestamp: number }> = new Map();

  private generateKey(params: PreviewRequestParams): string {
    // 生成缓存键：配置哈希 + 图片标识
    const configStr = JSON.stringify(params.pipeline_config);
    const imageId = params.sample_type === 'dataset' 
      ? `${params.dataset_id}_${params.image_id}`
      : 'uploaded';
    return `${this.hashString(configStr)}_${imageId}`;
  }

  private hashString(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return hash.toString(16);
  }

  get(params: PreviewRequestParams): PreviewResult | null {
    const key = this.generateKey(params);
    const cached = this.cache.get(key);
    
    if (!cached) return null;
    
    // 检查是否过期
    const now = Date.now();
    const expireTime = PREVIEW_CONFIG.CACHE_DURATION * 60 * 1000;
    
    if (now - cached.timestamp > expireTime) {
      this.cache.delete(key);
      return null;
    }
    
    return { ...cached.result, cache_hit: true };
  }

  set(params: PreviewRequestParams, result: PreviewResult): void {
    const key = this.generateKey(params);
    this.cache.set(key, {
      result: { ...result, cache_hit: false },
      timestamp: Date.now(),
    });
  }

  clear(): void {
    this.cache.clear();
  }
}

const previewCache = new PreviewCache();

/**
 * 验证上传文件
 */
export function validateUploadFile(file: File): PreviewError | null {
  // 检查文件大小
  if (file.size > PREVIEW_CONFIG.MAX_FILE_SIZE * 1024 * 1024) {
    return {
      type: 'FILE_TOO_LARGE',
      message: `文件大小超过限制（最大 ${PREVIEW_CONFIG.MAX_FILE_SIZE}MB）`,
      retryable: false,
    };
  }

  // 检查文件类型
  if (!PREVIEW_CONFIG.ALLOWED_FORMATS.includes(file.type)) {
    return {
      type: 'INVALID_FORMAT',
      message: `不支持的图片格式（支持: ${PREVIEW_CONFIG.ALLOWED_FORMATS.map(t => t.replace('image/', '')).join(', ')}）`,
      retryable: false,
    };
  }

  return null;
}

/**
 * 使用 Web Worker 提取图片元数据
 */
export async function extractImageMetadata(file: File): Promise<{ width?: number; height?: number; format?: string }> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    return await workerManager.sendMessage('extractMetadata', arrayBuffer);
  } catch (error) {
    console.warn('Metadata extraction failed:', error);
    return {};
  }
}

/**
 * 读取文件为 Data URL
 */
export function readFileAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error('文件读取失败'));
    reader.readAsDataURL(file);
  });
}

/**
 * 创建预览请求
 */
export async function createPreview(
  params: PreviewRequestParams,
  options: {
    signal?: AbortSignal;
    onProgress?: (progress: number) => void;
    uploadedImage?: string; // base64 编码的图片
  } = {}
): Promise<PreviewResult> {
  const { signal, onProgress, uploadedImage } = options;
  
  // 检查缓存（仅对数据集图片）
  if (!uploadedImage) {
    const cached = previewCache.get(params);
    if (cached) {
      return cached;
    }
  }

  // 模拟进度
  if (onProgress) {
    onProgress(10);
    await new Promise(r => setTimeout(r, 100));
    onProgress(30);
  }

  try {
    const response = await augmentationApi.createPreview({
      source_dataset_id: params.dataset_id || '',
      image_id: params.image_id,
      pipeline_config: params.pipeline_config,
      uploaded_image: uploadedImage,
    });

    if (onProgress) {
      onProgress(80);
    }

    if (!response.data.success) {
      throw new Error(response.data.message || '预览生成失败');
    }

    // 使用新的响应格式
    const data = response.data.data;
    const result: PreviewResult = {
      original: {
        url: data.original.url,
        width: data.original.width,
        height: data.original.height,
        bbox_count: data.original.bbox_count,
        bboxes: data.original.bboxes.map((bbox) => ({
          id: bbox.id,
          x1: bbox.x1,
          y1: bbox.y1,
          x2: bbox.x2,
          y2: bbox.y2,
          class_id: bbox.class_id,
          class_name: bbox.class_name,
        })),
      },
      augmented: {
        url: data.augmented.url,
        width: data.augmented.width,
        height: data.augmented.height,
        bbox_count: data.augmented.bbox_count,
        bboxes: data.augmented.bboxes.map((bbox) => ({
          id: bbox.id,
          x1: bbox.x1,
          y1: bbox.y1,
          x2: bbox.x2,
          y2: bbox.y2,
          class_id: bbox.class_id,
          class_name: bbox.class_name,
        })),
      },
      applied_operations: data.applied_operations,
      processing_time_ms: data.processing_time_ms || 0,
      cache_hit: false,
    };

    if (onProgress) {
      onProgress(100);
    }

    // 缓存结果
    previewCache.set(params, result);

    return result;
  } catch (error) {
    if (signal?.aborted) {
      throw new Error('请求已取消');
    }
    throw error;
  }
}

/**
 * 带重试的预览请求
 */
export async function createPreviewWithRetry(
  params: PreviewRequestParams,
  uploadedImage?: string,
  maxRetries: number = PREVIEW_CONFIG.MAX_RETRY
): Promise<PreviewResult> {
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), PREVIEW_CONFIG.TIMEOUT);
      
      const result = await createPreview(params, { 
        signal: controller.signal,
        uploadedImage 
      });
      clearTimeout(timeoutId);
      
      return result;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error('Unknown error');
      
      // 如果是用户取消或文件错误，不重试
      if (error instanceof Error && 
          (error.name === 'AbortError' || 
           error.message.includes('文件') || 
           error.message.includes('格式'))) {
        throw error;
      }
      
      // 指数退避
      if (attempt < maxRetries) {
        const delay = PREVIEW_CONFIG.RETRY_BASE_DELAY * Math.pow(2, attempt);
        await new Promise(r => setTimeout(r, delay));
      }
    }
  }
  
  throw lastError || new Error('预览请求失败');
}

/**
 * 获取数据集样本图片
 */
export async function fetchDatasetSampleImages(datasetId: string, count: number = 10): Promise<Array<{ id: string; filename: string; url: string }>> {
  try {
    const response = await datasetApi.getDatasetPreview(datasetId, count);
    if (!response.data.success) {
      return [];
    }
    
    return response.data.data.preview_images.map(img => ({
      id: img.id,
      filename: img.filename,
      url: img.filepath,
    }));
  } catch (error) {
    console.error('获取数据集样本失败:', error);
    return [];
  }
}

/**
 * 清除预览缓存
 */
export function clearPreviewCache(): void {
  previewCache.clear();
}

/**
 * 将预览错误分类
 */
export function classifyPreviewError(error: Error): PreviewError {
  const message = error.message.toLowerCase();
  
  // 超时错误
  if (message.includes('timeout') || message.includes('超时')) {
    return {
      type: 'TIMEOUT',
      message: '预览超时，请简化流水线或更换图片',
      details: error.message,
      retryable: true,
    };
  }
  
  // 网络错误
  if (message.includes('network') || message.includes('连接') || message.includes('offline')) {
    return {
      type: 'NETWORK_ERROR',
      message: '网络连接失败，请检查网络后重试',
      details: error.message,
      retryable: true,
    };
  }
  
  // 增强失败
  if (message.includes('augment') || message.includes('增强') || message.includes('rotate') || message.includes('边界')) {
    return {
      type: 'AUGMENTATION_FAILED',
      message: '增强处理失败，请检查参数设置',
      details: error.message,
      retryable: true,
    };
  }
  
  // 图片加载失败
  if (message.includes('load') || message.includes('读取')) {
    return {
      type: 'IMAGE_LOAD_FAILED',
      message: '图片加载失败，请重试或更换图片',
      details: error.message,
      retryable: true,
    };
  }
  
  // 默认错误
  return {
    type: 'AUGMENTATION_FAILED',
    message: error.message || '预览生成失败',
    retryable: true,
  };
}

export { workerManager };
