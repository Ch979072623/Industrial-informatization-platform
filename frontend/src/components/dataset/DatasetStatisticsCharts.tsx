/**
 * 数据集统计图表组件
 * 
 * 展示数据集的各类统计图表：
 * - 类别分布柱状图
 * - 图像尺寸散点图
 * - 数据集划分饼图
 * - 标注框大小分布
 * 
 * @example
 * ```tsx
 * <DatasetStatisticsCharts 
 *   datasetId="dataset-uuid"
 *   className="my-4"
 * />
 * ```
 */
import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { datasetApi } from '@/services/api';
import type { DatasetChartData } from '@/types/datasetStatistics';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  Cell,
  PieChart,
  Pie,
  Legend
} from 'recharts';
import { 
  RefreshCw, 
  AlertCircle, 
  Loader2,
  BarChart3,
  PieChart as PieChartIcon,
  ScatterChart as ScatterChartIcon,
  Box
} from 'lucide-react';
import { cn } from '@/utils/cn';

/** 组件Props类型定义 */
export interface DatasetStatisticsChartsProps {
  /** 数据集ID */
  datasetId: string;
  /** 自定义类名 */
  className?: string;
  /** 是否默认显示刷新按钮 */
  showRefreshButton?: boolean;
  /** 刷新成功后的回调 */
  onRefresh?: () => void;
}

/** 统计摘要卡片组件 */
interface StatSummaryCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon: React.ReactNode;
}

const StatSummaryCard = ({ title, value, description, icon }: StatSummaryCardProps) => (
  <Card>
    <CardContent className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {description && (
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
          )}
        </div>
        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
          {icon}
        </div>
      </div>
    </CardContent>
  </Card>
);

/** 类别分布图表 */
interface ClassDistributionChartProps {
  data: DatasetChartData['class_distribution'];
}

const ClassDistributionChart = ({ data }: ClassDistributionChartProps) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-[300px] flex items-center justify-center text-muted-foreground">
        <div className="text-center">
          <BarChart3 className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>暂无类别分布数据</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="class_name" 
            angle={-45}
            textAnchor="end"
            height={80}
            interval={0}
            tick={{ fontSize: 12 }}
          />
          <YAxis />
          <Tooltip 
            formatter={(value: number, name: string, props: any) => [
              `${value} (${props.payload.percentage}%)`,
              '标注数量'
            ]}
          />
          <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={`hsl(${210 + index * 20}, 70%, 60%)`} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

/** 图像尺寸分布图表 */
interface ImageSizeDistributionChartProps {
  data: DatasetChartData['image_sizes'];
}

const ImageSizeDistributionChart = ({ data }: ImageSizeDistributionChartProps) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-[250px] flex items-center justify-center text-muted-foreground">
        <div className="text-center">
          <ScatterChartIcon className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>暂无图像尺寸数据</p>
        </div>
      </div>
    );
  }

  // 计算 domain，确保只有一个点时也能正常显示
  const widths = data.map(d => d.width);
  const heights = data.map(d => d.height);
  const minWidth = Math.min(...widths);
  const maxWidth = Math.max(...widths);
  const minHeight = Math.min(...heights);
  const maxHeight = Math.max(...heights);
  
  // 如果只有一个尺寸，添加一些 padding
  const isUniformSize = minWidth === maxWidth && minHeight === maxHeight;
  const xDomain = isUniformSize 
    ? [minWidth * 0.8, maxWidth * 1.2] 
    : [minWidth, maxWidth];
  const yDomain = isUniformSize 
    ? [minHeight * 0.8, maxHeight * 1.2] 
    : [minHeight, maxHeight];

  return (
    <div className="h-[250px]">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            type="number" 
            dataKey="width" 
            name="宽度" 
            unit="px"
            domain={xDomain}
            tickFormatter={(value) => Math.round(value).toString()}
          />
          <YAxis 
            type="number" 
            dataKey="height" 
            name="高度" 
            unit="px"
            domain={yDomain}
            tickFormatter={(value) => Math.round(value).toString()}
          />
          <Tooltip 
            cursor={{ strokeDasharray: '3 3' }}
            formatter={(value: number, name: string) => [
              `${value}px`,
              name
            ]}
            labelFormatter={(label: any, payload: any) => {
              if (payload && payload[0]) {
                return `尺寸: ${payload[0].payload.width}x${payload[0].payload.height}`;
              }
              return '';
            }}
          />
          <Scatter 
            name="图片" 
            data={data} 
            fill="#8884d8"
          >
            {data.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={`hsl(${260 + index * 10}, 60%, ${50 + (entry.count || 1) * 5}%)`}
              />
            ))}
          </Scatter>
          {isUniformSize && (
            <text
              x="50%"
              y="50%"
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#6b7280"
              fontSize={12}
            >
              所有图像尺寸相同: {minWidth}x{minHeight}
            </text>
          )}
        </ScatterChart>
      </ResponsiveContainer>
      {isUniformSize && (
        <p className="text-center text-sm text-muted-foreground mt-2">
          所有 {data[0]?.count || 0} 张图像都是 {minWidth}x{minHeight} 像素
        </p>
      )}
    </div>
  );
};

/** 数据集划分饼图 */
interface SplitDistributionChartProps {
  data: DatasetChartData['split_distribution'];
}

const SplitDistributionChart = ({ data }: SplitDistributionChartProps) => {
  console.log('SplitDistributionChart data:', data);
  if (!data || data.length === 0 || data.every(d => d.value === 0)) {
    return (
      <div className="h-[250px] flex items-center justify-center text-muted-foreground">
        <div className="text-center">
          <PieChartIcon className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>暂无划分数据</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[250px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={80}
            paddingAngle={5}
            dataKey="value"
            nameKey="name"
            label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
            labelLine={false}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip 
            formatter={(value: number, name: string) => [`${value} 张`, name]}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

/** 标注框分布展示 */
interface BBoxDistributionDisplayProps {
  data: DatasetChartData['bbox_distribution'];
}

const BBoxDistributionDisplay = ({ data }: BBoxDistributionDisplayProps) => {
  if (!data) {
    return (
      <div className="h-[200px] flex items-center justify-center text-muted-foreground">
        <div className="text-center">
          <Box className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>暂无标注框数据</p>
        </div>
      </div>
    );
  }

  const total = data.small + data.medium + data.large;
  
  return (
    <div className="space-y-6">
      {/* 平均尺寸 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="text-center p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground">平均宽度</p>
          <p className="text-xl font-semibold">{data.avg_width.toFixed(1)}px</p>
        </div>
        <div className="text-center p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground">平均高度</p>
          <p className="text-xl font-semibold">{data.avg_height.toFixed(1)}px</p>
        </div>
        <div className="text-center p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground">平均宽高比</p>
          <p className="text-xl font-semibold">{data.avg_aspect_ratio.toFixed(2)}</p>
        </div>
      </div>

      {/* 目标大小分布 */}
      <div>
        <h4 className="text-sm font-medium mb-3">目标大小分布</h4>
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-sm w-20">小目标</span>
            <span className="text-xs text-muted-foreground w-24">(&lt; 32×32)</span>
            <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-red-400 rounded-full"
                style={{ width: `${total > 0 ? (data.small / total * 100) : 0}%` }}
              />
            </div>
            <span className="text-sm w-16 text-right">{data.small}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm w-20">中目标</span>
            <span className="text-xs text-muted-foreground w-24">(32×32 ~ 96×96)</span>
            <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-yellow-400 rounded-full"
                style={{ width: `${total > 0 ? (data.medium / total * 100) : 0}%` }}
              />
            </div>
            <span className="text-sm w-16 text-right">{data.medium}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm w-20">大目标</span>
            <span className="text-xs text-muted-foreground w-24">(&gt; 96×96)</span>
            <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-green-400 rounded-full"
                style={{ width: `${total > 0 ? (data.large / total * 100) : 0}%` }}
              />
            </div>
            <span className="text-sm w-16 text-right">{data.large}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

/** 主组件 */
export function DatasetStatisticsCharts({
  datasetId,
  className,
  showRefreshButton = true,
  onRefresh,
}: DatasetStatisticsChartsProps) {
  const [chartData, setChartData] = useState<DatasetChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchChartData = useCallback(async (forceRefresh = false) => {
    try {
      if (forceRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const response = await datasetApi.getDatasetChartData(datasetId);
      
      if (response.data.success) {
        const data = response.data.data;
        console.log('Chart data received:', data);
        console.log('Summary:', data.summary);
        setChartData(data);
      } else {
        setError(response.data.message || '获取图表数据失败');
      }
    } catch (err: any) {
      console.error('获取图表数据失败:', err);
      setError(err.response?.data?.message || '获取图表数据失败，请稍后重试');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [datasetId]);

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      await datasetApi.refreshDatasetStatistics(datasetId);
      // 刷新成功后重新获取图表数据
      await fetchChartData(true);
      // 通知父组件刷新数据集基本信息（类别名称等）
      if (onRefresh) {
        onRefresh();
      }
    } catch (err: any) {
      console.error('刷新统计数据失败:', err);
      setError(err.response?.data?.message || '刷新统计数据失败');
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchChartData();
  }, [fetchChartData]);

  if (loading) {
    return (
      <div className={cn("flex items-center justify-center py-20", className)}>
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2 text-muted-foreground">加载统计图表...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className={className}>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription className="flex items-center justify-between">
          <span>{error}</span>
          {showRefreshButton && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => fetchChartData()}
              disabled={refreshing}
            >
              {refreshing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              重试
            </Button>
          )}
        </AlertDescription>
      </Alert>
    );
  }

  if (!chartData) {
    return (
      <Alert className={className}>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>暂无统计数据</AlertDescription>
      </Alert>
    );
  }

  const { summary, class_distribution, image_sizes, split_distribution, bbox_distribution } = chartData;
  
  console.log('Rendering with summary:', summary);

  return (
    <div className={cn("space-y-6", className)}>
      {/* 操作按钮 */}
      {showRefreshButton && (
        <div className="flex justify-end">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            刷新统计
          </Button>
        </div>
      )}

      {/* 统计摘要 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatSummaryCard
          title="图像总数"
          value={summary.total_images}
          description={`${summary.images_with_annotations}张有标注`}
          icon={<BarChart3 className="h-5 w-5 text-primary" />}
        />
        <StatSummaryCard
          title="标注总数"
          value={summary.total_annotations}
          description={`平均每图${summary.avg_annotations_per_image}个`}
          icon={<Box className="h-5 w-5 text-primary" />}
        />
        <StatSummaryCard
          title="类别数量"
          value={summary.class_count}
          icon={<PieChartIcon className="h-5 w-5 text-primary" />}
        />
        <StatSummaryCard
          title="无标注图像"
          value={summary.images_without_annotations}
          description={`占比${((summary.images_without_annotations / summary.total_images) * 100).toFixed(1)}%`}
          icon={<ScatterChartIcon className="h-5 w-5 text-primary" />}
        />
      </div>

      {/* 类别分布 */}
      <Card>
        <CardHeader>
          <CardTitle>类别分布</CardTitle>
          <CardDescription>各类别的标注实例数量</CardDescription>
        </CardHeader>
        <CardContent>
          <ClassDistributionChart data={class_distribution} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 图像尺寸分布 */}
        <Card>
          <CardHeader>
            <CardTitle>图像尺寸分布</CardTitle>
            <CardDescription>图片宽度和高度的散点分布</CardDescription>
          </CardHeader>
          <CardContent>
            <ImageSizeDistributionChart data={image_sizes} />
          </CardContent>
        </Card>

        {/* 数据集划分饼图 */}
        <Card>
          <CardHeader>
            <CardTitle>数据划分比例</CardTitle>
            <CardDescription>训练/验证/测试集分布</CardDescription>
          </CardHeader>
          <CardContent>
            <SplitDistributionChart data={split_distribution} />
          </CardContent>
        </Card>
      </div>

      {/* 标注框分布 */}
      <Card>
        <CardHeader>
          <CardTitle>标注框分布</CardTitle>
          <CardDescription>标注框尺寸和目标大小分类统计</CardDescription>
        </CardHeader>
        <CardContent>
          <BBoxDistributionDisplay data={bbox_distribution} />
        </CardContent>
      </Card>
    </div>
  );
}

export default DatasetStatisticsCharts;
