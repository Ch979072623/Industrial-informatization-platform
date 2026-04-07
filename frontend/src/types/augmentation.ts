/**
 * 数据增强模块类型定义
 */

// ==================== 增强操作类型 ====================

/** 增强操作分类 */
export type AugmentationCategory = 'geometric' | 'color' | 'noise_blur' | 'advanced' | 'custom';

/** 增强操作定义 */
export interface AugmentationOperationDefinition {
  operation_type: string;
  name: string;
  description: string;
  category: AugmentationCategory;
  icon?: string;
  parameters: OperationParameter[];
  supports_bbox: boolean;
}

/** 操作参数定义 */
export interface OperationParameter {
  name: string;
  type: 'probability' | 'range' | 'float' | 'int' | 'boolean' | 'select';
  default: unknown;
  min?: number;
  max?: number;
  step?: number;
  options?: { label: string; value: unknown }[];
}

/** 增强操作配置（用于流水线） */
export interface AugmentationOperation {
  id?: string; // 客户端生成的唯一标识，用于 UI 状态管理
  operation_type: string;
  name: string;
  description?: string;
  probability: number;
  enabled: boolean;
  order: number;
  // 各操作的特定参数
  angle_range?: [number, number];
  crop_ratio?: number;
  scale_range?: [number, number];
  angle?: number;
  translate_x?: number;
  translate_y?: number;
  scale?: number;
  shear?: number;
  brightness_range?: [number, number];
  contrast_range?: [number, number];
  saturation_range?: [number, number];
  hue_range?: [number, number];
  clip_limit?: number;
  tile_grid_size?: number;
  std_range?: [number, number];
  noise_ratio?: number;
  kernel_size?: number;
  sigma?: number;
  erase_ratio?: number;
  max_erase_count?: number;
  alpha?: number;
  script_id?: string;
  // 其他动态参数
  [key: string]: unknown;
}

/** 可用操作列表响应 */
export interface AvailableOperationsResponse {
  operations: AugmentationOperationDefinition[];
  categories: { key: AugmentationCategory; name: string; icon: string }[];
}

// ==================== 模板类型 ====================

/** 增强模板 */
export interface AugmentationTemplate {
  id: string;
  name: string;
  description?: string;
  pipeline_config: AugmentationOperation[];
  is_preset: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

/** 创建模板请求 */
export interface CreateTemplateRequest {
  name: string;
  description?: string;
  pipeline_config: AugmentationOperation[];
}

/** 更新模板请求 */
export interface UpdateTemplateRequest {
  name?: string;
  description?: string;
  pipeline_config?: AugmentationOperation[];
}

// ==================== 增强任务类型 ====================

/** 增强任务状态 */
export type AugmentationJobStatus = 
  | 'pending' 
  | 'running' 
  | 'paused' 
  | 'completed' 
  | 'failed' 
  | 'cancelled';

/** 增强任务 */
export interface AugmentationJob {
  id: string;
  name: string;
  source_dataset_id: string;
  target_dataset_id?: string;
  pipeline_config: AugmentationOperation[];
  augmentation_factor: number;
  status: AugmentationJobStatus;
  progress: number;
  processed_count: number;
  total_count: number;
  generated_count: number;
  celery_task_id?: string;
  error_message?: string;
  execution_logs: ExecutionLog[];
  timing_stats?: TimingStats;
  created_by: string;
  created_at: string;
  updated_at: string;
}

/** 执行日志 */
export interface ExecutionLog {
  time: string;
  processed?: number;
  generated?: number;
  failed?: number;
  current_image?: string;
  error?: string;
}

/** 时间统计 */
export interface TimingStats {
  start_time: string;
  end_time: string;
  duration_seconds: number;
  images_per_second: number;
}

/** 创建任务请求 */
export interface CreateJobRequest {
  name: string;
  source_dataset_id: string;
  pipeline_config: AugmentationOperation[];
  augmentation_factor: number;
  new_dataset_name?: string;
  target_split?: 'train' | 'val' | 'test' | 'all';
  include_original?: boolean;
}

/** 更新任务请求 */
export interface UpdateJobRequest {
  name?: string;
  status?: AugmentationJobStatus;
}

/** 任务列表查询参数 */
export interface JobListQuery {
  page?: number;
  page_size?: number;
  status?: AugmentationJobStatus;
  source_dataset_id?: string;
}

/** 任务控制请求 */
export interface JobControlRequest {
  action: 'pause' | 'resume' | 'cancel';
}

/** 任务控制响应 */
export interface JobControlResponse {
  success: boolean;
  new_status: AugmentationJobStatus;
  message: string;
}

/** 任务进度响应 */
export interface JobProgressResponse {
  job_id: string;
  status: AugmentationJobStatus;
  progress: number;
  processed_count: number;
  total_count: number;
  generated_count: number;
  current_operation?: string;
  estimated_time_remaining?: number;
}

// ==================== 预览类型 ====================

/** 预览请求 */
export interface PreviewRequest {
  source_dataset_id: string;
  image_id?: string;
  pipeline_config: AugmentationOperation[];
  uploaded_image?: string; // base64 编码的图片
}

/** 预览响应 */
export interface PreviewResponse {
  preview_image_url: string;
  original_image_url: string;
  applied_operations: string[];
  annotations?: {
    bboxes: Array<{
      x1: number;
      y1: number;
      x2: number;
      y2: number;
      class_id: number;
    }>;
  };
}

// ==================== 自定义脚本类型 ====================

/** 自定义脚本 */
export interface CustomScript {
  id: string;
  name: string;
  description?: string;
  file_size: number;
  is_valid: boolean;
  validation_error?: string;
  interface_type: string;
  created_by: string;
  created_at: string;
}

/** 上传脚本请求 */
export interface UploadScriptRequest {
  name: string;
  description?: string;
  file: File;
}

// ==================== 流水线验证类型 ====================

/** 流水线验证响应 */
export interface PipelineValidationResponse {
  success: boolean;
  message: string;
}

// ==================== 组件 Props 类型 ====================

/** 操作卡片 Props */
export interface OperationCardProps {
  operation: AugmentationOperationDefinition;
  onDragStart: (operation: AugmentationOperationDefinition) => void;
  isDraggable?: boolean;
}

/** 流水线项 Props */
export interface PipelineItemProps {
  operation: AugmentationOperation;
  index: number;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onUpdate: (operation: AugmentationOperation) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
}

/** 预览面板 Props */
export interface PreviewPanelProps {
  datasetId: string;
  pipelineConfig: AugmentationOperation[];
  selectedImageId?: string;
  onImageSelect?: (imageId: string) => void;
}

/** 执行面板 Props */
export interface ExecutionPanelProps {
  datasetId: string;
  pipelineConfig: AugmentationOperation[];
  onJobCreated?: (job: AugmentationJob) => void;
}

// ==================== Store 状态类型 ====================

/** 增强状态 */
export interface AugmentationState {
  // 操作定义
  operations: AugmentationOperationDefinition[];
  categories: { key: AugmentationCategory; name: string; icon: string }[];
  operationsLoading: boolean;
  operationsError: string | null;
  
  // 流水线
  pipeline: AugmentationOperation[];
  selectedOperationId: string | null;
  
  // 模板
  templates: AugmentationTemplate[];
  templatesLoading: boolean;
  templatesError: string | null;
  
  // 任务
  jobs: AugmentationJob[];
  currentJob: AugmentationJob | null;
  jobsLoading: boolean;
  jobsError: string | null;
  
  // 预览
  preview: PreviewResponse | null;
  previewLoading: boolean;
  previewError: string | null;
  
  // 自定义脚本
  customScripts: CustomScript[];
  scriptsLoading: boolean;
  scriptsError: string | null;
  
  // Actions
  fetchOperations: () => Promise<void>;
  fetchTemplates: () => Promise<void>;
  createTemplate: (data: CreateTemplateRequest) => Promise<AugmentationTemplate>;
  updateTemplate: (id: string, data: UpdateTemplateRequest) => Promise<void>;
  deleteTemplate: (id: string) => Promise<void>;
  fetchJobs: (query?: JobListQuery) => Promise<void>;
  createJob: (data: CreateJobRequest) => Promise<AugmentationJob>;
  controlJob: (jobId: string, action: 'pause' | 'resume' | 'cancel') => Promise<void>;
  fetchJobProgress: (jobId: string) => Promise<JobProgressResponse>;
  generatePreview: (data: PreviewRequest) => Promise<void>;
  fetchCustomScripts: () => Promise<void>;
  uploadScript: (data: UploadScriptRequest) => Promise<void>;
  deleteScript: (id: string) => Promise<void>;
  
  // Pipeline Actions
  addToPipeline: (operation: AugmentationOperationDefinition) => void;
  updatePipelineItem: (index: number, operation: AugmentationOperation) => void;
  removeFromPipeline: (index: number) => void;
  movePipelineItem: (fromIndex: number, toIndex: number) => void;
  clearPipeline: () => void;
  setPipeline: (pipeline: AugmentationOperation[]) => void;
  loadTemplateToPipeline: (template: AugmentationTemplate) => void;
  setSelectedOperationId: (id: string | null) => void;
}

// ==================== 常量 ====================

/** 操作分类名称映射 */
export const CATEGORY_NAMES: Record<AugmentationCategory, string> = {
  geometric: '几何变换',
  color: '颜色变换',
  noise_blur: '噪声与模糊',
  advanced: '高级增强',
  custom: '自定义',
};

/** 操作分类图标映射 */
export const CATEGORY_ICONS: Record<AugmentationCategory, string> = {
  geometric: 'Move',
  color: 'Palette',
  noise_blur: 'Zap',
  advanced: 'Sparkles',
  custom: 'Code',
};

/** 任务状态显示映射 */
export const JOB_STATUS_LABELS: Record<AugmentationJobStatus, string> = {
  pending: '等待中',
  running: '运行中',
  paused: '已暂停',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

/** 任务状态颜色映射 */
export const JOB_STATUS_COLORS: Record<AugmentationJobStatus, string> = {
  pending: 'bg-yellow-500',
  running: 'bg-blue-500',
  paused: 'bg-orange-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  cancelled: 'bg-gray-500',
};
