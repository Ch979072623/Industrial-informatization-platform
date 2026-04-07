import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import { storage } from '@/utils/storage';
import type { ApiResponse, Token } from '@/types';

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

// 响应拦截器 - 处理 Token 刷新和错误
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiResponse>) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // 如果是 401 错误且不是刷新 token 的请求
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = storage.getRefreshToken();
        if (!refreshToken) {
          throw new Error('No refresh token');
        }

        // 调用刷新接口
        const response = await axios.post<ApiResponse<Token>>('/api/v1/auth/refresh', {
          refresh_token: refreshToken,
        });

        if (response.data.success) {
          const { access_token, refresh_token } = response.data.data;
          storage.setToken(access_token);
          storage.setRefreshToken(refresh_token);

          // 重试原请求
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
          }
          return api(originalRequest);
        }
      } catch (refreshError) {
        // 刷新失败，清除登录状态并跳转到登录页
        storage.clear();
        window.location.href = '/login';
        return Promise.reject(refreshError);
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
  AugmentationOperationDefinition,
  AvailableOperationsResponse,
  AugmentationTemplate,
  CreateTemplateRequest,
  UpdateTemplateRequest,
  AugmentationJob,
  CreateJobRequest,
  UpdateJobRequest,
  JobListQuery,
  JobControlRequest,
  JobControlResponse,
  JobProgressResponse,
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

  createTemplate: (data: CreateTemplateRequest) =>
    api.post<ApiResponse<AugmentationTemplate>>('/augmentation/templates', data),

  updateTemplate: (id: string, data: UpdateTemplateRequest) =>
    api.put<ApiResponse<AugmentationTemplate>>(`/augmentation/templates/${id}`, data),

  deleteTemplate: (id: string) =>
    api.delete<ApiResponse>(`/augmentation/templates/${id}`),

  // 任务管理
  getJobs: (params?: JobListQuery) =>
    api.get<ApiResponse<{ items: AugmentationJob[]; total: number }>>('/augmentation/jobs', { params }),

  getJob: (id: string) =>
    api.get<ApiResponse<AugmentationJob>>(`/augmentation/jobs/${id}`),

  createJob: (data: CreateJobRequest) =>
    api.post<ApiResponse<AugmentationJob>>('/augmentation/jobs', data),

  controlJob: (id: string, data: JobControlRequest) =>
    api.post<ApiResponse<JobControlResponse>>(`/augmentation/jobs/${id}/control`, data),

  getJobProgress: (id: string) =>
    api.get<ApiResponse<JobProgressResponse>>(`/augmentation/jobs/${id}/progress`),

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

export default api;
