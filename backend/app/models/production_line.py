"""
产线模型
"""
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.dataset import Dataset
    from app.models.training_job import TrainingJob
    from app.models.detection_record import DetectionRecord


class ProductionLine(BaseModel):
    """
    产线表
    
    用于数据隔离，不同产线的数据相互独立
    """
    
    # 产线名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="产线名称"
    )
    
    # 产线描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="产线描述"
    )
    
    # 创建者（外键）
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者ID"
    )
    
    # 关系
    users: Mapped[List["User"]] = relationship(
        "User",
        foreign_keys="User.production_line_id",
        back_populates="production_line"
    )
    datasets: Mapped[List["Dataset"]] = relationship(
        "Dataset",
        back_populates="production_line"
    )
    training_jobs: Mapped[List["TrainingJob"]] = relationship(
        "TrainingJob",
        back_populates="production_line"
    )
    detection_records: Mapped[List["DetectionRecord"]] = relationship(
        "DetectionRecord",
        back_populates="production_line"
    )
    
    def __repr__(self) -> str:
        return f"<ProductionLine(id={self.id}, name={self.name})>"
