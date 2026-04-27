"""
测试结果模型
"""
from typing import Optional, Dict, Any
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import BaseModel


class TestResult(BaseModel):
    """
    测试结果表
    
    存储模型测试的详细结果和评估指标
    """
    
    # 测试的模型ID
    trained_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("trainedmodel.id", ondelete="CASCADE"),
        nullable=False,
        comment="训练模型ID"
    )
    
    # 使用的测试数据集ID
    dataset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("dataset.id", ondelete="CASCADE"),
        nullable=False,
        comment="测试数据集ID"
    )
    
    # 评估指标 (JSON: mAP, recall, precision, F1等)
    metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="评估指标"
    )
    
    # 每类指标 (JSON)
    per_class_metrics: Mapped[Optional[Dict[str, Dict[str, float]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="每类指标"
    )
    
    # 混淆矩阵 (JSON)
    confusion_matrix: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="混淆矩阵"
    )
    
    # PR曲线数据 (JSON)
    pr_curve_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="PR曲线数据"
    )
    
    # 每张图像结果的路径
    per_image_results_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="每张图像结果路径"
    )
    
    # 所属产线
    production_line_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("productionline.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属产线ID"
    )
    
    # 关系
    trained_model: Mapped["TrainedModel"] = relationship(
        "TrainedModel",
        back_populates="test_results"
    )
    
    def __repr__(self) -> str:
        return f"<TestResult(id={self.id}, model_id={self.trained_model_id})>"
