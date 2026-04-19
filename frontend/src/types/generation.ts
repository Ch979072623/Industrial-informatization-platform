/**
 * 数据生成相关类型定义
 */

// ==================== 生成器类型 ====================

export interface GeneratorInfo {
  name: string;
  description: string;
  version: string;
  is_builtin: boolean;
  config_schema: Record<string, any>;
  supported_formats: string[];
  default_config: Record<string, any>;
}

export interface GeneratorListResponse {
  generators: GeneratorInfo[];
}

// ==================== 配置验证类型 ====================

export interface ValidateConfigRequest {
  generator_name: string;
  config: Record<string, any>;
}

export interface ValidateConfigResponse {
  is_valid: boolean;
  errors?: ConfigError[];
}

export interface ConfigError {
  field: string;
  message: string;
}

// ==================== 预览类型 ====================

export interface GenerationPreviewRequest {
  generator_name: string;
  config: Record<string, any>;
  seed?: number;
  base_image_id?: string;
}

export interface PreviewAnnotation {
  boxes: number[][]; // [[x1, y1, x2, y2], ...]
  labels: number[];
  scores: number[];
}

export interface GenerationMetadata {
  num_defects: number;
  color_match_mode?: string;
  placement_strategy?: string;
  fusion_quality_scores?: number[];
  average_quality: number;
  api_type?: string;
  api_call_time?: number;
}

export interface GenerationPreviewResponse {
  original_image: string;
  generated_image: string;
  annotations: PreviewAnnotation;
  metadata: GenerationMetadata;
  generation_time: number;
}

// ==================== 模板类型 ====================

export interface GenerationTemplate {
  id: string;
  name: string;
  description?: string;
  generator_name: string;
  config: Record<string, any>;
  is_preset: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface GenerationCreateTemplateRequest {
  name: string;
  description?: string;
  generator_name: string;
  config: Record<string, any>;
}

export interface GenerationUpdateTemplateRequest {
  name?: string;
  description?: string;
  config?: Record<string, any>;
}

// ==================== 任务类型 ====================

export type GenerationJobStatus = 
  | 'pending' 
  | 'running' 
  | 'paused' 
  | 'completed' 
  | 'failed' 
  | 'cancelled';

export interface GenerationJob {
  id: string;
  name: string;
  generator_name: string;
  config: Record<string, any>;
  count: number;
  annotation_format: string;
  status: GenerationJobStatus;
  progress: number;
  processed_count: number;
  total_count: number;
  success_count: number;
  failed_count: number;
  output_dataset_id?: string;
  celery_task_id?: string;
  error_message?: string;
  execution_logs: any[];
  quality_report?: Record<string, any>;
  timing_stats?: Record<string, any>;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface GenerationCreateJobRequest {
  name: string;
  generator_name: string;
  config: Record<string, any>;
  count: number;
  annotation_format?: string;
  output_dataset_name?: string;
}

export interface UpdateJobRequest {
  name?: string;
  status?: GenerationJobStatus;
}

export interface GenerationJobListQuery {
  page?: number;
  page_size?: number;
  status?: GenerationJobStatus;
  generator_name?: string;
}

// ==================== 执行生成类型 ====================

export interface ExecuteGenerationRequest {
  generator_name: string;
  config: Record<string, any>;
  count: number;
  output_dataset_name: string;
  annotation_format?: string;
}

export interface ExecuteGenerationResponse {
  task_id: string;
  estimated_time: number;
  estimated_disk_usage: number;
}

// ==================== 任务控制类型 ====================

export type JobControlAction = 'pause' | 'resume' | 'cancel';

export interface GenerationJobControlRequest {
  action: JobControlAction;
}

export interface GenerationJobControlResponse {
  success: boolean;
  new_status: string;
  message: string;
}

// ==================== 任务进度类型 ====================

export interface GenerationErrorDetail {
  image_index: number;
  image_name?: string;
  error: string;
}

export interface GenerationJobProgressResponse {
  task_id: string;
  status: string;
  progress: number;
  processed_count: number;
  total_count: number;
  success_count: number;
  failed_count: number;
  current_image?: string;
  estimated_remaining_time?: number;
  errors: GenerationErrorDetail[];
}

// ==================== 质量报告类型 ====================

export interface QualityReportImageDetail {
  filename: string;
  defect_count: number;
  quality_score: number;
  generation_time: number;
}

export interface QualityReportResponse {
  task_id: string;
  total_images: number;
  success_count: number;
  failed_count: number;
  average_quality_score: number;
  image_details: QualityReportImageDetail[];
  failed_images: GenerationErrorDetail[];
  quality_distribution: Record<string, number>;
  class_distribution: Record<string, number>;
}

// ==================== 合并结果类型 ====================

export type MergeMode = 'create_new' | 'append' | 'replace';

export interface MergeGenerationRequest {
  task_id: string;
  merge_mode: MergeMode;
  target_dataset_id?: string;
  new_dataset_name?: string;
  class_mapping?: Record<string, number>;
}

export interface MergeGenerationResponse {
  merge_task_id: string;
  target_dataset_id: string;
  merged_count: number;
}

// ==================== 缓存管理类型 ====================

export interface DefectCacheInfo {
  cache_key: string;
  source_dataset_id: string;
  color_mode: string;
  defect_count: number;
  cache_size_mb: number;
  expires_at?: string;
  created_at: string;
}

export interface DefectCacheListResponse {
  caches: DefectCacheInfo[];
  total_size_mb: number;
}

export interface RefreshCacheRequest {
  dataset_id: string;
  color_mode?: string;
}

// ==================== 热力图类型 ====================

export type HeatmapType = 'gaussian' | 'edge' | 'center';

export interface HeatmapGenerateRequest {
  type: HeatmapType;
  width: number;
  height: number;
  params?: Record<string, any>;
}

export interface HeatmapGenerateResponse {
  heatmap_image: string;
  type: HeatmapType;
}

// ==================== 颜色匹配模式 ====================

export type ColorMatchMode = 'light' | 'standard' | 'strong' | 'custom';

export interface ColorMatchParams {
  invert_colors?: boolean;
  brightness_adjust?: number;
  clip_limit?: number;
  tile_grid_size?: number;
  contrast_factor?: number;
}

// ==================== 放置策略类型 ====================

export type PlacementStrategyType = 
  | 'random' 
  | 'region' 
  | 'grid' 
  | 'heatmap' 
  | 'center' 
  | 'edge';

export interface PlacementStrategy {
  type: PlacementStrategyType;
  roi?: [number, number, number, number]; // [x, y, w, h]
  heatmap_path?: string;
  defects_per_image?: {
    min: number;
    max: number;
  };
}

// ==================== 缺陷尺寸控制 ====================

export type DefectSizeMode = 'original' | 'random_scale' | 'fixed';

export interface DefectSizeConfig {
  mode: DefectSizeMode;
  scale_range?: [number, number];
  fixed_size?: {
    width: number;
    height: number;
  };
}

// ==================== 融合参数 ====================

export interface FusionParams {
  blur_kernel?: number;
  fusion_strength?: number;
}

// ==================== 缺陷迁移配置 ====================

export interface DefectMigrationConfig {
  source_type: 'dataset' | 'upload';
  source_dataset_id?: string;
  source_image_paths?: string[];
  base_dataset_id: string;
  base_image_paths?: string[];
  color_match_mode: ColorMatchMode;
  color_match_params?: ColorMatchParams;
  placement_strategy: PlacementStrategy;
  defect_size?: DefectSizeConfig;
  overlap_strategy?: {
    allow_overlap: boolean;
    max_overlap_ratio: number;
  };
  fusion_params?: FusionParams;
  class_mapping?: Record<string, number>;
}

// ==================== Stable Diffusion API 配置 ====================

export interface StableDiffusionAPIConfig {
  api_endpoint: string;
  api_key?: string;
  prompt: string;
  negative_prompt?: string;
  num_inference_steps?: number;
  guidance_scale?: number;
  image_size?: {
    width: number;
    height: number;
  };
  use_controlnet?: boolean;
  controlnet_image?: string;
  controlnet_model?: 'canny' | 'depth' | 'pose' | 'scribble';
  controlnet_strength?: number;
  seed?: number;
  timeout?: number;
  max_retries?: number;
  sampler?: string;
}
