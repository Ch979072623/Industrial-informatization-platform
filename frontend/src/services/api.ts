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

export default api;
