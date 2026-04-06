import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/stores/authStore';
import { 
  Database, 
  Brain, 
  Microscope, 
  AlertCircle,
  TrendingUp,
  Activity
} from 'lucide-react';

export function DashboardPage() {
  const { user } = useAuthStore();

  // 模拟统计数据
  const stats = [
    {
      title: '数据集',
      value: '12',
      description: '共 5,280 张图像',
      icon: <Database className="h-4 w-4 text-muted-foreground" />,
      trend: '+2 本周',
    },
    {
      title: '训练模型',
      value: '8',
      description: '3 个正在训练',
      icon: <Brain className="h-4 w-4 text-muted-foreground" />,
      trend: '+1 本周',
    },
    {
      title: '检测记录',
      value: '1,245',
      description: '今日 89 条',
      icon: <Microscope className="h-4 w-4 text-muted-foreground" />,
      trend: '+12%',
    },
    {
      title: '缺陷检出',
      value: '98.5%',
      description: '平均准确率',
      icon: <Activity className="h-4 w-4 text-muted-foreground" />,
      trend: '+0.5%',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div>
        <h2 className="text-3xl font-bold tracking-tight">
          欢迎回来，{user?.username}！
        </h2>
        <p className="text-muted-foreground">
          这里是您的缺陷检测平台仪表盘，快速查看系统概况。
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, index) => (
          <Card key={index}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {stat.title}
              </CardTitle>
              {stat.icon}
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">
                {stat.description}
              </p>
              <div className="mt-2 flex items-center text-xs text-green-600">
                <TrendingUp className="mr-1 h-3 w-3" />
                {stat.trend}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        {/* Recent Activities */}
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>最近活动</CardTitle>
            <CardDescription>您最近的操作记录</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[
                { action: '上传数据集', detail: 'dataset_v1.zip', time: '2 小时前' },
                { action: '开始训练', detail: 'model_config_01', time: '5 小时前' },
                { action: '模型测试', detail: 'trained_model_v3', time: '1 天前' },
                { action: '缺陷检测', detail: 'batch_20240301', time: '2 天前' },
              ].map((activity, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between border-b pb-2 last:border-0"
                >
                  <div>
                    <p className="font-medium">{activity.action}</p>
                    <p className="text-sm text-muted-foreground">
                      {activity.detail}
                    </p>
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {activity.time}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>快速操作</CardTitle>
            <CardDescription>常用功能快捷入口</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {[
                { title: '上传数据', icon: Database, href: '/datasets' },
                { title: '新建模型', icon: Brain, href: '/models' },
                { title: '开始检测', icon: Microscope, href: '/detection' },
                { title: '查看记录', icon: Activity, href: '/records' },
              ].map((action, index) => (
                <a
                  key={index}
                  href={action.href}
                  className="flex flex-col items-center justify-center rounded-lg border p-4 hover:bg-accent transition-colors"
                >
                  <action.icon className="h-8 w-8 mb-2 text-primary" />
                  <span className="text-sm font-medium">{action.title}</span>
                </a>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Alert Section */}
      <Card className="border-yellow-200 bg-yellow-50">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5" />
            <div>
              <h4 className="font-medium text-yellow-900">系统通知</h4>
              <p className="text-sm text-yellow-700 mt-1">
                检测到 3 个正在进行的训练任务，预计将在 2 小时内完成。请留意系统资源使用情况。
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default DashboardPage;
