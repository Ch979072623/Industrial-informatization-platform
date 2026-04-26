import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import { storage } from '@/utils/storage';
import type { ApiResponse, Token, TokenRefreshResponse } from '@/types';

// 创建 Axios 实例
const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加 Token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = storage.getToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// 全局 token 刷新锁：所有并发 401 请求共享同一个刷新 Promise
let refreshingPromise: Promise<string> | null = null;

// 响应拦截器 - 处理 Token 刷新和错误
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiResponse>) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // 如果是 401 错误且不是刷新 token 的请求
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // 全局锁：所有并发 401 请求等待同一个刷新
      if (!refreshingPromise) {
        refreshingPromise = (async () => {
          const refreshToken = storage.getRefreshToken();
          if (!refreshToken) throw new Error('No refresh token');

          const resp = await axios.post<ApiResponse<TokenRefreshResponse>>('/api/v1/auth/refresh', {
            refresh_token: refreshToken,
          });

          if (!resp.data.success) throw new Error('Refresh failed');

          const { access_token } = resp.data.data;
          storage.setToken(access_token);
          // 后端 refresh 接口只返回新 access_token，不返回 refresh_token
          // refresh_token 保持原值，不要覆盖成 undefined
          return access_token;
        })().finally(() => {
          // 推迟到下一个 microtask 再清空，保证当前 tick 里所有并发请求
          // 都已完成 if (!refreshingPromise) 判断并共享同一个 promise
          queueMicrotask(() => { refreshingPromise = null; });
        });
      }

      try {
        const accessToken = await refreshingPromise;
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${accessToken}`;
        }
        return api(originalRequest);
      } catch (e) {
        console.error('[CRITICAL] token refresh failed, redirecting to login', e);
        storage.clear();
        window.location.href = '/login';
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

// 认证相关 API
export const authApi = {
  login: (username: string, password: string) =>
    api.post<ApiResponse<Token>>('/auth/login', { username, password }),

  register: (data: { username: string; email: string; password: string }) =>
    api.post<ApiResponse<{ id: string; username: string; email: string }>>('/auth/register', data),

  logout: () => api.post<ApiResponse>('/auth/logout'),

  getMe: () => api.get<ApiResponse>('/auth/me'),

  updateMe: (data: Partial<{ username: string; email: string; password: string }>) =>
    api.put<ApiResponse>('/auth/me', data),
};

// 用户管理 API（管理员）
export const userApi = {
  getUsers: (params?: { page?: number; page_size?: number }) =>
    api.get<ApiResponse>('/users', { params }),

  createUser: (data: { username: string; email: string; password: string; role: string }) =>
    api.post<ApiResponse>('/users', data),

  updateUser: (id: string, data: Partial<{ username: string; email: string; role: string; is_active: boolean }>) =>
    api.put<ApiResponse>(`/users/${id}`, data),

  deleteUser: (id: string) =>
    api.delete<ApiResponse>(`/users/${id}`),
};

import type { 
  DatasetStatistics, 
  DatasetChartData, 
  RefreshStatisticsParams 
} from '@/types/datasetStatistics';

// 数据集管理 API
export const datasetApi = {
  // 获取数据集列表
  getDatasets: (params?: { page?: number; page_size?: number; search?: string; type?: string }) =>
    api.get<ApiResponse>('/datasets/', { params }),

  // 获取数据集详情
  getDataset: (id: string) =>
    api.get<ApiResponse>(`/datasets/${id}`),

  // 上传数据集（支持分片上传）
  uploadDataset: (formData: FormData) => {
    return api.post<ApiResponse>('/datasets/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  // 获取数据集统计信息（新的详细统计API）
  getDatasetStatistics: (id: string, params?: RefreshStatisticsParams) =>
    api.get<ApiResponse<DatasetStatistics>>(`/datasets/${id}/statistics`, { params }),

  // 刷新数据集统计信息（强制重新分析）
  refreshDatasetStatistics: (id: string) =>
    api.post<ApiResponse<DatasetStatistics>>(`/datasets/${id}/statistics/refresh`),

  // 获取数据集图表数据（用于图表展示）
  getDatasetChartData: (id: string) =>
    api.get<ApiResponse<DatasetChartData>>(`/datasets/${id}/chart-data`),

  // 删除数据集统计信息
  deleteDatasetStatistics: (id: string) =>
    api.delete<ApiResponse>(`/datasets/${id}/statistics`),

  // 执行数据集划分
  splitDataset: (id: string, data: { train_ratio: number; val_ratio: number; test_ratio: number; random_seed?: number }) =>
    api.post<ApiResponse>(`/datasets/${id}/split`, data),

  // 格式转换
  convertDataset: (id: string, data: { target_format: string; options?: Record<string, unknown> }) =>
    api.post<ApiResponse>(`/datasets/${id}/convert`, data),

  // 获取图片列表
  getDatasetImages: (id: string, params?: { page?: number; page_size?: number; annotated?: boolean }) =>
    api.get<ApiResponse>(`/datasets/${id}/images`, { params }),

  // 获取缩略图
  getImageThumbnail: (datasetId: string, imageId: string, width?: number, height?: number) =>
    api.get<Blob>(`/datasets/${datasetId}/images/${imageId}/thumbnail`, {
      params: (width || height) ? { width: width || 256, height: height || 256 } : undefined,
      responseType: 'blob',
    }),

  // 获取带标注的图片
  getAnnotatedImage: (datasetId: string, imageId: string, options?: { showAnnotations?: boolean; annotationColor?: string }) =>
    api.get<Blob>(`/datasets/${datasetId}/images/${imageId}/annotated`, {
      params: options,
      responseType: 'blob',
    }),

  // 删除数据集
  deleteDataset: (id: string) =>
    api.delete<ApiResponse>(`/datasets/${id}`),

  // 获取数据集标签分析
  getDatasetLabels: (id: string) =>
    api.get<ApiResponse>(`/datasets/${id}/labels`),

  // 获取数据集预览
  getDatasetPreview: (id: string, count?: number) =>
    api.get<ApiResponse>(`/datasets/${id}/preview`, { params: { count } }),

  // 更新数据集标签
  updateDatasetLabels: (id: string, data: { class_names: string[]; save_to_yaml?: boolean }) =>
    api.put<ApiResponse>(`/datasets/${id}/labels`, data),

  // 上传YAML配置
  uploadYamlConfig: (id: string, yamlContent: string) =>
    api.post<ApiResponse>(`/datasets/${id}/labels/yaml`, { yaml_content: yamlContent }),

  // 获取数据集卡片信息（包含预览和统计）
  getDatasetCardInfo: (id: string, previewCount?: number) =>
    api.get<ApiResponse>(`/datasets/${id}/card-info`, { 
      params: previewCount ? { preview_count: previewCount } : undefined 
    }),

  // 导出数据集
  exportDataset: (id: string, format: string = 'original', splits?: string[]) =>
    api.get<Blob>(`/datasets/${id}/export`, {
      params: { format, splits: splits?.join(',') },
      responseType: 'blob',
    }),
};

// 数据增强 API
import type {
  AugmentationOperation,
  AvailableOperationsResponse,
  AugmentationTemplate,
  AugmentationCreateTemplateRequest,
  AugmentationUpdateTemplateRequest,
  AugmentationJob,
  AugmentationCreateJobRequest,
  AugmentationJobListQuery,
  AugmentationJobControlRequest,
  AugmentationJobControlResponse,
  AugmentationJobProgressResponse,
  PreviewRequest,
  PreviewResponse,
  CustomScript,
  UploadScriptRequest,
  PipelineValidationResponse,
} from '@/types/augmentation';

export const augmentationApi = {
  // 获取可用操作列表
  getOperations: () =>
    api.get<ApiResponse<AvailableOperationsResponse>>('/augmentation/operations'),

  // 模板管理
  getTemplates: (params?: { page?: number; page_size?: number }) =>
    api.get<ApiResponse<{ items: AugmentationTemplate[]; total: number }>>('/augmentation/templates', { params }),

  createTemplate: (data: AugmentationCreateTemplateRequest) =>
    api.post<ApiResponse<AugmentationTemplate>>('/augmentation/templates', data),

  updateTemplate: (id: string, data: AugmentationUpdateTemplateRequest) =>
    api.put<ApiResponse<AugmentationTemplate>>(`/augmentation/templates/${id}`, data),

  deleteTemplate: (id: string) =>
    api.delete<ApiResponse>(`/augmentation/templates/${id}`),

  // 任务管理
  getJobs: (params?: AugmentationJobListQuery) =>
    api.get<ApiResponse<{ items: AugmentationJob[]; total: number }>>('/augmentation/jobs', { params }),

  getJob: (id: string) =>
    api.get<ApiResponse<AugmentationJob>>(`/augmentation/jobs/${id}`),

  createJob: (data: AugmentationCreateJobRequest) =>
    api.post<ApiResponse<AugmentationJob>>('/augmentation/jobs', data),

  controlJob: (id: string, data: AugmentationJobControlRequest) =>
    api.post<ApiResponse<AugmentationJobControlResponse>>(`/augmentation/jobs/${id}/control`, data),

  getJobProgress: (id: string) =>
    api.get<ApiResponse<AugmentationJobProgressResponse>>(`/augmentation/jobs/${id}/progress`),

  // 预览
  createPreview: (data: PreviewRequest) =>
    api.post<ApiResponse<PreviewResponse>>('/augmentation/preview', data),

  getPreviewImage: (previewId: string) =>
    api.get<Blob>(`/augmentation/preview/${previewId}/image`, { responseType: 'blob' }),

  // 自定义脚本
  getCustomScripts: (params?: { page?: number; page_size?: number }) =>
    api.get<ApiResponse<{ items: CustomScript[]; total: number }>>('/augmentation/custom-scripts', { params }),

  uploadScript: (data: UploadScriptRequest) => {
    const formData = new FormData();
    formData.append('name', data.name);
    if (data.description) formData.append('description', data.description);
    formData.append('file', data.file);
    return api.post<ApiResponse<CustomScript>>('/augmentation/custom-scripts', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  deleteScript: (id: string) =>
    api.delete<ApiResponse>(`/augmentation/custom-scripts/${id}`),

  // 配置验证
  validatePipeline: (pipelineConfig: AugmentationOperation[]) =>
    api.post<ApiResponse<PipelineValidationResponse>>('/augmentation/validate', pipelineConfig),
};

// 数据生成 API
import type {
  GeneratorListResponse,
  ValidateConfigRequest,
  ValidateConfigResponse,
  GenerationPreviewRequest,
  GenerationPreviewResponse,
  GenerationTemplate,
  GenerationCreateTemplateRequest,
  GenerationUpdateTemplateRequest,
  GenerationJob,
  GenerationJobListQuery,
  ExecuteGenerationRequest,
  ExecuteGenerationResponse,
  GenerationJobControlRequest,
  GenerationJobControlResponse,
  GenerationJobProgressResponse,
  QualityReportResponse,
  MergeGenerationRequest,
  MergeGenerationResponse,
  DefectCacheListResponse,
  RefreshCacheRequest,
  HeatmapGenerateRequest,
  HeatmapGenerateResponse,
} from '@/types/generation';

export const generationApi = {
  // 数据集列表（用于选择缺陷源和基底）
  getDatasets: (params?: { has_annotations?: boolean }) =>
    api.get<ApiResponse<{ items: Array<{
      id: string;
      name: string;
      description?: string;
      format: string;
      image_count: number;
      annotated_count: number;
      class_names: string[];
      created_at: string;
    }>; total: number }>>('/generation/datasets', { params }),

  // 生成器管理
  getGenerators: () =>
    api.get<ApiResponse<GeneratorListResponse>>('/generation/generators'),

  validateConfig: (data: ValidateConfigRequest) =>
    api.post<ApiResponse<ValidateConfigResponse>>('/generation/validate', data),

  // 预览
  createPreview: (data: GenerationPreviewRequest) =>
    api.post<ApiResponse<GenerationPreviewResponse>>('/generation/preview', data),

  // 模板管理
  getTemplates: (params?: { page?: number; page_size?: number }) =>
    api.get<ApiResponse<{ items: GenerationTemplate[]; total: number }>>('/generation/templates', { params }),

  createTemplate: (data: GenerationCreateTemplateRequest) =>
    api.post<ApiResponse<GenerationTemplate>>('/generation/templates', data),

  updateTemplate: (id: string, data: GenerationUpdateTemplateRequest) =>
    api.put<ApiResponse<GenerationTemplate>>(`/generation/templates/${id}`, data),

  deleteTemplate: (id: string) =>
    api.delete<ApiResponse>(`/generation/templates/${id}`),

  // 任务管理
  getJobs: (params?: GenerationJobListQuery) =>
    api.get<ApiResponse<{ items: GenerationJob[]; total: number }>>('/generation/jobs', { params }),

  getJob: (id: string) =>
    api.get<ApiResponse<GenerationJob>>(`/generation/jobs/${id}`),

  executeGeneration: (data: ExecuteGenerationRequest) =>
    api.post<ApiResponse<ExecuteGenerationResponse>>('/generation/execute', data),

  controlJob: (id: string, data: GenerationJobControlRequest) =>
    api.post<ApiResponse<GenerationJobControlResponse>>(`/generation/jobs/${id}/control`, data),

  getJobProgress: (id: string) =>
    api.get<ApiResponse<GenerationJobProgressResponse>>(`/generation/jobs/${id}/progress`),

  // 质量报告
  getQualityReport: (jobId: string) =>
    api.get<ApiResponse<QualityReportResponse>>(`/generation/jobs/${jobId}/quality-report`),

  // 合并结果
  mergeResults: (data: MergeGenerationRequest) =>
    api.post<ApiResponse<MergeGenerationResponse>>('/generation/merge', data),

  // 缓存管理
  getCaches: () =>
    api.get<ApiResponse<DefectCacheListResponse>>('/generation/cache'),

  refreshCache: (data: RefreshCacheRequest) =>
    api.post<ApiResponse>('/generation/cache/refresh', data),

  deleteCache: (cacheKey: string) =>
    api.delete<ApiResponse>(`/generation/cache/${cacheKey}`),

  // 热力图工具
  generateHeatmap: (data: HeatmapGenerateRequest) =>
    api.post<ApiResponse<HeatmapGenerateResponse>>('/generation/heatmap/generate', data),

  // 删除任务
  deleteJob: (id: string) =>
    api.delete<ApiResponse<{ deleted_count: number }>>(`/generation/jobs/${id}`),

  deleteJobs: (params: { status?: string; job_ids?: string[] }) =>
    api.delete<ApiResponse<{ deleted_count: number }>>('/generation/jobs', { data: params }),
};

// 机器学习模块 API（新 module_definitions 表）
import type {
  ModuleDefinition,
  ModuleDefinitionDetail,
  ModuleDefinitionCreatePayload,
  MLModuleQuery,
  ConnectionValidationResult,
  ModelValidationResult,
  ModelBuilderConfig,
  ModelBuilderConfigListItem,
  ModelBuilderConfigCreate,
  ModelBuilderConfigUpdate,
  ModelNode,
  ModelEdge,
} from '@/types/mlModule';

export const mlModuleApi = {
  // 获取模块分类
  getCategories: () =>
    api.get<ApiResponse<Array<{key: string; label: string; icon: string}>>>('/models/modules/categories'),

  // 获取所有模块（扁平列表，前端按 category 分组）
  getModules: (query?: MLModuleQuery) =>
    api.get<ApiResponse<ModuleDefinition[]>>('/models/modules', { params: query }),

  // 获取单个模块详情（按 type 查询）
  getModule: (moduleType: string) =>
    api.get<ApiResponse<ModuleDefinitionDetail>>(`/models/modules/${moduleType}`),

  // 从 Module 画布注册新模块
  createModule: async (payload: ModuleDefinitionCreatePayload) => {
    const response = await api.post<ApiResponse<ModuleDefinition>>('/models/modules', payload);
    return { data: response.data, status: response.status };
  },

  // 重新生成模块代码
  regenerateModuleCode: async (moduleId: string, expandComposites: boolean) => {
    const response = await api.post<ApiResponse<{ path: string }>>(`/models/modules/${moduleId}/generate-code`, {
      expand_composites: expandComposites,
    });
    return { data: response.data, status: response.status };
  },

  // 验证连接
  validateConnection: (
    sourceModuleId: string,
    targetModuleId: string,
    sourcePort?: string,
    targetPort?: string,
    currentNodes?: ModelNode[],
    currentEdges?: ModelEdge[]
  ) =>
    api.post<ApiResponse<ConnectionValidationResult>>('/models/modules/validate-connection', {
      source_module_id: sourceModuleId,
      target_module_id: targetModuleId,
      source_port: sourcePort,
      target_port: targetPort,
      current_nodes: currentNodes,
      current_edges: currentEdges,
    }),

  // 验证模型
  validateModel: (nodes: ModelNode[], edges: ModelEdge[]) =>
    api.post<ApiResponse<ModelValidationResult>>('/models/modules/validate-model', { nodes, edges }),
};

// 模型构建器配置 API
export const modelBuilderApi = {
  // 获取配置列表
  getConfigs: (params?: { page?: number; page_size?: number; search?: string }) =>
    api.get<ApiResponse<{ items: ModelBuilderConfigListItem[]; total: number }>>('/model-configs', { params }),

  // 获取单个配置
  getConfig: (configId: string) =>
    api.get<ApiResponse<ModelBuilderConfig>>(`/model-configs/${configId}`),

  // 创建配置
  createConfig: (data: ModelBuilderConfigCreate) =>
    api.post<ApiResponse<ModelBuilderConfig>>('/model-configs', data),

  // 更新配置
  updateConfig: (configId: string, data: ModelBuilderConfigUpdate) =>
    api.put<ApiResponse<ModelBuilderConfig>>(`/model-configs/${configId}`, data),

  // 删除配置
  deleteConfig: (configId: string) =>
    api.delete<ApiResponse>(`/model-configs/${configId}`),

  // 克隆配置
  cloneConfig: (configId: string, newName?: string) =>
    api.post<ApiResponse<ModelBuilderConfig>>(`/model-configs/${configId}/clone`, null, {
      params: newName ? { new_name: newName } : undefined,
    }),

  // 获取代码
  getCode: (configId: string) =>
    api.get<ApiResponse<{ code: string; language: string }>>(`/model-configs/${configId}/code`),

  // 导出 YAML
  exportYaml: (configId: string) =>
    api.get<ApiResponse<{ yaml: string; codegen_results: Array<{ type: string; path?: string; error?: string }> }>>(`/model-configs/${configId}/export-yaml`),
};

export default api;

// 开发环境把 api 实例挂到 window，方便 Console 手动测试并发刷新
if (import.meta.env.DEV) {
  (window as unknown as { __api?: AxiosInstance }).__api = api;
}
