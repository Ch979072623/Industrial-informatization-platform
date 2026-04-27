# 编码规范

## Pydantic 类命名

业务模块的 Pydantic Request/Response/Query 类必须使用 `<Module><Name>` 前缀。

### 示例

| 模块 | 类名示例 |
|---|---|
| augmentation | `AugmentationJobCreate`, `AugmentationTemplateResponse` |
| generation | `GenerationJobCreate`, `GenerationJobProgressResponse` |
| training | `TrainingJobCreate`, `TrainingJobResponse` |
| dataset | `DatasetUploadRequest`, `DatasetSplitRequest` |

### 例外

允许跨模块共用的通用类（`JobControlRequest` 等）在 `schemas/common.py` 或类似位置维护，
但新模块原则上不引入新的"通用"类，优先使用前缀化的模块特有类。

### 历史现状

augmentation / generation / dataset 模块的 Pydantic 类已符合规范。
training 模块在 Phase 5 引入时按规范命名。

## ORM 命名

ORM 类名使用驼峰单数（例：`TrainingJob`、`Dataset`），表名走默认（SQLAlchemy 自动小写化）。

## 测试命名

测试文件 `test_<module>.py`，函数 `test_<scenario>`。
