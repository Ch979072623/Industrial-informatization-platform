"""
模型模块

导出所有数据库模型类
"""
from app.db.base import Base, BaseModel

# 导入所有模型以便 Alembic 能发现它们
from app.models.user import User
from app.models.production_line import ProductionLine
from app.models.dataset import Dataset, DatasetImage
from app.models.dataset_statistics import DatasetStatistics
from app.models.training_job import TrainingJob, TrainedModel
from app.models.detection_record import DetectionRecord, DefectStats
from app.models.ai_conversation import AIConversation
from app.models.pruning_distillation import PruningJob, DistillationJob

# 测试模型（用于检测结果的详细评估）
from app.models.test_result import TestResult

# 数据增强模型
from app.models.augmentation import (
    AugmentationTemplate,
    AugmentationJob,
    CustomAugmentationScript,
    AugmentationPreview,
)

# 数据生成模型
from app.models.generation import (
    GenerationTemplate,
    GenerationJob,
    DefectLibraryCache,
    GenerationPreview as GenerationPreviewModel,
)

# 模块定义（新分层结构）
from app.models.module_definition import ModuleDefinition

__all__ = [
    "Base",
    "BaseModel",
    "User",
    "ProductionLine",
    "Dataset",
    "DatasetImage",
    "DatasetStatistics",
    "TrainingJob",
    "TrainedModel",
    "DetectionRecord",
    "DefectStats",
    "AIConversation",
    "PruningJob",
    "DistillationJob",
    "TestResult",
    # 数据增强模型
    "AugmentationTemplate",
    "AugmentationJob",
    "CustomAugmentationScript",
    "AugmentationPreview",
    # 数据生成模型
    "GenerationTemplate",
    "GenerationJob",
    "DefectLibraryCache",
    "GenerationPreviewModel",
    # 模块定义
    "ModuleDefinition",
]
