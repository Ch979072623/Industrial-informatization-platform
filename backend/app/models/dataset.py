"""
数据集模型
"""
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.production_line import ProductionLine
    from app.models.training_job import TrainingJob
    from app.models.dataset_statistics import DatasetStatistics
    from app.models.augmentation import AugmentationJob


class Dataset(BaseModel):
    """
    数据集表
    
    存储数据集元信息
    """
    
    # 数据集名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="数据集名称"
    )
    
    # 数据集描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="数据集描述"
    )
    
    # 存储路径
    path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="数据集存储路径"
    )
    
    # 数据格式 (YOLO/COCO/VOC)
    format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="数据格式: YOLO/COCO/VOC"
    )
    
    # 图像总数
    total_images: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="图像总数"
    )
    
    # 标注框总数
    total_annotations: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="标注框总数"
    )
    
    # 类别名称列表 (JSON)
    class_names: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="类别名称列表"
    )
    
    # 数据集划分比例 (JSON: {"train": 0.7, "val": 0.2, "test": 0.1})
    split_ratio: Mapped[Dict[str, float]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="数据集划分比例"
    )
    
    # 所属产线
    production_line_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("productionline.id", ondelete="SET NULL"),
        nullable=True,
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
    production_line: Mapped["ProductionLine"] = relationship(
        "ProductionLine",
        back_populates="datasets"
    )
    images: Mapped[List["DatasetImage"]] = relationship(
        "DatasetImage",
        back_populates="dataset",
        cascade="all, delete-orphan"
    )
    training_jobs: Mapped[List["TrainingJob"]] = relationship(
        "TrainingJob",
        back_populates="dataset"
    )
    statistics: Mapped[Optional["DatasetStatistics"]] = relationship(
        "DatasetStatistics",
        back_populates="dataset",
        cascade="all, delete-orphan",
        uselist=False
    )
    augmentation_jobs: Mapped[List["AugmentationJob"]] = relationship(
        "AugmentationJob",
        foreign_keys="AugmentationJob.source_dataset_id",
        back_populates="source_dataset",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Dataset(id={self.id}, name={self.name}, format={self.format})>"


class DatasetImage(BaseModel):
    """
    数据集图像表
    
    存储数据集中每张图像的信息
    """
    
    # 所属数据集
    dataset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("dataset.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属数据集ID"
    )
    
    # 文件名ID（不含扩展名，用于API查询）
    name_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="文件名ID（不含扩展名）"
    )
    
    # 文件名
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="文件名"
    )
    
    # 文件路径
    filepath: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="文件完整路径"
    )
    
    # 数据划分 (train/val/test)
    split: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="数据划分: train/val/test"
    )
    
    # 图像宽度
    width: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="图像宽度"
    )
    
    # 图像高度
    height: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="图像高度"
    )
    
    # 标注文件路径
    annotation_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="标注文件路径"
    )
    
    # 关系
    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        back_populates="images"
    )
    
    def __repr__(self) -> str:
        return f"<DatasetImage(id={self.id}, filename={self.filename}, split={self.split})>"
