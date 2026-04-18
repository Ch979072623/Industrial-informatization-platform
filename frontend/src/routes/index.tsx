import { Navigate, RouteObject, useRoutes } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

// 页面组件（懒加载）
import { lazy, Suspense } from 'react';

const LoginPage = lazy(() => import('@/pages/LoginPage'));
const RegisterPage = lazy(() => import('@/pages/RegisterPage'));
const MainLayout = lazy(() => import('@/components/layout/MainLayout'));
const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));

// 管理员页面
const UserManagementPage = lazy(() => import('@/pages/admin/UserManagementPage'));
const DatasetListPage = lazy(() => import('@/pages/admin/DatasetListPage'));
const DatasetUploadPage = lazy(() => import('@/pages/admin/DatasetUploadPage'));
const DatasetDetailPage = lazy(() => import('@/pages/admin/DatasetDetailPage'));
const AugmentationPage = lazy(() => import('@/pages/admin/AugmentationPage'));
const GenerationPage = lazy(() => import('@/pages/admin/GenerationPage'));
const GenerationTaskListPage = lazy(() => import('@/pages/admin/GenerationTaskListPage'));
const ModelBuilderPage = lazy(() => import('@/pages/admin/ModelBuilder'));

// 加载中组件
const PageLoading = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
  </div>
);

// 路由守卫组件
interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

const ProtectedRoute = ({ children, requireAdmin = false }: ProtectedRouteProps) => {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requireAdmin && user?.role !== 'admin') {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

// 公开路由 - 已登录用户自动跳转到首页
const PublicRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated } = useAuthStore();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

// 路由配置
const routes: RouteObject[] = [
  // 公开路由
  {
    path: '/login',
    element: (
      <PublicRoute>
        <Suspense fallback={<PageLoading />}>
          <LoginPage />
        </Suspense>
      </PublicRoute>
    ),
  },
  {
    path: '/register',
    element: (
      <PublicRoute>
        <Suspense fallback={<PageLoading />}>
          <RegisterPage />
        </Suspense>
      </PublicRoute>
    ),
  },

  // 受保护路由
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <Suspense fallback={<PageLoading />}>
          <MainLayout />
        </Suspense>
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: 'dashboard',
        element: (
          <Suspense fallback={<PageLoading />}>
            <DashboardPage />
          </Suspense>
        ),
      },
      // 管理员路由
      {
        path: 'admin',
        children: [
          {
            path: 'users',
            element: (
              <ProtectedRoute requireAdmin>
                <Suspense fallback={<PageLoading />}>
                  <UserManagementPage />
                </Suspense>
              </ProtectedRoute>
            ),
          },
          {
            path: 'datasets',
            element: (
              <ProtectedRoute requireAdmin>
                <Suspense fallback={<PageLoading />}>
                  <DatasetListPage />
                </Suspense>
              </ProtectedRoute>
            ),
          },
          {
            path: 'datasets/upload',
            element: (
              <ProtectedRoute requireAdmin>
                <Suspense fallback={<PageLoading />}>
                  <DatasetUploadPage />
                </Suspense>
              </ProtectedRoute>
            ),
          },
          {
            path: 'datasets/:id',
            element: (
              <ProtectedRoute requireAdmin>
                <Suspense fallback={<PageLoading />}>
                  <DatasetDetailPage />
                </Suspense>
              </ProtectedRoute>
            ),
          },
          {
            path: 'augmentation',
            element: (
              <ProtectedRoute requireAdmin>
                <Suspense fallback={<PageLoading />}>
                  <AugmentationPage />
                </Suspense>
              </ProtectedRoute>
            ),
          },
          {
            path: 'generation',
            element: (
              <ProtectedRoute requireAdmin>
                <Suspense fallback={<PageLoading />}>
                  <GenerationPage />
                </Suspense>
              </ProtectedRoute>
            ),
          },
          {
            path: 'generation/tasks',
            element: (
              <ProtectedRoute requireAdmin>
                <Suspense fallback={<PageLoading />}>
                  <GenerationTaskListPage />
                </Suspense>
              </ProtectedRoute>
            ),
          },
          {
            path: 'model-builder',
            element: (
              <ProtectedRoute requireAdmin>
                <Suspense fallback={<PageLoading />}>
                  <ModelBuilderPage />
                </Suspense>
              </ProtectedRoute>
            ),
          },
        ],
      },
    ],
  },

  // 404 页面
  {
    path: '*',
    element: (
      <Suspense fallback={<PageLoading />}>
        <NotFoundPage />
      </Suspense>
    ),
  },
];

export const AppRoutes = () => {
  return useRoutes(routes);
};

export default AppRoutes;
