import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/utils/cn';
import { useAuthStore } from '@/stores/authStore';
import {
  LayoutDashboard,
  Users,
  Database,
  Brain,
  Microscope,
  BarChart3,
  Settings,
  MessageSquare,
  Layers,
  Scissors,
  GraduationCap,
  PlusCircle,
} from 'lucide-react';

interface NavItem {
  title: string;
  href: string;
  icon: React.ReactNode;
  roles?: ('admin' | 'user')[];
}

const navItems: NavItem[] = [
  {
    title: '仪表盘',
    href: '/dashboard',
    icon: <LayoutDashboard className="h-5 w-5" />,
  },
  {
    title: '数据集管理',
    href: '/datasets',
    icon: <Database className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: '数据增强',
    href: '/augmentation',
    icon: <PlusCircle className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: '数据生成',
    href: '/generation',
    icon: <Layers className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: '模型构建',
    href: '/models',
    icon: <Brain className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: '模型训练',
    href: '/training',
    icon: <Settings className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: '模型剪枝',
    href: '/pruning',
    icon: <Scissors className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: '知识蒸馏',
    href: '/distillation',
    icon: <GraduationCap className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: '缺陷检测',
    href: '/detection',
    icon: <Microscope className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: '检测记录',
    href: '/records',
    icon: <BarChart3 className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: 'AI诊断',
    href: '/ai-diagnosis',
    icon: <MessageSquare className="h-5 w-5" />,
    roles: ['admin', 'user'],
  },
  {
    title: '用户管理',
    href: '/admin/users',
    icon: <Users className="h-5 w-5" />,
    roles: ['admin'],
  },
];

export function Sidebar() {
  const location = useLocation();
  const { user } = useAuthStore();

  // 根据角色过滤菜单
  const filteredNavItems = navItems.filter(
    (item) => !item.roles || item.roles.includes(user?.role || 'user')
  );

  return (
    <div className="flex h-full flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-16 items-center border-b px-6">
        <Link to="/" className="flex items-center gap-2 font-semibold">
          <Microscope className="h-6 w-6 text-primary" />
          <span className="text-lg">缺陷检测平台</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4 overflow-y-auto">
        {filteredNavItems.map((item) => {
          const isActive = location.pathname === item.href ||
            location.pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              {item.icon}
              {item.title}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t p-4">
        <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
            {user?.username?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.username}</p>
            <p className="text-xs text-muted-foreground">
              {user?.role === 'admin' ? '管理员' : '普通用户'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
