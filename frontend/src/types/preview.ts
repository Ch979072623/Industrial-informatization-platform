/**
 * 实时预览模块类型定义
 */

/** 预览模式 */
export type PreviewDisplayMode = 'image_only' | 'image_with_bboxes';

/** 预览样本类型 */
export type PreviewSampleType = 'dataset' | 'upload';

/** 标注框信息 */
export interface PreviewBBox {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  class_id: number;
  class_name?: string;
  confidence?: number;
  color?: string;
}

/** 预览图像信息 */
export interface PreviewImageInfo {
  url: string;
  width: number;
  height: number;
  bbox_count: number;
  bboxes: PreviewBBox[];
}

/** 预览结果 */
export interface PreviewResult {
  original: PreviewImageInfo;
  augmented: PreviewImageInfo;
  applied_operations: string[];
  processing_time_ms: number;
  cache_hit: boolean;
}

/** 预览请求参数 */
export interface PreviewRequestParams {
  sample_type: PreviewSampleType;
  dataset_id?: string;
  image_id?: string;
  pipeline_config: unknown[];
  display_mode: PreviewDisplayMode;
  max_size?: number;
}

/** 预览状态 */
export interface PreviewState {
  isLoading: boolean;
  progress: number;
  error: PreviewError | null;
  result: PreviewResult | null;
  retryCount: number;
}

/** 预览错误类型 */
export type PreviewErrorType = 
  | 'TIMEOUT'
  | 'AUGMENTATION_FAILED'
  | 'IMAGE_LOAD_FAILED'
  | 'NETWORK_ERROR'
  | 'FILE_TOO_LARGE'
  | 'INVALID_FORMAT';

/** 预览错误 */
export interface PreviewError {
  type: PreviewErrorType;
  message: string;
  details?: string;
  retryable: boolean;
}

/** 上传文件信息 */
export interface UploadFileInfo {
  file: File;
  previewUrl: string;
  width: number;
  height: number;
}

/** 缩放状态 */
export interface ZoomState {
  scale: number;
  position: { x: number; y: number };
  isDragging: boolean;
}

/** 组件 Props */
export interface ImageCompareProps {
  original: PreviewImageInfo;
  augmented: PreviewImageInfo;
  displayMode: PreviewDisplayMode;
  zoom: ZoomState;
  onZoomChange: (zoom: ZoomState) => void;
  selectedBBoxId: string | null;
  onBBoxSelect: (id: string | null) => void;
  classNames: string[];
}

export interface BBoxOverlayProps {
  bboxes: PreviewBBox[];
  imageWidth: number;
  imageHeight: number;
  scale: number;
  displayMode: PreviewDisplayMode;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export interface PreviewToolbarProps {
  displayMode: PreviewDisplayMode;
  onDisplayModeChange: (mode: PreviewDisplayMode) => void;
  zoomScale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetZoom: () => void;
  onRefresh: () => void;
  isLoading: boolean;
}

/** 常量配置 */
export const PREVIEW_CONFIG = {
  /** 预览超时时间（毫秒） */
  TIMEOUT: 2000,
  /** 防抖延迟（毫秒） */
  DEBOUNCE: 500,
  /** 最大文件大小（MB） */
  MAX_FILE_SIZE: 20,
  /** 预览图片最大尺寸 */
  MAX_IMAGE_SIZE: 800,
  /** 缓存时间（分钟） */
  CACHE_DURATION: 5,
  /** 最大重试次数 */
  MAX_RETRY: 3,
  /** 指数退避基数（毫秒） */
  RETRY_BASE_DELAY: 1000,
  /** 支持的图片格式 */
  ALLOWED_FORMATS: ['image/jpeg', 'image/png', 'image/webp', 'image/bmp'],
  /** 缩放范围 */
  ZOOM_RANGE: { min: 0.5, max: 3, step: 0.1 },
} as const;

/** 默认颜色映射 */
export const DEFAULT_BBOX_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
  '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B739', '#52B788',
];

/** 获取类别颜色 */
export function getClassColor(classId: number): string {
  return DEFAULT_BBOX_COLORS[classId % DEFAULT_BBOX_COLORS.length];
}
