"""
检测记录模型
"""
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from sqlalchemy import String, Text, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.production_line import ProductionLine


class DetectionRecord(BaseModel):
    """
    检测记录表
    
    存储每次缺陷检测的结果
    """
    
    # 原始图像路径
    image_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="原始图像路径"
    )
    
    # 结果图像路径（带标注）
    result_image_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="结果图像路径"
    )
    
    # 使用的模型ID
    model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("trainedmodel.id", ondelete="CASCADE"),
        nullable=False,
        comment="模型ID"
    )
    
    # 检测到的缺陷列表 (JSON)
    defects: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="缺陷列表"
    )
    
    # 检测结果 (PASS/NG)
    verdict: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="检测结果: PASS/NG"
    )
    
    # 置信度阈值
    confidence_threshold: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
        comment="置信度阈值"
    )
    
    # 推理延迟（毫秒）
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="推理延迟(ms)"
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
    production_line: Mapped["ProductionLine"] = relationship(
        "ProductionLine",
        back_populates="detection_records"
    )
    
    def __repr__(self) -> str:
        return f"<DetectionRecord(id={self.id}, verdict={self.verdict}, latency={self.latency_ms}ms)>"


class DefectStats(BaseModel):
    """
    缺陷统计表
    
    按日期和产线统计检测结果
    """
    
    # 统计日期
    date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="统计日期 (YYYY-MM-DD)"
    )
    
    # 总检测数
    total_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="总检测数"
    )
    
    # 合格数
    pass_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="合格数"
    )
    
    # 不合格数
    ng_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="不合格数"
    )
    
    # 平均延迟
    avg_latency: Mapped[float] = mapped_column(
        nullable=False,
        default=0.0,
        comment="平均延迟(ms)"
    )
    
    # 缺陷分布 (JSON: {"defect_type": count})
    defect_distribution: Mapped[Dict[str, int]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="缺陷分布"
    )
    
    # 所属产线
    production_line_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("productionline.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属产线ID"
    )
    
    def __repr__(self) -> str:
        return f"<DefectStats(date={self.date}, total={self.total_count}, pass={self.pass_count}, ng={self.ng_count})>"
