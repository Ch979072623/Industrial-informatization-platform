# 数据生成模块 (Phase 3)

## 概述

数据生成模块是工业缺陷检测平台的第三阶段功能，提供合成数据生成和缺陷迁移功能。该模块支持多种生成器，包括基于 LAB 颜色空间匹配的缺陷迁移生成器和外部 API 生成器（如 Stable Diffusion）。

## 功能特性

### 1. 可扩展生成器框架
- **抽象基类设计**：所有生成器必须实现 `BaseGenerator` 接口
- **注册中心**：通过 `GeneratorRegistry` 管理所有可用生成器
- **动态配置**：基于 JSON Schema 自动生成配置界面

### 2. 内置生成器

#### 缺陷迁移生成器 (`defect_migration`)
基于论文方法的缺陷迁移实现：
- **颜色匹配模式**：
  - 轻度匹配：仅 LAB 空间统计匹配
  - 标准匹配（默认）：LAB + CLAHE 对比度增强
  - 强匹配：LAB + CLAHE + 自适应亮度 + 可见度增强
  - 自定义：手动配置各参数

- **放置策略**：
  - 完全随机
  - 指定区域随机
  - 网格式均匀
  - 热力图引导
  - 中心/边缘优先

- **融合参数**：
  - 高斯模糊核大小
  - 融合强度
  - 质量分数评估

#### Stable Diffusion API 生成器 (`stable_diffusion_api`)
支持多种 API 提供商：
- Replicate API
- Stability AI API
- Hugging Face Inference API
- AUTOMATIC1111 WebUI API
- 通用 API 接口

### 3. 任务管理
- **批量生成**：支持 1-10000 张图像生成
- **实时进度**：WebSocket 推送任务进度
- **任务控制**：暂停/恢复/取消
- **质量报告**：生成质量统计和可视化

### 4. 缓存管理
- **缺陷库缓存**：Redis 缓存提取的缺陷区域（TTL 24小时）
- **预览缓存**：避免重复生成预览
- **缓存管理界面**：刷新/删除缓存

### 5. 热力图生成工具
- 高斯分布热力图
- 边缘偏好热力图
- 中心偏好热力图

## 技术架构

### 后端
```
backend/
├── app/
│   ├── api/v1/generation.py      # API 路由
│   ├── models/generation.py       # 数据库模型
│   ├── schemas/generation.py      # Pydantic Schema
│   ├── services/generation_service.py  # 业务逻辑
│   ├── tasks/generation_task.py   # Celery 任务
│   └── ml/generation/             # 生成器实现
│       ├── base.py                # 抽象基类
│       ├── registry.py            # 注册中心
│       ├── defect_migration.py    # 缺陷迁移生成器
│       └── stable_diffusion_api.py # SD API 生成器
└── app/db/migrations/versions/0004_add_generation.py  # 数据库迁移
```

### 前端
```
frontend/src/
├── pages/admin/GenerationPage.tsx # 主页面
├── types/generation.ts            # TypeScript 类型
└── services/api.ts                # API 服务（已添加 generationApi）
```

## API 接口

### 生成器管理
- `GET /api/v1/generation/generators` - 获取生成器列表
- `POST /api/v1/generation/validate` - 验证配置

### 预览
- `POST /api/v1/generation/preview` - 生成预览（超时 2 秒）

### 任务管理
- `GET /api/v1/generation/jobs` - 获取任务列表
- `POST /api/v1/generation/execute` - 执行生成
- `GET /api/v1/generation/jobs/{id}` - 获取任务详情
- `POST /api/v1/generation/jobs/{id}/control` - 控制任务
- `GET /api/v1/generation/jobs/{id}/progress` - 获取进度
- `GET /api/v1/generation/jobs/{id}/quality-report` - 获取质量报告

### 模板管理
- `GET /api/v1/generation/templates` - 获取模板列表
- `POST /api/v1/generation/templates` - 创建模板
- `PUT /api/v1/generation/templates/{id}` - 更新模板
- `DELETE /api/v1/generation/templates/{id}` - 删除模板

### 缓存管理
- `GET /api/v1/generation/cache` - 获取缓存列表
- `POST /api/v1/generation/cache/refresh` - 刷新缓存
- `DELETE /api/v1/generation/cache/{key}` - 删除缓存

### 热力图工具
- `POST /api/v1/generation/heatmap/generate` - 生成热力图

## 使用方法

### 1. 数据库迁移
```bash
cd backend
alembic upgrade head
```

### 2. 启动 Celery Worker
```bash
cd backend
celery -A celery_worker worker --loglevel=info
```

### 3. 访问数据生成页面
登录后访问：`/admin/generation`

## 配置示例

### 缺陷迁移配置
```json
{
  "source_type": "dataset",
  "source_dataset_id": "uuid",
  "base_dataset_id": "uuid",
  "color_match_mode": "standard",
  "placement_strategy": {
    "type": "random",
    "defects_per_image": { "min": 1, "max": 3 }
  },
  "fusion_params": {
    "blur_kernel": 5,
    "fusion_strength": 0.7
  }
}
```

### Stable Diffusion API 配置
```json
{
  "api_endpoint": "https://api.replicate.com/v1/predictions",
  "api_key": "your-api-key",
  "prompt": "a scratch on white metal surface, industrial defect",
  "negative_prompt": "blurry, low quality, text",
  "num_inference_steps": 50,
  "guidance_scale": 7.5,
  "image_size": { "width": 512, "height": 512 }
}
```

## 注意事项

1. **外部 API 限制**：
   - 请求超时 30 秒
   - 失败自动重试 3 次（指数退避）
   - API 密钥请安全存储

2. **性能优化**：
   - 预览接口限制 2 秒超时
   - 批量处理每批 100 张图像
   - 缺陷库缓存 24 小时

3. **磁盘空间**：
   - 生成前自动检查磁盘空间
   - 预留 50% 余量
   - 失败自动清理临时文件

## 扩展开发

### 添加自定义生成器

1. 继承 `BaseGenerator` 基类：
```python
from app.ml.generation import BaseGenerator, GenerationResult, register_generator

@register_generator
class MyCustomGenerator(BaseGenerator):
    def get_name(self) -> str:
        return "my_custom_generator"
    
    def get_description(self) -> str:
        return "我的自定义生成器"
    
    def get_config_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string"}
            }
        }
    
    def generate_single(self, **kwargs) -> GenerationResult:
        # 实现生成逻辑
        pass
```

2. 重启服务后自动生成器将自动注册

## 测试

运行测试：
```bash
cd backend
python -m pytest tests/test_generation.py -v
```

## 待完善功能

1. 缺陷库提取的具体实现
2. GAN API 生成器实现
3. 类别映射 UI
4. 更多放置策略（网格、热力图）
5. 合并到现有数据集功能
6. 可视化质量报告
