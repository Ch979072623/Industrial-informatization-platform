# 数据增强模块 (Phase 2) 实现文档

## 概述

数据增强模块是工业缺陷检测平台的管理员专属功能，提供可视化的增强策略配置、预览和批量执行能力。

## 实现内容

### 1. 后端实现

#### 数据库模型 (`backend/app/models/augmentation.py`)
- **AugmentationTemplate**: 增强模板表，存储用户保存的增强配置
- **AugmentationJob**: 增强任务表，记录任务执行状态和结果
- **CustomAugmentationScript**: 自定义脚本表，管理用户上传的 Python 脚本
- **AugmentationPreview**: 预览缓存表，存储预览结果避免重复计算

#### Pydantic Schema (`backend/app/schemas/augmentation.py`)
- 定义了所有操作的参数 Schema（几何变换、颜色变换、噪声模糊、高级增强）
- 模板、任务、预览、自定义脚本的完整 CRUD Schema
- 详细的参数验证（范围、类型、边界检查）

#### 核心服务 (`backend/app/services/augmentation_service.py`)
- **AugmentationService**: 主服务类
  - 基于 albumentations 的增强实现
  - 降级方案（使用 OpenCV 实现基础功能）
  - 自定义脚本执行器（沙箱环境，5秒超时）
  - 边界框转换和裁剪处理
  - 配置哈希计算（用于缓存）

#### Celery 任务 (`backend/app/tasks/augmentation_task.py`)
- **augment_dataset_task**: 主增强任务
  - 支持暂停/恢复/取消控制
  - 批量处理大数据集
  - 详细的进度报告和日志
  - 自动创建 YOLO 格式数据集
- **control_augmentation_job**: 任务控制
- **cleanup_augmentation_cache**: 缓存清理

#### API 路由 (`backend/app/api/v1/augmentation.py`)
- 可用操作列表获取
- 模板管理（CRUD）
- 任务管理（创建、查询、控制）
- 预览生成和缓存
- 自定义脚本上传和管理
- 配置验证

#### 数据库迁移 (`backend/app/db/migrations/versions/0003_add_augmentation.py`)
- 完整的表结构定义
- 索引优化

### 2. 前端实现

#### 类型定义 (`frontend/src/types/augmentation.ts`)
- 完整的 TypeScript 类型定义
- 操作定义、流水线配置、任务状态等
- 组件 Props 类型
- 常量映射（分类名称、状态颜色等）

#### API 服务 (`frontend/src/services/api.ts`)
- `augmentationApi`: 完整的 API 调用封装

#### 状态管理 (`frontend/src/stores/augmentationStore.ts`)
- Zustand + Immer 实现
- 流水线编辑状态
- 任务和模板管理
- 预览状态管理

#### 组件实现

##### OperationList (`frontend/src/components/augmentation/OperationList.tsx`)
- 左侧操作列表侧边栏
- 分类折叠展示
- 搜索过滤功能
- 拖拽支持

##### PipelineEditor (`frontend/src/components/augmentation/PipelineEditor.tsx`)
- 流水线编排区域
- 拖拽排序
- 参数配置面板（Slider + InputNumber 组合）
- 实时参数验证
- 操作启用/禁用切换
- 批量删除和清空

##### PreviewPanel (`frontend/src/components/augmentation/PreviewPanel.tsx`)
- 原图和增强图对比
- 图像选择器
- 自动预览（500ms 防抖）
- 应用操作列表显示

##### ExecutionPanel (`frontend/src/components/augmentation/ExecutionPanel.tsx`)
- 任务配置（数据集名称、增强倍数）
- 实时进度显示
- 暂停/恢复/取消控制
- 预计剩余时间计算

##### AugmentationPage (`frontend/src/pages/admin/AugmentationPage.tsx`)
- 三栏布局整合
- 模板保存和加载
- 数据集选择和验证

### 3. UI 组件补充
- Slider: 滑动选择器
- ScrollArea: 滚动区域
- Switch: 开关组件

### 4. 测试用例 (`backend/tests/test_augmentation.py`)
- 配置验证测试
- 边界框转换测试
- 增强服务测试
- 并发测试
- 错误处理测试
- Schema 验证测试
- 集成测试

## 功能特性

### 支持的增强操作

#### 几何变换类
- 水平/垂直翻转
- 随机旋转（-180° ~ +180°）
- 随机裁剪（0.5-1.0 比例）
- 缩放（0.5-2.0 范围）
- 仿射变换（角度、平移、缩放、剪切）

#### 颜色变换类
- 亮度调整（-100 ~ +100）
- 对比度调整（0.5 ~ 2.0）
- 饱和度调整（0.5 ~ 2.0）
- 色调抖动（-30 ~ +30）
- 直方图均衡化
- CLAHE（clipLimit: 1-10, tileGridSize: 4-16）

#### 噪声与模糊类
- 高斯噪声（标准差：0-50）
- 椒盐噪声（噪声比例：0-0.1）
- 高斯模糊（核大小：3-15，奇数）
- 运动模糊（核大小：3-15，角度：0-360°）

#### 高级增强类
- CutOut（擦除区域比例：0.1-0.5）

#### 自定义操作
- Python 脚本上传（.py 文件，< 10MB）
- 沙箱执行环境（5秒超时）
- 标准接口：`def augment(image: np.ndarray, bboxes: List) -> Tuple[np.ndarray, List]`

### 安全特性
- 文件类型和大小限制
- 自定义脚本语法验证
- 沙箱执行环境
- 操作超时保护
- 参数范围自动修正

### 性能优化
- 预览结果缓存（24小时）
- 大数据集分批处理
- 预览图像自动缩放
- Celery 异步任务执行
- 进度实时推送

## 使用说明

### 访问路径
```
/admin/augmentation?dataset=<dataset_id>
```

### 基本流程
1. 从数据集列表点击"数据增强"
2. 从左侧拖拽操作到中间流水线
3. 配置每个操作的参数
4. 查看右侧预览效果
5. 配置增强倍数和新数据集名称
6. 点击"开始增强"执行任务

### 模板使用
1. 配置好流水线后点击"保存模板"
2. 输入模板名称和描述
3. 之后可以从顶部下拉框快速加载

## 开发规范遵守

### 代码质量
- ✅ 所有 API 调用有 try-catch 和错误提示
- ✅ 前后端双重验证
- ✅ 边界情况处理（空数组、null、超大图片等）
- ✅ TypeScript 严格模式
- ✅ 防御性编程
- ✅ 敏感操作日志记录

### 性能与安全
- ✅ 预览接口响应 < 2秒（带超时保护）
- ✅ 批量增强支持暂停/取消/恢复
- ✅ 文件上传限制：单文件 < 10MB，仅 .py 扩展名
- ✅ 自定义脚本沙箱执行
- ✅ 大数据集分批处理

### 类型安全
- ✅ 后端所有函数有类型注解和 docstring
- ✅ 前端组件有 Props 类型定义
- ✅ API 接口有完整的 Pydantic schema 校验

## 安装依赖

### 后端
依赖已在 `requirements.txt` 中：
```
albumentations==1.3.1
opencv-python==4.10.0.84
numpy==1.26.3
Pillow==10.2.0
```

### 前端
```bash
cd frontend
npm install @radix-ui/react-slider @radix-ui/react-scroll-area @radix-ui/react-switch immer
```

## 数据库迁移

```bash
cd backend
alembic upgrade head
```

## 待完善功能

1. Mosaic（4图拼接）完整实现
2. MixUp 和 CutMix 高级增强
3. 批量任务调度优化
4. 增强结果质量评估
5. 更多预设模板
