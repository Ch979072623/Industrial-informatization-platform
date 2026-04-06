/**
 * 数据集统计相关类型定义
 * 
 * 与后端 Pydantic Schema 对应
 */

/** 类别分布项 */
export interface ClassDistributionItem {
  class_name: string;
  count: number;
  percentage: number;
}

/** 图像尺寸分布项 */
export interface ImageSizeDistributionItem {
  width: number;
  height: number;
  count: number;
}

/** 标注框分布 */
export interface BBoxDistributionItem {
  avg_width: number;
  avg_height: number;
  avg_aspect_ratio: number;
  small_boxes: number;
  medium_boxes: number;
  large_boxes: number;
}

/** 数据集划分分布项 */
export interface SplitDistributionItem {
  name: string;
  value: number;
  fill: string;
}

/** 数据集统计响应 */
export interface DatasetStatistics {
  dataset_id: string;
  total_images: number;
  total_annotations: number;
  avg_annotations_per_image: number;
  images_with_annotations: number;
  images_without_annotations: number;
  class_count: number;
  class_distribution: ClassDistributionItem[];
  size_distribution: ImageSizeDistributionItem[];
  bbox_distribution: BBoxDistributionItem;
  split_distribution: Record<string, number>;
  scan_status: 'pending' | 'running' | 'completed' | 'failed';
  last_scan_time?: string;
}

/** 图表数据汇总 */
export interface DatasetChartSummary {
  total_images: number;
  total_annotations: number;
  avg_annotations_per_image: number;
  class_count: number;
  images_with_annotations: number;
  images_without_annotations: number;
}

/** 图表标注框分布 */
export interface DatasetChartBboxDistribution {
  avg_width: number;
  avg_height: number;
  avg_aspect_ratio: number;
  small: number;
  medium: number;
  large: number;
}

/** 数据集图表数据响应 */
export interface DatasetChartData {
  class_distribution: ClassDistributionItem[];
  image_sizes: ImageSizeDistributionItem[];
  split_distribution: SplitDistributionItem[];
  bbox_distribution: DatasetChartBboxDistribution;
  summary: DatasetChartSummary;
}

/** 统计刷新参数 */
export interface RefreshStatisticsParams {
  force_refresh?: boolean;
}
