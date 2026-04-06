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
