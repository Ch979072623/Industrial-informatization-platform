"""
数据集统计分析模型

存储数据集的统计信息，包括类别分布、图像尺寸分布、标注框分布等。
用于数据集卡片展示和数据分析。
"""
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.dataset import Dataset


class DatasetStatistics(BaseModel):
    """
    数据集统计信息表
    
    存储数据集的各类统计数据，用于快速展示和分析。
    当数据集labels文件变化时，需要重新计算并更新此表。
    """
    
    # 关联的数据集ID
    dataset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("dataset.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="关联的数据集ID"
    )
    
    # 图像统计
    total_images: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="图像总数"
    )
    
    total_annotations: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="标注框总数"
    )
    
    images_with_annotations: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="有标注的图像数量"
    )
    
    images_without_annotations: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="无标注的图像数量"
    )
    
    avg_annotations_per_image: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="平均每图标注数"
    )
    
    # 类别统计
    class_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="类别数量"
    )
    
    class_distribution: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="类别分布统计 [{class_name, count, percentage}]"
    )
    
    annotations_per_class: Mapped[Dict[str, int]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="每个类别的标注数量"
    )
    
    # 图像尺寸统计
    image_sizes: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="图像尺寸列表 [{width, height, count}]"
    )
    
    avg_image_width: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="平均图像宽度"
    )
    
    avg_image_height: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="平均图像高度"
    )
    
    # 标注框统计
    avg_bbox_width: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="平均标注框宽度"
    )
    
    avg_bbox_height: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="平均标注框高度"
    )
    
    avg_bbox_aspect_ratio: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="平均标注框宽高比"
    )
    
    small_bboxes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="小目标数量（< 32x32）"
    )
    
    medium_bboxes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="中目标数量（32x32 ~ 96x96）"
    )
    
    large_bboxes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="大目标数量（> 96x96）"
    )
    
    # 数据集划分统计
    split_distribution: Mapped[Dict[str, int]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="训练/验证/测试集分布 {train, val, test}"
    )
    
    # 元数据
    last_scan_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="上次扫描时间"
    )
    
    scan_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="扫描状态: pending/running/completed/failed"
    )
    
    scan_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="扫描错误信息"
    )
    
    # 原始labels文件哈希，用于检测变化
    labels_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Labels文件内容哈希"
    )
    
    # 关系
    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        back_populates="statistics"
    )
    
    def __repr__(self) -> str:
        return f"<DatasetStatistics(dataset_id={self.dataset_id}, total_images={self.total_images})>"
    
    def is_stale(self, max_age_hours: int = 24) -> bool:
        """
        检查统计数据是否过期
        
        Args:
            max_age_hours: 最大允许的年龄（小时）
            
        Returns:
            如果数据过期返回True
        """
        if not self.last_scan_time:
            return True
        
        # 处理时区不一致问题
        now = datetime.now(timezone.utc)
        scan_time = self.last_scan_time
        
        # 如果 scan_time 没有时区信息，添加 UTC 时区
        if scan_time.tzinfo is None:
            scan_time = scan_time.replace(tzinfo=timezone.utc)
        
        age = now - scan_time
        return age.total_seconds() > max_age_hours * 3600
    
    def to_chart_data(self) -> Dict[str, Any]:
        """
        转换为图表展示数据格式
        
        Returns:
            适合前端图表展示的数据格式
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 处理 split_distribution，确保是字典格式
        split_dist = self.split_distribution or {}
        logger.info(f"to_chart_data: split_distribution raw={split_dist}, type={type(split_dist)}")
        
        train_val = split_dist.get("train", 0) if isinstance(split_dist, dict) else 0
        val_val = split_dist.get("val", 0) if isinstance(split_dist, dict) else 0
        test_val = split_dist.get("test", 0) if isinstance(split_dist, dict) else 0
        
        logger.info(f"to_chart_data: train={train_val}, val={val_val}, test={test_val}")
        
        return {
            "class_distribution": self.class_distribution,
            "image_sizes": self.image_sizes,
            "split_distribution": [
                {"name": "训练集", "value": train_val, "fill": "#3b82f6"},
                {"name": "验证集", "value": val_val, "fill": "#10b981"},
                {"name": "测试集", "value": test_val, "fill": "#f59e0b"},
            ],
            "bbox_distribution": {
                "avg_width": round(self.avg_bbox_width, 2),
                "avg_height": round(self.avg_bbox_height, 2),
                "avg_aspect_ratio": round(self.avg_bbox_aspect_ratio, 2) if self.avg_bbox_aspect_ratio > 0 else 1.0,
                "small": self.small_bboxes,
                "medium": self.medium_bboxes,
                "large": self.large_bboxes,
            },
            "summary": {
                "total_images": self.total_images,
                "total_annotations": self.total_annotations,
                "avg_annotations_per_image": round(self.avg_annotations_per_image, 2),
                "class_count": self.class_count,
                "images_with_annotations": self.images_with_annotations,
                "images_without_annotations": self.images_without_annotations,
            }
        }
