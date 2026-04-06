# 数据集统计图表功能文档

## 功能概述

数据集统计图表功能实现了自动扫描数据集的labels文件进行统计分析，并将结果保存在数据库中方便调用。如果已有数据集的分析数据为空，则会自动触发更新。

## 主要特性

- **自动扫描分析**: 自动识别YOLO、COCO、VOC格式的labels文件
- **数据缓存**: 统计结果保存在数据库，避免重复计算
- **自动更新**: 检测到labels文件变化或数据过期时自动重新分析
- **图表展示**: 提供丰富的图表展示（柱状图、散点图、饼图等）
- **哈希校验**: 使用MD5哈希检测labels文件是否发生变化

## 后端实现

### 1. 数据库模型

**文件**: `backend/app/models/dataset_statistics.py`

```python
class DatasetStatistics(BaseModel):
    # 主要字段:
    - dataset_id: 关联的数据集ID
    - total_images: 图像总数
    - total_annotations: 标注框总数
    - class_distribution: 类别分布统计
    - image_sizes: 图像尺寸分布
    - split_distribution: 数据集划分分布
    - bbox_distribution: 标注框大小分布
    - labels_hash: labels文件哈希（用于检测变化）
    - scan_status: 扫描状态
    - last_scan_time: 上次扫描时间
```

### 2. 统计服务

**文件**: `backend/app/services/dataset_statistics_service.py`

```python
class DatasetStatisticsService:
    # 主要方法:
    - get_or_create_statistics(): 获取或创建统计信息
    - analyze_and_save(): 分析数据集并保存结果
    - get_chart_data(): 获取图表展示数据
    - is_stale(): 检查数据是否过期
```

### 3. API 端点

**文件**: `backend/app/api/v1/datasets.py`

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/datasets/{id}/statistics` | GET | 获取数据集统计信息 |
| `/api/v1/datasets/{id}/statistics/refresh` | POST | 刷新统计信息（强制重新分析） |
| `/api/v1/datasets/{id}/chart-data` | GET | 获取图表展示数据 |
| `/api/v1/datasets/{id}/statistics` | DELETE | 删除统计信息 |

### 4. Schema 定义

**文件**: `backend/app/schemas/dataset_statistics.py`

- `ClassDistributionItem`: 类别分布项
- `ImageSizeDistributionItem`: 图像尺寸分布项
- `BBoxDistributionItem`: 标注框分布
- `DatasetStatisticsResponse`: 统计响应
- `DatasetChartDataResponse`: 图表数据响应

## 前端实现

### 1. 类型定义

**文件**: `frontend/src/types/datasetStatistics.ts`

### 2. API 服务

**文件**: `frontend/src/services/api.ts`

```typescript
export const datasetApi = {
  getDatasetStatistics: (id: string, params?: RefreshStatisticsParams) =>
    api.get<ApiResponse<DatasetStatistics>>(`/datasets/${id}/statistics`, { params }),
  
  refreshDatasetStatistics: (id: string) =>
    api.post<ApiResponse<DatasetStatistics>>(`/datasets/${id}/statistics/refresh`),
  
  getDatasetChartData: (id: string) =>
    api.get<ApiResponse<DatasetChartData>>(`/datasets/${id}/chart-data`),
}
```

### 3. 图表组件

**文件**: `frontend/src/components/dataset/DatasetStatisticsCharts.tsx`

```typescript
export interface DatasetStatisticsChartsProps {
  datasetId: string;
  className?: string;
  showRefreshButton?: boolean;
}

// 包含以下图表:
// - 类别分布柱状图
// - 图像尺寸散点图
// - 数据集划分饼图
// - 标注框大小分布
```

## 使用方法

### 后端使用

```python
from app.services.dataset_statistics_service import DatasetStatisticsService

# 获取或创建统计信息（自动分析如果不存在）
service = DatasetStatisticsService(db)
stats = await service.get_or_create_statistics(dataset_id)

# 强制重新分析
stats = await service.analyze_and_save(dataset_id)

# 获取图表数据
chart_data = await service.get_chart_data(dataset_id)
```

### 前端使用

```tsx
import { DatasetStatisticsCharts } from '@/components/dataset';

// 在页面中使用
<DatasetStatisticsCharts 
  datasetId={datasetId}
  showRefreshButton={true}
/>
```

## 数据库迁移

执行以下SQL创建统计表：

```sql
-- 数据集统计表
CREATE TABLE datasetstatistics (
    id VARCHAR(36) PRIMARY KEY,
    dataset_id VARCHAR(36) NOT NULL UNIQUE,
    total_images INTEGER DEFAULT 0,
    total_annotations INTEGER DEFAULT 0,
    images_with_annotations INTEGER DEFAULT 0,
    images_without_annotations INTEGER DEFAULT 0,
    avg_annotations_per_image FLOAT DEFAULT 0,
    class_count INTEGER DEFAULT 0,
    class_distribution JSON DEFAULT '[]',
    annotations_per_class JSON DEFAULT '{}',
    image_sizes JSON DEFAULT '[]',
    avg_image_width FLOAT DEFAULT 0,
    avg_image_height FLOAT DEFAULT 0,
    avg_bbox_width FLOAT DEFAULT 0,
    avg_bbox_height FLOAT DEFAULT 0,
    avg_bbox_aspect_ratio FLOAT DEFAULT 0,
    small_bboxes INTEGER DEFAULT 0,
    medium_bboxes INTEGER DEFAULT 0,
    large_bboxes INTEGER DEFAULT 0,
    split_distribution JSON DEFAULT '{}',
    last_scan_time TIMESTAMP WITH TIME ZONE,
    scan_status VARCHAR(20) DEFAULT 'pending',
    scan_error TEXT,
    labels_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (dataset_id) REFERENCES dataset(id) ON DELETE CASCADE
);

CREATE INDEX idx_datasetstatistics_dataset_id ON datasetstatistics(dataset_id);
```

使用 Alembic 迁移：

```bash
cd backend
alembic revision --autogenerate -m "add dataset statistics table"
alembic upgrade head
```

## 配置说明

### 过期时间配置

在 `DatasetStatistics.is_stale()` 方法中可以配置数据过期时间（默认24小时）：

```python
def is_stale(self, max_age_hours: int = 24) -> bool:
    # 检查统计数据是否过期
```

### 目标大小阈值

在 `DatasetStatisticsService` 中可以配置目标大小分类阈值：

```python
class DatasetStatisticsService:
    SMALL_BBOX_THRESHOLD = 32 * 32   # 小目标: < 32x32
    MEDIUM_BBOX_THRESHOLD = 96 * 96  # 中目标: 32x32 ~ 96x96
```

## 性能优化

1. **数据库查询优化**: 使用 `joinedload` 预加载避免N+1问题
2. **哈希缓存**: 使用MD5哈希快速检测labels文件变化
3. **异步分析**: 分析过程异步执行，不阻塞API响应
4. **增量更新**: 仅在必要时重新分析（数据过期或文件变化）

## 错误处理

- **文件不存在**: 记录警告日志，返回空统计
- **解析错误**: 保存错误状态，返回友好的错误信息
- **数据库错误**: 回滚事务，返回500错误

## 日志记录

关键操作都有日志记录：
- 数据集分析开始/完成
- 哈希计算结果
- 统计更新事件
- 错误信息

## 安全考虑

1. **权限检查**: 只有数据集所有者或管理员可以查看统计
2. **管理员操作**: 刷新统计和删除统计需要管理员权限
3. **数据验证**: 使用Pydantic进行完整的输入验证
