"""
训练任务模型
"""
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.production_line import ProductionLine
    from app.models.dataset import Dataset
    from app.models.ml_module import ModelBuilderConfig
    from app.models.user import User


class TrainingJob(BaseModel):
    """
    训练任务表
    
    存储模型训练任务的信息和状态
    """
    
    # 关联的模型构建器配置
    model_builder_config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("modelbuilderconfig.id", ondelete="CASCADE"),
        nullable=False,
        comment="模型构建器配置ID"
    )
    
    # 关联的数据集
    dataset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("dataset.id", ondelete="CASCADE"),
        nullable=False,
        comment="数据集ID"
    )
    
    # 超参数 (JSON)
    hyperparams: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="训练超参数"
    )
    
    # 任务状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="状态: pending/running/completed/failed"
    )
    
    # 训练进度 (0-100)
    progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="训练进度 0-100"
    )
    
    # 训练指标 (JSON)
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="训练指标"
    )
    
    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )
    
    # 最佳权重路径
    best_weights_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="最佳权重文件路径"
    )
    
    # 日志路径
    log_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="训练日志路径"
    )
    
    # Celery 任务ID
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Celery任务ID"
    )
    
    # 开始时间
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始时间"
    )
    
    # 完成时间
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="完成时间"
    )
    
    # 所属产线
    production_line_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("productionline.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属产线ID"
    )
    
    # 创建者
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者ID"
    )
    
    # 关系
    model_builder_config: Mapped["ModelBuilderConfig"] = relationship(
        "ModelBuilderConfig", back_populates="training_jobs"
    )
    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        back_populates="training_jobs"
    )
    production_line: Mapped["ProductionLine"] = relationship(
        "ProductionLine",
        back_populates="training_jobs"
    )
    creator: Mapped["User"] = relationship("User")
    trained_models: Mapped[List["TrainedModel"]] = relationship(
        "TrainedModel",
        back_populates="training_job"
    )
    
    def __repr__(self) -> str:
        return f"<TrainingJob(id={self.id}, status={self.status}, progress={self.progress:.1f}%)>"


class TrainedModel(BaseModel):
    """
    已训练模型表
    
    存储训练完成的模型信息
    """
    
    # 关联的训练任务
    training_job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("trainingjob.id", ondelete="CASCADE"),
        nullable=False,
        comment="训练任务ID"
    )
    
    # 模型名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="模型名称"
    )
    
    # 权重文件路径
    weights_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="权重文件路径"
    )
    
    # 架构配置
    architecture_config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="架构配置"
    )
    
    # 指标摘要 (JSON)
    metrics_summary: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="指标摘要"
    )
    
    # 参数量
    params_count: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="参数量"
    )
    
    # FLOPs
    flops: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="FLOPs"
    )
    
    # 是否剪枝
    is_pruned: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否剪枝模型"
    )
    
    # 是否蒸馏
    is_distilled: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否蒸馏模型"
    )
    
    # 父模型ID（用于剪枝/蒸馏追踪）
    parent_model_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("trainedmodel.id", ondelete="SET NULL"),
        nullable=True,
        comment="父模型ID"
    )
    
    # 所属产线
    production_line_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("productionline.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属产线ID"
    )
    
    # 关系
    training_job: Mapped["TrainingJob"] = relationship(
        "TrainingJob",
        back_populates="trained_models"
    )
    test_results: Mapped[List["TestResult"]] = relationship(
        "TestResult",
        back_populates="trained_model"
    )
    
    def __repr__(self) -> str:
        return f"<TrainedModel(id={self.id}, name={self.name})>"
