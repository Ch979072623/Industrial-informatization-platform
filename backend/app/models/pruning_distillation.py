"""
剪枝和蒸馏任务模型
"""
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import BaseModel


class PruningJob(BaseModel):
    """
    剪枝任务表
    
    存储模型剪枝任务的信息
    """
    
    # 源模型ID
    source_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("trainedmodel.id", ondelete="CASCADE"),
        nullable=False,
        comment="源模型ID"
    )
    
    # 剪枝策略
    strategy: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="剪枝策略"
    )
    
    # 剪枝参数 (JSON)
    params: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="剪枝参数"
    )
    
    # 任务状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="状态: pending/running/completed/failed"
    )
    
    # 结果模型ID
    result_model_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("trainedmodel.id", ondelete="SET NULL"),
        nullable=True,
        comment="结果模型ID"
    )
    
    # 压缩统计 (JSON)
    compression_stats: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="压缩统计信息"
    )
    
    def __repr__(self) -> str:
        return f"<PruningJob(id={self.id}, strategy={self.strategy}, status={self.status})>"


class DistillationJob(BaseModel):
    """
    蒸馏任务表
    
    存储知识蒸馏任务的信息
    """
    
    # 教师模型ID
    teacher_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("trainedmodel.id", ondelete="CASCADE"),
        nullable=False,
        comment="教师模型ID"
    )
    
    # 学生模型ID
    student_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("trainedmodel.id", ondelete="CASCADE"),
        nullable=False,
        comment="学生模型ID"
    )
    
    # 蒸馏策略
    strategy: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="蒸馏策略"
    )
    
    # 蒸馏参数 (JSON)
    params: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="蒸馏参数"
    )
    
    # 任务状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="状态: pending/running/completed/failed"
    )
    
    # 结果模型ID
    result_model_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("trainedmodel.id", ondelete="SET NULL"),
        nullable=True,
        comment="结果模型ID"
    )
    
    # 蒸馏指标 (JSON)
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="蒸馏指标"
    )
    
    def __repr__(self) -> str:
        return f"<DistillationJob(id={self.id}, strategy={self.strategy}, status={self.status})>"
