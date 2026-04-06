/**
 * 全局类型定义
 */

// 用户相关
export interface User {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'user';
  is_active: boolean;
  production_line_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserLogin {
  username: string;
  password: string;
}

export interface UserRegister {
  username: string;
  email: string;
  password: string;
  production_line_id?: string;
}

// Token 相关
export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// API 响应
export interface ApiResponse<T = unknown> {
  success: boolean;
  message: string;
  data: T;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// 产线
export interface ProductionLine {
  id: string;
  name: string;
  description?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

// 导航菜单
export interface NavItem {
  title: string;
  href: string;
  icon: string;
  roles?: ('admin' | 'user')[];
  children?: NavItem[];
}

// 主题
export type Theme = 'light' | 'dark' | 'system';

// 数据集相关
export interface Dataset {
  id: string;
  name: string;
  description?: string;
  /** 数据格式: YOLO/COCO/VOC */
  format: 'YOLO' | 'COCO' | 'VOC';
  /** 存储路径 */
  path: string;
  total_images: number;
  total_annotations: number;
  class_names: string[];
  split_ratio: DatasetSplitRatio;
  /** 所属产线ID */
  production_line_id?: string | null;
  /** 创建者ID */
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface DatasetImage {
  id: string;
  filename: string;
  filepath: string;
  split: 'train' | 'val' | 'test';
  width?: number;
  height?: number;
  annotation_path?: string;
  created_at: string;
}

export interface DatasetStatistics {
  dataset_id: string;
  total_images: number;
  total_annotations: number;
  avg_annotations_per_image: number;
  images_with_annotations: number;
  images_without_annotations: number;
  class_count: number;
  class_distribution: ClassDistribution[];
  scan_status: 'pending' | 'running' | 'completed' | 'failed';
  last_scan_time?: string;
}

export interface DatasetSplitRatio {
  train: number;
  val: number;
  test: number;
}

export interface ClassDistribution {
  class_name: string;
  count: number;
  percentage: number;
}

export interface DatasetUploadParams {
  dataset_id: string;
  files?: File[];
  split?: 'train' | 'val' | 'test' | 'auto';
  auto_annotate?: boolean;
  annotation_file?: File;
}

export interface DatasetConvertParams {
  dataset_id: string;
  target_format: 'coco' | 'voc' | 'yolo';
  target_split_ratio?: DatasetSplitRatio;
  include_empty_images?: boolean;
  output_name?: string;
}

export interface DatasetListQuery {
  page?: number;
  page_size?: number;
  keyword?: string;
  type?: 'detection' | 'classification' | 'segmentation';
  status?: 'pending' | 'processing' | 'ready' | 'error';
  created_by?: string;
  sort_by?: 'created_at' | 'updated_at' | 'name' | 'total_images';
  sort_order?: 'asc' | 'desc';
}


// 数据集卡片信息（用于列表页展示）
export interface PreviewImageInfo {
  id: string;
  filename: string;
  filepath: string;
  width: number;
  height: number;
  split: 'train' | 'val' | 'test';
  annotation_count: number;
}

export interface DatasetCardInfo {
  id: string;
  name: string;
  description?: string;
  format: string;
  total_images: number;
  class_count: number;
  class_names: string[];
  preview_images: PreviewImageInfo[];
  annotations_per_class: Record<string, number>;
  created_at: string;
}

// 标签分析结果
export interface LabelAnalysisResult {
  class_names: string[];
  class_count: number;
  annotations_per_class: Record<string, number>;
  images_per_class: Record<string, number>;
  total_annotations: number;
  yaml_config?: Record<string, any>;
  has_yaml: boolean;
}

// 数据集预览结果
export interface DatasetPreviewResult {
  dataset_id: string;
  total_images: number;
  preview_images: PreviewImageInfo[];
}
