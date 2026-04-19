import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types';
import { authApi } from '@/services/api';
import { storage } from '@/utils/storage';

interface AuthState {
  // 状态
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // 方法
  login: (username: string, password: string) => Promise<boolean>;
  register: (data: { username: string; email: string; password: string }) => Promise<boolean>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // 初始状态
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // 登录
      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.login(username, password);
          
          if (response.data.success) {
            const { access_token, refresh_token } = response.data.data;
            storage.setToken(access_token);
            storage.setRefreshToken(refresh_token);
            
            // 获取用户信息
            await get().fetchUser();
            
            set({ isAuthenticated: true, isLoading: false });
            return true;
          }
          
          set({ 
            error: response.data.message || '登录失败', 
            isLoading: false 
          });
          return false;
        } catch (error: unknown) {
          const err = error as { response?: { data?: { message?: string } } };
          set({ 
            error: err.response?.data?.message || '登录失败，请检查网络连接', 
            isLoading: false 
          });
          return false;
        }
      },

      // 注册
      register: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.register(data);
          
          if (response.data.success) {
            set({ isLoading: false });
            return true;
          }
          
          set({ 
            error: response.data.message || '注册失败', 
            isLoading: false 
          });
          return false;
        } catch (error: unknown) {
          const err = error as { response?: { data?: { message?: string } } };
          set({ 
            error: err.response?.data?.message || '注册失败，请检查网络连接', 
            isLoading: false 
          });
          return false;
        }
      },

      // 登出
      logout: async () => {
        try {
          await authApi.logout();
        } catch {
          // 忽略登出接口错误
        }
        storage.clear();
        set({ 
          user: null, 
          isAuthenticated: false, 
          error: null 
        });
      },

      // 获取当前用户信息
      fetchUser: async () => {
        try {
          const response = await authApi.getMe();
          if (response.data.success) {
            set({ user: response.data.data as User });
          }
        } catch (error) {
          console.error('获取用户信息失败:', error);
          set({ user: null, isAuthenticated: false });
          storage.clear();
        }
      },

      // 清除错误
      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ 
        user: state.user, 
        isAuthenticated: state.isAuthenticated 
      }),
    }
  )
);
