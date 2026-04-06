import { AppRoutes } from '@/routes';
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';

function App() {
  const { fetchUser, isAuthenticated } = useAuthStore();

  // 应用启动时检查登录状态
  useEffect(() => {
    if (isAuthenticated) {
      fetchUser();
    }
  }, [isAuthenticated, fetchUser]);

  return <AppRoutes />;
}

export default App;
